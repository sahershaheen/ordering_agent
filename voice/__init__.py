"""Real-time voice layer for the Flavour & Rush ordering agent.

Pipeline for every conversational turn:

    microphone -> voice activity detection -> speech-to-text
        -> ordering_agent (GPT-4o + RAG + SQLite tools)
        -> streaming text-to-speech -> speakers

Low-latency techniques used:
    - Utterance end is detected locally (energy-based VAD), so transcription
      starts the moment the customer stops talking.
    - TTS audio is streamed: playback starts as soon as the first audio
      chunk arrives instead of waiting for the full clip.
    - Barge-in: the microphone stays open while the agent speaks; if the
      customer starts talking, playback stops immediately and the agent
      listens (natural interruption handling).
"""
