"""Event-related desynchronization/synchronization computation."""

from __future__ import annotations

import numpy as np

from constants.signal_bands import BAND_NAMES
from utils.ring_buffer import RingBuffer


class ERDComputer:
    """
    Track baseline band power and compute ERD/ERS relative to baseline.

    ERD(%) = (current - baseline) / baseline × 100
    Negative = desynchronization, positive = synchronization.
    """

    def __init__(self, baseline_sec: float = 2.0) -> None:
        self.baseline_sec = baseline_sec
        self._num_channels: int = 0
        self._baseline_frames: int = 1
        self._frames_seen = 0
        self._baseline_established = False
        self._baseline_powers: dict[str, np.ndarray] = {
            name: np.array([], dtype=np.float64) for name in BAND_NAMES
        }
        self._power_history: dict[str, RingBuffer] = {}

    def configure(
        self,
        num_channels: int,
        sample_rate_hz: float,
        samples_per_frame: int,
    ) -> None:
        self._num_channels = num_channels
        frame_rate = sample_rate_hz / samples_per_frame
        self._baseline_frames = max(1, int(round(self.baseline_sec * frame_rate)))
        self._frames_seen = 0
        self._power_history = {
            name: RingBuffer(self._baseline_frames, num_channels) for name in BAND_NAMES
        }
        self._baseline_established = False
        self._baseline_powers = {
            name: np.zeros(num_channels, dtype=np.float64) for name in BAND_NAMES
        }

    def update_baseline(self, band_powers: dict[str, np.ndarray]) -> None:
        """Accumulate band power vectors until baseline window is filled."""
        for name in BAND_NAMES:
            power = band_powers[name]
            if power.shape[0] != self._num_channels:
                continue
            self._power_history[name].append(power.reshape(-1, 1))

        self._frames_seen += 1
        if self._frames_seen >= self._baseline_frames and not self._baseline_established:
            for name in BAND_NAMES:
                window = self._power_history[name].get_window()
                self._baseline_powers[name] = window.mean(axis=1)
            self._baseline_established = True

    def compute(self, band_powers: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        erd: dict[str, np.ndarray] = {}
        for name in BAND_NAMES:
            current = band_powers[name]
            baseline = self._baseline_powers[name]
            if baseline.size == 0 or not self._baseline_established:
                erd[name] = np.zeros_like(current)
            else:
                erd[name] = (current - baseline) / (baseline + 1e-10) * 100.0
        return erd

    @property
    def baseline_established(self) -> bool:
        return self._baseline_established

    def force_baseline(self, band_powers: dict[str, np.ndarray]) -> None:
        """Set baseline directly (used after calibration period)."""
        for name in BAND_NAMES:
            self._baseline_powers[name] = band_powers[name].astype(np.float64, copy=True)
        self._baseline_established = True
