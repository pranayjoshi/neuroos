"""Tests for artifact detection."""

from __future__ import annotations

import numpy as np

from artifact.artifact_detector import ArtifactDetector
from conftest import STANDARD_16_LABELS, synthesize_band_signal


def _detector() -> ArtifactDetector:
    return ArtifactDetector(
        sample_rate_hz=160.0,
        emg_threshold_sd=2.5,
        channel_labels=STANDARD_16_LABELS,
    )


def test_detects_saturation() -> None:
    detector = _detector()
    signal = np.zeros((16, 10))
    signal[0, 0] = 450.0
    _, flag, artifact_type = detector.detect(signal)
    assert flag is True
    assert artifact_type == "saturation"


def test_detects_ocular_artifact() -> None:
    detector = _detector()
    signal = np.zeros((16, 10))
    signal[0] = 150.0
    _, flag, artifact_type = detector.detect(signal)
    assert flag is True
    assert artifact_type == "ocular"


def test_emg_detection_sensitivity_and_specificity() -> None:
    detector = _detector()
    rng = np.random.default_rng(42)

    for _ in range(20):
        clean = rng.normal(0.0, 5.0, size=(16, 256))
        detector.detect(clean)

    clean_hits = 0
    emg_hits = 0

    for _ in range(100):
        clean = rng.normal(0.0, 5.0, size=(16, 256))
        _, flag, _ = detector.detect(clean)
        if flag:
            clean_hits += 1

    for _ in range(100):
        clean = rng.normal(0.0, 5.0, size=(16, 256))
        emg = synthesize_band_signal(160.0, 256, 70.0, amplitude_uv=120.0, rng=rng)
        contaminated = clean.copy()
        contaminated[5] += emg
        contaminated[6] += emg
        _, flag, artifact_type = detector.detect(contaminated)
        if flag and artifact_type == "emg":
            emg_hits += 1

    assert emg_hits >= 90
    assert clean_hits <= 10
