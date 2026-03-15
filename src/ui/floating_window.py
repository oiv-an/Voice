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
    QScrollArea,
    QFrame,
    QSizeGrip,
    QMenu,
)

from PyQt6.QtGui import QMouseEvent, QGuiApplication, QAction
from config.settings import UIConfig
from ui.animated_icons import RecordingIcon, ProcessingIcon, ReadyIcon


class IdeaItemWidget(QWidget):
    """
    Виджет для одной идеи в списке.
    Поддерживает зачеркивание по клику и удаление через 5 секунд.
    """
    
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self._is_done = False
        self._delete_timer = QTimer()
        self._delete_timer.setSingleShot(True)
        self._delete_timer.timeout.connect(self._perform_delete)
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        
        # Применяем стиль, аналогичный textBlock
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            IdeaItemWidget {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
            }
        """)
        
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: white; font-size: 10pt; background: transparent; border: none;")
        
        layout.addWidget(self.label)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_done()
            
    def _toggle_done(self):
        self._is_done = not self._is_done
        
        if self._is_done:
            # Зачеркиваем
            font = self.label.font()
            font.setStrikeOut(True)
            self.label.setFont(font)
            # Меняем стиль всего виджета, чтобы было видно, что он "выполнен"
            self.setStyleSheet("""
                IdeaItemWidget {
                    background-color: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 8px;
                }
            """)
            self.label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10pt; background: transparent; border: none;")
            
            # Запускаем таймер удаления
            self._delete_timer.start(5000)
        else:
            # Убираем зачеркивание
            font = self.label.font()
            font.setStrikeOut(False)
            self.label.setFont(font)
            # Возвращаем обычный стиль
            self.setStyleSheet("""
                IdeaItemWidget {
                    background-color: rgba(255, 255, 255, 0.08);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                }
            """)
            self.label.setStyleSheet("color: white; font-size: 10pt; background: transparent; border: none;")
            
            # Останавливаем таймер
            self._delete_timer.stop()
            
    def _perform_delete(self):
        # Удаляем виджет из родительского layout и уничтожаем
        if self.parent():
            self.setParent(None)
            self.deleteLater()


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
    retry_requested = pyqtSignal()

    def __init__(self, ui_config: UIConfig, history_manager=None) -> None:
        super().__init__()

        self._ui_config = ui_config
        self.history_manager = history_manager
        self._drag_position: Optional[QPoint] = None
        self._state: str = "idle"
        self._compact: bool = False
        self._text_blocks_enabled: bool = True
        self._postprocess_enabled: bool = True

        # режимы содержимого: "main" (основной) / "settings" (панель настроек)
        self._content_mode: str = "main"

        self._init_window_flags()
        self._init_ui()
        self._load_icons()
        self._apply_config()
        self.set_state("idle")

    # ------------------------------------------------------------------ setup

    def _init_window_flags(self) -> None:
        # Убираем Qt.WindowType.Tool, чтобы окно отображалось в панели задач (taskbar).
        # Добавляем Qt.WindowType.Window, чтобы это было полноценное окно.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _init_ui(self) -> None:
        # --- Создаём все виджеты один раз ---
        self._create_controls()

        # --- Страница для обычного режима ---
        self.normal_page = QWidget()
        normal_layout = QVBoxLayout(self.normal_page)
        normal_layout.setContentsMargins(6, 6, 6, 6)
        normal_layout.setSpacing(6)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setSpacing(4)
        top_layout.addWidget(self.menu_button)
        top_layout.addWidget(self.history_button)
        top_layout.addStretch()
        top_layout.addWidget(self.compact_button_normal)
        top_layout.addWidget(self.close_button)

        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)
        status_layout.addWidget(self.icons_container)
        status_layout.addWidget(self.status_text_label)
        status_layout.addStretch()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        normal_layout.addLayout(top_layout)
        normal_layout.addWidget(status_container, alignment=Qt.AlignmentFlag.AlignCenter)
        normal_layout.addWidget(self.retry_button, alignment=Qt.AlignmentFlag.AlignCenter)
        normal_layout.addWidget(self.raw_label)
        normal_layout.addWidget(self.processed_label)
        
        # Добавляем список идей в layout
        normal_layout.addWidget(self.ideas_scroll)
        normal_layout.addWidget(self.clear_ideas_button, alignment=Qt.AlignmentFlag.AlignRight)
        normal_layout.addWidget(self.webhook_status_label)

        # --- Страница для компактного режима ---
        self.compact_page = QWidget()
        compact_layout = QHBoxLayout(self.compact_page)
        compact_layout.setContentsMargins(4, 4, 4, 4)
        compact_layout.setSpacing(10)
        compact_layout.addWidget(self.icons_container_compact)
        compact_layout.addWidget(self.status_text_label_compact)
        compact_layout.addStretch()
        compact_layout.addWidget(self.compact_button_compact)

        # --- Основной стек и контейнер ---
        self._stack = QStackedLayout()
        self._stack.addWidget(self.normal_page)
        self._stack.addWidget(self.compact_page)

        container = QWidget()
        container.setLayout(self._stack)
        container.setObjectName("container")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(container)

        self._apply_styles()

        # Добавляем уголок для изменения размера
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(20, 20)
        # Скрываем в начале, пока не определится режим (хотя по дефолту normal, но лучше явно управлять)
        
    def resizeEvent(self, event):
        # Позиционируем уголок в правом нижнем углу
        if hasattr(self, "size_grip"):
            rect = self.rect()
            self.size_grip.move(
                rect.right() - self.size_grip.width(),
                rect.bottom() - self.size_grip.height()
            )
        
        # Сохраняем размер в конфиг, если мы не в компактном режиме
        if not self._compact and hasattr(self, "_ui_config"):
            new_size = event.size()
            self._ui_config.window_size = (new_size.width(), new_size.height())
            self.settings_save_requested.emit()
            
        super().resizeEvent(event)

    def _create_controls(self) -> None:
        """Создаёт все управляющие элементы, чтобы избежать дублирования."""
        # --- Кнопки ---
        self.menu_button = QPushButton("⚙️")
        self.menu_button.setFixedSize(24, 24)
        self.menu_button.clicked.connect(self._on_menu_clicked)

        self.history_button = QPushButton("🕒")
        self.history_button.setFixedSize(24, 24)
        self.history_button.clicked.connect(self._on_history_clicked)

        self.close_button = QPushButton("✖️")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._on_close_clicked)

        # Две кнопки компактного режима для разных страниц
        self.compact_button_normal = QPushButton("—")
        self.compact_button_normal.setFixedSize(24, 24)
        self.compact_button_normal.clicked.connect(self._on_compact_clicked)
        self.compact_button_normal.setStyleSheet("font-weight: bold; font-size: 14pt;")

        self.compact_button_compact = QPushButton("—")
        self.compact_button_compact.setFixedSize(24, 24)
        self.compact_button_compact.clicked.connect(self._on_compact_clicked)
        self.compact_button_compact.setStyleSheet("font-weight: bold; font-size: 14pt;")

        self.retry_button = QPushButton("Попробуйте еще раз")
        self.retry_button.clicked.connect(self._on_retry_clicked)
        self.retry_button.setObjectName("retryButton")
        self.retry_button.hide()

        # --- Иконки состояний ---
        self.icons_stack = QStackedLayout()
        self.icon_idle = QLabel("🎙️")
        self.icon_idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_idle.setStyleSheet("font-size: 24pt; color: rgba(255, 255, 255, 0.5);")
        self.icon_recording = RecordingIcon()
        self.icon_processing = ProcessingIcon()
        self.icon_ready = ReadyIcon()
        self.icon_error = QLabel("⚠️")
        self.icon_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_error.setStyleSheet("font-size: 24pt; color: #FF9500;")

        for icon in [self.icon_idle, self.icon_recording, self.icon_processing, self.icon_ready, self.icon_error]:
            self.icons_stack.addWidget(icon)

        self.icons_container = QWidget()
        self.icons_container.setLayout(self.icons_stack)
        self.icons_container.setFixedSize(40, 40)

        # Клонируем стек иконок для компактного режима
        self.icons_stack_compact = QStackedLayout()
        for i in range(self.icons_stack.count()):
            # Мы не можем использовать те же виджеты, поэтому создаём их заново или клонируем.
            # В данном случае, QLabel и кастомные виджеты можно создать заново.
            # Это упрощение; в сложном случае потребовалось бы более аккуратное клонирование.
            widget = self.icons_stack.widget(i)
            if isinstance(widget, QLabel):
                new_label = QLabel(widget.text())
                new_label.setAlignment(widget.alignment())
                new_label.setStyleSheet(widget.styleSheet())
                self.icons_stack_compact.addWidget(new_label)
            elif isinstance(widget, RecordingIcon):
                self.icons_stack_compact.addWidget(RecordingIcon())
            elif isinstance(widget, ProcessingIcon):
                self.icons_stack_compact.addWidget(ProcessingIcon())
            elif isinstance(widget, ReadyIcon):
                self.icons_stack_compact.addWidget(ReadyIcon())

        self.icons_container_compact = QWidget()
        self.icons_container_compact.setLayout(self.icons_stack_compact)
        self.icons_container_compact.setFixedSize(40, 40)

        # --- Текстовые поля ---
        self.raw_label = ClickableLabel("")
        self.raw_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.raw_label.setWordWrap(True)
        self.raw_label.setObjectName("textBlock")
        self.raw_label.clicked.connect(lambda: self._copy_text(self.raw_label.text()))

        self.processed_label = ClickableLabel("")
        self.processed_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.processed_label.setWordWrap(True)
        self.processed_label.setObjectName("textBlock")
        self.processed_label.clicked.connect(lambda: self._copy_text(self.processed_label.text()))
        self.result_label = self.processed_label

        # --- Список идей ---
        self.ideas_container = QWidget()
        self.ideas_layout = QVBoxLayout(self.ideas_container)
        self.ideas_layout.setContentsMargins(0, 0, 0, 0)
        self.ideas_layout.setSpacing(4)
        self.ideas_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.ideas_scroll = QScrollArea()
        self.ideas_scroll.setWidgetResizable(True)
        self.ideas_scroll.setWidget(self.ideas_container)
        self.ideas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ideas_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#ideas_container {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 4px;
                background: rgba(0,0,0,0.1);
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.3);
                border-radius: 2px;
            }
        """)
        # Важно: делаем фон контейнера прозрачным
        self.ideas_container.setObjectName("ideas_container")
        self.ideas_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.ideas_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Скрываем по умолчанию, пока нет идей
        self.ideas_scroll.hide()
        self.ideas_scroll.setMaximumHeight(150) # Ограничиваем высоту списка

        self.clear_ideas_button = QPushButton("Очистить список")
        self.clear_ideas_button.setStyleSheet("""
            QPushButton {
                color: rgba(255, 255, 255, 0.6);
                font-size: 9pt;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                color: white;
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.clear_ideas_button.clicked.connect(self._clear_all_ideas)
        self.clear_ideas_button.hide()

        # --- Статус отправки на webhook ---
        self.webhook_status_label = QLabel("")
        self.webhook_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.webhook_status_label.setWordWrap(True)
        self.webhook_status_label.setStyleSheet(
            "color: rgba(100, 255, 100, 0.9); font-size: 10pt; background: transparent; border: none; padding: 4px 8px;"
        )
        self.webhook_status_label.hide()

        # Флаг: webhook mode (скрывает список идей, показывает статус)
        self._webhook_mode: bool = False

        self.status_text_label = QLabel("")
        self.status_text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_text_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 11pt; font-weight: bold;")

        self.status_text_label_compact = QLabel("")
        self.status_text_label_compact.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_text_label_compact.setStyleSheet(self.status_text_label.styleSheet())

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
           QPushButton#retryButton {
               background-color: #007bff;
               color: white;
               border: none;
               border-radius: 5px;
               padding: 8px 12px;
               font-size: 10pt;
               font-weight: bold;
           }
           QPushButton#retryButton:hover {
               background-color: #0056b3;
           }
            """
        )

    def _load_icons(self) -> None:
        """Устанавливает иконку окна, которая будет видна в панели задач."""
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
        
        # Генерируем программную иконку (синий круг), такую же как в трее
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#007bff"))
        painter.setPen(QColor("white"))
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()
        
        self.setWindowIcon(QIcon(pixmap))

    def _apply_config(self) -> None:
        w, h = self._ui_config.window_size
        self.resize(w, h)
        self.setWindowOpacity(self._ui_config.opacity)
        if self._ui_config.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    # ------------------------------------------------------------------ state / mode

    def set_state(self, state: str) -> None:
        self._state = state

        # Обновляем оба стека иконок и текстовые метки
        state_map = {
            "idle": (self.icon_idle, ""),
            "recording": (self.icon_recording, "Запись..."),
            "processing": (self.icon_processing, "Обработка..."),
            "ready": (self.icon_ready, "Готово"),
            "error": (self.icon_error, "Ошибка"),
        }
        
        target_icon, status_text = state_map.get(state, (self.icon_idle, ""))

        # Находим индекс целевой иконки в основном стеке
        target_index = self.icons_stack.indexOf(target_icon)
        if target_index != -1:
            self.icons_stack.setCurrentIndex(target_index)
            # Синхронизируем компактный стек
            if self.icons_stack_compact.count() > target_index:
                self.icons_stack_compact.setCurrentIndex(target_index)

        self.status_text_label.setText(status_text)
        self.status_text_label_compact.setText(status_text)

        if state == "ready":
            QTimer.singleShot(1000, lambda: self.set_state("idle"))
        
        if state != "error":
            self.hide_retry_button()

        # управляем отображением текстовых блоков
        self._text_blocks_enabled = state not in {"recording"}
        if state == "recording":
            self.raw_label.setText("")
            self.processed_label.setText("")
        self._refresh_text_block_visibility()

        # Если мы в компактном режиме, нужно обновить размер, т.к. текст мог измениться
        if self._compact:
            self.adjustSize()

    def set_compact(self, compact: bool) -> None:
        """Переключение между большим окном и компактным микрофоном."""
        if self._compact == compact:
            return
        self._compact = compact
        self._apply_compact_mode()
        self.toggle_compact_requested.emit()

    def set_postprocess_enabled(self, enabled: bool) -> None:
        """Включить/выключить отображение поля постпроцессинга."""
        self._postprocess_enabled = enabled
        
        # Переключаем лейбл, куда будут падать системные сообщения (например, про API key)
        if enabled:
            self.result_label = self.processed_label
        else:
            self.result_label = self.raw_label
            
        self._refresh_text_block_visibility()

    def _refresh_text_block_visibility(self) -> None:
        # Теперь видимость зависит от состояния и флага постпроцессинга
        should_show_raw = self._text_blocks_enabled
        should_show_processed = self._text_blocks_enabled and self._postprocess_enabled
        
        self.raw_label.setVisible(should_show_raw)
        self.processed_label.setVisible(should_show_processed)

    def _apply_compact_mode(self) -> None:
        if self._compact:
            self._stack.setCurrentWidget(self.compact_page)
            # Задаём жёсткий размер для компактного режима, чтобы он не "прыгал".
            self.setFixedSize(220, 48)
            if hasattr(self, "size_grip"):
                self.size_grip.hide()
        else:
            self._stack.setCurrentWidget(self.normal_page)
            self._refresh_text_block_visibility()
            
            # Восстанавливаем исходный размер с отсрочкой.
            # Сначала снимаем ограничения, чтобы окно могло свободно расшириться.
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            w, h = self._ui_config.window_size
            # Используем resize вместо setFixedSize, чтобы можно было менять размер
            QTimer.singleShot(0, lambda: self.resize(w, h))
            
            if hasattr(self, "size_grip"):
                self.size_grip.show()

    def show_message(self, text: str, timeout_ms: int = 2000) -> None:
        self.status_text_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self.set_state(self._state))

    def _copy_text(self, text: str) -> None:
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.status_text_label.setText("Скопировано в буфер обмена")
        QTimer.singleShot(1200, lambda: self.set_state(self._state))

    def show_retry_button(self) -> None:
        """Показывает кнопку повторной попытки."""
        self.retry_button.show()

    def hide_retry_button(self) -> None:
        """Скрывает кнопку повторной попытки."""
        self.retry_button.hide()

    # ------------------------------------------------------------------ text setters

    def set_raw_text(self, text: str) -> None:
        """Показать сырой текст от Whisper (верхний блок)."""
        self.raw_label.setText(text or "")

    def set_processed_text(self, text: str) -> None:
        """Показать текст после постпроцессинга (нижний блок)."""
        self.processed_label.setText(text or "")

    def add_idea(self, text: str) -> None:
        """Добавить новую идею в список. Если webhook mode — ничего не добавляем."""
        if self._webhook_mode:
            return
        if not text.strip():
            return
            
        item = IdeaItemWidget(text)
        self.ideas_layout.addWidget(item)
        
        self.ideas_scroll.show()
        self.clear_ideas_button.show()
        
        # Прокручиваем вниз
        QTimer.singleShot(100, lambda: self.ideas_scroll.verticalScrollBar().setValue(
            self.ideas_scroll.verticalScrollBar().maximum()
        ))

    def show_idea_recording_status(self, webhook_mode: bool = False) -> None:
        """Показать статус записи идеи (или webhook-записи)."""
        if webhook_mode:
            self.status_text_label.setText("Запись → N8N Webhook...")
            self.status_text_label_compact.setText("Запись → N8N...")
        else:
            self.status_text_label.setText("Запись идеи...")
            self.status_text_label_compact.setText("Запись идеи...")

    def set_webhook_mode(self, enabled: bool) -> None:
        """Включить/выключить режим webhook (скрывает список идей)."""
        self._webhook_mode = enabled
        if enabled:
            self.ideas_scroll.hide()
            self.clear_ideas_button.hide()
        self.webhook_status_label.hide()

    def show_webhook_status(self, success: bool) -> None:
        """Показать статус отправки на webhook."""
        if success:
            self.webhook_status_label.setText("✅ Отправлено на N8N Webhook")
            self.webhook_status_label.setStyleSheet(
                "color: rgba(100, 255, 100, 0.9); font-size: 10pt; background: transparent; border: none; padding: 4px 8px;"
            )
        else:
            self.webhook_status_label.setText("❌ Ошибка отправки на N8N Webhook")
            self.webhook_status_label.setStyleSheet(
                "color: rgba(255, 100, 100, 0.9); font-size: 10pt; background: transparent; border: none; padding: 4px 8px;"
            )
        self.webhook_status_label.show()
        # Скрываем через 5 секунд
        QTimer.singleShot(5000, self.webhook_status_label.hide)

    def _clear_all_ideas(self) -> None:
        """Очистить весь список идей."""
        while self.ideas_layout.count():
            item = self.ideas_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.ideas_scroll.hide()
        self.clear_ideas_button.hide()

    # ------------------------------------------------------------------ events

    def _on_menu_clicked(self) -> None:
        """
        Клик по иконке ⚙️.

        Поведение:
        - всегда просим верхний уровень (App) открыть диалог настроек.
        """
        self.settings_requested.emit()

    def _on_history_clicked(self) -> None:
        """Показать диалог истории."""
        if not self.history_manager:
            return

        from ui.history_dialog import HistoryDialog
        
        # Показываем основное окно, чтобы диалог был поверх
        self.show()
        self.raise_()
        
        dlg = HistoryDialog(self.history_manager, parent=self)
        dlg.exec()

    def _on_compact_clicked(self) -> None:
        # Переключить режим окна
        self.set_compact(not self._compact)

    def _on_close_clicked(self) -> None:
        # Кнопка закрытия: сигнал наверх (App решает — выйти или скрыть окно)
        self.exit_requested.emit()

    def _on_retry_clicked(self) -> None:
        """Клик по кнопке "Попробуйте еще раз"."""
        self.hide_retry_button()
        self.retry_requested.emit()

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
            # двойной клик по окну — тоже запросить открытие настроек
            self.settings_requested.emit()
        super().mouseDoubleClickEvent(event)