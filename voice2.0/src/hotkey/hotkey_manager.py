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

        # Block until stop() is called; simple polling loop.
        import time

        while self._running:
            time.sleep(0.1)

    def _handle_release(self) -> None:
        """
        Вызывается при отпускании модификаторов.
        Мы просто дергаем оба release-колбэка.
        App сам проверит, какой режим был активен, и остановит нужный.
        """
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