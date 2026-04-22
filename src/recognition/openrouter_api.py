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

        # Вычисляем длительность аудио — нужно для адаптивного таймаута
        try:
            duration_sec = len(audio.samples) / audio.sample_rate
        except Exception:
            duration_sec = 0.0

        requested_format = (self.config.audio_format or "ogg").strip().lower() or "ogg"
        logger.info(
            "OpenRouter ASR: encoding audio (duration={:.2f}s, requested_format={})",
            duration_sec,
            requested_format,
        )
        audio_bytes, actual_format = self._audio_to_bytes(audio, requested_format)
        logger.info(
            "OpenRouter ASR: encoded {} bytes as {} (base64 will be ~{} bytes)",
            len(audio_bytes),
            actual_format,
            int(len(audio_bytes) * 4 / 3),
        )
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
            "OpenRouter ASR: preparing request model={} audio_format={} audio_bytes={} b64_len={}",
            model,
            actual_format,
            len(audio_bytes),
            len(b64_audio),
        )

        try:
            # Адаптивные таймауты:
            # - connect: 5 сек (если прокси недоступен — быстро падаем)
            # - read: зависит от длительности аудио, 30 сек базы + 3 сек на
            #   каждую секунду аудио (для 20 мин = 30 + 3600 = 1 час max).
            #   Мультимодальные модели на длинном аудио действительно думают долго.
            # - write: 60 сек (для больших base64-пэйлоадов)
            read_timeout = max(30.0, 30.0 + duration_sec * 3.0)
            timeout = httpx.Timeout(
                connect=5.0,
                read=read_timeout,
                write=60.0,
                pool=10.0,
            )
            logger.info(
                "OpenRouter ASR: POST {} (read_timeout={:.0f}s)", url, read_timeout
            )
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

        ВАЖНО о форматах:
        - OGG Vorbis через libsndfile на Windows может падать со stack overflow
          на длинных записях (>30 сек). Поэтому OGG пробуем, но с жёстким
          ограничением по длительности — если аудио длиннее 25 секунд,
          принудительно используем FLAC или WAV.
        - FLAC — сжатие ~2× от WAV, всегда стабильно работает в libsndfile.
        - WAV — универсальный fallback, всегда работает.
        - MP3 — опциональная поддержка в libsndfile, часто недоступна.
        """
        samples = audio.samples
        if not isinstance(samples, np.ndarray):
            samples = np.asarray(samples, dtype=np.float32)
        elif samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        # Вычисляем длительность — на длинных записях OGG небезопасен
        try:
            duration_sec = len(samples) / audio.sample_rate
        except Exception:
            duration_sec = 0.0

        # Для длинных записей OGG может упасть со stack overflow —
        # форсируем FLAC или WAV.
        OGG_MAX_SAFE_DURATION = 25.0  # сек
        if duration_sec > OGG_MAX_SAFE_DURATION and requested_format in ("mp3", "ogg"):
            logger.warning(
                "OpenRouter ASR: audio too long for OGG/MP3 ({:.1f}s > {:.0f}s). "
                "Forcing FLAC to avoid libsndfile stack overflow.",
                duration_sec,
                OGG_MAX_SAFE_DURATION,
            )
            requested_format = "flac"

        requested_format = (requested_format or "ogg").lower()

        # Попытка #1 — MP3, если запрошен (и запись короткая)
        if requested_format == "mp3":
            try:
                buf = io.BytesIO()
                sf.write(buf, samples, audio.sample_rate, format="MP3")
                buf.seek(0)
                result = buf.read()
                if len(result) > 0:
                    return result, "mp3"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenRouter ASR: MP3 encoding failed ({}). Trying OGG.",
                    exc,
                )

        # Попытка #2 — OGG Vorbis (только для коротких записей)
        if requested_format == "ogg":
            try:
                buf = io.BytesIO()
                sf.write(buf, samples, audio.sample_rate, format="OGG", subtype="VORBIS")
                buf.seek(0)
                result = buf.read()
                if len(result) > 0:
                    return result, "ogg"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenRouter ASR: OGG encoding failed ({}). Falling back to FLAC.",
                    exc,
                )

        # Попытка #3 — FLAC (надёжное сжатие без потерь, ~2× от WAV)
        if requested_format in ("flac", "mp3", "ogg"):
            try:
                buf = io.BytesIO()
                sf.write(buf, samples, audio.sample_rate, format="FLAC")
                buf.seek(0)
                result = buf.read()
                if len(result) > 0:
                    return result, "flac"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenRouter ASR: FLAC encoding failed ({}). Falling back to WAV.",
                    exc,
                )

        # Попытка #4 — WAV (работает всегда, но большой объём)
        buf = io.BytesIO()
        sf.write(buf, samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read(), "wav"
