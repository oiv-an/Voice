from __future__ import annotations

from typing import Protocol

from audio.recorder import AudioData
from config.settings import RecognitionConfig
from recognition.groq_api import GroqWhisperRecognizer
from recognition.gigaam_local import GigaAMRecognizer
from recognition.openai_api import OpenAIWhisperRecognizer


class IRecognizer(Protocol):
    def transcribe(self, audio: AudioData) -> str:  # pragma: no cover - protocol
        ...


def create_recognizer(config: RecognitionConfig) -> IRecognizer:
    """
    Factory for recognizers.

    Поддерживаем три backend'а:
      - "groq"   — облачный Groq Whisper
      - "openai" — облачный OpenAI Whisper
      - "local"  — локальный GigaAM-v3-CTC (v2_ctc)
    """
    backend = (config.backend or "groq").lower()

    if backend == "local":
        # Локальный GigaAM-v3 e2e_rnnt через HuggingFace
        return GigaAMRecognizer()

    if backend == "groq":
        return GroqWhisperRecognizer(config.groq)

    if backend == "openai":
        return OpenAIWhisperRecognizer(config.openai)

    # Fallback: по умолчанию Groq
    return GroqWhisperRecognizer(config.groq)