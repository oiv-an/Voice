from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import httpx  # type: ignore[import]
import soundfile as sf  # type: ignore[import]
from loguru import logger  # type: ignore[import]

from audio.recorder import AudioData
from config.settings import OpenRouterRecognitionConfig


# ---------------------------------------------------------------------------#
# ВАЖНО — логика передачи audio в OpenRouter:
#
# OpenRouter НЕ использует whisper /audio/transcriptions (multipart).
# Вместо этого аудио отправляется как base64 строка в поле input_audio
# внутри стандартного chat/completions запроса.
#
# Схема запроса (пример для google/gemini-3.1-flash-lite-preview):
#
# {
#   "model": "google/gemini-3.1-flash-lite-preview",
#   "modalities": ["text"],
#   "messages": [
#     {
#       "role": "user",
#       "content": [
#         { "type": "text",        "text": "ASR prompt" },
#         { "type": "input_audio", "input_audio": { "data": "<base64>", "format": "mp3" } }
#       ]
#     }
#   ],
#   "stream": false
# }
#
# api_key и base_url НЕ зашиваются в код — только из настроек пользователя.
# По умолчанию аудио кодируем в WAV (надёжно через soundfile). Если
# пользователь укажет "mp3" в настройках — попробуем сохранить mp3
# (зависит от libsndfile), иначе откатимся к wav.
# ---------------------------------------------------------------------------#


TRANSCRIBE_PATH = "/chat/completions"


@dataclass
class OpenRouterRecognizer:
    """
    Recognizer для OpenRouter (и совместимых прокси OpenRouter-формата).

    Использует:
      - recognition.openrouter.api_key
      - recognition.openrouter.base_url
      - recognition.openrouter.model
      - recognition.openrouter.prompt
      - recognition.openrouter.audio_format
    """

    config: OpenRouterRecognitionConfig

    def _build_url(self) -> str:
        base = (self.config.base_url or "").strip()
        if not base:
            raise RuntimeError(
                "OpenRouter ASR: base_url не задан. Укажите 'OpenRouter Base URL' в настройках."
            )
        base = base.rstrip("/")
        return f"{base}{TRANSCRIBE_PATH}"

    # ------------------------------------------------------------------ main

    def transcribe(self, audio: AudioData) -> str:
        api_key = (self.config.api_key or "").strip()
        model = (self.config.model or "").strip()
        if not api_key:
            raise RuntimeError("OpenRouter ASR: API‑ключ не задан.")
        if not model:
            raise RuntimeError("OpenRouter ASR: модель не задана.")

        url = self._build_url()

        requested_format = (self.config.audio_format or "mp3").strip().lower() or "mp3"
        audio_bytes, actual_format = self._audio_to_bytes(audio, requested_format)
        b64_audio = base64.b64encode(audio_bytes).decode("ascii")

        prompt_text = (self.config.prompt or "").strip()
        if not prompt_text:
            # Если пользователь не задал prompt — отправляем дефолтную инструкцию.
            # Это не хардкод endpoint-а, это дефолтный текст, который пользователь
            # всегда может переопределить в настройках.
            prompt_text = "Транскрибируй аудио. Ответь ТОЛЬКО распознанным текстом, без пояснений."

        payload: Dict[str, Any] = {
            "model": model,
            "modalities": ["text"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": b64_audio,
                                "format": actual_format,
                            },
                        },
                    ],
                }
            ],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "OpenRouter ASR: POST {} model={} audio_format={} audio_bytes={}",
            url,
            model,
            actual_format,
            len(audio_bytes),
        )

        try:
            # Раздельные таймауты:
            # - connect: 5 сек (если прокси недоступен — быстро падаем)
            # - read: 30 сек (gemini-flash-lite обычно отвечает за 2-5 сек,
            #   но cold-start у некоторых прокси может быть до 15-20 сек)
            # - write/pool: 10 сек
            timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            logger.error("OpenRouter ASR timeout: {}", exc)
            raise RuntimeError("OpenRouter: превышено время ожидания ответа.") from exc
        except httpx.RequestError as exc:
            logger.error("OpenRouter ASR network error: {}", exc)
            raise RuntimeError("OpenRouter: сетевая ошибка при обращении к API.") from exc

        if resp.status_code == 401:
            logger.error("OpenRouter returned 401 Unauthorized")
            raise RuntimeError("OpenRouter: неверный или отсутствующий API‑ключ (401).")
        if resp.status_code == 429:
            logger.error("OpenRouter returned 429 Too Many Requests")
            raise RuntimeError("OpenRouter: превышен лимит запросов (429). Попробуйте позже.")
        if not resp.is_success:
            body = ""
            try:
                body = resp.text[:500]
            except Exception:
                body = ""
            logger.error("OpenRouter returned HTTP {}: {}", resp.status_code, body)
            raise RuntimeError(f"OpenRouter: ошибка сервера ({resp.status_code}).")

        try:
            data = resp.json()
        except ValueError as exc:
            logger.exception("OpenRouter JSON parse error: {}", exc)
            raise RuntimeError("OpenRouter: не удалось разобрать ответ сервера.") from exc

        text = self._extract_text(data)
        if not text:
            logger.error("OpenRouter: пустой ответ. Raw: {}", str(data)[:500])
            raise RuntimeError("OpenRouter: модель вернула пустой ответ.")

        return text

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _extract_text(data: Dict[str, Any]) -> str:
        """
        Извлекаем итоговый текст из ответа chat/completions.

        Поддерживаем два варианта content:
        - строка
        - список объектов вида [{"type": "text", "text": "..."}, ...]
        """
        try:
            choices = data.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            content = message.get("content")

            if isinstance(content, str):
                return content.strip()

            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    # text-парт
                    t = item.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                return "".join(parts).strip()
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenRouter: ошибка извлечения текста: {}", exc)
            return ""

        return ""

    @staticmethod
    def _audio_to_bytes(audio: AudioData, requested_format: str) -> tuple[bytes, str]:
        """
        Кодируем AudioData в байты в указанном формате.

        Возвращаем (bytes, actual_format_string).

        Приоритет по умолчанию: mp3 -> ogg -> wav.
        - mp3 сильнее сжимает, но его поддержка в libsndfile опциональна
        - ogg (Vorbis) всегда доступен в libsndfile >= 1.0.28 и даёт
          сопоставимое с mp3 сжатие (в ~8-10 раз меньше, чем WAV)
        - wav — всегда работает, но большой объём
        """
        samples = audio.samples
        if not isinstance(samples, np.ndarray):
            samples = np.asarray(samples, dtype=np.float32)
        elif samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        requested_format = (requested_format or "mp3").lower()

        # Попытка #1 — MP3, если запрошен
        if requested_format == "mp3":
            try:
                buf = io.BytesIO()
                sf.write(buf, samples, audio.sample_rate, format="MP3")
                buf.seek(0)
                return buf.read(), "mp3"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenRouter ASR: MP3 кодирование не поддерживается ({}). Пробуем OGG.",
                    exc,
                )

        # Попытка #2 — OGG Vorbis (почти всегда доступен и сильно сжимает)
        if requested_format in ("mp3", "ogg"):
            try:
                buf = io.BytesIO()
                sf.write(buf, samples, audio.sample_rate, format="OGG", subtype="VORBIS")
                buf.seek(0)
                return buf.read(), "ogg"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenRouter ASR: OGG кодирование не удалось ({}). Fallback на WAV.",
                    exc,
                )

        # Попытка #3 — WAV fallback (работает всегда, но тяжёлый)
        buf = io.BytesIO()
        sf.write(buf, samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read(), "wav"
