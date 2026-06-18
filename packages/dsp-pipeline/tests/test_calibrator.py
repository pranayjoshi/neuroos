"""Tests for the Calibrator operator."""

from __future__ import annotations

import numpy as np

from calibration.calibrator import Calibrator


def test_calibrator_converts_ad_units_to_microvolts() -> None:
    calibrator = Calibrator(gain_uv_per_unit=2.0, offset_uv=1.0)
    raw = np.array([[0.0, 1.0], [2.0, 3.0]])
    output = calibrator.process(raw, already_calibrated=False)
    assert np.allclose(output, [[1.0, 3.0], [5.0, 7.0]])


def test_calibrator_removes_dc_baseline() -> None:
    calibrator = Calibrator(gain_uv_per_unit=1.0, offset_uv=0.0, baseline_window_sec=0.5)
    calibrator.configure(sample_rate_hz=160.0, num_channels=1)
    signal = np.full((1, 10), 50.0)
    output = calibrator.process(signal, already_calibrated=True)
    assert np.allclose(output, 0.0, atol=1e-6)


def test_calibrator_fit_accepts_calibration_data() -> None:
    calibrator = Calibrator()
    data = np.random.randn(4, 100)
    calibrator.fit(data)
