"""Microphone capture, voice activity detection, and interruptible playback.

All audio is int16 mono. The microphone runs at 16 kHz (what speech models
expect); TTS playback runs at 24 kHz (what OpenAI's PCM output uses).
"""

import queue
from typing import Iterator

import numpy as np
import sounddevice as sd

from ingestion.logger import get_logger

logger = get_logger(__name__)

# --- Audio formats ----------------------------------------------------------
MIC_SAMPLE_RATE = 16_000   # capture rate for speech-to-text
TTS_SAMPLE_RATE = 24_000   # OpenAI TTS 'pcm' output rate
FRAME_MS = 30              # analysis frame length
MIC_FRAME = MIC_SAMPLE_RATE * FRAME_MS // 1000  # samples per mic frame

# --- Voice activity tuning --------------------------------------------------
SILENCE_HANG_S = 0.8       # how much silence ends an utterance
MAX_UTTERANCE_S = 30.0     # hard cap so a noisy room can't record forever
MIN_UTTERANCE_S = 0.25     # discard blips shorter than this (coughs, taps)
# Barge-in must clear a higher bar than normal speech detection, because
# the speakers bleed into the microphone while the agent is talking.
BARGE_IN_FACTOR = 2.5
BARGE_IN_SUSTAIN_FRAMES = 8  # ~0.24s of sustained speech to count as a real interruption


def _rms(frame: np.ndarray) -> float:
    """Root-mean-square energy of an int16 frame (simple loudness measure)."""
    return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))


def calibrate_noise_floor(seconds: float = 0.7) -> float:
    """Measure ambient room noise and derive the speech energy threshold.

    Recorded once at startup while the user is silent; speech is then
    "energy well above the room's background noise".

    Returns:
        The RMS threshold above which a frame counts as speech.

    Raises:
        RuntimeError: If the microphone cannot be opened.
    """
    logger.info("Calibrating microphone noise floor (%.1fs)...", seconds)
    try:
        recording = sd.rec(
            int(seconds * MIC_SAMPLE_RATE),
            samplerate=MIC_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
    except Exception as exc:
        logger.exception("Could not open the microphone")
        raise RuntimeError(f"Microphone unavailable: {exc}") from exc

    ambient = _rms(recording.flatten())
    # Speech must be clearly louder than ambient noise; the floor of 150
    # prevents a hyper-quiet room from making the threshold oversensitive.
    threshold = max(150.0, ambient * 4.0)
    logger.info("Noise floor RMS=%.0f -> speech threshold=%.0f", ambient, threshold)
    return threshold


def record_utterance(threshold: float) -> np.ndarray | None:
    """Record one utterance: wait for speech, then capture until silence.

    Blocks until the user starts speaking, keeps recording while they talk,
    and returns once SILENCE_HANG_S of quiet follows the speech.

    Args:
        threshold: Speech energy threshold from calibrate_noise_floor().

    Returns:
        The utterance as int16 mono samples at 16 kHz, or None if what was
        captured was too short to be real speech.

    Raises:
        RuntimeError: If the microphone stream fails.
    """
    frames: list[np.ndarray] = []
    speech_started = False
    silence_frames = 0
    silence_limit = int(SILENCE_HANG_S * 1000 / FRAME_MS)
    max_frames = int(MAX_UTTERANCE_S * 1000 / FRAME_MS)

    try:
        with sd.InputStream(
            samplerate=MIC_SAMPLE_RATE, channels=1, dtype="int16", blocksize=MIC_FRAME
        ) as stream:
            while True:
                frame, _ = stream.read(MIC_FRAME)
                frame = frame.flatten()
                is_speech = _rms(frame) > threshold

                if not speech_started:
                    # Still waiting for the user to start talking
                    if is_speech:
                        speech_started = True
                        frames.append(frame)
                    continue

                frames.append(frame)

                # Track trailing silence to detect the end of the utterance
                silence_frames = 0 if is_speech else silence_frames + 1
                if silence_frames >= silence_limit or len(frames) >= max_frames:
                    break
    except Exception as exc:
        logger.exception("Microphone stream failed")
        raise RuntimeError(f"Microphone failure: {exc}") from exc

    # Drop the trailing silence; check the speech part is long enough
    speech = np.concatenate(frames[: len(frames) - silence_frames or None])
    if len(speech) < MIN_UTTERANCE_S * MIC_SAMPLE_RATE:
        logger.info("Captured audio too short (%.2fs) — ignoring", len(speech) / MIC_SAMPLE_RATE)
        return None

    logger.info("Captured utterance: %.2fs of audio", len(speech) / MIC_SAMPLE_RATE)
    return speech


def play_pcm_stream(pcm_chunks: Iterator[bytes], threshold: float) -> bool:
    """Play streaming TTS audio, stopping instantly if the user barges in.

    While the agent's voice plays, the microphone keeps listening. If the
    user speaks loudly enough for long enough (to distinguish real speech
    from speaker echo), playback is cut off mid-sentence.

    Args:
        pcm_chunks: Iterator of raw 16-bit PCM chunks at 24 kHz (from TTS).
        threshold: Base speech threshold from calibrate_noise_floor().

    Returns:
        True if the user interrupted playback, False if it finished normally.
    """
    interrupted = False
    consecutive_speech = 0
    barge_threshold = threshold * BARGE_IN_FACTOR

    # Mic frames arrive via callback so playback never blocks listening
    mic_frames: queue.Queue[np.ndarray] = queue.Queue()

    def on_mic_frame(indata, _frames, _time, _status) -> None:
        mic_frames.put(indata.copy().flatten())

    try:
        with (
            sd.OutputStream(
                samplerate=TTS_SAMPLE_RATE, channels=1, dtype="int16"
            ) as speaker,
            sd.InputStream(
                samplerate=MIC_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=MIC_FRAME,
                callback=on_mic_frame,
            ),
        ):
            leftover = b""
            for chunk in pcm_chunks:
                # PCM samples are 2 bytes; carry odd bytes to the next chunk
                data = leftover + chunk
                usable = len(data) - (len(data) % 2)
                leftover = data[usable:]
                samples = np.frombuffer(data[:usable], dtype=np.int16)
                if len(samples):
                    speaker.write(samples)

                # --- Barge-in check: is the user talking over us? ----------
                while not mic_frames.empty():
                    frame = mic_frames.get_nowait()
                    if _rms(frame) > barge_threshold:
                        consecutive_speech += 1
                    else:
                        consecutive_speech = 0
                    if consecutive_speech >= BARGE_IN_SUSTAIN_FRAMES:
                        interrupted = True
                        break
                if interrupted:
                    speaker.abort()  # cut the voice off immediately
                    break
    except Exception:
        # A playback glitch shouldn't kill the conversation loop
        logger.exception("Audio playback failed")
        return False

    if interrupted:
        logger.info("User interrupted playback (barge-in)")
    return interrupted
