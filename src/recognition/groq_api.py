from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Tuple

import numpy as np
import requests  # type: ignore[import]
import soundfile as sf  # type: ignore[import]
from loguru import logger  # type: ignore[import]

from config.settings import GroqRecognitionConfig
from audio.recorder import AudioData


GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


@dataclass
class GroqWhisperRecognizer:
    """
    Minimal Groq Whisper recognizer for MVP.

    Converts AudioData to in-memory WAV and sends it to Groq Whisper endpoint.

    Для удобства обработки ошибок метод transcribe возвращает только текст
    и выбрасывает осмысленные исключения с человекочитаемыми сообщениями.
    """

    config: GroqRecognitionConfig

    def transcribe(self, audio: AudioData) -> str:
        """
        Две попытки запроса к Groq:
        - первая сразу,
        - вторая через 1 секунду, если первая упала по timeout / сетевой ошибке.
        Если обе попытки неудачны — выбрасываем RuntimeError.
        """
        import time

        wav_bytes = self._audio_to_wav_bytes(audio)

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

        last_exc: Exception | None = None

        for attempt in (1, 2):
            try:
                logger.info("Groq request attempt {} to {}", attempt, GROQ_TRANSCRIBE_URL)
                resp = requests.post(
                    GROQ_TRANSCRIBE_URL,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60,
                )
                # Если дошли до сюда — HTTP-запрос выполнен, выходим из цикла
                break
            except requests.Timeout as exc:  # type: ignore[attr-defined]
                logger.exception("Groq request timeout (attempt {}): {}", attempt, exc)
                last_exc = exc
            except requests.RequestException as exc:  # type: ignore[attr-defined]
                logger.exception("Groq network error (attempt {}): {}", attempt, exc)
                last_exc = exc

            if attempt == 1:
                # Пауза 1 секунда перед второй попыткой
                time.sleep(1.0)

        # Если обе попытки не удались — поднимаем осмысленную ошибку
        if last_exc is not None and "resp" not in locals():
            if isinstance(last_exc, requests.Timeout):  # type: ignore[attr-defined]
                raise RuntimeError("Groq: превышено время ожидания ответа.") from last_exc
            raise RuntimeError("Groq: сетевая ошибка при обращении к API.") from last_exc

        # HTTP-ошибки обрабатываем с разными сообщениями
        if resp.status_code == 401:
            logger.error("Groq returned 401 Unauthorized")
            raise RuntimeError("Groq: неверный или отсутствующий API‑ключ (401).")
        if resp.status_code == 429:
            logger.error("Groq returned 429 Too Many Requests")
            raise RuntimeError("Groq: превышен лимит запросов (429). Попробуйте позже.")
        if not resp.ok:
            logger.error(
                "Groq returned HTTP {}: {}",
                resp.status_code,
                resp.text[:500],
            )
            raise RuntimeError(f"Groq: ошибка сервера ({resp.status_code}).")

        try:
            payload: dict[str, Any] = resp.json()
        except ValueError as exc:
            logger.exception("Groq JSON parse error: {}", exc)
            raise RuntimeError("Groq: не удалось разобрать ответ сервера.") from exc

        text = payload.get("text", "")
        if not isinstance(text, str):
            logger.error("Groq response does not contain 'text' field: {}", payload)
            raise RuntimeError("Groq: в ответе нет поля 'text'.")

        return text

    @staticmethod
    def _audio_to_wav_bytes(audio: AudioData) -> bytes:
        """
        Convert AudioData (float32 numpy) to WAV bytes (16kHz mono).
        """
        buf = io.BytesIO()
        sf.write(buf, audio.samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read()