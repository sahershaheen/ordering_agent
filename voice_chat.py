"""Entry point for the real-time voice assistant.

Usage:
    uv run python voice_chat.py

Requires a working microphone and speakers, plus OPENAI_API_KEY in .env.
Speak naturally; say "goodbye" (or press Ctrl+C) to end the call.
"""

import sys

from voice.pipeline import VoiceSession

if __name__ == "__main__":
    try:
        VoiceSession().run()
    except Exception as exc:
        # Startup failures (no mic, missing API key) land here
        print(f"Could not start the voice assistant: {exc}")
        sys.exit(1)
