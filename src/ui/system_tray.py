from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget, QApplication, QStyle

from config.settings import AppInfoConfig


class SystemTrayIcon(QObject):
    """
    Minimal system tray integration for MVP.

    Сигналы:
        - show_window_requested
        - settings_requested
        - toggle_debug_requested
        - exit_requested
    """

    show_window_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    toggle_debug_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent_window: QWidget, app_info: AppInfoConfig) -> None:
        super().__init__(parent_window)
        self._parent_window = parent_window
        self._app_info = app_info

        # Используем ТОЛЬКО штатные системные иконки Qt/Windows.
        # Никаких внешних файлов, всё берём из стандартных QStyle.StandardPixmap.
        
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon()

            # Сразу ставим системную иконку, чтобы не было состояния "no icon set".
            system_icon = self._create_system_icon()
            self.tray.setIcon(system_icon)

            # Меню и обработчики.
            self._init_menu()
            self.tray.activated.connect(self._on_activated)
            self.tray.show()
        else:
            from loguru import logger
            logger.warning("System tray is not available. Tray icon will not be shown.")
            self.tray = None

    # ------------------------------------------------------------------ setup

    def _create_system_icon(self) -> QIcon:
        """
        Возвращает системную иконку из стандартного набора Qt/Windows.

        Приоритет:
        1) SP_MediaVolume (часто отображается как динамик/аудио).
        2) SP_ComputerIcon.
        3) Пустой QIcon (как крайний случай, но setIcon всё равно вызывается).
        """
        app = QApplication.instance()
        if app is None:
            return QIcon()

        style = app.style()
        if style is None:
            return QIcon()

        # 1. Пробуем иконку, связанную с аудио/медиа.
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        if not icon.isNull():
            return icon

        # 2. Фолбэк — стандартная иконка компьютера.
        icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        if not icon.isNull():
            return icon

        # 3. Крайний случай — генерируем программную иконку (цветной квадрат).
        # Это гарантирует, что иконка будет видна, даже если системные не найдены.
        return self._create_fallback_icon()

    def _create_fallback_icon(self) -> QIcon:
        """Генерирует простую программную иконку (синий круг)."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor
        
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(0, 0, 0, 0))  # Прозрачный фон
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#007bff"))  # Синий цвет
        painter.setPen(QColor("white"))
        painter.drawEllipse(1, 1, 14, 14)
        painter.end()
        
        return QIcon(pixmap)

    def _init_icon(self) -> None:
        """
        Инициализация иконки трея.

        Сейчас мы сознательно ИГНОРИРУЕМ любые внешние файлы и иконку окна
        и используем только системные иконки Windows через QStyle.
        Это гарантирует отсутствие зависимости от ресурсов и предупреждений
        вида 'No Icon set'.
        """
        system_icon = self._create_system_icon()
        self.tray.setIcon(system_icon)
        self.tray.setToolTip(self._app_info.name)

    def _init_menu(self) -> None:
        menu = QMenu()

        action_show = menu.addAction("Показать/скрыть окно")
        action_show.triggered.connect(self.show_window_requested.emit)

        action_settings = menu.addAction("Настройки")
        action_settings.triggered.connect(self.settings_requested.emit)

        action_toggle_debug = menu.addAction("Переключить debug")
        action_toggle_debug.triggered.connect(self.toggle_debug_requested.emit)

        menu.addSeparator()

        action_exit = menu.addAction("Выход")
        action_exit.triggered.connect(self.exit_requested.emit)

        self.tray.setContextMenu(menu)

    # ----------------------------------------------------------------- events

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # ЛКМ по иконке — показать/скрыть окно
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()