import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf
from loguru import logger

from audio.recorder import AudioData


class RecoveryManager:
    """
    Manages temporary audio files for crash recovery.
    
    Files are saved in `recovery/` directory relative to the application executable/script.
    Naming convention: `rec_{timestamp}_{duration}.wav`
    """

    def __init__(self, base_dir: Path):
        self.recovery_dir = base_dir / "recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)

    def save_audio(self, audio: AudioData) -> Path:
        """
        Saves AudioData to a WAV file in the recovery directory.
        Returns the path to the saved file.
        """
        timestamp = int(time.time() * 1000)
        duration = len(audio.samples) / audio.sample_rate
        filename = f"rec_{timestamp}_{duration:.2f}.wav"
        filepath = self.recovery_dir / filename

        try:
            sf.write(filepath, audio.samples, audio.sample_rate, format="WAV", subtype="PCM_16")
            logger.info(f"Audio saved for recovery: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save recovery audio: {e}")
            raise

    def load_audio(self, filepath: Path) -> Optional[AudioData]:
        """
        Loads AudioData from a WAV file.
        """
        try:
            data, sample_rate = sf.read(filepath, dtype="float32")
            # soundfile reads as (samples, channels) if channels > 1, or just (samples,) if mono.
            # AudioData expects (samples,) for mono or (samples, channels).
            # Our recorder usually produces mono or stereo.
            
            channels = 1
            if len(data.shape) > 1:
                channels = data.shape[1]
            
            return AudioData(samples=data, sample_rate=sample_rate, channels=channels)
        except Exception as e:
            logger.error(f"Failed to load recovery audio from {filepath}: {e}")
            return None

    def get_recovery_files(self) -> List[Path]:
        """
        Returns a list of all .wav files in the recovery directory, sorted by creation time (oldest first).
        """
        if not self.recovery_dir.exists():
            return []
        
        files = list(self.recovery_dir.glob("*.wav"))
        # Sort by modification time
        files.sort(key=lambda p: p.stat().st_mtime)
        return files

    def cleanup(self, filepath: Path):
        """
        Deletes the recovery file.
        """
        try:
            if filepath.exists():
                filepath.unlink()
                logger.info(f"Recovery file deleted: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete recovery file {filepath}: {e}")
