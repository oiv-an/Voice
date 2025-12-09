from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import sounddevice as sd  # type: ignore[import]

from config.settings import AudioConfig


@dataclass
class AudioData:
    samples: np.ndarray
    sample_rate: int
    channels: int


class AudioRecorder:
    """
    Simple audio recorder for MVP using sounddevice.

    - Starts recording on start()
    - Stops on stop() or when max_duration reached
    - Returns AudioData via callback
    """

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cancel_event = threading.Event()
        self._on_finished: Optional[Callable[[AudioData], None]] = None

    # ------------------------------------------------------------------ public

    def start(self, on_finished: Callable[[AudioData], None]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._on_finished = on_finished
        self._stop_event.clear()
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._stop_event.set()

    # ---------------------------------------------------------------- internal

    def _record_loop(self) -> None:
        sample_rate = self._config.sample_rate
        channels = self._config.channels
        max_duration = self._config.max_duration

        frames: list[np.ndarray] = []
        start_time = time.time()

        def callback(indata, frames_count, time_info, status):  # type: ignore[no-untyped-def]
            if self._stop_event.is_set() or self._cancel_event.is_set():
                raise sd.CallbackStop()
            frames.append(indata.copy())

        try:
            device = self._config.device
            if device == "default":
                device = None

            with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                callback=callback,
                device=device,
            ):
                while not self._stop_event.is_set():
                    if time.time() - start_time >= max_duration:
                        self._stop_event.set()
                        break
                    time.sleep(0.05)
        except sd.PortAudioError:
            # In MVP we silently ignore and do nothing; later we can log and notify UI
            return

        if self._cancel_event.is_set():
            return

        if not frames:
            return

        data = np.concatenate(frames, axis=0)
        audio = AudioData(samples=data, sample_rate=sample_rate, channels=channels)

        if self._on_finished:
            self._on_finished(audio)