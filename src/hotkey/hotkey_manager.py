from __future__ import annotations

from dataclasses import dataclass
from threading import Thread
from typing import Callable, Optional

import keyboard  # type: ignore[import]


Callback = Callable[[], None]


@dataclass
class HotkeyCallbacks:
    on_record_press: Callback
    on_record_release: Callback
    on_cancel: Callback
    on_toggle_window: Callback
    on_toggle_debug: Callback


class HotKeyManager:
    """
    Global hotkey manager using `keyboard` library.

    Default bindings (configurable via config.yaml):
        - record:        ctrl+win   (press / release)
        - cancel:        esc
        - toggle_window: ctrl+alt+s
        - toggle_debug:  ctrl+alt+d
    """

    def __init__(
        self,
        record_hotkey: str,
        cancel_hotkey: str,
        toggle_window_hotkey: str,
        toggle_debug_hotkey: str,
        on_record_press: Callback,
        on_record_release: Callback,
        on_cancel: Callback,
        on_toggle_window: Callback,
        on_toggle_debug: Callback,
    ) -> None:
        self.record_hotkey = record_hotkey
        self.cancel_hotkey = cancel_hotkey
        self.toggle_window_hotkey = toggle_window_hotkey
        self.toggle_debug_hotkey = toggle_debug_hotkey

        self.callbacks = HotkeyCallbacks(
            on_record_press=on_record_press,
            on_record_release=on_record_release,
            on_cancel=on_cancel,
            on_toggle_window=on_toggle_window,
            on_toggle_debug=on_toggle_debug,
        )

        self._listener_thread: Optional[Thread] = None
        self._running: bool = False

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        """
        Start listening for global hotkeys in a background thread.
        """
        if self._running:
            return
        self._running = True
        self._listener_thread = Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()

    def stop(self) -> None:
        """
        Stop listening for hotkeys.
        """
        if not self._running:
            return
        self._running = False
        keyboard.unhook_all()

    # ---------------------------------------------------------------- internal

    def _listen_loop(self) -> None:
        """
        Register hotkeys and block in a loop until stop() is called.
        """
        # Record press / release
        # Явно разделяем старт и стоп по нажатию/отжатию основной клавиши,
        # чтобы не было залипания.
        main_key = self._normalize_hotkey_main_key(self.record_hotkey)

        keyboard.on_press_key(
            main_key,
            lambda e: self.callbacks.on_record_press(),
            suppress=False,
        )
        keyboard.on_release_key(
            main_key,
            lambda e: self.callbacks.on_record_release(),
            suppress=False,
        )

        # Cancel
        keyboard.add_hotkey(self.cancel_hotkey, self.callbacks.on_cancel, suppress=False)

        # Toggle window
        keyboard.add_hotkey(
            self.toggle_window_hotkey,
            self.callbacks.on_toggle_window,
            suppress=False,
        )

        # Toggle debug
        keyboard.add_hotkey(
            self.toggle_debug_hotkey,
            self.callbacks.on_toggle_debug,
            suppress=False,
        )

        # Block until stop() is called; simple polling loop.
        import time

        while self._running:
            time.sleep(0.1)

    @staticmethod
    def _normalize_hotkey_main_key(hotkey: str) -> str:
        """
        Оставлено для совместимости, сейчас не используется.
        """
        parts = hotkey.split("+")
        return parts[-1].strip()

    # ----------------------------------------------------------------- helpers

    def _toggle_record(self) -> None:
        """
        Один хоткей переключает запись:
        - если сейчас не пишем → on_record_press()
        - если уже пишем      → on_record_release()
        """
        # Простейшая логика: App сам хранит флаг is_recording,
        # поэтому мы просто вызываем оба колбэка по очереди,
        # а App решает, что делать.
        # Если нужно, можно заменить на явный флаг в HotKeyManager.
        try:
            self.callbacks.on_record_press()
        except Exception:
            pass
        try:
            self.callbacks.on_record_release()
        except Exception:
            pass