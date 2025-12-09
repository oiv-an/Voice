from __future__ import annotations

import time
from typing import Optional

import pyperclip  # type: ignore[import]
from loguru import logger  # type: ignore[import]

try:
    # Используем keyboard для эмуляции Ctrl+V, чтобы не тащить ещё один контроллер.
    import keyboard  # type: ignore[import]
except Exception:  # noqa: BLE001
    keyboard = None  # type: ignore[assignment]


class ClipboardManager:
    """
    Clipboard helper.

    - copy(text): put text into Windows clipboard
    - paste(): авто-вставка через Ctrl+V с простыми ретраями и логированием ошибок.
    """

    def __init__(self, max_paste_retries: int = 3, paste_retry_delay: float = 0.15) -> None:
        """
        :param max_paste_retries: сколько раз пробовать эмулировать Ctrl+V
        :param paste_retry_delay: задержка между попытками (секунды)
        """
        self._max_paste_retries = max_paste_retries
        self._paste_retry_delay = paste_retry_delay

    def copy(self, text: str) -> None:
        """
        Кладёт текст в системный буфер обмена.
        """
        try:
            pyperclip.copy(text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Clipboard copy failed: {}", exc)
            return

        # небольшая пауза, чтобы ОС успела обновить буфер
        time.sleep(0.05)

    def paste(self) -> None:
        """
        Авто-вставка текста через эмуляцию Ctrl+V.

        Реализация максимально простая:
        - если библиотека keyboard недоступна — просто выходим (пользователь вставит вручную),
        - иначе несколько раз пробуем отправить Ctrl+V с небольшими паузами.
        """
        if keyboard is None:
            logger.warning("keyboard library is not available; auto-paste is disabled.")
            return

        for attempt in range(1, self._max_paste_retries + 1):
            try:
                logger.debug("Auto-paste attempt {} / {}", attempt, self._max_paste_retries)
                keyboard.send("ctrl+v")
                # даём целевому приложению время обработать вставку
                time.sleep(self._paste_retry_delay)
                # На этом этапе мы не можем надёжно проверить, что текст действительно вставился
                # во внешнее приложение, поэтому просто выходим после успешной отправки.
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Auto-paste attempt {} failed: {}", attempt, exc)
                time.sleep(self._paste_retry_delay)