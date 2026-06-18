"""Small Laplacian spatial filter."""

from __future__ import annotations

import numpy as np

from base_operator import SignalOperator

STANDARD_ADJACENCY: dict[str, list[str]] = {
    "Fp1": ["Fp2", "F3", "F7"],
    "Fp2": ["Fp1", "F4", "F8"],
    "F3": ["Fp1", "F4", "C3", "F7"],
    "F4": ["Fp2", "F3", "C4", "F8"],
    "C3": ["F3", "C4", "P3", "T3"],
    "C4": ["F4", "C3", "P4", "T4"],
    "P3": ["C3", "P4", "O1", "T5"],
    "P4": ["C4", "P3", "O2", "T6"],
    "O1": ["P3", "O2", "T5"],
    "O2": ["P4", "O1", "T6"],
    "F7": ["Fp1", "F3", "T3"],
    "F8": ["Fp2", "F4", "T4"],
    "T3": ["F7", "C3", "T5"],
    "T4": ["F8", "C4", "T6"],
    "T5": ["T3", "P3", "O1"],
    "T6": ["T4", "P4", "O2"],
    "Cz": ["Fz", "C3", "C4", "Pz"],
    "Fz": ["Fp1", "Fp2", "F3", "F4", "Cz"],
    "Pz": ["P3", "P4", "O1", "O2", "Cz"],
}


class LaplacianFilter(SignalOperator):
    """Subtract weighted average of surrounding channels for each electrode."""

    def __init__(self, channel_labels: list[str] | None = None) -> None:
        super().__init__()
        self._channel_labels = channel_labels or []
        self._adjacency: dict[int, list[int]] = {}
        self._rebuild_adjacency()

    @property
    def operator_name(self) -> str:
        return "laplacian_filter"

    def set_channel_labels(self, labels: list[str]) -> None:
        self._channel_labels = labels
        self._rebuild_adjacency()

    def _rebuild_adjacency(self) -> None:
        label_to_idx = {label: idx for idx, label in enumerate(self._channel_labels)}
        self._adjacency = {}
        for ch_idx, label in enumerate(self._channel_labels):
            neighbors = STANDARD_ADJACENCY.get(label, [])
            neighbor_indices = [label_to_idx[n] for n in neighbors if n in label_to_idx]
            if neighbor_indices:
                self._adjacency[ch_idx] = neighbor_indices

    def fit(self, calibration_data: np.ndarray) -> None:
        return

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    def _process_impl(self, signal: np.ndarray) -> np.ndarray:
        output = signal.copy()
        for ch_idx, neighbor_indices in self._adjacency.items():
            output[ch_idx] -= signal[neighbor_indices].mean(axis=0)
        return output
