"""EMG artifact injection for EEG frames."""

from __future__ import annotations

import math

import numpy as np

from data_generator.constants import EMG_AMPLITUDE_RANGE_UV


class EMGGenerator:
    """Inject muscle artifact bursts into EEG frames."""

    def __init__(
        self,
        affected_channels: list[int],
        burst_probability: float = 0.1,
        amplitude_uv: tuple[float, float] = (200, 2000),
        *,
        sample_rate_hz: int = 160,
        random_seed: int | None = None,
    ) -> None:
        if not 0.0 <= burst_probability <= 1.0:
            raise ValueError("burst_probability must be between 0 and 1")

        self.affected_channels = list(affected_channels)
        self.burst_probability = burst_probability
        self.amplitude_uv = amplitude_uv
        self.sample_rate_hz = sample_rate_hz
        self._rng = np.random.default_rng(random_seed)
        self._burst_count = 0
        self._frame_count = 0

    @property
    def burst_rate(self) -> float:
        if self._frame_count == 0:
            return 0.0
        return self._burst_count / self._frame_count

    def _emg_waveform(self, n_samples: int, amplitude: float) -> np.ndarray:
        t = np.arange(n_samples, dtype=np.float64) / self.sample_rate_hz
        nyquist = self.sample_rate_hz / 2.0
        low_hz = max(20.0, nyquist * 0.35)
        high_hz = min(500.0, nyquist * 0.95)
        freqs = self._rng.uniform(low_hz, high_hz, size=3)
        phases = self._rng.uniform(0.0, 2.0 * math.pi, size=3)
        waveform = np.zeros(n_samples, dtype=np.float64)
        for freq, phase in zip(freqs, phases, strict=True):
            waveform += np.sin(2.0 * math.pi * freq * t + phase)
        waveform /= max(float(np.max(np.abs(waveform))), 1e-9)

        envelope = np.exp(-((t - t[-1] * 0.5) ** 2) / (2.0 * (0.02**2)))
        return amplitude * waveform * envelope

    def apply_artifact(self, frame: dict, frame_index: int) -> dict:
        """Inject EMG artifact into an existing EEG frame in-place."""
        self._frame_count += 1
        if self._rng.random() >= self.burst_probability:
            return frame

        self._burst_count += 1
        channels = frame["channels"]
        n_samples = frame["samplesPerFrame"]
        low, high = self.amplitude_uv
        low = max(low, EMG_AMPLITUDE_RANGE_UV[0])
        high = min(high, EMG_AMPLITUDE_RANGE_UV[1])
        amplitude = float(self._rng.uniform(low, high))

        for ch_idx in self.affected_channels:
            if ch_idx >= len(channels):
                continue
            burst = self._emg_waveform(n_samples, amplitude)
            peak = float(np.max(np.abs(burst)))
            if peak > 0.0 and peak < amplitude:
                burst = burst * (amplitude / peak)
            channels[ch_idx] = [a + b for a, b in zip(channels[ch_idx], burst, strict=True)]

        return frame
