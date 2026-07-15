"""The FastAPI application: every part of the system behind one HTTP API.

Run with:
    uv run python server.py          (or: uv run uvicorn api.main:app --port 8000)

Interactive docs: http://localhost:8000/docs
"""

import base64
import io
import os
import sqlite3
import threading
import time
import wave
from collections import defaultdict, deque

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from agent import guardrails
from agent.memory import chat, session_config
from agent.ordering_agent import build_agent
from agent.tools.orders import create_order, find_orders
from agent.tools.reservations import cancel_reservation_record, create_reservation
from api.schemas import (
    CancelReservationRequest,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MenuPassage,
    MenuResponse,
    MetricsResponse,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    ReservationRequest,
    ReservationResponse,
    Source,
    VoiceChatResponse,
)
from database.db import get_connection
from ingestion.config import PROJECT_ROOT, VECTOR_STORE_DIR
from ingestion.logger import get_logger
from retrieval.retriever import (
    cache_stats,
    get_recorded_sources,
    reset_recorded_sources,
    retrieve,
)
from voice.stt import transcribe
from voice.tts import stream_speech

logger = get_logger(__name__)

app = FastAPI(
    title="Flavour & Rush API",
    description="Real-time ordering & booking backend: GPT-4o agent, "
    "RAG knowledge base (FAISS), SQLite records, and voice.",
    version="1.0.0",
)

# The Next.js frontend runs on its own dev server (port 3000) and calls
# this API from the browser, so those origins must be allowed via CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# The agent is built once at startup and shared by /chat and /voice-chat;
# per-user isolation comes from session IDs, not separate agents.
agent = None


@app.on_event("startup")
def startup() -> None:
    """Build the agent once so the first request doesn't pay the cost."""
    global agent
    logger.info("API starting: building the ordering agent...")
    agent = build_agent()
    logger.info("API ready")


# --- Monitoring: in-process metrics registry ---------------------------------

_METRICS_LOCK = threading.Lock()
METRICS = {
    "started_at": time.time(),
    "requests_total": 0,
    "errors_total": 0,
    "rate_limited_total": 0,
    "requests_by_path": defaultdict(int),
    "latency_sum_ms": defaultdict(float),
}

# --- Rate limiting -------------------------------------------------------------
# Sliding one-minute window per client IP. Protects the OpenAI budget and
# the server from floods/abuse. Static frontend files are exempt.
RATE_LIMIT_PER_MINUTE = 30
_rate_windows: dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()


def _rate_limited(client_ip: str) -> bool:
    """Record one request from this IP; True if they exceeded the limit."""
    now = time.monotonic()
    with _rate_lock:
        window = _rate_windows[client_ip]
        # Drop requests that left the 60-second window
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= RATE_LIMIT_PER_MINUTE:
            return True
        window.append(now)
        return False


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    """Rate-limit, time, log, and count every request (monitoring layer)."""
    path = request.url.path

    # Static frontend assets and monitoring endpoints are never rate
    # limited: dashboards and health checks must always get through.
    if not path.startswith("/app") and path not in ("/health", "/metrics"):
        client_ip = request.client.host if request.client else "unknown"
        if _rate_limited(client_ip):
            with _METRICS_LOCK:
                METRICS["rate_limited_total"] += 1
            logger.warning("Rate limit exceeded", extra={"client": client_ip, "path": path})
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests — please slow down."},
                headers={"Retry-After": "30"},
            )

    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000

    # Update the metrics registry
    with _METRICS_LOCK:
        METRICS["requests_total"] += 1
        METRICS["requests_by_path"][path] += 1
        METRICS["latency_sum_ms"][path] += elapsed_ms
        if response.status_code >= 500:
            METRICS["errors_total"] += 1

    logger.info(
        "%s %s -> %d (%.0f ms)",
        request.method, path, response.status_code, elapsed_ms,
        extra={"path": path, "status": response.status_code, "ms": round(elapsed_ms)},
    )
    return response


# --- Error handlers -------------------------------------------------------------

@app.exception_handler(sqlite3.Error)
async def database_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
    """Database failures get their own handler so they're easy to spot."""
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please try again."},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch anything unexpected: log the traceback, return a clean 500."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. The issue has been logged."},
    )


# --- Endpoints -------------------------------------------------------------------

