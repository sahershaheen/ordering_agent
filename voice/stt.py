"""Speech-to-text: turn one recorded utterance into a transcript."""

import io
import wave

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from ingestion.logger import get_logger
from voice.audio_io import MIC_SAMPLE_RATE

logger = get_logger(__name__)

# gpt-4o-mini-transcribe is fast and accurate — good for low-latency voice
STT_MODEL = "gpt-4o-mini-transcribe"

# One shared client (reads OPENAI_API_KEY from .env)
load_dotenv()
_client = OpenAI()


def _to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Wrap raw int16 samples in a WAV container (what the STT API expects)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # int16 = 2 bytes per sample
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()


def transcribe(samples: np.ndarray, sample_rate: int = MIC_SAMPLE_RATE) -> str | None:
    """Transcribe one utterance to text.

    Args:
        samples: int16 mono audio samples.
        sample_rate: Sample rate of the audio (default: mic rate, 16 kHz).

    Returns:
        The transcript text, or None if transcription failed or the audio
        contained no recognisable speech.
    """
    wav_bytes = _to_wav_bytes(samples, sample_rate)

    try:
        result = _client.audio.transcriptions.create(
            model=STT_MODEL,
            # (filename, bytes) tuple — the name just tells the API the format
            file=("speech.wav", wav_bytes),
            language="en",
        )
    except Exception:
        # Network/API failure: log it and let the caller ask the user to repeat
        logger.exception("Speech-to-text request failed")
        return None

    text = result.text.strip()
    if not text:
        logger.info("STT returned an empty transcript — ignoring")
        return None

    logger.info("Transcript: %r", text)
    return text
