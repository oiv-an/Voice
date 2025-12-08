from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


# ---------------------------------------------------------------------------#
# Dataclasses for structured settings
# ---------------------------------------------------------------------------#


@dataclass
class AppInfoConfig:
    name: str = "VoiceCapture"
    version: str = "1.1.0"
    language: str = "ru"
    debug: bool = False


@dataclass
class HotkeysConfig:
    record: str = "ctrl+win"
    record_idea: str = "ctrl+win+alt"
    cancel: str = "esc"
    toggle_window: str = "ctrl+alt+s"
    toggle_debug: str = "ctrl+alt+d"


@dataclass
class AudioConfig:
    device: str | int = "default"
    sample_rate: int = 16000
    channels: int = 1
    format: str = "float32"
    max_duration: int = 60
    vad_threshold: float = 0.5
    vad_min_duration: float = 0.1
    speedup_x2: bool = False


@dataclass
class LocalRecognitionConfig:
    model: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: str = "ru"
    beam_size: int = 5
    temperature: float = 0.0


@dataclass
class OpenAIRecognitionConfig:
    api_key: str = "sk-..."
    model: str = "whisper-1"
    # Модель для постобработки текста (LLM), чтобы не плодить отдельные блоки.
    model_process: str = "gpt-5.1"
    language: str = "ru"
    base_url: str = ""  # URL всегда задаётся только в config.yaml / настройках


@dataclass
class GroqRecognitionConfig:
    api_key: str = "gsk-..."
    model: str = "whisper-large-v3"
    # Модель для постобработки текста (LLM) — одно поле рядом с моделью распознавания.
    model_process: str = "moonshotai/kimi-k2-instruct"
    language: str = "ru"


from dataclasses import dataclass, field
...
@dataclass
class RecognitionConfig:
    backend: str = "local"  # local, openai, groq
    local: LocalRecognitionConfig = field(default_factory=LocalRecognitionConfig)
    openai: OpenAIRecognitionConfig = field(default_factory=OpenAIRecognitionConfig)
    groq: GroqRecognitionConfig = field(default_factory=GroqRecognitionConfig)


# Блоки постпроцессинга больше не хранят свои ключи — только для обратной
# совместимости структуры. Модели LLM берём из recognition.*.model_process.
@dataclass
class GroqPostprocessConfig:
    model: str = "moonshotai/kimi-k2-instruct"


@dataclass
class OpenAIPostprocessConfig:
    model: str = "gpt-5.1"


@dataclass
class PostprocessConfig:
    enabled: bool = True
    mode: str = "llm"  # simple, llm
    llm_backend: str = "groq"  # groq, openai
    groq: GroqPostprocessConfig = field(default_factory=GroqPostprocessConfig)
    openai: OpenAIPostprocessConfig = field(default_factory=OpenAIPostprocessConfig)


@dataclass
class UIConfig:
    always_on_top: bool = True
    opacity: float = 0.8
    # Дефолтный размер окна: 600x500
    window_size: tuple[int, int] = (600, 500)
    auto_hide_after_paste: bool = True
    hide_delay: int = 2000  # ms


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "app.log"
    max_file_size: int = 10 * 1024 * 1024
    backup_count: int = 3


