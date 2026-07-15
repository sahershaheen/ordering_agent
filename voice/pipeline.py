"""The real-time voice conversation loop.

Continuous conversation:  listen -> transcribe -> think -> speak -> listen...
The loop only ends when the user stops it (Ctrl+C) or says goodbye.

Interruption handling: if the user starts talking while the agent is
speaking, playback stops instantly and the loop goes straight back to
listening — the user's interruption becomes their next message.
"""

import uuid

from agent.memory import chat
from agent.ordering_agent import build_agent
from ingestion.logger import get_logger
from voice.audio_io import calibrate_noise_floor, play_pcm_stream, record_utterance
from voice.stt import transcribe
from voice.tts import stream_speech

logger = get_logger(__name__)

# Spoken when a turn fails (STT error, agent error) so the user isn't
# left in silence wondering what happened
RETRY_LINE = "Sorry, I didn't catch that. Could you say it again?"

# Phrases that end the conversation naturally
GOODBYE_WORDS = {"bye", "goodbye", "bye bye", "that's all", "thats all", "exit", "quit"}


class VoiceSession:
    """One continuous voice conversation with the ordering agent."""

    def __init__(self) -> None:
        # The text agent does the thinking; one session ID keeps this
        # conversation's memory separate from any other user's
        self.agent = build_agent()
        self.session_id = f"voice-{uuid.uuid4().hex[:8]}"
        # Learn how noisy this room is so we can tell speech from silence
        self.threshold = calibrate_noise_floor()
        logger.info("Voice session %s started", self.session_id)

    def speak(self, text: str) -> bool:
        """Speak a reply aloud. Returns True if the user interrupted."""
        print(f"Agent: {text}")
        return play_pcm_stream(stream_speech(text), self.threshold)

    def run_turn(self) -> bool:
        """Run one turn of conversation. Returns False to end the loop."""
        # --- 1. Listen: wait for the user to speak, record until silence ---
        print("\n[listening...]")
        audio = record_utterance(self.threshold)
        if audio is None:
            return True  # too short / noise blip — just listen again

        # --- 2. Real-time transcription -------------------------------------
        transcript = transcribe(audio)
        if transcript is None:
            self.speak(RETRY_LINE)
            return True
        print(f"You: {transcript}")

        # --- Natural ending --------------------------------------------------
        if transcript.lower().strip(" .!?") in GOODBYE_WORDS:
            self.speak("Thank you for calling Flavour & Rush. Goodbye!")
            return False

        # --- 3. The restaurant agent thinks (RAG + tools + memory) ----------
        # chat() handles agent errors internally and returns a spoken apology
        reply = chat(self.agent, self.session_id, transcript)

        # --- 4. Speak the reply; user may barge in at any moment -------------
        interrupted = self.speak(reply)
        if interrupted:
            # Cut off mid-sentence: loop straight back to listening so the
            # user's interruption is captured as their next message
            print("[interrupted — go ahead]")
        return True

    def run(self) -> None:
        """Run the continuous conversation until the user ends it."""
        print("=" * 60)
        print("  Flavour & Rush — Voice Assistant")
        print("  Speak naturally. Say 'goodbye' or press Ctrl+C to end.")
        print("=" * 60)

        # Open with a spoken greeting so the user knows we're live
        self.speak("Welcome to Flavour and Rush! How can I help you today?")

        while True:
            try:
                if not self.run_turn():
                    break
            except KeyboardInterrupt:
                print("\n[session ended]")
                break
            except RuntimeError as exc:
                # Microphone-level failure — cannot continue a voice session
                print(f"\nAudio device error: {exc}")
                logger.error("Voice session %s aborted: %s", self.session_id, exc)
                break

        logger.info("Voice session %s ended", self.session_id)
