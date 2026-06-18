"""Multi-channel EEG signal synthesis."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from scipy.linalg import cholesky

from data_generator.constants import (
    CHANNEL_LABELS_16,
    CHANNEL_LABELS_64,
    CHANNEL_LABELS_8,
    DEFAULT_DEVICE_ID,
    EEG_AMPLITUDE_RANGE_UV,
    HIGH_CORRELATION_PAIRS,
    SIGNAL_BANDS,
)
from data_generator.scenarios.scenario_library import resolve_active_scenario

if TYPE_CHECKING:
    from data_generator.scenarios.scenario import Scenario

VALID_CHANNEL_COUNTS = {8, 16, 64}

# Scenario band amplitude multipliers (alpha, beta) relative to baseline.
_SCENARIO_BAND_SCALE: dict[str, dict[str, tuple[float, float]]] = {
    "rest": {"default": (1.0, 0.7)},
    "motor_imagery_left": {
        "C3": (1.15, 0.85),
        "C4": (0.70, 0.75),
        "default": (1.0, 0.7),
    },
    "motor_imagery_right": {
        "C3": (0.70, 0.75),
        "C4": (1.15, 0.85),
        "default": (1.0, 0.7),
    },
    "p300_target": {"default": (1.0, 0.7)},
    "artifact_heavy": {"default": (1.0, 0.7)},
    "mixed_sequence": {"default": (1.0, 0.7)},
}


def _labels_for_count(num_channels: int) -> list[str]:
    if num_channels == 8:
        return list(CHANNEL_LABELS_8)
    if num_channels == 16:
        return list(CHANNEL_LABELS_16)
    if num_channels == 64:
        return list(CHANNEL_LABELS_64)
    raise ValueError(f"num_channels must be one of {sorted(VALID_CHANNEL_COUNTS)}")


def nearest_posdef(matrix: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Project a symmetric matrix to the nearest positive-definite matrix."""
    sym = (matrix + matrix.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = np.maximum(eigvals, eps)
    return (eigvecs * eigvals) @ eigvecs.T


def _build_spatial_covariance(labels: list[str]) -> np.ndarray:
    n = len(labels)
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    cov = np.eye(n, dtype=np.float64)

    for left, right in HIGH_CORRELATION_PAIRS:
        if left in label_to_idx and right in label_to_idx:
            i, j = label_to_idx[left], label_to_idx[right]
            cov[i, j] = 0.8
            cov[j, i] = 0.8

    for i in range(n):
        for j in range(i + 1, n):
            if cov[i, j] == 0.0:
                same_region = labels[i][0] == labels[j][0]
                cov[i, j] = cov[j, i] = 0.35 if same_region else 0.1

    return nearest_posdef(cov)


def _p300_component(t_sec: float, onset_sec: float, amplitude_uv: float = 10.0) -> float:
    sigma = 0.075
    return amplitude_uv * math.exp(-0.5 * ((t_sec - onset_sec) / sigma) ** 2)


class EEGGenerator:
    """Synthesize multi-channel EEG frames for BCI scenarios."""

    def __init__(
        self,
        num_channels: int,
        sample_rate_hz: int,
        channel_labels: list[str],
        snr_db: float = 10.0,
        random_seed: int | None = None,
        *,
        samples_per_frame: int = 10,
        device_id: str = DEFAULT_DEVICE_ID,
    ) -> None:
        if num_channels not in VALID_CHANNEL_COUNTS:
            raise ValueError(f"num_channels must be one of {sorted(VALID_CHANNEL_COUNTS)}")
        if sample_rate_hz not in (160, 256):
            raise ValueError("sample_rate_hz must be 160 or 256")
        if len(channel_labels) != num_channels:
            raise ValueError("channel_labels length must match num_channels")

        self.num_channels = num_channels
        self.sample_rate_hz = sample_rate_hz
        self.channel_labels = list(channel_labels)
        self.snr_db = snr_db
        self.samples_per_frame = samples_per_frame
        self.device_id = device_id

        self._rng = np.random.default_rng(random_seed)
        self._cov = _build_spatial_covariance(self.channel_labels)
        self._mixing = cholesky(self._cov, lower=True)

        self._ar_state = np.zeros(num_channels, dtype=np.float64)
        self._ar_coeff = 0.97
        self._band_phases = self._rng.uniform(0.0, 2.0 * math.pi, size=(num_channels, len(SIGNAL_BANDS)))

        self._label_to_idx = {label: idx for idx, label in enumerate(self.channel_labels)}
        self._session_start_ns = int(self._rng.integers(1_700_000_000_000_000_000, 1_800_000_000_000_000_000))

    @classmethod
    def from_channel_count(
        cls,
        num_channels: int,
        sample_rate_hz: int = 160,
        snr_db: float = 10.0,
        random_seed: int | None = None,
        **kwargs: object,
    ) -> EEGGenerator:
        labels = _labels_for_count(num_channels)
        return cls(num_channels, sample_rate_hz, labels, snr_db, random_seed, **kwargs)

    def _band_scale(self, scenario_type: str, label: str) -> tuple[float, float]:
        scales = _SCENARIO_BAND_SCALE.get(scenario_type, _SCENARIO_BAND_SCALE["rest"])
        return scales.get(label, scales["default"])

    def _generate_pink_noise_block(self, n_samples: int) -> np.ndarray:
        """AR(1) pink noise per channel, spatially mixed."""
        raw = np.zeros((self.num_channels, n_samples), dtype=np.float64)
        for sample_idx in range(n_samples):
            innovation = self._rng.standard_normal(self.num_channels)
            self._ar_state = self._ar_coeff * self._ar_state + innovation
            raw[:, sample_idx] = self._ar_state

        return self._mixing @ raw

    def _synthesize_block(
        self,
        active: Scenario,
        frame_index: int,
    ) -> np.ndarray:
        n_samples = self.samples_per_frame
        start_sample = frame_index * n_samples
        t = (start_sample + np.arange(n_samples, dtype=np.float64)) / self.sample_rate_hz

        pink = self._generate_pink_noise_block(n_samples)
        signal = np.zeros((self.num_channels, n_samples), dtype=np.float64)

        band_names = list(SIGNAL_BANDS.keys())[:5]
        base_alpha_uv = 15.0
        base_beta_uv = 6.0

        for ch_idx, label in enumerate(self.channel_labels):
            alpha_scale, beta_scale = self._band_scale(active.scenario_type, label)

            for band_idx, band_name in enumerate(band_names):
                band = SIGNAL_BANDS[band_name]
                freq = band.center_hz
                phase = self._band_phases[ch_idx, band_idx]

                if band_name == "alpha":
                    amp = base_alpha_uv * alpha_scale
                elif band_name == "beta":
                    amp = base_beta_uv * beta_scale
                elif band_name == "delta":
                    amp = 8.0
                elif band_name == "theta":
                    amp = 5.0
                else:
                    amp = 2.5

                signal[ch_idx] += amp * np.sin(2.0 * math.pi * freq * t + phase)

            if active.scenario_type == "p300_target" and active.stimulus_onset_sec is not None:
                if label in ("Pz", "Cz"):
                    p300_peak = active.stimulus_onset_sec + 0.3
                    topo_scale = 1.0 if label == "Pz" else 0.5
                    signal[ch_idx] += topo_scale * np.array(
                        [_p300_component(ts, p300_peak) for ts in t],
                        dtype=np.float64,
                    )

        combined = signal + pink

        signal_power = float(np.mean(signal**2))
        noise_power = float(np.mean(pink**2))
        if noise_power > 0.0 and signal_power > 0.0:
            target_ratio = 10.0 ** (self.snr_db / 10.0)
            current_ratio = signal_power / noise_power
            pink *= math.sqrt(signal_power / (target_ratio * noise_power)) if current_ratio > 0 else 1.0
            combined = signal + pink

        white = self._rng.standard_normal((self.num_channels, n_samples)) * 0.5
        combined += white

        min_uv, max_uv = EEG_AMPLITUDE_RANGE_UV
        peak = float(np.max(np.abs(combined))) or 1.0
        target_peak = min(max_uv * 0.4, max(min_uv * 10.0, peak))
        combined *= target_peak / peak

        return combined.astype(np.float64)

    def generate_frame(self, scenario: Scenario, frame_index: int) -> dict:
        """Synthesize one RawSignalFrame-compatible dict."""
        elapsed_sec = frame_index * self.samples_per_frame / self.sample_rate_hz
        active = resolve_active_scenario(scenario, elapsed_sec)
        block = self._synthesize_block(active, frame_index)

        period_ns = int(round(1e9 * self.samples_per_frame / self.sample_rate_hz))
        timestamp_ns = str(self._session_start_ns + frame_index * period_ns)

        channels = [[float(v) for v in block[ch]] for ch in range(self.num_channels)]

        return {
            "deviceId": self.device_id,
            "frameIndex": frame_index,
            "timestampNs": timestamp_ns,
            "signalType": "EEG",
            "channels": channels,
            "samplesPerFrame": self.samples_per_frame,
            "sampleRateHz": float(self.sample_rate_hz),
            "channelLabels": list(self.channel_labels),
            "calibrated": True,
        }