@app.get("/")
def root() -> dict:
    """API overview: what's here and where to find the docs and the app."""
    return {
        "name": "Flavour & Rush — Restaurant Ordering & Booking API",
        "web_app": "/app",
        "docs": "/docs",
        "endpoints": [
            "/chat", "/voice-chat", "/order", "/order-status",
            "/reservation", "/cancel-reservation", "/menu", "/health",
        ],
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(body: ChatRequest) -> ChatResponse:
    """Text conversation with the agent (RAG answers, orders, reservations).

    Memory is per session_id: reuse the same id to continue a conversation.
    Replies that used the knowledge base include source citations (PDF page
    + snippet) and a confidence score for the best-matching source.
    """
    # Track which knowledge-base chunks get retrieved during this turn
    reset_recorded_sources()
    reply = chat(agent, body.session_id, body.message)
    sources = get_recorded_sources()

    return ChatResponse(
        session_id=body.session_id,
        reply=reply,
        sources=[Source(**s) for s in sources],
        confidence=sources[0]["confidence"] if sources else None,
    )


@app.post("/voice-chat", response_model=VoiceChatResponse)
def voice_chat_endpoint(
    audio: UploadFile = File(description="Spoken message as a WAV file"),
    session_id: str = Form(min_length=1, max_length=100),
) -> VoiceChatResponse:
    """Voice conversation: WAV in -> transcript -> agent -> spoken WAV out."""
    # --- Decode the uploaded WAV into raw samples --------------------------
    try:
        with wave.open(io.BytesIO(audio.file.read()), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise ValueError("Audio must be 16-bit PCM WAV")
            sample_rate = wav.getframerate()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
            # Mix stereo down to mono if needed
            if wav.getnchannels() == 2:
                samples = samples.reshape(-1, 2).mean(axis=1).astype(np.int16)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid WAV file: {exc}") from exc

    # --- Speech-to-text ------------------------------------------------------
    transcript = transcribe(samples, sample_rate=sample_rate)
    if transcript is None:
        raise HTTPException(
            status_code=422, detail="Could not transcribe any speech from the audio."
        )

    # --- The agent thinks (tracking knowledge-base sources for citations) ------
    reset_recorded_sources()
    reply = chat(agent, session_id, transcript)
    sources = get_recorded_sources()

    # --- Text-to-speech: collect the streamed PCM and wrap it as WAV -----------
    pcm = b"".join(stream_speech(reply))
    if not pcm:
        raise HTTPException(status_code=502, detail="Speech synthesis failed.")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)  # OpenAI TTS PCM rate
        wav.writeframes(pcm)

    return VoiceChatResponse(
        session_id=session_id,
        transcript=transcript,
        reply=reply,
        audio_base64=base64.b64encode(buffer.getvalue()).decode(),
        sources=[Source(**s) for s in sources],
        confidence=sources[0]["confidence"] if sources else None,
    )


@app.post("/order", response_model=OrderResponse, status_code=201)
def order_endpoint(body: OrderRequest) -> OrderResponse:
    """Place an order directly (structured, no conversation).

    The total price is computed server-side from the items.
    """
    try:
        order = create_order(
            full_name=body.full_name,
            phone=body.phone,
            items=[item.model_dump() for item in body.items],
            total_price=body.total_price,
            payment_method=body.payment_method,
            delivery_address=body.delivery_address,
            email=body.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return OrderResponse(**order)


@app.get("/order-status", response_model=list[OrderStatus])
def order_status_endpoint(
    order_id: int | None = None, phone: str | None = None
) -> list[OrderStatus]:
    """Track order(s) by order_id or phone number (at least one required)."""
    try:
        orders = find_orders(phone=phone, order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not orders:
        raise HTTPException(status_code=404, detail="No matching orders found.")
    return [OrderStatus(**o) for o in orders]


@app.post("/reservation", response_model=ReservationResponse, status_code=201)
def reservation_endpoint(body: ReservationRequest) -> ReservationResponse:
    """Book a table reservation."""
    try:
        reservation = create_reservation(
            customer_name=body.customer_name,
            phone=body.phone,
            date_iso=body.date,
            time_24h=body.time,
            guests=body.guests,
            special_requests=body.special_requests,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ReservationResponse(**reservation)


@app.post("/cancel-reservation")
def cancel_reservation_endpoint(body: CancelReservationRequest) -> dict:
    """Cancel a reservation (phone must match the booking)."""
    try:
        cancel_reservation_record(body.reservation_id, body.phone)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"reservation_id": body.reservation_id, "status": "cancelled"}


@app.get("/menu", response_model=MenuResponse)
def menu_endpoint(query: str = "full menu with prices") -> MenuResponse:
    """Retrieve menu (or any knowledge-base) passages via RAG.

    Pass ?query=... to filter, e.g. ?query=spicy burgers or ?query=desserts.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty.")

    try:
        documents = retrieve(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Knowledge base unavailable.") from exc

    return MenuResponse(
        query=query,
        passages=[
            MenuPassage(
                page=doc.metadata.get("page", -1),
                content=doc.page_content,
                confidence=doc.metadata.get("confidence", 0.0),
            )
            for doc in documents
        ],
    )


@app.get("/metrics", response_model=MetricsResponse)
def metrics_endpoint() -> MetricsResponse:
    """Monitoring: live counters for requests, latency, guardrails, cache."""
    with _METRICS_LOCK:
        by_path = dict(METRICS["requests_by_path"])
        avg_latency = {
            path: round(METRICS["latency_sum_ms"][path] / count, 1)
            for path, count in by_path.items()
            if count
        }
        return MetricsResponse(
            uptime_seconds=round(time.time() - METRICS["started_at"], 1),
            requests_total=METRICS["requests_total"],
            errors_total=METRICS["errors_total"],
            rate_limited_total=METRICS["rate_limited_total"],
            requests_by_path=by_path,
            avg_latency_ms_by_path=avg_latency,
            guardrails=dict(guardrails.stats),
            retrieval_cache=dict(cache_stats),
        )


# The web frontend (HTML/CSS/JS) is served at /app from the frontend folder
app.mount(
    "/app",
    StaticFiles(directory=PROJECT_ROOT / "frontend", html=True),
    name="frontend",
)


@app.get("/health", response_model=HealthResponse)
def health_endpoint() -> HealthResponse:
    """Check every component: SQLite, FAISS index, OpenAI key, agent."""
    components: dict[str, str] = {}

    # SQLite: run a trivial query
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        components["sqlite"] = "ok"
    except Exception as exc:
        components["sqlite"] = f"error: {exc}"

    # FAISS: index files present on disk
    components["faiss_index"] = (
        "ok" if (VECTOR_STORE_DIR / "index.faiss").exists()
        else "error: index not found — run build_index.py"
    )

    # OpenAI: key configured (validity is proven by actual calls)
    components["openai_key"] = "ok" if os.getenv("OPENAI_API_KEY") else "error: not set"

    # Agent: built at startup
    components["agent"] = "ok" if agent is not None else "error: not initialised"

    all_ok = all(v == "ok" for v in components.values())
    return HealthResponse(status="ok" if all_ok else "degraded", components=components)
