"""P300 evoked response epoch averaging."""

from __future__ import annotations

import numpy as np

from base_operator import SignalOperator


class P300Averager(SignalOperator):
    """Accumulate stimulus-locked epochs and return running average."""

    def __init__(
        self,
        sample_rate_hz: float,
        epoch_start_sec: float = -0.1,
        epoch_end_sec: float = 0.8,
        num_averages: int = 15,
    ) -> None:
        super().__init__()
        self.sample_rate_hz = sample_rate_hz
        self.epoch_start_sec = epoch_start_sec
        self.epoch_end_sec = epoch_end_sec
        self.num_averages = num_averages
        self.pre_samples = int(round(-epoch_start_sec * sample_rate_hz))
        self.post_samples = int(round(epoch_end_sec * sample_rate_hz))
        self.epoch_length = self.pre_samples + self.post_samples
        self._epochs: list[np.ndarray] = []

    @property
    def operator_name(self) -> str:
        return "p300_averager"

    def fit(self, calibration_data: np.ndarray) -> None:
        return

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    def _process_impl(self, signal: np.ndarray) -> np.ndarray:
        average = self.get_average()
        if average is None:
            return np.zeros((signal.shape[0], 1), dtype=np.float64)
        return average

    def add_epoch(self, signal: np.ndarray, stimulus_onset_sample: int) -> bool:
        """Extract and store one epoch if boundaries are valid."""
        start = stimulus_onset_sample - self.pre_samples
        end = stimulus_onset_sample + self.post_samples
        if start < 0 or end > signal.shape[1]:
            return False
        epoch = signal[:, start:end].astype(np.float64, copy=True)
        self._epochs.append(epoch)
        if len(self._epochs) > self.num_averages:
            self._epochs.pop(0)
        return True

    def get_average(self) -> np.ndarray | None:
        if not self._epochs:
            return None
        return np.mean(self._epochs, axis=0)

    def reset(self) -> None:
        self._epochs.clear()
