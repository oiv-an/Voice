from __future__ import annotations

from typing import Protocol

from audio.recorder import AudioData
from config.settings import RecognitionConfig
from recognition.groq_api import GroqWhisperRecognizer
from recognition.openai_api import OpenAIWhisperRecognizer
from recognition.openrouter_api import OpenRouterRecognizer


class IRecognizer(Protocol):
    def transcribe(self, audio: AudioData) -> str:  # pragma: no cover - protocol
        ...


def create_recognizer(config: RecognitionConfig) -> IRecognizer:
    """
    Factory for recognizers.

    Поддерживаем три backend-а:
      - "groq"       — облачный Groq Whisper (multipart /audio/transcriptions)
      - "openai"     — облачный OpenAI Whisper (multipart /audio/transcriptions)
      - "openrouter" — OpenRouter / совместимый прокси (chat/completions + input_audio)
    """
    backend = (config.backend or "groq").lower()

    if backend == "groq":
        return GroqWhisperRecognizer(config.groq)

    if backend == "openai":
        return OpenAIWhisperRecognizer(config.openai)

    if backend == "openrouter":
        return OpenRouterRecognizer(config.openrouter)

    # Fallback: по умолчанию Groq
    return GroqWhisperRecognizer(config.groq)
