import sys
from pathlib import Path
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
        audio -> recognizer (Groq/GigaAM) -> postprocess -> clipboard.copy + paste
    """

    def __init__(self) -> None:
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

        # Core components
        self.window = FloatingWindow(self.settings.ui)
        self.tray = SystemTrayIcon(self.window, self.settings.app)
        self.clipboard = ClipboardManager()
        self.audio_recorder = AudioRecorder(self.settings.audio)
        self.recognizer = create_recognizer(self.settings.recognition)

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
        self.recognizer = create_recognizer(self.settings.recognition)

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

    def start_recording(self) -> None:
        if self._is_recording:
            return
        self._is_recording = True
        self.window.set_state("recording")

        def on_finished(audio_data):
            # Этот колбэк вызывается из потока рекордера.
            # Возвращаемся к синхронной обработке, как в рабочем варианте.
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
        """
        Синхронная обработка аудио с каскадом backend'ов:
        1) основной backend из настроек (groq / openai / local),
        2) при ошибке — fallback на остальные по приоритету.
        """
        from loguru import logger
        from pathlib import Path
        from datetime import datetime
        from recognition.postprocessor import TextPostprocessor as TP  # для _simple_cleanup
        from recognition import create_recognizer  # каскадное создание по backend'у

        self.window.set_state("processing")

        # Собираем приоритетный список backend'ов:
        # сначала выбранный пользователем, затем остальные.
        primary = (self.settings.recognition.backend or "groq").lower()
        all_backends = ["groq", "openai", "local"]
        cascade = [b for b in [primary] + all_backends if b in all_backends]
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        ordered_backends = []
        for b in cascade:
            if b not in seen:
                seen.add(b)
                ordered_backends.append(b)

        last_error: str | None = None
        raw_text: str | None = None

        for backend in ordered_backends:
            try:
                logger.info("Trying recognition backend: {}", backend)
                # Временно подменяем backend в настройках для фабрики
                original_backend = self.settings.recognition.backend
                self.settings.recognition.backend = backend
                recognizer = create_recognizer(self.settings.recognition)
                # ВАЖНО: возвращаем исходный backend в настройках
                self.settings.recognition.backend = original_backend

                raw_text = recognizer.transcribe(audio_data)
                logger.info("Recognition succeeded with backend: {}", backend)
                break
            except RuntimeError as exc:
                # Осмысленная ошибка — логируем и пробуем следующий backend
                logger.error("Recognition error on backend {}: {}", backend, exc)
                last_error = str(exc)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected recognition error on backend {}: {}", backend, exc)
                last_error = f"Неизвестная ошибка backend '{backend}'. См. логи."
                continue

        if raw_text is None:
            # Все backend'ы упали — показываем последнюю ошибку
            msg = last_error or "Не удалось распознать аудио ни одним backend'ом."
            self.window.set_state("error")
            self.window.show_message(msg)
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
                self.window.show_message(str(exc))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Unexpected LLM postprocess error: {}", exc)
                self.window.show_message("Ошибка LLM-постпроцессинга. См. логи.")

            # 4) показать оба варианта в окне
            try:
                if hasattr(self.window, "set_raw_text"):
                    self.window.set_raw_text(raw_text or "")
                else:
                    self.window.result_label.setText(processed_text or "")

                if hasattr(self.window, "set_processed_text"):
                    self.window.set_processed_text(processed_text or "")
            except Exception:
                _logger.debug("window text update failed", exc_info=True)

            # 5) положить ОБРАБОТАННЫЙ текст в буфер обмена
            self.clipboard.copy(processed_text or "")

            # 6) авто-вставка текста через Ctrl+V (с ретраями внутри ClipboardManager)
            self.clipboard.paste()

            # 7) сохранить распознавание в отдельный текстовый лог с ротацией по ~3 МБ
            try:
                base_dir = Path(__file__).resolve().parents[2]
                log_dir = base_dir / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                transcript_path = log_dir / "transcripts.log"

                max_size_bytes = 3 * 1024 * 1024
                if transcript_path.exists() and transcript_path.stat().st_size >= max_size_bytes:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rotated = log_dir / f"transcripts_{ts}.log"
                    transcript_path.rename(rotated)

                with transcript_path.open("a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\\n"
                        f"RAW: { (raw_text or '').strip() }\\n"
                        f"PROCESSED: { (processed_text or '').strip() }\\n"
                        "----------------------------------------\\n"
                    )
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Failed to append transcript log: {}", exc)

            self.window.set_state("ready")
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Unexpected error during post-processing: {}", exc)
            self.window.set_state("error")
            self.window.show_message("Неизвестная ошибка постобработки. См. логи.")

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
                    "version": "0.1.0",
                },
                "hotkeys": {
                    "record": "ctrl+win",
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
                    "backend": "local",
                    "local": {
                        "model": "large-v3",
                        "device": "cuda",
                        "compute_type": "float16",
                        "language": "ru",
                        "beam_size": 5,
                        "temperature": 0.0,
                    },
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
                        "model_process": "llama-3.3-70b-versatile",
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
                        "model": "llama-3.3-70b-versatile",
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
            settings.recognition.backend = "local"

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