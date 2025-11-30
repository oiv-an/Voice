from __future__ import annotations

from pathlib import Path
from typing import Final

from loguru import logger  # type: ignore[import]
from transformers import AutoModel  # type: ignore[import]

from audio.recorder import AudioData


class GigaAMRecognizer:
    """
    Локальный распознаватель на базе GigaAM-v3 e2e_rnnt через HuggingFace.

    Использует официальный API:
      - модель:   ai-sage/GigaAM-v3
      - revision: "e2e_rnnt" (лучшее качество + пунктуация)
      - встроенный метод model.transcribe(path) для распознавания

    Требует заранее установленного окружения (см. requirements проекта):
      - torch, torchaudio, transformers, pyannote-audio, torchcodec, hydra-core, omegaconf, sentencepiece, ffmpeg в PATH.
    """

    HF_MODEL_ID: Final[str] = "ai-sage/GigaAM-v3"
    HF_REVISION: Final[str] = "e2e_rnnt"

    def __init__(self) -> None:
        import torch  # локальный импорт, чтобы не тянуть при импорте модуля

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            "Loading GigaAM-v3 model '{}' (revision='{}') on {}",
            self.HF_MODEL_ID,
            self.HF_REVISION,
            self.device,
        )

        # ВАЖНО:
        # Официальные примеры используют float16 только на GPU.
        # На CPU должны быть и входы, и веса в float32, иначе получаем:
        # "Input type (float) and bias type (struct c10::Half) should be the same".
        import torch  # локальный импорт

        if self.device == "cuda":
            torch_dtype = torch.float16
        else:
            torch_dtype = torch.float32

        try:
            self.model = AutoModel.from_pretrained(
                self.HF_MODEL_ID,
                revision=self.HF_REVISION,
                trust_remote_code=True,
                torch_dtype=torch_dtype,
            ).to(self.device)
            # На всякий случай приводим модель к нужному dtype ещё раз
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
        """
        import tempfile
        import soundfile as sf  # type: ignore[import]
        import numpy as np  # type: ignore[import]

        # Создаём временный WAV-файл
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "input.wav"

            samples = audio.samples
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
                # Официальный API: модель сама читает файл и делает всю обработку
                transcription = self.model.transcribe(str(wav_path))
            except Exception as exc:  # noqa: BLE001
                logger.exception("GigaAM-v3 transcribe error: {}", exc)
                raise RuntimeError("GigaAM-v3: ошибка распознавания.") from exc

        if not isinstance(transcription, str):
            logger.error("GigaAM-v3 returned non-string transcription: {}", transcription)
            raise RuntimeError("GigaAM-v3: некорректный формат ответа.")

        return transcription or ""