@dataclass
class AppSettings:
    app: AppInfoConfig
    hotkeys: HotkeysConfig
    audio: AudioConfig
    recognition: RecognitionConfig
    postprocess: PostprocessConfig
    ui: UIConfig
    logging: LoggingConfig

    # ------------------------------------------------------------------ factory

    @classmethod
    def load_default(cls) -> "AppSettings":
        """
        Единая загрузка настроек из ОДНОГО файла config.yaml.

        Логика:

        1. Определяем base_dir:
           - если PyInstaller EXE: папка exe;
           - иначе: корень проекта (двумя уровнями выше этого файла).

        2. Файл настроек: base_dir/config.yaml
           - если файла нет — создаём его с дефолтами из датаклассов.

        3. Загружаем config.yaml и маппим в AppSettings.
        """
        import sys

        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parents[2]

        config_path = base_dir / "config.yaml"

        # Если файла нет — создаём дефолтный config.yaml
        if not config_path.exists():
            default = {
                "app": AppInfoConfig().__dict__,
                "hotkeys": HotkeysConfig().__dict__,
                "audio": AudioConfig().__dict__,
                "recognition": {
                    "backend": RecognitionConfig().backend,
                    "local": LocalRecognitionConfig().__dict__,
                    "openai": OpenAIRecognitionConfig().__dict__,
                    "groq": GroqRecognitionConfig().__dict__,
                },
                "postprocess": {
                    "enabled": PostprocessConfig().enabled,
                    "mode": PostprocessConfig().mode,
                    "llm_backend": PostprocessConfig().llm_backend,
                    "groq": {"model": GroqPostprocessConfig().model},
                    "openai": {
                        "model": OpenAIPostprocessConfig().model,
                    },
                },
                "ui": UIConfig().__dict__,
                "logging": LoggingConfig().__dict__,
            }
            try:
                with config_path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(default, f, allow_unicode=True, sort_keys=False)
            except Exception:
                # Если не удалось записать файл — просто вернём дефолтные настройки
                return cls(
                    app=AppInfoConfig(),
                    hotkeys=HotkeysConfig(),
                    audio=AudioConfig(),
                    recognition=RecognitionConfig(),
                    postprocess=PostprocessConfig(),
                    ui=UIConfig(),
                    logging=LoggingConfig(),
                )

        with config_path.open("r", encoding="utf-8") as f:
            raw: Dict[str, Any] = yaml.safe_load(f) or {}

        def get_section(name: str, default: Dict[str, Any]) -> Dict[str, Any]:
            section = raw.get(name, {}) or {}
            # Shallow-merge section over defaults so that missing keys
            # still get dataclass defaults.
            merged: Dict[str, Any] = dict(default)
            merged.update(section)
            return merged

        app_cfg = AppInfoConfig(**get_section("app", AppInfoConfig().__dict__))
        hotkeys_cfg = HotkeysConfig(**get_section("hotkeys", HotkeysConfig().__dict__))
        audio_cfg = AudioConfig(**get_section("audio", AudioConfig().__dict__))

        rec_raw = raw.get("recognition", {}) or {}
        local_raw_rec = rec_raw.get("local", {}) or {}
        openai_raw_rec = rec_raw.get("openai", {}) or {}
        groq_raw_rec = rec_raw.get("groq", {}) or {}

        # Удаляем устаревшее поле hf_token из локального блока, если оно есть в старом config.yaml
        if "hf_token" in local_raw_rec:
            local_raw_rec.pop("hf_token", None)

        recognition_cfg = RecognitionConfig(
            backend=rec_raw.get("backend", "local"),
            local=LocalRecognitionConfig(
                **{**LocalRecognitionConfig().__dict__, **local_raw_rec}
            ),
            openai=OpenAIRecognitionConfig(
                **{**OpenAIRecognitionConfig().__dict__, **openai_raw_rec}
            ),
            groq=GroqRecognitionConfig(
                **{**GroqRecognitionConfig().__dict__, **groq_raw_rec}
            ),
        )

        post_raw = raw.get("postprocess", {}) or {}
        groq_post_raw = post_raw.get("groq", {}) or {}
        openai_post_raw = post_raw.get("openai", {}) or {}

        # Старые поля api_key/model/model_process/base_url в postprocess.* игнорируем —
        # ключи, модели и URL живут в recognition.*.
        for k in ("api_key", "model", "model_process", "base_url"):
            if k in groq_post_raw:
                groq_post_raw.pop(k, None)
            if k in openai_post_raw:
                openai_post_raw.pop(k, None)

        postprocess_cfg = PostprocessConfig(
            enabled=post_raw.get("enabled", True),
            mode=post_raw.get("mode", "llm"),
            llm_backend=post_raw.get("llm_backend", "groq"),
            groq=GroqPostprocessConfig(
                **{**GroqPostprocessConfig().__dict__, **groq_post_raw}
            ),
            openai=OpenAIPostprocessConfig(
                **{**OpenAIPostprocessConfig().__dict__, **openai_post_raw}
            ),
        )

        # UI: дополнительно фильтруем устаревшие/лишние поля (width/height/compact_mode)
        ui_raw = get_section("ui", UIConfig().__dict__)
        for k in ("width", "height", "compact_mode"):
            ui_raw.pop(k, None)
        ui_cfg = UIConfig(**ui_raw)

        # Logging: фильтруем устаревшие поля (log_dir и т.п.), чтобы не падать
        logging_raw = get_section("logging", LoggingConfig().__dict__)
        for k in ("log_dir",):
            logging_raw.pop(k, None)
        logging_cfg = LoggingConfig(**logging_raw)

        return cls(
            app=app_cfg,
            hotkeys=hotkeys_cfg,
            audio=audio_cfg,
            recognition=recognition_cfg,
            postprocess=postprocess_cfg,
            ui=ui_cfg,
            logging=logging_cfg,
        )

    # ------------------------------------------------------------------ save

    @classmethod
    def save_default(cls, settings: "AppSettings") -> None:
        """
        Сохранить ВСЕ текущие настройки в ОДИН файл config.yaml в base_dir.

        - Тот же base_dir, что и в load_default().
        - Никаких config.local.yaml, никаких src/config/config.yaml.
        - Этот файл должен быть добавлен в .gitignore и не коммититься.
        """
        import sys

        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parents[2]

        config_path = base_dir / "config.yaml"

        data: Dict[str, Any] = {
            "app": settings.app.__dict__,
            "hotkeys": settings.hotkeys.__dict__,
            "audio": settings.audio.__dict__,
            "recognition": {
                "backend": settings.recognition.backend,
                "local": settings.recognition.local.__dict__,
                "openai": settings.recognition.openai.__dict__,
                "groq": settings.recognition.groq.__dict__,
            },
            "postprocess": {
                "enabled": settings.postprocess.enabled,
                "mode": settings.postprocess.mode,
                "llm_backend": settings.postprocess.llm_backend,
                "groq": {"model": settings.postprocess.groq.model},
                "openai": {
                    "model": settings.postprocess.openai.model,
                },
            },
            "ui": settings.ui.__dict__,
            "logging": settings.logging.__dict__,
        }

        with config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)