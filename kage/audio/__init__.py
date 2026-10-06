"""Voice In (Speech-to-Text) via Groq Whisper API and Voice Out (TTS) via Edge-TTS."""

from __future__ import annotations

from kage.audio.transcription import transcribe_audio
from kage.audio.tts import synthesize_speech

__all__ = ["transcribe_audio", "synthesize_speech"]
