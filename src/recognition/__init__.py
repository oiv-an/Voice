from __future__ import annotations

from typing import Protocol

from audio.recorder import AudioData
from config.settings import RecognitionConfig
from recognition.groq_api import GroqWhisperRecognizer
from recognition.openai_api import OpenAIWhisperRecognizer


class IRecognizer(Protocol):
    def transcribe(self, audio: AudioData) -> str:  # pragma: no cover - protocol
        ...


def create_recognizer(config: RecognitionConfig) -> IRecognizer:
    """
    Factory for recognizers.

    Поддерживаем два backend'а:
      - "groq"   — облачный Groq Whisper
      - "openai" — облачный OpenAI Whisper
    """
    backend = (config.backend or "groq").lower()

    if backend == "groq":
        return GroqWhisperRecognizer(config.groq)

    if backend == "openai":
        return OpenAIWhisperRecognizer(config.openai)

    # Fallback: по умолчанию Groq
    return GroqWhisperRecognizer(config.groq)