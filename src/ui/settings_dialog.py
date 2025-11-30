from __future__ import annotations

from dataclasses import replace
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import AppSettings, RecognitionConfig


class SettingsDialog(QDialog):
    """
    Простое окно настроек для выбора backend'а распознавания и ввода ключей/URL.

    Что есть:
    - Выпадающий список backend'ов: Groq / OpenAI.
    - Для Groq: поле API key.
    - Для OpenAI: поля API key и Base URL.
    - Кнопки OK / Cancel.

    Диалог работает поверх текущего AppSettings и возвращает обновлённый
    экземпляр настроек через метод get_result().
    """

    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self._original_settings = settings
        self._result_settings: Optional[AppSettings] = None

        self._init_ui()
        self._load_from_settings(settings)
        # палитру пока не трогаем, чтобы не падать; вернёмся к этому позже

    # ------------------------------------------------------------------ public API

    def get_result(self) -> Optional[AppSettings]:
        """
        Возвращает новый экземпляр AppSettings, если пользователь нажал OK,
        иначе None.
        """
        return self._result_settings

    # ------------------------------------------------------------------ UI

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Backend selection
        backend_layout = QFormLayout()
        self.backend_label = QLabel("Сервис распознавания:")
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Groq", userData="groq")
        self.backend_combo.addItem("OpenAI", userData="openai")
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        backend_layout.addRow(self.backend_label, self.backend_combo)

        layout.addLayout(backend_layout)

        # --- Backend-specific settings
        self.backend_widget = QWidget()
        backend_grid = QGridLayout(self.backend_widget)
        backend_grid.setColumnStretch(1, 1)

        # Groq controls
        self.groq_label = QLabel("Groq API key:")
        self.groq_api_key_edit = QLineEdit()
        self.groq_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        backend_grid.addWidget(self.groq_label, 0, 0)
        backend_grid.addWidget(self.groq_api_key_edit, 0, 1)

        self.groq_model_label = QLabel("Groq model:")
        self.groq_model_edit = QLineEdit()
        backend_grid.addWidget(self.groq_model_label, 1, 0)
        backend_grid.addWidget(self.groq_model_edit, 1, 1)

        # OpenAI controls
        self.openai_key_label = QLabel("OpenAI API key:")
        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.openai_url_label = QLabel("OpenAI Base URL:")
        self.openai_base_url_edit = QLineEdit()

        self.openai_model_label = QLabel("OpenAI model:")
        self.openai_model_edit = QLineEdit()

        backend_grid.addWidget(self.openai_key_label, 2, 0)
        backend_grid.addWidget(self.openai_api_key_edit, 2, 1)
        backend_grid.addWidget(self.openai_url_label, 3, 0)
        backend_grid.addWidget(self.openai_base_url_edit, 3, 1)
        backend_grid.addWidget(self.openai_model_label, 4, 0)
        backend_grid.addWidget(self.openai_model_edit, 4, 1)

        layout.addWidget(self.backend_widget)

        # --- Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.setLayout(layout)
        # Увеличиваем окно настроек
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

    # ------------------------------------------------------------------ load/save

    def _load_from_settings(self, settings: AppSettings) -> None:
        rec: RecognitionConfig = settings.recognition

        # backend
        backend = rec.backend.lower()
        if backend == "groq":
            index = self.backend_combo.findData("groq")
        elif backend == "openai":
            index = self.backend_combo.findData("openai")
        else:
            # по умолчанию groq
            index = self.backend_combo.findData("groq")
        if index != -1:
            self.backend_combo.setCurrentIndex(index)

        # groq
        self.groq_api_key_edit.setText(rec.groq.api_key)
        self.groq_model_edit.setText(rec.groq.model)

        # openai
        self.openai_api_key_edit.setText(rec.openai.api_key)
        self.openai_base_url_edit.setText(rec.openai.base_url)
        self.openai_model_edit.setText(rec.openai.model)

        # применить видимость полей
        self._on_backend_changed()

    def _build_new_settings(self) -> AppSettings:
        """
        Создаёт новый экземпляр AppSettings на основе текущих значений в диалоге.
        """
        backend_data = self.backend_combo.currentData()
        backend = str(backend_data) if backend_data is not None else "groq"

        old = self._original_settings

        # Обновляем recognition-конфиг
        groq_model = self.groq_model_edit.text().strip()
        openai_model = self.openai_model_edit.text().strip()

        new_recognition = RecognitionConfig(
            backend=backend,
            local=old.recognition.local,
            openai=replace(
                old.recognition.openai,
                api_key=self.openai_api_key_edit.text().strip(),
                base_url=self.openai_base_url_edit.text().strip(),
                # если поле пустое — оставляем старую модель
                model=openai_model or old.recognition.openai.model,
            ),
            groq=replace(
                old.recognition.groq,
                api_key=self.groq_api_key_edit.text().strip(),
                # если поле пустое — оставляем старую модель
                model=groq_model or old.recognition.groq.model,
            ),
        )

        new_settings = replace(
            old,
            recognition=new_recognition,
        )
        return new_settings

    # ------------------------------------------------------------------ slots

    def _on_backend_changed(self) -> None:
        """
        Показываем/скрываем поля в зависимости от выбранного backend'а.
        """
        backend_data = self.backend_combo.currentData()
        backend = str(backend_data) if backend_data is not None else "groq"

        is_groq = backend == "groq"
        is_openai = backend == "openai"

        # Groq: API key + model
        self.groq_api_key_edit.setVisible(is_groq)
        self.groq_model_edit.setVisible(is_groq)
        self.groq_label.setVisible(is_groq)
        self.groq_model_label.setVisible(is_groq)

        # OpenAI: API key + Base URL + model
        self.openai_api_key_edit.setVisible(is_openai)
        self.openai_base_url_edit.setVisible(is_openai)
        self.openai_key_label.setVisible(is_openai)
        self.openai_url_label.setVisible(is_openai)
        self.openai_model_edit.setVisible(is_openai)
        self.openai_model_label.setVisible(is_openai)

    def _on_accept(self) -> None:
        self._result_settings = self._build_new_settings()
        self.accept()