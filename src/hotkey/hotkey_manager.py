from __future__ import annotations

from dataclasses import dataclass
from threading import RLock, Thread
from typing import Callable, Optional

import keyboard  # type: ignore[import]
from loguru import logger


Callback = Callable[[], None]


@dataclass
class HotkeyCallbacks:
    on_record_press: Callback
    on_record_release: Callback
    on_record_idea_press: Callback
    on_record_idea_release: Callback
    on_convert_to_idea: Callback  # New callback for Alt press
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
        record_idea_hotkey: str,
        cancel_hotkey: str,
        toggle_window_hotkey: str,
        toggle_debug_hotkey: str,
        on_record_press: Callback,
        on_record_release: Callback,
        on_record_idea_press: Callback,
        on_record_idea_release: Callback,
        on_convert_to_idea: Callback,
        on_cancel: Callback,
        on_toggle_window: Callback,
        on_toggle_debug: Callback,
    ) -> None:
        self.record_hotkey = record_hotkey
        self.record_idea_hotkey = record_idea_hotkey
        self.cancel_hotkey = cancel_hotkey
        self.toggle_window_hotkey = toggle_window_hotkey
        self.toggle_debug_hotkey = toggle_debug_hotkey

        self.callbacks = HotkeyCallbacks(
            on_record_press=on_record_press,
            on_record_release=on_record_release,
            on_record_idea_press=on_record_idea_press,
            on_record_idea_release=on_record_idea_release,
            on_convert_to_idea=on_convert_to_idea,
            on_cancel=on_cancel,
            on_toggle_window=on_toggle_window,
            on_toggle_debug=on_toggle_debug,
        )

        self._listener_thread: Optional[Thread] = None
        self._running: bool = False
        self._lock = RLock()

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        """
        Start listening for global hotkeys in a background thread.
        """
        with self._lock:
            if self._running:
                return
            self._running = True
            self._listener_thread = Thread(
                target=self._listen_loop,
                name="HotKeyManagerListener",
                daemon=True,
            )
            self._listener_thread.start()

    def stop(self) -> None:
        """
        Stop listening for hotkeys.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
            try:
                keyboard.unhook_all()
                logger.info("Global hotkeys stopped")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to stop global hotkeys: {}", exc)

    def restart(self) -> bool:
        """
        Soft-restart global keyboard hooks without restarting the application.

        The `keyboard` library can occasionally stop delivering global hotkey
        events on Windows while the Qt application itself remains alive. In that
        case a full app restart is unnecessary: unhooking and registering the
        hotkeys again is usually enough.
        """
        with self._lock:
            if not self._running:
                logger.info("Hotkey restart requested while stopped; starting listener")
                self.start()
                return True

            try:
                logger.info("Restarting global hotkey hooks")
                keyboard.unhook_all()
                self._register_hotkeys()
                logger.info("Global hotkey hooks restarted successfully")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to restart global hotkey hooks: {}", exc)
                return False

    # ---------------------------------------------------------------- internal

    def _listen_loop(self) -> None:
        """
        Register hotkeys and block in a loop until stop() is called.
        """
        try:
            self._register_hotkeys()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to register global hotkeys: {}", exc)
            with self._lock:
                self._running = False
            return

        # Block until stop() is called; simple polling loop.
        import time

        while self._running:
            time.sleep(0.1)

    def _register_hotkeys(self) -> None:
        """
        Register all configured hotkeys.

        This method is intentionally idempotent only when callers unhook first.
        Use restart() for safe re-registration during runtime.
        """
        # Record press / release
        # Явно разделяем старт и стоп по нажатию/отжатию основной клавиши,
        # чтобы не было залипания.
        
        # 1. Основная запись (Ctrl+Win)
        # Для сложных сочетаний (Ctrl+Win) лучше использовать add_hotkey для press
        # и отслеживать release отдельно, но keyboard.on_release_key работает по скан-коду клавиши.
        # В текущей реализации мы используем подход:
        #  - on_press_key(main_key) -> callback
        #  - on_release_key(main_key) -> callback
        # Это работает, если record_hotkey - это одна клавиша или модификатор+клавиша,
        # где мы слушаем именно "последнюю" клавишу.
        
        # Однако, пользователь хочет Ctrl+Win (обычная запись) и Ctrl+Win+Alt (идея).
        # Это пересекающиеся хоткеи.
        # Чтобы их различать, нужно проверять состояние модификаторов или использовать add_hotkey.
        
        # Попробуем использовать add_hotkey для обоих случаев для нажатия.
        # А для отпускания - сложнее, так как add_hotkey не дает события release.
        # Но библиотека keyboard позволяет вешать хук на сочетание.
        
        # ВАЖНО: Чтобы различать Ctrl+Win и Ctrl+Win+Alt, нужно регистрировать их аккуратно.
        # Если мы просто повесим хук на Ctrl+Win, он может срабатывать и при Ctrl+Win+Alt.
        
        # Поэтому используем keyboard.add_hotkey для старта записи.
        # А для остановки - придется слушать release всех участвующих клавиш или хотя бы одной.
        
        # Реализация через add_hotkey (press) + wait release (не подходит для асинхронности).
        
        # Вернемся к логике:
        # record_hotkey = "ctrl+win"
        # record_idea_hotkey = "ctrl+win+alt"
        
        # Мы можем зарегистрировать оба хоткея на нажатие.
        keyboard.add_hotkey(
            self.record_hotkey,
            self.callbacks.on_record_press,
            suppress=False,
            trigger_on_release=False
        )
        
        keyboard.add_hotkey(
            self.record_idea_hotkey,
            self.callbacks.on_record_idea_press,
            suppress=False,
            trigger_on_release=False
        )

        # Отслеживаем нажатие Alt для конвертации обычной записи в идею
        # Используем 'alt' (или 'left alt' / 'right alt')
        keyboard.on_press_key(
            "alt",
            lambda e: self.callbacks.on_convert_to_idea(),
            suppress=False
        )
        
        # Для отпускания нам нужно знать, когда пользователь отпустил комбинацию.
        # Обычно достаточно отпускания любой из клавиш комбинации или основной клавиши.
        # В данном случае (Ctrl+Win и Ctrl+Win+Alt) нет явной "основной" буквы.
        # Но обычно это Win (Left Windows).
        
        # Чтобы не усложнять, повесим обработчик на отпускание клавиш, которые могут входить в хоткей.
        # Но проще всего сделать так:
        # При нажатии мы запускаем запись.
        # При отпускании ЛЮБОЙ клавиши из хоткея мы останавливаем запись.
        
        # Но keyboard не дает простого способа "on_hotkey_release".
        # Поэтому используем старый проверенный способ: слушаем release конкретных клавиш.
        # Предположим, что "win" (left windows) или "ctrl" являются триггерами отпускания.
        
        # В предыдущей реализации было:
        # main_key = self._normalize_hotkey_main_key(self.record_hotkey)
        # keyboard.on_release_key(main_key, ...)
        
        # Если record_hotkey="ctrl+win", то main_key="win".
        # Если record_idea_hotkey="ctrl+win+alt", то main_key="alt" (или win, зависит от порядка).
        
        # Давайте сделаем так:
        # Мы будем слушать отпускание клавиш 'ctrl', 'win', 'alt'.
        # Если отпущена любая из них - мы шлем сигнал release.
        # Приложение (App) само разберется: если оно пишет "обычно", то остановит обычную запись.
        # Если пишет "идею", то остановит идею.
        
        for key in ['ctrl', 'left windows', 'right windows', 'alt', 'left alt', 'right alt']:
             keyboard.on_release_key(key, lambda e: self._handle_release(), suppress=False)

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

        logger.info(
            "Global hotkeys registered: record='{}', idea='{}', cancel='{}', toggle_window='{}', toggle_debug='{}'",
            self.record_hotkey,
            self.record_idea_hotkey,
            self.cancel_hotkey,
            self.toggle_window_hotkey,
            self.toggle_debug_hotkey,
        )

    def _handle_release(self) -> None:
        """
        Вызывается при отпускании модификаторов.
        Проверяем, что комбинация ДЕЙСТВИТЕЛЬНО разорвана (хотя бы одна
        ключевая клавиша отпущена), прежде чем слать release.
        Это предотвращает мигание при нажатии Ctrl+Win+Alt.
        """
        # Проверяем, что хотя бы Ctrl или Win отпущены
        # (если только Alt отпущен, но Ctrl+Win ещё зажаты — запись продолжается)
        try:
            ctrl_pressed = keyboard.is_pressed('ctrl')
            win_pressed = keyboard.is_pressed('left windows') or keyboard.is_pressed('right windows')
        except Exception:
            ctrl_pressed = False
            win_pressed = False

        # Если Ctrl+Win всё ещё зажаты — не останавливаем запись
        if ctrl_pressed and win_pressed:
            return

        try:
            self.callbacks.on_record_release()
        except Exception:
            pass
        try:
            self.callbacks.on_record_idea_release()
        except Exception:
            pass

    @staticmethod
    def _normalize_hotkey_main_key(hotkey: str) -> str:
        """
        Оставлено для совместимости, сейчас не используется.
        """
        parts = hotkey.split("+")
        return parts[-1].strip()