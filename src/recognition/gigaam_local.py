from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from loguru import logger  # type: ignore[import]
from transformers import AutoModel  # type: ignore[import]

from audio.recorder import AudioData


# Базовая директория приложения:
# - в dev-режиме: корень проекта (родитель src)
# - в собранном .exe: папка, где лежит exe
if getattr(sys, "frozen", False):
    _BASE_DIR: Final[Path] = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parents[2]

MODELS_DIR: Final[Path] = _BASE_DIR / "models"
GIGAAM_DIR: Final[Path] = MODELS_DIR / "GigaAM-v3-e2e_rnnt"


class GigaAMRecognizer:
    """
    Локальный распознаватель на базе GigaAM-v3 e2e_rnnt через HuggingFace.

    Использует официальный API:
      - модель:   ai-sage/GigaAM-v3
      - revision: "e2e_rnnt" (лучшее качество + пунктуация)
      - встроенный метод model.transcribe(path) для распознавания

    Требует заранее установленного окружения (см. requirements проекта):
      - torch, torchaudio, transformers, pyannote-audio, torchcodec, hydra-core, omegaconf, sentencepiece, ffmpeg в PATH.

    ВАЖНО: веса модели хранятся в папке:
        {BASE_DIR}/models/GigaAM-v3-e2e_rnnt

    где BASE_DIR:
      - рядом с exe в портативной сборке,
      - корень проекта при запуске из исходников.
    """

    HF_MODEL_ID: Final[str] = "ai-sage/GigaAM-v3"
    HF_REVISION: Final[str] = "e2e_rnnt"

    def __init__(self) -> None:
        import torch  # локальный импорт, чтобы не тянуть при импорте модуля

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Всегда используем локальную папку {BASE_DIR}/models/GigaAM-v3-e2e_rnnt
        # как cache_dir HuggingFace, чтобы веса модели лежали РЯДОМ с exe
        # и могли быть упакованы в портативную сборку.
        GIGAAM_DIR.mkdir(parents=True, exist_ok=True)
        cache_dir = str(GIGAAM_DIR)
        logger.info(
            "GigaAM-v3 local model directory: {} (using as cache_dir).",
            GIGAAM_DIR,
        )

        logger.info(
            "Loading GigaAM-v3 model '{}' (revision='{}') on {}",
            self.HF_MODEL_ID,
            self.HF_REVISION,
            self.device,
        )

        # ВАЖНО:
        # На практике half-precision (float16) на некоторых связках CUDA/cuFFT
        # приводит к падениям вида:
        #   "cuFFT only supports dimensions whose sizes are powers of two
        #    when computing in half precision, but got a signal size of [320]"
        # Поэтому для десктоп-приложения надёжнее всегда использовать float32
        # и на GPU, и на CPU.
        import torch  # локальный импорт

        torch_dtype = torch.float32

        try:
            # Жёстко используем локальный cache_dir, чтобы веса всегда лежали
            # в {BASE_DIR}/models/GigaAM-v3-e2e_rnnt и могли быть добавлены
            # в портативный exe через --add-data "models;models".
            from_kwargs = {
                "revision": self.HF_REVISION,
                "trust_remote_code": True,
                "dtype": torch_dtype,  # torch_dtype устарел, используем dtype
                "cache_dir": cache_dir,
            }
    
            # Папка снапшотов Hugging Face для этой модели внутри локального cache_dir.
            snapshot_root = GIGAAM_DIR / f"models--{self.HF_MODEL_ID.replace('/', '--')}"
            has_local_snapshot = snapshot_root.exists()
    
            def _load_model(local_files_only: bool = False) -> None:
                kwargs = dict(from_kwargs)
                if local_files_only:
                    # Не делать НИКАКИХ сетевых запросов, использовать только локальные файлы.
                    kwargs["local_files_only"] = True
                self.model = AutoModel.from_pretrained(
                    self.HF_MODEL_ID,
                    **kwargs,
                ).to(self.device)
                # На всякий случай приводим модель к нужному dtype ещё раз
                self.model = self.model.to(dtype=torch_dtype, device=self.device)
    
            try:
                if has_local_snapshot:
                    # 1) Если снапшот уже есть локально — сначала пробуем строго оффлайн.
                    try:
                        _load_model(local_files_only=True)
                    except Exception as local_exc:  # noqa: BLE001
                        # Если по какой-то причине оффлайн-загрузка не удалась (битые файлы и т.п.),
                        # логируем и даём шанс обычной загрузке (с сетью / перекачкой).
                        logger.warning(
                            "GigaAM-v3: не удалось загрузить модель только из локального кэша {}: {}. "
                            "Пробую с разрешённым доступом к сети.",
                            GIGAAM_DIR,
                            local_exc,
                        )
                        _load_model(local_files_only=False)
                else:
                    # 2) Локального снапшота ещё нет — разрешаем сети докачать модель.
                    _load_model(local_files_only=False)
            except Exception as exc:
                msg = str(exc)
                # Типовой кейс: локальный кэш HuggingFace повреждён
                # (битый/обрубленный pytorch_model.bin и т.п.).
                if isinstance(exc, (OSError, ValueError)) and (
                    "Unable to load weights from pytorch checkpoint file" in msg
                    or "Unable to locate the file" in msg
                ):
                    logger.warning(
                        "GigaAM-v3: локальный кэш модели повреждён, "
                        "очищаю {} и перезапускаю загрузку.",
                        GIGAAM_DIR,
                    )
                    import shutil  # локальный импорт, чтобы не тянуть при импорте модуля
    
                    try:
                        shutil.rmtree(GIGAAM_DIR)
                    except Exception as cleanup_exc:  # noqa: BLE001
                        logger.exception(
                            "GigaAM-v3: не удалось удалить повреждённый кэш {}: {}",
                            GIGAAM_DIR,
                            cleanup_exc,
                        )
    
                    GIGAAM_DIR.mkdir(parents=True, exist_ok=True)
                    from_kwargs["cache_dir"] = str(GIGAAM_DIR)
    
                    # После очистки кэша снова разрешаем сети скачать модель.
                    _load_model(local_files_only=False)
                    logger.info(
                        "GigaAM-v3: модель успешно перезаписана после очистки кэша {}",
                        GIGAAM_DIR,
                    )
                else:
                    # Не наш кейс — пробрасываем исключение выше.
                    raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load GigaAM-v3 model from {}: {}", GIGAAM_DIR, exc)
            raise RuntimeError("GigaAM-v3: ошибка загрузки модели.") from exc
    
        logger.info("GigaAM-v3 model loaded successfully from {}", GIGAAM_DIR)

    def transcribe(self, audio: AudioData) -> str:
        """
        Принимает AudioData и возвращает текст с пунктуацией.
    
        ВНИМАНИЕ:
        - официальный API модели ожидает путь к аудиофайлу;
        - локальный backend GigaAM-v3 в этом приложении ОБРАБАТЫВАЕТ ТОЛЬКО
          КОРОТКИЕ ЗАПИСИ (до ~25 секунд).
    
        Всё, что длиннее порога, НЕ отправляется в longform и не требует HF_TOKEN —
        вместо этого выбрасывается понятная ошибка, чтобы каскад перешёл на Groq/OpenAI.
        """
        import tempfile
        import soundfile as sf  # type: ignore[import]
        import numpy as np  # type: ignore[import]
    
        # 1) Проверяем длительность и сразу отсекаем слишком длинные записи.
        samples = audio.samples
        sample_rate = audio.sample_rate
    
        # Приводим к numpy для вычисления длины
        if isinstance(samples, np.ndarray):
            total_samples = samples.shape[0]
        else:
            samples = np.asarray(samples)
            total_samples = samples.shape[0]
    
        duration_sec = float(total_samples) / float(sample_rate or 1)
        LONGFORM_THRESHOLD_SEC = 25.0
    
        if duration_sec > LONGFORM_THRESHOLD_SEC:
            msg = (
                "GigaAM-v3: аудио длиннее 25 секунд. "
                "Локальный backend обрабатывает только короткие записи; "
                "для длинных используется облачный backend."
            )
            logger.error(msg + " duration_sec={}", duration_sec)
            raise RuntimeError(msg)
    
        # 2) Создаём временный WAV-файл и вызываем обычный transcribe().
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
                sample_rate,
                format="WAV",
            )
    
            try:
                # Официальный API: модель сама читает файл и делает всю обработку.
                # Используем ТОЛЬКО обычный .transcribe() без longform.
                transcription = self.model.transcribe(str(wav_path))
            except Exception as exc:  # noqa: BLE001
                logger.exception("GigaAM-v3 transcribe error: {}", exc)
                raise RuntimeError("GigaAM-v3: ошибка распознавания.") from exc
    
        if not isinstance(transcription, str):
            logger.error("GigaAM-v3 returned non-string transcription: {}", transcription)
            raise RuntimeError("GigaAM-v3: некорректный формат ответа.")
    
        return transcription or ""