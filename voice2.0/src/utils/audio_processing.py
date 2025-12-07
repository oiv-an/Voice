import numpy as np
from audio.recorder import AudioData
from loguru import logger

def speed_up_audio(audio: AudioData, factor: float = 2.0) -> AudioData:
    """
    Speeds up audio by the given factor using simple decimation (dropping samples).
    WARNING: This increases pitch (chipmunk effect).
    """
    if factor <= 1.0:
        return audio

    try:
        # Simple decimation: take every Nth sample
        # factor = 2.0 -> take every 2nd sample
        step = int(factor)
        if step < 1:
            step = 1
            
        # If factor is not an integer, this is an approximation.
        # For factor=2.0, step=2.
        
        # Better approach for non-integer factors:
        # indices = np.arange(0, len(audio.samples), factor)
        # indices = indices.astype(int)
        # new_samples = audio.samples[indices]
        
        # Using integer step for simplicity and performance if factor is integer-ish
        if abs(factor - round(factor)) < 0.01:
            new_samples = audio.samples[::int(round(factor))]
        else:
            indices = np.arange(0, len(audio.samples), factor).astype(int)
            # Ensure indices are within bounds
            indices = indices[indices < len(audio.samples)]
            new_samples = audio.samples[indices]

        logger.info(f"Audio speed up x{factor}: {len(audio.samples)} -> {len(new_samples)} samples")
        
        return AudioData(
            samples=new_samples,
            sample_rate=audio.sample_rate,
            channels=audio.channels
        )
    except Exception as e:
        logger.error(f"Failed to speed up audio: {e}")
        return audio