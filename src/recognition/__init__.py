from __future__ import annotations

from typing import Protocol

from audio.recorder import AudioData
from config.settings import RecognitionConfig
from recognition.groq_api import GroqWhisperRecognizer


class IRecognizer(Protocol):
    def transcribe(self, audio: AudioData) -> str:  # pragma: no cover - protocol
        ...


def create_recognizer(config: RecognitionConfig) -> IRecognizer:
    """
    Factory for recognizers.

    MVP: only Groq backend is fully implemented.
    """
    backend = config.backend.lower()

    if backend == "groq":
        return GroqWhisperRecognizer(config.groq)

    # Fallback: use Groq even if config says otherwise, to keep MVP working.
    return GroqWhisperRecognizer(config.groq)