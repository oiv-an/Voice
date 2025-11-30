from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
import requests  # type: ignore[import]
import soundfile as sf  # type: ignore[import]
from loguru import logger  # type: ignore[import]

from audio.recorder import AudioData
from config.settings import OpenAIRecognitionConfig


OPENAI_TRANSCRIBE_PATH = "/audio/transcriptions"


@dataclass
class OpenAIWhisperRecognizer:
    """
    OpenAI Whisper recognizer.

    Конвертирует AudioData в in-memory WAV и отправляет на OpenAI-совместимый
    endpoint (base_url из конфига + /audio/transcriptions).

    Использует:
      - recognition.openai.api_key
      - recognition.openai.model
      - recognition.openai.language
      - recognition.openai.base_url
    """

    config: OpenAIRecognitionConfig

    def _build_url(self) -> str:
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        return f"{base}{OPENAI_TRANSCRIBE_PATH}"

    def transcribe(self, audio: AudioData) -> str:
        wav_bytes = self._audio_to_wav_bytes(audio)

        url = self._build_url()
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
        }

        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
        }

        data = {
            "model": self.config.model,
            "language": self.config.language,
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=60,
            )
        except requests.Timeout as exc:  # type: ignore[attr-defined]
            logger.exception("OpenAI request timeout: {}", exc)
            raise RuntimeError("OpenAI: превышено время ожидания ответа.") from exc
        except requests.RequestException as exc:  # type: ignore[attr-defined]
            logger.exception("OpenAI network error: {}", exc)
            raise RuntimeError("OpenAI: сетевая ошибка при обращении к API.") from exc

        if resp.status_code == 401:
            logger.error("OpenAI returned 401 Unauthorized")
            raise RuntimeError("OpenAI: неверный или отсутствующий API‑ключ (401).")
        if resp.status_code == 429:
            logger.error("OpenAI returned 429 Too Many Requests")
            raise RuntimeError(
                "OpenAI: превышен лимит запросов (429). Попробуйте позже."
            )
        if not resp.ok:
            logger.error(
                "OpenAI returned HTTP {}: {}",
                resp.status_code,
                resp.text[:500],
            )
            raise RuntimeError(f"OpenAI: ошибка сервера ({resp.status_code}).")

        try:
            payload: dict[str, Any] = resp.json()
        except ValueError as exc:
            logger.exception("OpenAI JSON parse error: {}", exc)
            raise RuntimeError("OpenAI: не удалось разобрать ответ сервера.") from exc

        text = payload.get("text", "")
        if not isinstance(text, str):
            logger.error("OpenAI response does not contain 'text' field: {}", payload)
            raise RuntimeError("OpenAI: в ответе нет поля 'text'.")

        return text

    @staticmethod
    def _audio_to_wav_bytes(audio: AudioData) -> bytes:
        """
        Convert AudioData (float32 numpy) to WAV bytes (16kHz mono).
        """
        # На всякий случай приводим к float32 numpy
        samples = audio.samples
        if not isinstance(samples, np.ndarray):
            samples = np.asarray(samples, dtype=np.float32)
        elif samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        buf = io.BytesIO()
        sf.write(buf, samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read()