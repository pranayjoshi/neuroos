"""Fixed-capacity ring buffer for multi-channel signal windows."""

from __future__ import annotations

import numpy as np


class RingBuffer:
    """Store the most recent samples per channel without unbounded growth."""

    def __init__(self, capacity: int, num_channels: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._num_channels = num_channels
        self._buffer = np.zeros((num_channels, capacity), dtype=np.float64)
        self._size = 0
        self._write_pos = 0

    @property
    def size(self) -> int:
        return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    def reset(self, num_channels: int | None = None) -> None:
        if num_channels is not None and num_channels != self._num_channels:
            self._num_channels = num_channels
            self._buffer = np.zeros((num_channels, self._capacity), dtype=np.float64)
        else:
            self._buffer.fill(0.0)
        self._size = 0
        self._write_pos = 0

    def append(self, frame: np.ndarray) -> None:
        """Append [channels, samples] in chronological order."""
        if frame.ndim != 2:
            raise ValueError("frame must be 2-D [channels, samples]")
        channels, samples = frame.shape
        if channels != self._num_channels:
            self.reset(channels)

        for sample_idx in range(samples):
            self._buffer[:, self._write_pos] = frame[:, sample_idx]
            self._write_pos = (self._write_pos + 1) % self._capacity
            self._size = min(self._size + 1, self._capacity)

    def get_window(self) -> np.ndarray:
        """Return stored samples in chronological order [channels, size]."""
        if self._size == 0:
            return np.empty((self._num_channels, 0), dtype=np.float64)

        if self._size < self._capacity:
            return self._buffer[:, : self._size].copy()

        start = self._write_pos
        if start == 0:
            return self._buffer.copy()
        return np.concatenate(
            (self._buffer[:, start:], self._buffer[:, :start]),
            axis=1,
        )
