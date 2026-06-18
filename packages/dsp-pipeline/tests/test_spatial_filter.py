"""Tests for spatial filters."""

from __future__ import annotations

import numpy as np

from spatial.car_filter import CARFilter
from spatial.csp_filter import CSPFilter
from spatial.laplacian_filter import LaplacianFilter


def _pairwise_correlation(signal: np.ndarray) -> float:
    channels = signal.shape[0]
    if channels < 2:
        return 0.0
    corr_sum = 0.0
    count = 0
    for i in range(channels):
        for j in range(i + 1, channels):
            corr_sum += np.corrcoef(signal[i], signal[j])[0, 1]
            count += 1
    return corr_sum / count


def test_car_reduces_cross_channel_correlation() -> None:
    rng = np.random.default_rng(0)
    common = rng.normal(size=100)
    channels = 8
    signal = np.stack([common + rng.normal(scale=0.2, size=100) for _ in range(channels)])
    raw_corr = _pairwise_correlation(signal)
    filtered = CARFilter().process(signal)
    car_corr = _pairwise_correlation(filtered)
    assert car_corr <= raw_corr * 0.9


def test_laplacian_changes_neighbor_channels() -> None:
    labels = ["Fp1", "Fp2", "F3", "F4", "C3", "C4"]
    signal = np.ones((6, 20))
    signal[4] = 10.0
    output = LaplacianFilter(labels).process(signal)
    assert not np.allclose(output[4], 10.0)


def test_csp_produces_fewer_channels() -> None:
    rng = np.random.default_rng(1)
    trials1 = rng.normal(size=(10, 8, 50))
    trials2 = rng.normal(size=(10, 8, 50))
    trials2[:, 0, :] += 5.0
    csp = CSPFilter(n_components=4)
    csp.fit_classes(trials1, trials2)
    output = csp.process(rng.normal(size=(8, 50)))
    assert output.shape[0] == 4
