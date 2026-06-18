"""Tests for feature extraction helpers."""

from __future__ import annotations

import numpy as np
import pytest

from features.band_power import compute_band_powers
from features.erd_computer import ERDComputer


def test_compute_band_powers_returns_all_bands() -> None:
    freqs = np.linspace(0, 100, 256)
    psd = np.ones((3, len(freqs)))
    powers = compute_band_powers(psd, freqs)
    assert set(powers.keys()) == {"delta", "theta", "alpha", "beta", "gamma", "high_gamma"}
    assert powers["alpha"].shape == (3,)


def test_erd_computer_reports_desynchronization() -> None:
    erd = ERDComputer(baseline_sec=1.0)
    erd.configure(num_channels=2, sample_rate_hz=160.0, samples_per_frame=10)
    baseline = {name: np.array([100.0, 100.0]) for name in erd._baseline_powers}
    erd.force_baseline(baseline)
    current = {name: np.array([70.0, 100.0]) for name in baseline}
    result = erd.compute(current)
    assert result["alpha"][0] == pytest.approx(-30.0)
    assert result["alpha"][1] == pytest.approx(0.0)
