from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict

import httpx  # type: ignore[import]
from loguru import logger  # type: ignore[import]

from config.settings import PostprocessConfig


@dataclass
class TextPostprocessor:
    """
    Постобработка текста.

    Режимы:
      - enabled = False  -> только возвращаем текст как есть (без даже regex)
      - enabled = True, mode = "simple" -> лёгкая regex-очистка
      - enabled = True, mode = "llm"    -> regex-очистка + LLM (Groq/OpenAI)

    ВАЖНО: при любой ошибке LLM мы не ломаем UX, а возвращаем regex-вариант.
    """

    config: PostprocessConfig

    def process(self, text: str) -> str:
        text = text or ""

        # Постпроцессинг полностью выключен
        if not self.config.enabled:
            return self._simple_cleanup(text)

        # Только простая очистка
        if (self.config.mode or "simple").lower() == "simple":
            return self._simple_cleanup(text)

        # Режим LLM: сначала regex, потом попытка прогнать через модель.
        # Если ключей нет или что-то падает — тихо откатываемся к regex,
        # без выброса исключения наружу (чтобы не ломать поток записи).
        cleaned = self._simple_cleanup(text)

        # Если нет ключа для выбранного backend'а — сразу возвращаем regex.
        backend = (self.config.llm_backend or "groq").lower()

        # Для Groq/OpenAI больше НЕТ отдельных ключей в блоке postprocess.
        # Используем только recognition.*.api_key, который должен быть
        # передан сюда извне (например, через App). Если его нет — просто
        # не вызываем LLM и возвращаем regex-вариант.
        if backend == "groq":
            api_key = getattr(self.config.groq, "api_key", "") or ""
            if not api_key.strip():
                logger.warning("Groq LLM postprocess skipped: API key is empty")
                return cleaned

        if backend == "openai":
            api_key = getattr(self.config.openai, "api_key", "") or ""
            if not api_key.strip():
                logger.warning("OpenAI LLM postprocess skipped: API key is empty")
                return cleaned

        try:
            llm_text = self._llm_cleanup(cleaned)
            return llm_text or cleaned
        except RuntimeError as exc:
            # Эти ошибки уже залогированы в _llm_groq/_llm_openai.
            # Просто возвращаем очищенный текст.
            logger.warning("LLM postprocess failed, fallback to regex-only: {}", exc)
            return cleaned
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unexpected LLM postprocess error, fallback to regex-only: {}", exc
            )
            return cleaned

    # ------------------------------------------------------------------ simple regex

    @staticmethod
    def _simple_cleanup(text: str) -> str:
        # Удалить лишние пробелы
        text = re.sub(r"\s+", " ", text).strip()

        # Пробел перед знаками препинания убрать
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)

        # Пробел после запятой/точки/восклицательного/вопросительного знака
        text = re.sub(r"([,.!?;:])([^\s])", r"\1 \2", text)

        # Удалить артефакты вида [BLANK_AUDIO] и т.п.
        text = re.sub(r"\[[^\]]+\]", "", text).strip()

        return text

    # ------------------------------------------------------------------ LLM cleanup

    def _llm_cleanup(self, text: str) -> str:
        """
        Прогоняет текст через LLM (Groq/OpenAI) для улучшения грамматики и пунктуации.

        Промпт:
        «Исправь опечатки, добавь пунктуацию, сделай предложение грамматически верным.
         Не меняй смысл. Ответь ТОЛЬКО исправленным текстом.»
        """
        backend = (self.config.llm_backend or "groq").lower()

        if backend == "groq":
            return self._llm_groq(text)
        if backend == "openai":
            return self._llm_openai(text)

        logger.warning("Unknown LLM backend '{}', fallback to original text", backend)
        return text

    def _llm_groq(self, text: str) -> str:
        """
        Вызов Groq LLM (chat.completions) для постобработки текста.

        Для препроцессинга используем тот же ключ, что и для Whisper через Groq,
        чтобы пользователь вводил его один раз в одном месте.

        ВАЖНО:
        - ключ берём из self.config.groq.api_key, который должен быть
          прокинут из recognition.groq.api_key;
        - модель LLM берём ТОЛЬКО из recognition.groq.model_process.
        """
        api_key = (getattr(self.config.groq, "api_key", "") or "").strip()
        # Модель LLM Groq берём только из recognition.groq.model_process.
        # Никаких fallback'ов на postprocess.groq.model и жёстких дефолтов.
        model = getattr(self.config.groq, "model_process", "") or ""
        model = model.strip()

        if not api_key:
            raise RuntimeError("Groq LLM: API‑ключ не задан.")
        if not model:
            raise RuntimeError(
                "Groq LLM: модель не задана. Укажите модель в настройках (поле Groq LLM model)."
            )

        logger.info("Groq LLM postprocess using model: {}", model)

        # Базовый URL для LLM Groq должен быть тем же, что и для транскрибации:
        # единый публичный endpoint Groq OpenAI-совместимого API.
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
        }

        try:
            # Короткий таймаут 2 секунды, чтобы не подвешивать постпроцессинг.
            # Короткий таймаут 2 секунды, чтобы не подвешивать постпроцессинг.
            resp = httpx.post(url, headers=headers, json=payload, timeout=2.0)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("LLM (Groq) timeout for model {}: {}", model, exc)
            raise RuntimeError(f"Timeout connecting to Groq LLM: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error("LLM (Groq) network error for model {}: {}", model, exc)
            raise RuntimeError(f"Network error connecting to Groq LLM: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM (Groq) HTTP error {} for model {}: {}",
                exc.response.status_code,
                model,
                exc.response.text,
            )
            if exc.response.status_code == 401:
                raise RuntimeError("Groq LLM: Invalid API key (401).")
            if exc.response.status_code == 429:
                raise RuntimeError("Groq LLM: Rate limit exceeded (429).")
            if exc.response.status_code == 400:
                raise RuntimeError(
                    "Groq LLM: The selected model may no longer be supported (400)."
                )
            raise RuntimeError(
                f"Groq LLM server error: {exc.response.status_code}"
            ) from exc


        try:
            data = resp.json()
        except ValueError as exc:
            logger.exception("Groq LLM JSON parse error: {}", exc)
            raise RuntimeError("Groq LLM: не удалось разобрать ответ сервера.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.error("Groq LLM unexpected response format: {}", data)
            raise RuntimeError("Groq LLM: неожиданный формат ответа.") from exc

        if not isinstance(content, str):
            raise RuntimeError("Groq LLM: контент ответа не является строкой.")

        return content.strip()

    def _llm_openai(self, text: str) -> str:
        """
        Вызов OpenAI LLM для постобработки.

        ВАЖНО:
        - ключ всегда берём из recognition.openai.api_key, который SettingsDialog пишет в config.yaml;
        - модель берём из recognition.openai.model_process (с fallback на recognition.openai.model);
        - base_url берём ТОЛЬКО из recognition.openai.base_url;
        - блок postprocess.openai НЕ содержит ни ключа, ни base_url.
        """
        # Ключ и модель/URL приходят из recognition.openai.*,
        # которые App и SettingsDialog прокидывают в config.postprocess.openai
        # как "прозрачный" контейнер.
        api_key = (getattr(self.config.openai, "api_key", "") or "").strip()
        model = (getattr(self.config.openai, "model_process", "") or "").strip()
        if not model:
            # Fallback на основную модель OpenAI ASR, если отдельная LLM‑модель не задана.
            model = (getattr(self.config.openai, "model", "") or "").strip()

        base_url = (getattr(self.config.openai, "base_url", "") or "").strip()

        if not base_url:
            raise RuntimeError(
                "OpenAI LLM: base_url не задан. Укажите 'OpenAI Base URL' в настройках."
            )

        if not api_key:
            raise RuntimeError(
                "OpenAI LLM: отсутствует API‑ключ. "
                "Заполните поле 'OpenAI API key' в настройках и сохраните."
            )

        if not model:
            raise RuntimeError(
                "OpenAI LLM: модель не задана. Укажите модель в настройках (поле OpenAI postprocess model)."
            )

        # Совместимый с OpenAI / proxy формат /chat/completions
        url = base_url.rstrip("/") + "/chat/completions"
        logger.info("OpenAI LLM postprocess URL: {}", url)
        logger.info("OpenAI LLM postprocess using model: {}", model)
        logger.info("OpenAI LLM postprocess using api_key (first 8 chars): {}***", api_key[:8])
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.prompt,
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
        }

        try:
            # Короткий таймаут 2 секунды, чтобы не подвешивать постпроцессинг.
            # Короткий таймаут 2 секунды, чтобы не подвешивать постпроцессинг.
            resp = httpx.post(url, headers=headers, json=payload, timeout=2.0)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("OpenAI LLM timeout for model {}: {}", model, exc)
            raise RuntimeError(f"Timeout connecting to OpenAI LLM: {exc}") from exc
        except httpx.RequestError as exc:
            logger.error("OpenAI LLM network error for model {}: {}", model, exc)
            raise RuntimeError(f"Network error connecting to OpenAI LLM: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OpenAI LLM HTTP error {} for model {}: {}",
                exc.response.status_code,
                model,
                exc.response.text,
            )
            if exc.response.status_code == 401:
                raise RuntimeError("OpenAI LLM: Invalid API key (401).")
            if exc.response.status_code == 429:
                raise RuntimeError("OpenAI LLM: Rate limit exceeded (429).")
            raise RuntimeError(
                f"OpenAI LLM server error: {exc.response.status_code}"
            ) from exc


        try:
            data = resp.json()
        except ValueError as exc:
            logger.exception("OpenAI LLM JSON parse error: {}", exc)
            raise RuntimeError("OpenAI LLM: не удалось разобрать ответ сервера.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI LLM unexpected response format: {}", data)
            raise RuntimeError("OpenAI LLM: неожиданный формат ответа.") from exc

        if not isinstance(content, str):
            raise RuntimeError("OpenAI LLM: контент ответа не является строкой.")

        return content.strip()