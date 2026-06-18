"""Artifact detection: EMG, ocular, saturation, and motion."""

from __future__ import annotations

from collections import deque

import numpy as np
from scipy.signal import welch

from base_operator import SignalOperator

ArtifactType = str | None


class ArtifactDetector(SignalOperator):
    """
    Detect contaminated frames without modifying the signal.

    Returns (signal_unchanged, artifact_flag, artifact_type).
    """

    def __init__(
        self,
        sample_rate_hz: float,
        emg_threshold_sd: float = 3.0,
        ocular_threshold_uv: float = 100.0,
        saturation_clip_uv: float = 400.0,
        motion_threshold_uv: float = 150.0,
        fp1_label: str = "Fp1",
        fp2_label: str = "Fp2",
        channel_labels: list[str] | None = None,
        history_size: int = 50,
    ) -> None:
        super().__init__()
        self.sample_rate_hz = sample_rate_hz
        self.emg_threshold_sd = emg_threshold_sd
        self.ocular_threshold_uv = ocular_threshold_uv
        self.saturation_clip_uv = saturation_clip_uv
        self.motion_threshold_uv = motion_threshold_uv
        self.fp1_label = fp1_label
        self.fp2_label = fp2_label
        self._channel_labels = channel_labels or []
        self._ratio_history: deque[float] = deque(maxlen=history_size)
        self._last_artifact_flag = False
        self._last_artifact_type: ArtifactType = None

    @property
    def operator_name(self) -> str:
        return "artifact_detector"

    def set_channel_labels(self, labels: list[str]) -> None:
        self._channel_labels = labels

    def fit(self, calibration_data: np.ndarray) -> None:
        return

    def process(self, signal: np.ndarray) -> np.ndarray:
        self._timed_process(lambda x: x, signal)
        return signal

    def detect(self, signal: np.ndarray) -> tuple[np.ndarray, bool, ArtifactType]:
        """Run all detectors; first positive result sets artifact_type."""
        flag, artifact_type = self._detect_impl(signal)
        self._last_artifact_flag = flag
        self._last_artifact_type = artifact_type
        return signal, flag, artifact_type

    def _detect_impl(self, signal: np.ndarray) -> tuple[bool, ArtifactType]:
        if self._detect_saturation(signal):
            return True, "saturation"
        if self._detect_ocular(signal):
            return True, "ocular"
        if self._detect_motion(signal):
            return True, "motion"
        if self._detect_emg(signal):
            return True, "emg"
        return False, None

    def _detect_saturation(self, signal: np.ndarray) -> bool:
        return bool(np.any(np.abs(signal) >= self.saturation_clip_uv))

    def _detect_ocular(self, signal: np.ndarray) -> bool:
        label_to_idx = {label: idx for idx, label in enumerate(self._channel_labels)}
        indices = []
        for label in (self.fp1_label, self.fp2_label):
            if label in label_to_idx:
                indices.append(label_to_idx[label])
        if not indices:
            return False
        fp_amplitude = float(np.abs(signal[indices]).max())
        return fp_amplitude > self.ocular_threshold_uv

    def _detect_motion(self, signal: np.ndarray) -> bool:
        peak_per_channel = np.abs(signal).max(axis=1)
        return bool(np.all(peak_per_channel > self.motion_threshold_uv))

    def _detect_emg(self, signal: np.ndarray) -> bool:
        nperseg = min(128, signal.shape[1])
        if nperseg < 8:
            return False

        freqs, psd = welch(signal, fs=self.sample_rate_hz, nperseg=nperseg, axis=1)
        emg_mask = (freqs >= 40.0) & (freqs <= 100.0)
        eeg_mask = (freqs >= 1.0) & (freqs <= 40.0)
        if not np.any(emg_mask) or not np.any(eeg_mask):
            return False

        emg_power = psd[:, emg_mask].mean(axis=1)
        eeg_power = psd[:, eeg_mask].mean(axis=1)
        ratio = emg_power / (eeg_power + 1e-10)
        max_ratio = float(ratio.max())

        if max_ratio > 5.0:
            return True

        if len(self._ratio_history) < 10:
            self._ratio_history.append(max_ratio)
            return False

        history = np.array(self._ratio_history, dtype=np.float64)
        mean = history.mean()
        std = history.std()
        threshold = mean + self.emg_threshold_sd * max(std, 1e-6)
        flagged = max_ratio > threshold
        if not flagged:
            self._ratio_history.append(max_ratio)
        return flagged
