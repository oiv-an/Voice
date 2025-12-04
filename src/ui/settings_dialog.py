from __future__ import annotations

from dataclasses import replace
from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import AppSettings, RecognitionConfig, HotkeysConfig


class SettingsDialog(QDialog):
    """
    Окно настроек распознавания и постобработки.

    Блоки:
    - Сервис распознавания (Groq / OpenAI) + ключи / Base URL.
    - Модели распознавания (ASR) для Groq и OpenAI.
    - Постобработка (LLM) + модели Groq/OpenAI для коррекции текста.
    """

    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self._original_settings = settings
        self._result_settings: Optional[AppSettings] = None

        self._init_ui()
        self._load_from_settings(settings)

    # ------------------------------------------------------------------ public API

    def get_result(self) -> Optional[AppSettings]:
        return self._result_settings

    # ------------------------------------------------------------------ UI

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Сделать текст и подписи более контрастными
        self.setStyleSheet(
            """
            QDialog {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QGroupBox {
                color: #f0f0f0;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QLabel {
                color: #f0f0f0;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 2px 4px;
            }
            QLineEdit:disabled {
                background-color: #444444;
                color: #aaaaaa;
            }
            QCheckBox {
                color: #f0f0f0;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 2px 4px;
            }
            QDialogButtonBox QPushButton {
                min-width: 70px;
            }
            """
        )

        # === Блок: сервис распознавания (backend + ключи) ======================
        backend_group = QGroupBox("Сервис распознавания")
        backend_form = QFormLayout(backend_group)

        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Groq", userData="groq")
        self.backend_combo.addItem("OpenAI", userData="openai")
        self.backend_combo.addItem("GigaAM-v3 (local)", userData="local")
        # выбор сервиса распознавания ничего не скрывает, сигнал больше не нужен
        backend_form.addRow("Сервис распознавания:", self.backend_combo)

        self.groq_api_key_edit = QLineEdit()
        self.groq_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        backend_form.addRow("Groq API key:", self.groq_api_key_edit)

        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        backend_form.addRow("OpenAI API key:", self.openai_api_key_edit)

        self.openai_base_url_edit = QLineEdit()
        backend_form.addRow("OpenAI Base URL:", self.openai_base_url_edit)

        layout.addWidget(backend_group)

        # === Блок: Горячие клавиши =============================================
        hotkeys_group = QGroupBox("Горячие клавиши")
        hotkeys_form = QFormLayout(hotkeys_group)

        self.record_hotkey_edit = QLineEdit()
        hotkeys_form.addRow("Запись (основная):", self.record_hotkey_edit)

        self.record_idea_hotkey_edit = QLineEdit()
        hotkeys_form.addRow("Запись идеи:", self.record_idea_hotkey_edit)

        layout.addWidget(hotkeys_group)

        # === Блок: модели распознавания (ASR) ==================================
        asr_group = QGroupBox("Модели распознавания (ASR)")
        asr_form = QFormLayout(asr_group)

        self.groq_asr_model_edit = QLineEdit()
        asr_form.addRow("Groq ASR model:", self.groq_asr_model_edit)

        self.openai_asr_model_edit = QLineEdit()
        asr_form.addRow("OpenAI ASR model:", self.openai_asr_model_edit)

        # Локальный GigaAM-v3 использует фиксированную модель из кода
        # (ai-sage/GigaAM-v3, revision="e2e_rnnt"), поэтому отдельного выбора
        # модели в настройках нет и поле не отображается.
        # self.gigaam_model_edit = QLineEdit()
        # asr_form.addRow("GigaAM-v3 local model:", self.gigaam_model_edit)

        layout.addWidget(asr_group)

        # === Блок: постобработка (LLM) =========================================
        post_group = QGroupBox("Постобработка текста (LLM)")
        post_form = QFormLayout(post_group)

        self.post_enabled_checkbox = QCheckBox("Включить постпроцессинг")
        post_form.addRow(self.post_enabled_checkbox)

        # выбор backend для постпроцессинга (независимо от backend'а распознавания)
        self.post_backend_combo = QComboBox()
        self.post_backend_combo.addItem("Groq", userData="groq")
        self.post_backend_combo.addItem("OpenAI", userData="openai")
        post_form.addRow("Сервис постпроцессинга:", self.post_backend_combo)

        self.groq_llm_model_edit = QLineEdit()
        post_form.addRow("Groq postprocess model:", self.groq_llm_model_edit)

        self.openai_llm_model_edit = QLineEdit()
        post_form.addRow("OpenAI postprocess model:", self.openai_llm_model_edit)

        layout.addWidget(post_group)

        # === Кнопки ============================================================
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

    # ------------------------------------------------------------------ load/save

    def _load_from_settings(self, settings: AppSettings) -> None:
        rec: RecognitionConfig = settings.recognition

        # backend
        backend = (rec.backend or "groq").lower()
        index = self.backend_combo.findData(backend)
        if index == -1:
            index = self.backend_combo.findData("groq")
        if index != -1:
            self.backend_combo.setCurrentIndex(index)

        # ключи / URL
        self.groq_api_key_edit.setText(rec.groq.api_key)
        self.openai_api_key_edit.setText(rec.openai.api_key)
        self.openai_base_url_edit.setText(rec.openai.base_url)

        # Hotkeys
        self.record_hotkey_edit.setText(settings.hotkeys.record)
        self.record_idea_hotkey_edit.setText(settings.hotkeys.record_idea)

        # ASR‑модели
        self.groq_asr_model_edit.setText(rec.groq.model)
        self.openai_asr_model_edit.setText(rec.openai.model)
        # Для локального GigaAM-v3 модель зашита в коде (ai-sage/GigaAM-v3, e2e_rnnt),
        # поэтому в настройках её не редактируем.
        # self.gigaam_model_edit.setText(rec.local.model)

        # LLM‑модели (постпроцессинг)
        self.post_enabled_checkbox.setChecked(settings.postprocess.enabled)

        # backend постпроцессинга (llm_backend)
        llm_backend = (settings.postprocess.llm_backend or "groq").lower()
        idx_llm = (
            self.post_backend_combo.findData(llm_backend)
            if llm_backend in ("groq", "openai")
            else -1
        )
        if idx_llm == -1:
            idx_llm = self.post_backend_combo.findData("groq")
        if idx_llm != -1:
            self.post_backend_combo.setCurrentIndex(idx_llm)

        # Модели LLM берём из recognition.*.model_process — это единственный источник правды.
        self.groq_llm_model_edit.setText(settings.recognition.groq.model_process)
        self.openai_llm_model_edit.setText(settings.recognition.openai.model_process)

        # раньше здесь вызывался _on_backend_changed(), который скрывал поля ключей.
        # теперь все поля всегда видимы, поэтому вызов не нужен.
        # self._on_backend_changed()

    def _build_new_settings(self) -> AppSettings:
        backend_data = self.backend_combo.currentData()
        backend = str(backend_data) if backend_data is not None else "groq"

        old = self._original_settings

        groq_asr_model = self.groq_asr_model_edit.text().strip()
        openai_asr_model = self.openai_asr_model_edit.text().strip()

        groq_llm_model = self.groq_llm_model_edit.text().strip()
        openai_llm_model = self.openai_llm_model_edit.text().strip()

        new_hotkeys = replace(
            old.hotkeys,
            record=self.record_hotkey_edit.text().strip() or old.hotkeys.record,
            record_idea=self.record_idea_hotkey_edit.text().strip() or old.hotkeys.record_idea,
        )

        # Обновляем recognition:
        # - ASR‑модели (model) берём из полей ASR.
        # - LLM‑модели для постпроцессинга:
        #     * Groq: пишем в recognition.groq.model_process
        #     * OpenAI: пишем в recognition.openai.model_process
        new_recognition = RecognitionConfig(
            backend=backend,
            # Локальный GigaAM-v3: модель не настраивается через UI, используем
            # значение из конфига/дефолта, а фактический идентификатор и ревизия
            # заданы в [`GigaAMRecognizer`](src/recognition/gigaam_local.py:25).
            local=replace(
                old.recognition.local,
            ),
            openai=replace(
                old.recognition.openai,
                api_key=self.openai_api_key_edit.text().strip(),
                base_url=self.openai_base_url_edit.text().strip(),
                model=openai_asr_model or old.recognition.openai.model,
                model_process=openai_llm_model or old.recognition.openai.model_process,
            ),
            groq=replace(
                old.recognition.groq,
                api_key=self.groq_api_key_edit.text().strip(),
                model=groq_asr_model or old.recognition.groq.model,
                model_process=groq_llm_model or old.recognition.groq.model_process,
            ),
        )

        # Блок postprocess больше не является источником правды для моделей LLM.
        # Держим его только как "отображение" текущих значений (для обратной совместимости),
        # но в рантайме TextPostprocessor берёт модели из recognition.*.model_process.
        new_postprocess = replace(
            old.postprocess,
            enabled=self.post_enabled_checkbox.isChecked(),
            llm_backend=str(
                self.post_backend_combo.currentData()
                or old.postprocess.llm_backend
                or "groq"
            ),
            groq=replace(
                old.postprocess.groq,
                model=groq_llm_model or old.postprocess.groq.model,
            ),
            openai=replace(
                old.postprocess.openai,
                model=openai_llm_model or old.postprocess.openai.model,
            ),
        )

        return replace(
            old,
            hotkeys=new_hotkeys,
            recognition=new_recognition,
            postprocess=new_postprocess,
        )

    # ------------------------------------------------------------------ slots

    def _on_backend_changed(self) -> None:
        backend_data = self.backend_combo.currentData()
        backend = str(backend_data) if backend_data is not None else "groq"

        is_groq = backend == "groq"
        is_openai = backend == "openai"

        # Groq поля видимы только при Groq backend
        self.groq_api_key_edit.setVisible(is_groq)

        # OpenAI поля видимы только при OpenAI backend
        self.openai_api_key_edit.setVisible(is_openai)
        self.openai_base_url_edit.setVisible(is_openai)

    def _on_accept(self) -> None:
        self._result_settings = self._build_new_settings()
        self.accept()