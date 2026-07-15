"""Pydantic request/response models: the API's validation layer.

FastAPI validates every request against these models automatically and
returns a 422 with details when a field is missing or malformed, so the
endpoints only ever see clean data.
"""

from pydantic import BaseModel, Field, computed_field


# --- /chat -------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100,
                            description="Unique id for this user's conversation")
    message: str = Field(min_length=1, max_length=2000,
                         description="The user's message")


class Source(BaseModel):
    """A knowledge-base citation: where a piece of the answer came from."""
    page: int                # page of the source PDF
    snippet: str             # first ~120 chars of the cited chunk
    confidence: float        # 0..1 similarity between question and chunk


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: list[Source] = []       # knowledge-base citations used this turn
    confidence: float | None = None  # best source confidence (None = no retrieval)


# --- /voice-chat --------------------------------------------------------------

class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str          # what the customer said (STT result)
    reply: str               # the agent's text reply
    audio_base64: str        # the spoken reply: WAV audio, base64-encoded
    sources: list[Source] = []
    confidence: float | None = None


# --- /order -------------------------------------------------------------------

class OrderItem(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    qty: int = Field(ge=1, le=50)
    unit_price: float = Field(ge=0)


class OrderRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=20, pattern=r"^[+\d][\d\s\-]+$")
    items: list[OrderItem] = Field(min_length=1)
    payment_method: str = Field(
        description="cash, credit card, debit card, jazzcash, or easypaisa"
    )
    delivery_address: str | None = Field(default=None, max_length=300,
                                         description="Omit for takeaway")
    email: str | None = Field(default=None, max_length=100)

    @computed_field
    @property
    def total_price(self) -> float:
        """Total is computed server-side from the items, never trusted from input."""
        return sum(item.qty * item.unit_price for item in self.items)


class OrderResponse(BaseModel):
    order_id: int
    order_type: str
    items: list[OrderItem]
    total_price: float
    payment_method: str
    delivery_address: str | None
    estimated_time: str


# --- /order-status --------------------------------------------------------------

class OrderStatus(BaseModel):
    order_id: int
    order_type: str
    status: str
    status_label: str
    items: list[dict]
    total_price: float
    created_at: str


# --- /reservation ----------------------------------------------------------------

class ReservationRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=20, pattern=r"^[+\d][\d\s\-]+$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    time: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM, 24-hour")
    guests: int = Field(ge=1, le=50)
    special_requests: str | None = Field(default=None, max_length=300)


class ReservationResponse(BaseModel):
    reservation_id: int
    customer_name: str
    phone: str
    date: str
    time: str
    guests: int
    special_requests: str | None
    status: str


# --- /cancel-reservation -----------------------------------------------------------

class CancelReservationRequest(BaseModel):
    reservation_id: int = Field(ge=1)
    phone: str = Field(min_length=7, max_length=20)


# --- /menu ---------------------------------------------------------------------------

class MenuPassage(BaseModel):
    page: int
    content: str
    confidence: float = 0.0      # 0..1 match score for the search query


class MenuResponse(BaseModel):
    query: str
    passages: list[MenuPassage]


# --- /health --------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str                  # "ok" or "degraded"
    components: dict[str, str]   # component name -> "ok" / error description


# --- /metrics -----------------------------------------------------------------------

class MetricsResponse(BaseModel):
    uptime_seconds: float
    requests_total: int
    errors_total: int
    rate_limited_total: int
    requests_by_path: dict[str, int]
    avg_latency_ms_by_path: dict[str, float]
    guardrails: dict[str, int]       # blocked injection/jailbreak/leak counts
    retrieval_cache: dict[str, int]  # hits / misses
