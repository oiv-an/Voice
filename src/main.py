import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication

from config.settings import AppSettings
from ui.floating_window import FloatingWindow
from ui.system_tray import SystemTrayIcon
from hotkey.hotkey_manager import HotKeyManager
from audio.recorder import AudioRecorder
from clipboard.clipboard_manager import ClipboardManager
from recognition import create_recognizer
from recognition.postprocessor import TextPostprocessor
from utils.logger import setup_logging


class App:
    """
    Main application class: wires UI, hotkeys, audio recorder, recognizer and clipboard.

    MVP workflow:
        global hotkey (record) down   -> start_recording()
        global hotkey (record) up     -> stop_recording()
        audio -> recognizer (Groq) -> postprocess -> clipboard.copy + paste
    """

    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)

        # Load settings and logging
        self.settings = AppSettings.load_default()
        setup_logging(self.settings.logging)

        # Core components
        self.window = FloatingWindow(self.settings.ui)
        self.tray = SystemTrayIcon(self.window, self.settings.app)
        self.clipboard = ClipboardManager()
        self.audio_recorder = AudioRecorder(self.settings.audio)
        self.recognizer = create_recognizer(self.settings.recognition)

        # Постпроцессинг текста.
        # ВАЖНО: сразу прокидываем в postprocess.* тот же ключ и model_process,
        # что и в recognition.*, чтобы LLM работал уже при первом запуске.
        post_cfg = self.settings.postprocess
        rec_cfg = self.settings.recognition

        if (post_cfg.llm_backend or "").lower() == "groq":
            # один ключ Groq: берём из recognition.groq.api_key
            setattr(post_cfg.groq, "api_key", rec_cfg.groq.api_key)
            # модель LLM: из recognition.groq.model_process
            if not getattr(post_cfg.groq, "model_process", ""):
                setattr(post_cfg.groq, "model_process", rec_cfg.groq.model_process)

        if (post_cfg.llm_backend or "").lower() == "openai":
            setattr(post_cfg.openai, "api_key", rec_cfg.openai.api_key)
            if not getattr(post_cfg.openai, "model_process", ""):
                setattr(post_cfg.openai, "model_process", rec_cfg.openai.model_process)

        self.postprocessor = TextPostprocessor(post_cfg)

        # Первое сообщение: если нет ключа для текущего backend'а — подсказка пользователю
        backend = (self.settings.recognition.backend or "groq").lower()
        missing_key = False
        if backend == "groq" and not (self.settings.recognition.groq.api_key or "").strip():
            missing_key = True
        elif backend == "openai" and not (self.settings.recognition.openai.api_key or "").strip():
            missing_key = True

        if missing_key:
            self.window.result_label.setText(
                "Добавьте API‑ключ в настройках (⚙️) перед использованием распознавания."
            )

        # State
        self._is_recording: bool = False

        # Hotkeys
        self.hotkeys = HotKeyManager(
            record_hotkey=self.settings.hotkeys.record,
            cancel_hotkey=self.settings.hotkeys.cancel,
            toggle_window_hotkey=self.settings.hotkeys.toggle_window,
            toggle_debug_hotkey=self.settings.hotkeys.toggle_debug,
            on_record_press=self.start_recording,
            on_record_release=self.stop_recording,
            on_cancel=self.cancel_recording,
            on_toggle_window=self.toggle_window_visibility,
            on_toggle_debug=self.toggle_debug_mode,
        )

        # Wire UI signals
        self.window.settings_requested.connect(self.open_settings_dialog)
        self.window.settings_save_requested.connect(self._on_settings_save_requested)
        self.window.exit_requested.connect(self.quit)
        self.tray.show_window_requested.connect(self.show_window)
        self.tray.settings_requested.connect(self.open_settings_dialog)
        self.tray.toggle_debug_requested.connect(self.toggle_debug_mode)
        self.tray.exit_requested.connect(self.quit)

    # --------------------------------------------------------------------- UI

    def show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def toggle_window_visibility(self) -> None:
        """
        Горячая клавиша "Показать/скрыть окно".

        Для твоего сценария окно должно быть ВСЕГДА видно, поэтому
        мы больше не будем его прятать, а только:
        - если оно свернуто в компактный режим — разворачивать,
        - если оно где-то "потерялось" — показывать и поднимать наверх.
        """
        # просто гарантируем, что окно показано и на переднем плане
        self.show_window()

    def open_settings_dialog(self) -> None:
        """
        Открыть панель настроек внутри основного окна.

        ВАЖНО: все значения берём/кладём только в config.yaml через AppSettings.
        """
        # показать окно
        self.show_window()

        # заполнить UI текущими значениями из self.settings
        rec = self.settings.recognition
        post = self.settings.postprocess

        # backend
        backend_value = (rec.backend or "groq").lower()
        idx = self.window.settings_backend_combo.findData(backend_value)
        if idx >= 0:
            self.window.settings_backend_combo.setCurrentIndex(idx)

        # API keys / base URL
        self.window.settings_groq_key.setText(rec.groq.api_key or "")
        self.window.settings_openai_key.setText(rec.openai.api_key or "")
        self.window.settings_openai_url.setText(rec.openai.base_url or "")

        # postprocess
        self.window.postprocess_enabled_checkbox.setChecked(post.enabled)

        # Если в конфиге пустые строки, подставляем дефолты,
        # чтобы поля в UI были уже заполнены при первом открытии.
        # По твоему запросу:
        #   - Groq postprocess model:   mixtral-8x7b-32768
        #   - OpenAI postprocess model: gpt-5.1
        groq_model = (post.groq.model or "").strip() or "mixtral-8x7b-32768"
        openai_model = (post.openai.model or "").strip() or "gpt-5.1"

        self.window.postprocess_groq_model.setText(groq_model)
        self.window.postprocess_openai_model.setText(openai_model)

        # переключаем окно в режим настроек
        self.window._enter_settings_mode()

    # ----------------------------------------------------------------- Hotkeys

    def start_recording(self) -> None:
        if self._is_recording:
            return
        self._is_recording = True
        self.window.set_state("recording")

        def on_finished(audio_data):
            # Этот колбэк вызывается из потока рекордера.
            # Для MVP просто передаём данные в обработку синхронно.
            self._process_audio(audio_data)

        self.audio_recorder.start(on_finished=on_finished)

    def stop_recording(self) -> None:
        if not self._is_recording:
            return
        self._is_recording = False
        self.audio_recorder.stop()

    def cancel_recording(self) -> None:
        if not self._is_recording:
            return
        self._is_recording = False
        self.audio_recorder.cancel()
        self.window.set_state("idle")

    # ----------------------------------------------------------- Processing
    
    def _process_audio(self, audio_data) -> None:
        """Synchronous processing for MVP; later can be moved to worker thread."""
        from loguru import logger
        from pathlib import Path
        from datetime import datetime
    
        try:
            self.window.set_state("processing")
            # 1) сырой текст от Whisper
            raw_text = self.recognizer.transcribe(audio_data)
    
            # 2) regex-очистка (базовый препроцессинг всегда)
            from recognition.postprocessor import TextPostprocessor as TP  # локальный импорт для статик-метода
            regex_text = TP._simple_cleanup(raw_text or "")
    
            # 3) LLM-постпроцессинг (если включён в конфиге)
            processed_text = regex_text
            try:
                processed_text = self.postprocessor.process(raw_text or "")
            except RuntimeError as exc:
                # осмысленные ошибки LLM
                logger.error("LLM postprocess error: {}", exc)
                self.window.show_message(str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected LLM postprocess error: {}", exc)
                self.window.show_message("Ошибка LLM-постпроцессинга. См. логи.")
    
            # 4) показать оба варианта в окне
            try:
                # верхний блок — сырой текст от Whisper
                if hasattr(self.window, "set_raw_text"):
                    self.window.set_raw_text(raw_text or "")
                else:
                    # fallback в старый result_label
                    self.window.result_label.setText(processed_text)
    
                # нижний блок — обработанный текст (regex/LLM)
                if hasattr(self.window, "set_processed_text"):
                    self.window.set_processed_text(processed_text)
            except Exception:
                logger.debug("window text update failed", exc_info=True)
    
            # 5) положить ОБРАБОТАННЫЙ текст в буфер обмена
            self.clipboard.copy(processed_text)
    
            # авто-вставка текста через Ctrl+V (с ретраями внутри ClipboardManager)
            self.clipboard.paste()
    
            # 6) сохранить распознавание в отдельный текстовый лог с ротацией по ~3 МБ
            try:
                base_dir = Path(__file__).resolve().parents[2]
                log_dir = base_dir / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                transcript_path = log_dir / "transcripts.log"
    
                # простая ротация: если файл больше 3 МБ — переименовать в transcripts_YYYYmmdd_HHMMSS.log
                max_size_bytes = 3 * 1024 * 1024
                if transcript_path.exists() and transcript_path.stat().st_size >= max_size_bytes:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rotated = log_dir / f"transcripts_{ts}.log"
                    transcript_path.rename(rotated)
    
                # формат записи: время, сырой текст, обработанный текст
                with transcript_path.open("a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\\n"
                        f"RAW: { (raw_text or '').strip() }\\n"
                        f"PROCESSED: { (processed_text or '').strip() }\\n"
                        "----------------------------------------\\n"
                    )
            except Exception as exc:  # noqa: BLE001
                # не ломаем основной флоу, если что-то пошло не так с логом
                logger.exception("Failed to append transcript log: {}", exc)
    
            self.window.set_state("ready")
        except RuntimeError as exc:
            # Осмысленные ошибки от распознавания (например, Groq API)
            logger.error("Processing error: {}", exc)
            self.window.set_state("error")
            # Показываем пользователю человекочитаемое сообщение
            self.window.show_message(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during processing: {}", exc)
            self.window.set_state("error")
            self.window.show_message("Неизвестная ошибка распознавания. См. логи.")

    # -------------------------------------------------------------- Debug

    def toggle_debug_mode(self) -> None:
        # Placeholder: will reconfigure logging level later
        self.window.show_message("Toggle debug (not fully implemented yet).")

    # ----------------------------------------------------------- Settings save

    def _on_settings_save_requested(self) -> None:
        """
        Пользователь нажал «Сохранить» в панели настроек.
        Читаем значения из UI, обновляем self.settings, сохраняем в config.yaml
        и пересоздаём recognizer/postprocessor.
        """
        from config.settings import AppSettings  # локальный импорт, чтобы избежать циклов
    
        rec = self.settings.recognition
        post = self.settings.postprocess
    
        # 1) backend
        backend_data = self.window.settings_backend_combo.currentData()
        if backend_data in ("groq", "openai", "local"):
            rec.backend = backend_data
    
        # 2) API keys / base URL
        rec.groq.api_key = self.window.settings_groq_key.text().strip() or rec.groq.api_key
        rec.openai.api_key = self.window.settings_openai_key.text().strip() or rec.openai.api_key
        base_url = self.window.settings_openai_url.text().strip()
        if base_url:
            rec.openai.base_url = base_url
    
        # 3) postprocess
        post.enabled = self.window.postprocess_enabled_checkbox.isChecked()
    
        # модели LLM: пишем в recognition.*.model_process и синхронизируем postprocess.*.model
        groq_model_proc = self.window.postprocess_groq_model.text().strip()
        if groq_model_proc:
            rec.groq.model_process = groq_model_proc
            post.groq.model = groq_model_proc
    
        openai_model_proc = self.window.postprocess_openai_model.text().strip()
        if openai_model_proc:
            rec.openai.model_process = openai_model_proc
            post.openai.model = openai_model_proc
    
        # 4) сохранить всё в config.yaml
        AppSettings.save_default(self.settings)
    
        # 5) пересоздать recognizer и postprocessor
        self.recognizer = create_recognizer(self.settings.recognition)
    
        post_cfg = self.settings.postprocess
        if (post_cfg.llm_backend or "").lower() == "groq":
            setattr(post_cfg.groq, "api_key", rec.groq.api_key)
            if not getattr(post_cfg.groq, "model_process", ""):
                setattr(post_cfg.groq, "model_process", rec.groq.model_process)
        if (post_cfg.llm_backend or "").lower() == "openai":
            setattr(post_cfg.openai, "api_key", rec.openai.api_key)
            if not getattr(post_cfg.openai, "model_process", ""):
                setattr(post_cfg.openai, "model_process", rec.openai.model_process)
    
        self.postprocessor = TextPostprocessor(post_cfg)
    
        # 6) если теперь ключи заданы — убрать предупреждающую надпись
        backend = (self.settings.recognition.backend or "groq").lower()
        has_key = False
        if backend == "groq" and (self.settings.recognition.groq.api_key or "").strip():
            has_key = True
        elif backend == "openai" and (self.settings.recognition.openai.api_key or "").strip():
            has_key = True
    
        if has_key:
            # очищаем все текстовые блоки, чтобы не висело старое предупреждение
            if hasattr(self.window, "set_raw_text"):
                self.window.set_raw_text("")
            if hasattr(self.window, "set_processed_text"):
                self.window.set_processed_text("")
            self.window.result_label.setText("")
    
        # 7) показать уведомление
        self.window.show_message("Настройки сохранены.", timeout_ms=1500)

    # -------------------------------------------------------------- Lifecycle

    def quit(self) -> None:
        self.hotkeys.stop()
        self.qt_app.quit()

    def run(self) -> None:
        self.hotkeys.start()
        self.show_window()
        sys.exit(self.qt_app.exec())


def main() -> None:
    app = App()
    app.run()


if __name__ == "__main__":
    main()