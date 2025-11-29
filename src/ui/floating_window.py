from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QGuiApplication
from PyQt6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QStackedLayout,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QCheckBox,
)

from config.settings import UIConfig


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class FloatingWindow(QWidget):
    """
    Главное плавающее окно VoiceCapture.

    Режимы:
        - normal  — большое окно с текстом и кнопками
        - compact — маленький "висячий микрофон"

    Состояния:
        - idle
        - recording
        - processing
        - ready
        - error
    """

    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    toggle_compact_requested = pyqtSignal()
    settings_save_requested = pyqtSignal()

    def __init__(self, ui_config: UIConfig) -> None:
        super().__init__()

        self._ui_config = ui_config
        self._drag_position: Optional[QPoint] = None
        self._state: str = "idle"
        self._compact: bool = False
        self._text_blocks_enabled: bool = True

        # режимы содержимого: "main" (основной) / "settings" (панель настроек)
        self._content_mode: str = "main"

        self._init_window_flags()
        self._init_ui()
        self._load_icons()
        self._apply_config()
        self.set_state("idle")

    # ------------------------------------------------------------------ setup

    def _init_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _init_ui(self) -> None:
        # верхняя панель (один набор кнопок для всех режимов)
        self.menu_button = QPushButton("⚙️")
        self.menu_button.setFixedSize(24, 24)
        self.menu_button.clicked.connect(self._on_menu_clicked)

        self.compact_button = QPushButton("▢")
        self.compact_button.setFixedSize(24, 24)
        self.compact_button.clicked.connect(self._on_compact_clicked)

        self.close_button = QPushButton("✖️")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._on_close_clicked)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setSpacing(4)
        top_layout.addWidget(self.menu_button)
        top_layout.addStretch()
        # В обычном режиме: ▢ и ✖️ справа
        top_layout.addWidget(self.compact_button)
        top_layout.addWidget(self.close_button)

        # ---------- основное содержимое (режим "main") ----------
        # верхняя иконка нам не нужна в обычном режиме — используем только для компактного
        self.icon_label = QLabel()
        # В компактном режиме иконка должна быть строго по центру по вертикали и горизонтали.
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setText("🎙️")
        # Без лишних отступов, только размер шрифта.
        self.icon_label.setStyleSheet("font-size: 16pt;")
        self.icon_label.setVisible(False)

        # текст распознанного результата (сырой текст от Whisper)
        self.raw_label = ClickableLabel("")
        self.raw_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.raw_label.setWordWrap(True)
        self.raw_label.setObjectName("textBlock")
        self.raw_label.clicked.connect(lambda: self._copy_text(self.raw_label.text()))

        # текст после постпроцессинга (LLM / regex)
        self.processed_label = ClickableLabel("")
        self.processed_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.processed_label.setWordWrap(True)
        self.processed_label.setObjectName("textBlock")
        self.processed_label.clicked.connect(
            lambda: self._copy_text(self.processed_label.text())
        )

        # для обратной совместимости (старый код использует result_label)
        self.result_label = self.processed_label

        # текст статуса
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_page = QWidget()
        main_layout = QVBoxLayout(main_page)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        main_layout.addLayout(top_layout)
        # В обычном режиме иконка скрыта, в компактном — она по центру.
        main_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Два текста: сверху — сырой, снизу — после постпроцессинга.
        main_layout.addWidget(self.raw_label)
        main_layout.addWidget(self.processed_label)
        main_layout.addWidget(self.status_label)

        # ---------- панель настроек (режим "settings") ----------
        self.settings_backend_combo = QComboBox()
        self.settings_backend_combo.addItem("Groq", userData="groq")
        self.settings_backend_combo.addItem("OpenAI", userData="openai")
        self.settings_backend_combo.addItem("Local (GigaAM)", userData="local")

        self.settings_groq_key = QLineEdit()
        self.settings_groq_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.settings_openai_key = QLineEdit()
        self.settings_openai_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.settings_openai_url = QLineEdit()

        # постпроцессинг
        self.postprocess_enabled_checkbox = QCheckBox("Включить постпроцессинг")
        self.postprocess_enabled_checkbox.setChecked(True)
        # сделать текст чекбокса белым, как у остальных QLabel
        self.postprocess_enabled_checkbox.setStyleSheet("color: white;")

        self.postprocess_groq_model = QLineEdit()
        self.postprocess_openai_model = QLineEdit()

        form = QFormLayout()
        form.addRow("Сервис распознавания:", self.settings_backend_combo)
        form.addRow("Groq API key:", self.settings_groq_key)
        form.addRow("OpenAI API key:", self.settings_openai_key)
        form.addRow("OpenAI Base URL:", self.settings_openai_url)
        form.addRow(self.postprocess_enabled_checkbox)
        form.addRow("Groq postprocess model:", self.postprocess_groq_model)
        form.addRow("OpenAI postprocess model:", self.postprocess_openai_model)

        self.settings_save_button = QPushButton("Сохранить")
        self.settings_save_button.clicked.connect(self._on_settings_save_clicked)

        self.settings_cancel_button = QPushButton("Отмена")
        self.settings_cancel_button.clicked.connect(self._on_settings_cancel_clicked)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.settings_save_button)
        buttons_layout.addWidget(self.settings_cancel_button)

        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(6, 6, 6, 6)
        settings_layout.setSpacing(6)

        # отдельная верхняя панель для настроек (своими кнопками)
        self.settings_menu_button = QPushButton("⚙️")
        self.settings_menu_button.setFixedSize(24, 24)
        self.settings_menu_button.clicked.connect(self._on_menu_clicked)

        self.settings_compact_button = QPushButton("▢")
        self.settings_compact_button.setFixedSize(24, 24)
        self.settings_compact_button.clicked.connect(self._on_compact_clicked)

        self.settings_close_button = QPushButton("✖️")
        self.settings_close_button.setFixedSize(24, 24)
        self.settings_close_button.clicked.connect(self._on_close_clicked)

        settings_top_layout = QHBoxLayout()
        settings_top_layout.setContentsMargins(4, 4, 4, 4)
        settings_top_layout.setSpacing(4)
        settings_top_layout.addWidget(self.settings_menu_button)
        settings_top_layout.addStretch()
        settings_top_layout.addWidget(self.settings_compact_button)
        settings_top_layout.addWidget(self.settings_close_button)

        settings_layout.addLayout(settings_top_layout)
        settings_layout.addLayout(form)
        settings_layout.addLayout(buttons_layout)

        # ---------- стек страниц ----------
        self._stack = QStackedLayout()
        self._stack.addWidget(main_page)      # index 0: main
        self._stack.addWidget(settings_page)  # index 1: settings

        container = QWidget()
        container.setLayout(self._stack)
        container.setObjectName("container")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(container)

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#container {
                background-color: rgba(30, 30, 30, 230);
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 10pt;
            }
            QLabel#textBlock {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 8px 10px;
            }
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                font-size: 11pt;
            }
            QPushButton:hover {
                color: #00bcd4;
            }
            """
        )

    def _load_icons(self) -> None:
        """Иконки из файлов больше не используются — всё на эмодзи."""
        # Оставлено на будущее, если понадобится системная иконка окна.
        return

    def _apply_config(self) -> None:
        w, h = self._ui_config.window_size
        self.resize(w, h)
        self.setWindowOpacity(self._ui_config.opacity)
        if self._ui_config.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    # ------------------------------------------------------------------ state / mode

    def set_state(self, state: str) -> None:
        self._state = state

        # обычный режим: только нижний индикатор
        if state == "idle":
            self.status_label.setText("")
        elif state == "recording":
            self.status_label.setText("🔴")
            self.result_label.setText("")
        elif state == "processing":
            self.status_label.setText("⏳")
        elif state == "ready":
            self.status_label.setText("✅")
            QTimer.singleShot(1000, lambda: self.set_state("idle"))
        elif state == "error":
            self.status_label.setText("⚠️")
        else:
            self.status_label.setText("")

        # компактный режим: одна иконка
        if self._compact:
            if state == "recording":
                self.icon_label.setText("🔴")
            elif state == "processing":
                self.icon_label.setText("⏳")
            elif state == "error":
                self.icon_label.setText("⚠️")
            else:
                self.icon_label.setText("🎙️")

        # управляем отображением текстовых блоков
        self._text_blocks_enabled = state not in {"recording"}
        if state == "recording":
            self.raw_label.setText("")
            self.processed_label.setText("")
        self._refresh_text_block_visibility()

        # применяем текущий режим (compact/normal)
        self._apply_compact_mode()

    def set_compact(self, compact: bool) -> None:
        """Переключение между большим окном и компактным микрофоном."""
        self._compact = compact
        self._apply_compact_mode()

    def _refresh_text_block_visibility(self) -> None:
        should_show = self._text_blocks_enabled and not self._compact
        self.raw_label.setVisible(should_show)
        self.processed_label.setVisible(should_show)

    def _apply_compact_mode(self) -> None:
        """
        Компактный режим.

        Горизонтальная плашка:
        [   🎙️ / 🔴 / ⏳   ]      [ ▢ ]

        - по центру — иконка микрофона/статуса,
        - справа — маленькая кнопка разворота.
        """
        if self._compact:
            # скрываем текст
            self.status_label.setVisible(False)

            # в компактном режиме:
            # - меню и крестик прячем,
            # - оставляем только кнопку compact (▢) как точку возврата.
            self.menu_button.setVisible(False)
            self.close_button.setVisible(False)
            self.compact_button.setVisible(True)

            # в шапке настроек тоже прячем всё, кроме compact
            if hasattr(self, "settings_menu_button"):
                self.settings_menu_button.setVisible(False)
                self.settings_close_button.setVisible(False)
                self.settings_compact_button.setVisible(True)

            # включаем иконку
            self.icon_label.setVisible(True)

            # Компактное окно: невысокая горизонтальная плашка.
            # Высота подобрана так, чтобы иконка и ▢ были на одной линии и не обрезались.
            self.setFixedSize(180, 70)
        else:
            # обычный режим
            self.status_label.setVisible(True)

            self.menu_button.setVisible(True)
            self.close_button.setVisible(True)
            self.compact_button.setVisible(True)

            if hasattr(self, "settings_menu_button"):
                self.settings_menu_button.setVisible(True)
                self.settings_close_button.setVisible(True)
                self.settings_compact_button.setVisible(True)

            # верхняя иконка в обычном режиме не нужна
            self.icon_label.setVisible(False)

            w, h = self._ui_config.window_size
            self.setFixedSize(w, h)

        self._refresh_text_block_visibility()

    def show_message(self, text: str, timeout_ms: int = 2000) -> None:
        self.status_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self.set_state(self._state))

    def _copy_text(self, text: str) -> None:
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText("Скопировано в буфер обмена")
        QTimer.singleShot(1200, lambda: self.set_state(self._state))

    # ------------------------------------------------------------------ text setters

    def set_raw_text(self, text: str) -> None:
        """Показать сырой текст от Whisper (верхний блок)."""
        self.raw_label.setText(text or "")

    def set_processed_text(self, text: str) -> None:
        """Показать текст после постпроцессинга (нижний блок)."""
        self.processed_label.setText(text or "")

    # ------------------------------------------------------------------ settings mode

    def _enter_settings_mode(self) -> None:
        """Показать панель настроек внутри этого же окна.

        ВАЖНО: здесь мы не читаем config.yaml и не трогаем AppSettings.
        Все реальные значения (backend, ключи, модели) заполняет App.open_settings_dialog().
        Эта функция только переключает страницу.
        """
        self._content_mode = "settings"
        self._stack.setCurrentIndex(1)

    def leave_settings_mode(self) -> None:
        """Вернуться в основной режим отображения."""
        self._content_mode = "main"
        self._stack.setCurrentIndex(0)

    def _on_settings_save_clicked(self) -> None:
        """
        Пользователь нажал «Сохранить» в панели настроек.
        Отправляем сигнал наверх (в App), чтобы он:
        - прочитал значения из полей,
        - сохранил их в config.yaml,
        - пересоздал recognizer/postprocessor.
        """
        self.settings_save_requested.emit()
        self.leave_settings_mode()

    def _on_settings_cancel_clicked(self) -> None:
        """Отмена изменений и возврат в основной режим."""
        self.leave_settings_mode()

    # ------------------------------------------------------------------ events

    def _on_menu_clicked(self) -> None:
        """
        Клик по иконке ⚙️.

        Поведение:
        - если сейчас основной режим (main) → открыть настройки (как раньше);
        - если уже открыта панель настроек → свернуть её, как будто нажали «Отмена».
        """
        if self._content_mode == "settings":
            # Поведение как у кнопки «Отмена»
            self._on_settings_cancel_clicked()
            return

        self.settings_requested.emit()

    def _on_compact_clicked(self) -> None:
        # Переключить режим окна
        self.set_compact(not self._compact)
        self.toggle_compact_requested.emit()

    def _on_close_clicked(self) -> None:
        # Кнопка закрытия: сигнал наверх (App решает — выйти или скрыть окно)
        self.exit_requested.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_position is not None:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # двойной клик по окну — тоже открыть настройки
            self._enter_settings_mode()
        super().mouseDoubleClickEvent(event)