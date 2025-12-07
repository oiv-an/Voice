import sys
import time
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
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
from utils.recovery import RecoveryManager
from utils.audio_processing import speed_up_audio


class App(QObject):
    # Сигналы для безопасного обновления UI из других потоков
    state_changed = pyqtSignal(str)
    message_shown = pyqtSignal(str, int)
    text_updated = pyqtSignal(str, str)
    idea_added = pyqtSignal(str)

    """
    Main application class: wires UI, hotkeys, audio recorder, recognizer and clipboard.

    MVP workflow:
        global hotkey (record) down   -> start_recording()
        global hotkey (record) up     -> stop_recording()
        audio -> recognizer (Groq/OpenAI) -> postprocess -> clipboard.copy + paste
    """

    def __init__(self) -> None:
        super().__init__()
        self.qt_app = QApplication(sys.argv)

        # Определяем базовую директорию приложения:
        # - в dev-режиме: корень проекта (родитель src)
        # - в собранном .exe: папка, где лежит exe
        if getattr(sys, "frozen", False):
            # PyInstaller / frozen
            self.base_dir = Path(sys.executable).resolve().parent
        else:
            # Обычный запуск из исходников
            self.base_dir = Path(__file__).resolve().parents[1]

        # Load settings and logging (с учётом base_dir и config.local.yaml)
        self.settings = self._load_or_init_settings()
        setup_logging(self.settings.logging)
        
        # Recovery manager
        self.recovery_manager = RecoveryManager(self.base_dir)

        # Core components
        self.window = FloatingWindow(self.settings.ui)
        self.tray = SystemTrayIcon(self.window, self.settings.app)
        self.clipboard = ClipboardManager()
        self.audio_recorder = AudioRecorder(self.settings.audio)
        # Основной распознаватель для текущего backend'а
        self.recognizer = create_recognizer(self.settings.recognition)
        # Кэш распознавателей по backend'ам
        self._recognizers = {}
        primary_backend = (self.settings.recognition.backend or "groq").lower()
        self._recognizers[primary_backend] = self.recognizer

        # Постпроцессинг текста.
        # ВАЖНО: сразу прокидываем в postprocess.* тот же ключ, model_process и base_url,
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
            # ключ для LLM всегда берём из поля OpenAI API key (recognition.openai.api_key)
            setattr(post_cfg.openai, "api_key", rec_cfg.openai.api_key)
            # модель LLM
            if not getattr(post_cfg.openai, "model_process", ""):
                setattr(post_cfg.openai, "model_process", rec_cfg.openai.model_process)
            # базовый URL LLM = тот же, что и у ASR
            setattr(post_cfg.openai, "base_url", rec_cfg.openai.base_url)

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
        self._is_idea: bool = False # True, if the current recording is an idea
        self._last_audio_data: Optional[any] = None
        self._processing_lock = threading.Lock()

        # Hotkeys
        self.hotkeys = HotKeyManager(
            record_hotkey=self.settings.hotkeys.record,
            record_idea_hotkey=self.settings.hotkeys.record_idea,
            cancel_hotkey=self.settings.hotkeys.cancel,
            toggle_window_hotkey=self.settings.hotkeys.toggle_window,
            toggle_debug_hotkey=self.settings.hotkeys.toggle_debug,
            on_record_press=self.start_recording,
            on_record_release=self.stop_recording,
            on_record_idea_press=self.start_idea_recording,
            on_record_idea_release=self.stop_recording, # Stop is the same for both
            on_convert_to_idea=self.convert_to_idea,
            on_cancel=self.cancel_recording,
            on_toggle_window=self.toggle_window_visibility,
            on_toggle_debug=self.toggle_debug_mode,
        )

        # Wire UI signals
        self.window.settings_requested.connect(self.open_settings_dialog)
        self.window.exit_requested.connect(self.quit)
        self.window.retry_requested.connect(self._retry_processing)
        self.tray.show_window_requested.connect(self.show_window)
        self.tray.settings_requested.connect(self.open_settings_dialog)
        self.tray.toggle_debug_requested.connect(self.toggle_debug_mode)
        self.tray.exit_requested.connect(self.quit)

        # Подключаем сигналы к слотам окна
        self.state_changed.connect(self.window.set_state)
        self.message_shown.connect(self.window.show_message)
        self.text_updated.connect(self._on_text_updated)
        self.idea_added.connect(self.window.add_idea)

        # Check for recovery files on startup
        self._check_recovery_files()

    # --------------------------------------------------------------------- UI

    def _on_text_updated(self, raw_text: str, processed_text: str) -> None:
        """Слот для обновления текстовых полей в окне."""
        if hasattr(self.window, "set_raw_text"):
            self.window.set_raw_text(raw_text or "")
        else:
            # fallback для старых версий окна
            self.window.result_label.setText(processed_text or "")

        if hasattr(self.window, "set_processed_text"):
            self.window.set_processed_text(processed_text or "")

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
        Открыть диалог настроек (SettingsDialog) и применить изменения.
        """
        from ui.settings_dialog import SettingsDialog  # локальный импорт, чтобы избежать циклов

        # показать основное окно, чтобы диалог был поверх
        self.show_window()

        dlg = SettingsDialog(self.settings, parent=self.window)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        new_settings = dlg.get_result()
        if new_settings is None:
            return

        # обновляем настройки в памяти
        self.settings = new_settings
        
        # сохраняем в config.yaml
        AppSettings.save_default(self.settings)
        
        # пересоздаём recognizer и postprocessor с учётом новых настроек
        # и сбрасываем кэш распознавателей по backend'ам.
        self._recognizers = {}
        self.recognizer = create_recognizer(self.settings.recognition)
        primary_backend = (self.settings.recognition.backend or "groq").lower()
        self._recognizers[primary_backend] = self.recognizer
        
        post_cfg = self.settings.postprocess
        rec_cfg = self.settings.recognition

        if (post_cfg.llm_backend or "").lower() == "groq":
            setattr(post_cfg.groq, "api_key", rec_cfg.groq.api_key)
            if not getattr(post_cfg.groq, "model_process", ""):
                setattr(post_cfg.groq, "model_process", rec_cfg.groq.model_process)

        if (post_cfg.llm_backend or "").lower() == "openai":
            setattr(post_cfg.openai, "api_key", rec_cfg.openai.api_key)
            if not getattr(post_cfg.openai, "model_process", ""):
                setattr(post_cfg.openai, "model_process", rec_cfg.openai.model_process)
            # базовый URL LLM = тот же, что и у ASR
            setattr(post_cfg.openai, "base_url", rec_cfg.openai.base_url)

        self.postprocessor = TextPostprocessor(post_cfg)

        # если теперь ключи заданы — убрать предупреждающую надпись
        backend = (self.settings.recognition.backend or "groq").lower()
        has_key = False
        if backend == "groq" and (self.settings.recognition.groq.api_key or "").strip():
            has_key = True
        elif backend == "openai" and (self.settings.recognition.openai.api_key or "").strip():
            has_key = True

        if has_key:
            if hasattr(self.window, "set_raw_text"):
                self.window.set_raw_text("")
            if hasattr(self.window, "set_processed_text"):
                self.window.set_processed_text("")
            self.window.result_label.setText("")

        self.window.show_message("Настройки сохранены.", timeout_ms=1500)

    # ----------------------------------------------------------------- Hotkeys

    def _retry_processing(self) -> None:
        """Запускает повторную обработку последнего записанного аудио."""
        from loguru import logger

        if self._last_audio_data:
            logger.info("Retrying processing for the last audio data.")
            # Запускаем в новом потоке, чтобы не блокировать UI
            thread = threading.Thread(target=self._process_audio, args=(self._last_audio_data, None))
            thread.start()
        else:
            logger.warning("Retry requested, but no audio data is available.")
            self.state_changed.emit("idle")

    def start_recording(self, is_idea: bool = False) -> None:
        if self._is_recording:
            return
        self._is_recording = True
        self._is_idea = is_idea
        
        self._last_audio_data = None
        self.window.hide_retry_button()
        self.window.set_state("recording")

        def on_finished(audio_data):
            # Speed up audio x2 before processing/saving
            # This reduces duration and file size, but increases pitch.
            processed_audio = speed_up_audio(audio_data, factor=2.0)

            # Save audio to disk for recovery
            try:
                recovery_path = self.recovery_manager.save_audio(processed_audio)
            except Exception:
                # If saving fails, we still try to process in-memory
                recovery_path = None

            # The final `is_idea` flag is checked inside _process_audio
            thread = threading.Thread(target=self._process_audio, args=(processed_audio, recovery_path))
            thread.start()

        self.audio_recorder.start(on_finished=on_finished)

    def stop_recording(self) -> None:
        if not self._is_recording:
            return
        # We don't reset flags here, _process_audio will do it
        self.audio_recorder.stop()

    def start_idea_recording(self) -> None:
        """Starts a recording that is immediately flagged as an idea."""
        self.start_recording(is_idea=True)

    def convert_to_idea(self) -> None:
        """If a recording is in progress, flag it as an idea."""
        if self._is_recording:
            self._is_idea = True
            # Optionally, provide some visual feedback
            self.message_shown.emit("Запись будет добавлена в идеи", 1000)

    def cancel_recording(self) -> None:
        if self._is_recording:
            self._is_recording = False
            self._is_idea = False
            self.audio_recorder.cancel()
            self.window.set_state("idle")

    # ----------------------------------------------------------- Processing

    def _get_or_create_recognizer(self, backend: str):
        from dataclasses import replace  # локальный импорт, чтобы избежать циклов

        backend = (backend or "groq").lower()
        cache = getattr(self, "_recognizers", None)
        if cache is None:
            cache = {}
            self._recognizers = cache
            primary = (self.settings.recognition.backend or "groq").lower()
            cache[primary] = self.recognizer

        if backend in cache:
            return cache[backend]

        rec_cfg = self.settings.recognition
        tmp_cfg = replace(rec_cfg, backend=backend)
        recognizer = create_recognizer(tmp_cfg)
        cache[backend] = recognizer
        return recognizer
    
    # ----------------------------------------------------------- Processing
    
    def _process_audio(self, audio_data, recovery_path: Optional[Path] = None) -> None:
        """
        Синхронная обработка аудио.
        Флаг self._is_idea определяет, нужно ли добавлять результат в список идей.
        """
        from loguru import logger
        from pathlib import Path
        from datetime import datetime
        from recognition.postprocessor import TextPostprocessor as TP

        if not self._processing_lock.acquire(blocking=False):
            logger.warning("Processing is already in progress. Skipping new request.")
            return

        try:
            # Reset recording state immediately after starting processing
            self._is_recording = False
            is_idea_flag = self._is_idea
            self._is_idea = False # Reset for the next recording

            self._last_audio_data = audio_data
            self.state_changed.emit("processing")

            # ------------------------ вычисляем длительность аудио -----------------
            try:
                import numpy as _np
                samples = audio_data.samples
                sample_rate = getattr(audio_data, "sample_rate", 16000)
                total_samples = samples.shape[0]
                audio_duration_sec = float(total_samples) / float(sample_rate)
            except Exception as exc:
                logger.exception("Failed to compute audio duration: {}", exc)
                audio_duration_sec = -1.0

            # ------------------------ каскад backend'ов с ретраями ----------------
            primary = (self.settings.recognition.backend or "groq").lower()
            all_backends = ["groq", "openai"]
            cascade = [b for b in [primary] + all_backends if b in all_backends]
            seen = set()
            ordered_backends = [b for b in cascade if not (b in seen or seen.add(b))]

            MAX_ATTEMPTS = 5
            RETRY_DELAY_SEC = 2
            BACKEND_SWITCH_DELAY_SEC = 1

            last_error: str | None = None
            raw_text: str | None = None
            used_backend: str | None = None

            for attempt in range(MAX_ATTEMPTS):
                logger.info(f"Recognition attempt #{attempt + 1}/{MAX_ATTEMPTS}")
                for backend in ordered_backends:
                    try:
                        logger.info("Trying recognition backend: {}", backend)
                        recognizer = self._get_or_create_recognizer(backend)
                        raw_text = recognizer.transcribe(audio_data)
                        used_backend = backend
                        logger.info("Recognition succeeded with backend: {}", backend)
                        break  # Exit inner loop (backends)
                    except Exception as exc:
                        logger.error("Recognition error on backend {}: {}", backend, exc)
                        last_error = str(exc)
                        time.sleep(BACKEND_SWITCH_DELAY_SEC)
                        continue
                
                if raw_text is not None:
                    break  # Exit outer loop (attempts)

                if attempt < MAX_ATTEMPTS - 1:
                    logger.info(f"Attempt #{attempt + 1} failed. Retrying in {RETRY_DELAY_SEC} seconds...")
                    time.sleep(RETRY_DELAY_SEC)

            if raw_text is None:
                msg = "Ошибка соединения. Настройте соединение и попробуйте еще раз."
                self.state_changed.emit("error")
                self.message_shown.emit(msg, 0)  # 0 timeout to keep it visible
                self.window.show_retry_button()
                return

            from loguru import logger as _logger

            try:
                # 2) regex-очистка (базовый препроцессинг всегда)
                regex_text = TP._simple_cleanup(raw_text or "")

                # 3) LLM-постпроцессинг (если включён в конфиге)
                processed_text = regex_text
                try:
                    processed_text = self.postprocessor.process(raw_text or "")
                except RuntimeError as exc:
                    _logger.error("LLM postprocess error: {}", exc)
                    self.message_shown.emit(str(exc), 3000)
                except Exception as exc:  # noqa: BLE001
                    _logger.exception("Unexpected LLM postprocess error: {}", exc)
                    self.message_shown.emit("Ошибка LLM-постпроцессинга. См. логи.", 3000)

                # 4) показать оба варианта в окне (через сигнал)
                self.text_updated.emit(raw_text or "", processed_text or "")

                # 5) положить ОБРАБОТАННЫЙ текст в буфер обмена (ВСЕГДА)
                self.clipboard.copy(processed_text or "")

                # 6) авто-вставка текста через Ctrl+V (ВСЕГДА)
                self.clipboard.paste()

                # 7) если это была идея, добавить в список идей
                if is_idea_flag:
                    self.idea_added.emit(processed_text or "")
                    self._log_idea(processed_text or "")

                # 8) сохранить распознавание в отдельный текстовый лог с ротацией по ~3 МБ
                try:
                    if getattr(sys, "frozen", False):
                        base_dir = Path(sys.executable).resolve().parent
                    else:
                        base_dir = Path(__file__).resolve().parents[1]

                    log_dir = base_dir / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    transcript_path = log_dir / "transcripts.log"

                    max_size_bytes = 3 * 1024 * 1024
                    if transcript_path.exists() and transcript_path.stat().st_size >= max_size_bytes:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        rotated = log_dir / f"transcripts_{ts}.log"
                        transcript_path.rename(rotated)

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    backend_str = used_backend or (self.settings.recognition.backend or "unknown")

                    with transcript_path.open("a", encoding="utf-8") as f:
                        f.write(
                            f"[{timestamp}] backend={backend_str} "
                            f"duration={audio_duration_sec:.3f}s\n"
                            f"RAW: {(raw_text or '').strip()}\n"
                            f"PROCESSED: {(processed_text or '').strip()}\n"
                            "----------------------------------------\n"
                        )
                except Exception as exc:  # noqa: BLE001
                    _logger.exception("Failed to append transcript log: {}", exc)

                self.state_changed.emit("ready")

                # If successful, delete recovery file
                if recovery_path:
                    self.recovery_manager.cleanup(recovery_path)

            except Exception as exc:  # noqa: BLE001
                _logger.exception("Unexpected error during post-processing: {}", exc)
                self.state_changed.emit("error")
                self.message_shown.emit("Неизвестная ошибка постобработки. См. логи.", 3000)
        finally:
            self._processing_lock.release()

    def _log_idea(self, text: str):
        """Appends an idea to the ideas.log file."""
        from loguru import logger
        from datetime import datetime
        
        if not text.strip():
            return
            
        try:
            # Use the same base_dir logic as in _process_audio
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).resolve().parent
            else:
                base_dir = Path(__file__).resolve().parents[1]

            log_dir = base_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            idea_log_path = log_dir / "ideas.log"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with idea_log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {text.strip()}\n")
                
        except Exception as exc:
            logger.exception("Failed to append idea to log: {}", exc)

    def _check_recovery_files(self) -> None:
        """
        Checks for existing recovery files and processes them.
        """
        from loguru import logger
        
        files = self.recovery_manager.get_recovery_files()
        if not files:
            return

        logger.info(f"Found {len(files)} recovery files. Processing...")
        
        # Process files in a separate thread to not block UI startup
        def process_recovery():
            for filepath in files:
                logger.info(f"Recovering file: {filepath}")
                audio_data = self.recovery_manager.load_audio(filepath)
                if audio_data:
                    # We process it as a normal recording.
                    # Note: this will trigger UI updates and clipboard paste.
                    # We pass the filepath so it gets deleted on success.
                    
                    self._process_audio(audio_data, recovery_path=filepath)
                    
                    # Small delay between files
                    time.sleep(1)
                else:
                    logger.error(f"Failed to load audio from {filepath}, skipping.")

        threading.Thread(target=process_recovery, daemon=True).start()

    # -------------------------------------------------------------- Debug

    def toggle_debug_mode(self) -> None:
        # Placeholder: will reconfigure logging level later
        self.window.show_message("Toggle debug (not fully implemented yet).")

    # ----------------------------------------------------------- Settings / config helpers

    def _load_or_init_settings(self) -> AppSettings:
        """
        Загрузка настроек с учётом портативного режима.

        Логика:
        - Ищем config.yaml в self.base_dir (рядом с exe или в корне проекта).
        - Если файла нет — создаём минимальный config.yaml с backend=local.
        - Затем вызываем AppSettings.load_default(), который уже умеет
          подмешивать config.local.yaml поверх config.yaml.
        """
        config_path = self.base_dir / "config.yaml"

        if not config_path.exists():
            # Минимальный конфиг по умолчанию: локальный backend, безопасные значения.
            default_config = {
                "app": {
                    "name": "VoiceCapture",
                    "version": "2.0.0",
                },
                "hotkeys": {
                    "record": "ctrl+win",
                    "record_idea": "ctrl+win+alt",
                    "cancel": "esc",
                    "toggle_window": "ctrl+alt+s",
                    "toggle_debug": "ctrl+alt+d",
                },
                "audio": {
                    "sample_rate": 16000,
                    "channels": 1,
                    "max_duration": 120,
                },
                "recognition": {
                    "backend": "groq",
                    "openai": {
                        "api_key": "",
                        "model": "whisper-1",
                        "model_process": "gpt-4o-mini",
                        "language": "ru",
                        # base_url намеренно оставляем пустым, чтобы пользователь
                        # задал его в настройках (OpenAI Base URL).
                        "base_url": "",
                    },
                    "groq": {
                        "api_key": "",
                        "model": "whisper-large-v3",
                        "model_process": "moonshotai/kimi-k2-instruct",
                        "language": "ru",
                    },
                },
                # Блок postprocess больше не хранит ключи / base_url.
                # Здесь только включение, режим и "отображательные" модели.
                "postprocess": {
                    "enabled": True,
                    "mode": "llm",
                    "llm_backend": "groq",
                    "groq": {
                        "model": "moonshotai/kimi-k2-instruct",
                    },
                    "openai": {
                        "model": "gpt-5.1",
                    },
                },
                "ui": {
                    # Старые поля width/height/compact_mode больше не используются,
                    # но при первой генерации конфига запишем их для обратной совместимости.
                    "width": 320,
                    "height": 200,
                    "opacity": 0.9,
                    "compact_mode": False,
                },
                "logging": {
                    "level": "INFO",
                    "log_dir": "logs",
                },
            }

            try:
                import yaml

                with config_path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)
            except Exception:
                # Если по какой-то причине не удалось записать файл — продолжаем
                # с дефолтами из dataclass'ов AppSettings.
                pass

        # Теперь загружаем настройки стандартным способом:
        settings = AppSettings.load_default()

        # Гарантируем, что backend задан
        if not getattr(settings.recognition, "backend", None):
            settings.recognition.backend = "groq"

        return settings

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