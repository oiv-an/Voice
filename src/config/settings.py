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
    version: str = "1.0.0"
    language: str = "ru"
    debug: bool = False


@dataclass
class HotkeysConfig:
    record: str = "ctrl+win"
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
    model_process: str = "gpt-4"
    language: str = "ru"
    base_url: str = "https://api.openai.com/v1"  # кастомный/дефолтный URL


@dataclass
class GroqRecognitionConfig:
    api_key: str = "gsk-..."
    model: str = "whisper-large-v3"
    # Модель для постобработки текста (LLM) — одно поле рядом с моделью распознавания.
    model_process: str = "mixtral-8x7b-32768"
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
    model: str = "mixtral-8x7b-32768"


@dataclass
class OpenAIPostprocessConfig:
    model: str = "gpt-4"
    base_url: str = "https://api.openai.com/v1"  # кастомный/дефолтный URL


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
    window_size: tuple[int, int] = (120, 120)
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
        Load settings from src/config/config.yaml and optionally
        src/config/config.local.yaml (local overrides).

        The merge strategy is:
        - Load base config.yaml (if present).
        - Load config.local.yaml (if present).
        - Deep-merge: values from config.local.yaml override config.yaml.
        - Apply dataclass defaults for any missing fields.
        """
        base_dir = Path(__file__).resolve().parents[2]
        config_dir = base_dir / "src" / "config"
        config_path = config_dir / "config.yaml"
        local_config_path = config_dir / "config.local.yaml"

        # If there is no base config at all, fall back to pure defaults.
        if not config_path.exists():
            return cls(
                app=AppInfoConfig(),
                hotkeys=HotkeysConfig(),
                audio=AudioConfig(),
                recognition=RecognitionConfig(),
                postprocess=PostprocessConfig(),
                ui=UIConfig(),
                logging=LoggingConfig(),
            )

        def _load_yaml(path: Path) -> Dict[str, Any]:
            if not path.exists():
                return {}
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

        def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """
            Recursively merge two dicts.

            - base: original data (e.g. from config.yaml)
            - override: local overrides (e.g. from config.local.yaml)

            Values from override take precedence. Nested dicts are merged
            recursively; other types are replaced.
            """
            result: Dict[str, Any] = dict(base)
            for key, value in (override or {}).items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = _deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        base_raw: Dict[str, Any] = _load_yaml(config_path)
        local_raw: Dict[str, Any] = _load_yaml(local_config_path)

        # Local config overrides base config.
        raw: Dict[str, Any] = _deep_merge(base_raw, local_raw)

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

        # Старые поля api_key/model в postprocess.* игнорируем — ключи и модели
        # живут в recognition.*.api_key / recognition.*.model_process.
        for k in ("api_key",):
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

        ui_cfg = UIConfig(**get_section("ui", UIConfig().__dict__))
        logging_cfg = LoggingConfig(**get_section("logging", LoggingConfig().__dict__))

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
        Save current settings back to src/config/config.yaml.
        """
        base_dir = Path(__file__).resolve().parents[2]
        config_path = base_dir / "src" / "config" / "config.yaml"

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
                # В groq/openai больше нет своих api_key — только модель и base_url.
                "groq": {"model": settings.postprocess.groq.model},
                "openai": {
                    "model": settings.postprocess.openai.model,
                    "base_url": settings.postprocess.openai.base_url,
                },
            },
            "ui": settings.ui.__dict__,
            "logging": settings.logging.__dict__,
        }

        with config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)