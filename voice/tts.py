"""Text-to-speech: stream the agent's reply as raw PCM audio chunks.

Streaming is the key latency win: the first audio chunk arrives (and starts
playing) while the rest of the clip is still being generated, so the
customer hears the agent's voice almost immediately.
"""

from typing import Iterator

from dotenv import load_dotenv
from openai import OpenAI

from ingestion.logger import get_logger

logger = get_logger(__name__)

# gpt-4o-mini-tts: fast, natural-sounding, supports style instructions
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "nova"

# Style guidance so the voice matches the assistant's personality
TTS_INSTRUCTIONS = (
    "Speak as a warm, friendly, professional restaurant host. "
    "Natural conversational pace, upbeat but not exaggerated."
)

# One shared client (reads OPENAI_API_KEY from .env)
load_dotenv()
_client = OpenAI()


def stream_speech(text: str) -> Iterator[bytes]:
    """Convert text to speech, yielding raw PCM chunks as they arrive.

    Output format is 16-bit mono PCM at 24 kHz (playable directly by
    voice.audio_io.play_pcm_stream).

    Args:
        text: The agent's reply to speak.

    Yields:
        Raw PCM audio chunks. Yields nothing if the TTS request fails
        (the failure is logged; the conversation loop continues).
    """
    logger.info("TTS: synthesising %d chars", len(text))
    try:
        # with_streaming_response yields audio incrementally instead of
        # waiting for the full clip — this is what makes playback instant
        with _client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
            instructions=TTS_INSTRUCTIONS,
            response_format="pcm",  # raw samples, no decoding needed
        ) as response:
            yield from response.iter_bytes(chunk_size=4096)
    except Exception:
        logger.exception("Text-to-speech request failed")
        # Yield nothing: the caller falls back to printing the reply
        return
