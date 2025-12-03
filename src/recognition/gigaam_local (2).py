from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

from loguru import logger  # type: ignore[import]
from transformers import AutoModel  # type: ignore[import]

from audio.recorder import AudioData


class GigaAMRecognizer:
    """
    Упрощённый локальный распознаватель на базе GigaAM-v3 e2e_rnnt через HuggingFace.

    Использует только стандартный метод model.transcribe(path) без longform
    и без Hugging Face токена.

    Дополнительное ограничение:
    - если длительность аудио превышает 25 секунд, локальный backend
      сразу возвращает контролируемую ошибку, чтобы пайплайн переключился
      на Groq/OpenAI.
    """

    HF_MODEL_ID: Final[str] = "ai-sage/GigaAM-v3"
    HF_REVISION: Final[str] = "e2e_rnnt"
    MAX_DURATION_SEC: Final[float] = 25.0

    def __init__(self, device: Optional[str] = None) -> None:
        """
        :param device: "cuda" / "cpu" / None
                       None -> автоопределение по torch.cuda.is_available().
        """
        import torch  # локальный импорт, чтобы не тянуть при импорте модуля

        requested_device = (device or "").lower().strip() or None

        if requested_device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        elif requested_device == "cuda":
            if torch.cuda.is_available():
                self.device = "cuda"
            else:
                logger.warning(
                    "GigaAM: в конфиге запрошен device='cuda', "
                    "но torch.cuda.is_available() == False. "
                    "Переходим на CPU."
                )
                self.device = "cpu"
        elif requested_device == "cpu":
            self.device = "cpu"
        else:
            logger.warning(
                "GigaAM: неизвестное значение device='{}'. "
                "Ожидалось 'cuda' или 'cpu'. Используем автоопределение.",
                requested_device,
            )
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            "Loading GigaAM-v3 model '{}' (revision='{}') on {}",
            self.HF_MODEL_ID,
            self.HF_REVISION,
            self.device,
        )

        # Используем float32, чтобы избежать проблем с half precision в STFT.
        torch_dtype = torch.float32

        try:
            self.model = AutoModel.from_pretrained(
                self.HF_MODEL_ID,
                revision=self.HF_REVISION,
                trust_remote_code=True,
                torch_dtype=torch_dtype,
            ).to(self.device)
            self.model = self.model.to(dtype=torch_dtype, device=self.device)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load GigaAM-v3 model: {}", exc)
            raise RuntimeError("GigaAM-v3: ошибка загрузки модели.") from exc

        logger.info("GigaAM-v3 model loaded successfully")

    def transcribe(self, audio: AudioData) -> str:
        """
        Принимает AudioData и возвращает текст с пунктуацией.

        ВНИМАНИЕ: официальный API модели ожидает путь к аудиофайлу.
        Поэтому мы сохраняем временный WAV и передаём путь в model.transcribe().

        Дополнительно:
        - если длительность аудио > MAX_DURATION_SEC (25 сек),
          локальный backend сразу отдаёт контролируемую ошибку,
          чтобы пайплайн переключился на Groq/OpenAI.
        """
        import tempfile
        import soundfile as sf  # type: ignore[import]
        import numpy as np  # type: ignore[import]

        samples = audio.samples
        sample_rate = float(audio.sample_rate)

        # Оценка длительности
        try:
            if isinstance(samples, np.ndarray):
                num_samples = samples.shape[0]
            else:
                num_samples = len(samples)
        except Exception:  # noqa: BLE001
            num_samples = len(samples)  # type: ignore[arg-type]

        duration_sec = num_samples / sample_rate if sample_rate > 0 else 0.0

        # Жёсткое ограничение: всё, что длиннее 25 секунд, сразу уходит на Groq/OpenAI.
        if duration_sec > self.MAX_DURATION_SEC:
            logger.info(
                "GigaAM-v3: длительность {:.1f}s превышает лимит {:.1f}s для локального backend'а. "
                "Пропускаем GigaAM и даём шанс Groq/OpenAI.",
                duration_sec,
                self.MAX_DURATION_SEC,
            )
            raise RuntimeError(
                "GigaAM-v3: аудио длиннее 25 секунд, используем облачный backend."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "input.wav"

            if isinstance(samples, np.ndarray):
                if samples.ndim == 2 and samples.shape[1] == 1:
                    samples = samples[:, 0]
                samples = samples.astype("float32")
            else:
                samples = np.asarray(samples, dtype="float32")

            sf.write(
                wav_path,
                samples,
                audio.sample_rate,
                format="WAV",
            )

            try:
                transcription = self.model.transcribe(str(wav_path))
            except ValueError as exc:
                msg_text = str(exc)
                # Специальный случай: модель просит использовать longform.
                if "Too long wav file, use 'transcribe_longform' method." in msg_text:
                    logger.error(
                        "GigaAM-v3: аудио слишком длинное для локального режима без longform. "
                        "Локальный backend пропускаем, даём шанс Groq/OpenAI. Исходная ошибка: {}",
                        exc,
                    )
                    raise RuntimeError(
                        "GigaAM-v3: аудио слишком длинное для локального режима без longform."
                    ) from exc

                logger.exception("GigaAM-v3 transcribe error: {}", exc)
                raise RuntimeError("GigaAM-v3: ошибка распознавания.") from exc
            except Exception as exc:  # noqa: BLE001
                logger.exception("GigaAM-v3 transcribe error: {}", exc)
                raise RuntimeError("GigaAM-v3: ошибка распознавания.") from exc

        if not isinstance(transcription, str):
            logger.error("GigaAM-v3 returned non-string transcription: {}", transcription)
            raise RuntimeError("GigaAM-v3: некорректный формат ответа.")

        return transcription or ""