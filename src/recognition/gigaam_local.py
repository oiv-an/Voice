from __future__ import annotations

import tempfile
from pathlib import Path

import gigaam  # type: ignore[import]
import soundfile as sf  # type: ignore[import]
from loguru import logger  # type: ignore[import]

from audio.recorder import AudioData


class GigaAMRecognizer:
    """
    Локальный распознаватель на базе GigaAM-v3-CTC (API: v2_ctc).

    Используется как backend "local" наряду с Groq и OpenAI.
    Интерфейс совместим с GroqWhisperRecognizer: метод transcribe(audio) -> str.
    """

    def __init__(self, model_name: str = "v2_ctc") -> None:
        import torch  # локальный импорт, чтобы не тянуть при импорте модуля

        self.model_name = model_name

        # Определяем, есть ли CUDA
        has_cuda = torch.cuda.is_available()
        device = "cuda" if has_cuda else "cpu"

        if has_cuda:
            logger.info("Loading GigaAM model: {} on GPU (cuda)", model_name)
        else:
            logger.info("Loading GigaAM model: {} on CPU (no CUDA detected)", model_name)

        # Модель автоматически скачивается при первом запуске.
        # Явно указываем device, чтобы при наличии CUDA использовать GPU.
        self.model = gigaam.load_model(
            model_name,
            device=device,
        )

    def transcribe(self, audio: AudioData) -> str:
        """
        Принимает AudioData (float32 numpy, 16kHz mono) и возвращает текст.

        Для надёжности пишем во временный WAV и даём путь модели.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "input.wav"

            # Сохраняем numpy → WAV (16kHz mono, PCM_16)
            sf.write(
                wav_path,
                audio.samples,
                audio.sample_rate,
                format="WAV",
                subtype="PCM_16",
            )

            try:
                text = self.model.transcribe(str(wav_path))
            except Exception as exc:  # noqa: BLE001
                logger.exception("GigaAM transcribe error: {}", exc)
                raise RuntimeError("GigaAM: ошибка распознавания.") from exc

        if not isinstance(text, str):
            logger.error("GigaAM returned non-string transcription: {}", text)
            raise RuntimeError("GigaAM: некорректный формат ответа.")

        return text or ""