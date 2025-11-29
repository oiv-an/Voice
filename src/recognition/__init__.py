from __future__ import annotations

from typing import Protocol

from audio.recorder import AudioData
from config.settings import RecognitionConfig
from recognition.groq_api import GroqWhisperRecognizer
from recognition.gigaam_local import GigaAMRecognizer


class IRecognizer(Protocol):
    def transcribe(self, audio: AudioData) -> str:  # pragma: no cover - protocol
        ...


def create_recognizer(config: RecognitionConfig) -> IRecognizer:
    """
    Factory for recognizers.

    Поддерживаем три backend'а:
      - "groq"   — облачный Groq Whisper
      - "openai" — (зарезервировано, можно добавить позже)
      - "local"  — локальный GigaAM-v3-CTC (v2_ctc)
    """
    backend = (config.backend or "groq").lower()

    if backend == "local":
        # Локальный GigaAM, модель фиксированная: v2_ctc
        return GigaAMRecognizer(model_name="v2_ctc")

    if backend == "groq":
        return GroqWhisperRecognizer(config.groq)

    # Fallback: по умолчанию Groq
    return GroqWhisperRecognizer(config.groq)