from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
)

class HistoryItemWidget(QFrame):
    """
    Виджет для одной записи истории.
    Показывает время, сырой текст и обработанный текст.
    """
    copy_requested = pyqtSignal(str)

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.item = item
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            HistoryItemWidget {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            HistoryItemWidget:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header: Timestamp
        header_layout = QHBoxLayout()
        time_label = QLabel(self.item.get("timestamp", ""))
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 9pt;")
        header_layout.addWidget(time_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        # Raw Text (Left)
        raw_container = QWidget()
        raw_layout = QVBoxLayout(raw_container)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.setSpacing(4)
        
        raw_title = QLabel("Исходный:")
        raw_title.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 9pt; font-weight: bold;")
        
        self.raw_text = QLabel(self.item.get("raw_text", ""))
        self.raw_text.setWordWrap(True)
        self.raw_text.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 10pt;")
        self.raw_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        raw_layout.addWidget(raw_title)
        raw_layout.addWidget(self.raw_text)
        raw_layout.addStretch()

        # Processed Text (Right)
        proc_container = QWidget()
        proc_layout = QVBoxLayout(proc_container)
        proc_layout.setContentsMargins(0, 0, 0, 0)
        proc_layout.setSpacing(4)
        
        proc_title = QLabel("Обработанный:")
        proc_title.setStyleSheet("color: #00bcd4; font-size: 9pt; font-weight: bold;")
        
        self.proc_text = QLabel(self.item.get("processed_text", ""))
        self.proc_text.setWordWrap(True)
        self.proc_text.setStyleSheet("color: white; font-size: 10pt; font-weight: bold;")
        self.proc_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        proc_layout.addWidget(proc_title)
        proc_layout.addWidget(self.proc_text)
        proc_layout.addStretch()

        # Add to content layout (50% width each)
        content_layout.addWidget(raw_container, 1)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        content_layout.addWidget(line)
        
        content_layout.addWidget(proc_container, 1)
        
        layout.addLayout(content_layout)

        # Actions
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        copy_raw_btn = QPushButton("Копировать исходный")
        copy_raw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_raw_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255, 255, 255, 0.6);
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        copy_raw_btn.clicked.connect(lambda: self.copy_requested.emit(self.item.get("raw_text", "")))
        
        copy_proc_btn = QPushButton("Копировать результат")
        copy_proc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_proc_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #007bff;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        copy_proc_btn.clicked.connect(lambda: self.copy_requested.emit(self.item.get("processed_text", "")))
        
        actions_layout.addWidget(copy_raw_btn)
        actions_layout.addWidget(copy_proc_btn)
        
        layout.addLayout(actions_layout)


class HistoryDialog(QDialog):
    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.setWindowTitle("История распознаваний")
        self.resize(800, 600)
        self._init_ui()

    def _init_ui(self):
        # Dark theme style
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("История распознаваний")
        title.setStyleSheet("color: white; font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(container)
        self.items_layout.setSpacing(10)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Load items
        self._load_items()

        # Footer
        footer_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Очистить историю")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                color: #ff4d4d;
                background: transparent;
                border: 1px solid #ff4d4d;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: rgba(255, 77, 77, 0.1);
            }
        """)
        clear_btn.clicked.connect(self._clear_history)
        
        close_btn = QPushButton("Закрыть")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #444;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        close_btn.clicked.connect(self.accept)
        
        footer_layout.addWidget(clear_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        
        layout.addLayout(footer_layout)

    def _load_items(self):
        # Clear existing
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = self.history_manager.get_items()
        if not items:
            empty_label = QLabel("История пуста")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 12pt; margin-top: 50px;")
            self.items_layout.addWidget(empty_label)
            return

        for item in items:
            widget = HistoryItemWidget(item)
            widget.copy_requested.connect(self._copy_to_clipboard)
            self.items_layout.addWidget(widget)

    def _copy_to_clipboard(self, text):
        QGuiApplication.clipboard().setText(text)
        # Optional: Show toast or feedback? 
        # For now, just copy.

    def _clear_history(self):
        self.history_manager.clear()
        self._load_items()