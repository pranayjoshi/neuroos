"""End-to-end pipeline tests."""

from __future__ import annotations

import numpy as np

from config import DSPConfig
from conftest import STANDARD_16_LABELS, make_test_frame, validate_feature_vector
from pipeline import Pipeline


def _pipeline(*, enforce_latency: bool = False) -> Pipeline:
    config = DSPConfig.default()
    config.enforce_latency = enforce_latency
    return Pipeline(config)


def test_pipeline_produces_feature_vector(feature_vector_schema: dict) -> None:
    pipeline = _pipeline()
    frame = make_test_frame()
    result = pipeline.process(frame)
    assert "vectorId" in result
    assert "bandPowers" in result
    assert "alpha" in result["bandPowers"]
    assert result["artifactFlag"] in (True, False)
    validate_feature_vector(result, feature_vector_schema)


def test_motor_imagery_left_alpha_erd_at_c4(feature_vector_schema: dict) -> None:
    pipeline = _pipeline()
    sample_rate = 160.0
    samples_per_frame = 10
    rng = np.random.default_rng(99)
    c4_idx = STANDARD_16_LABELS.index("C4")
    num_channels = len(STANDARD_16_LABELS)

    def build_frame(frame_index: int, *, alpha_amplitude: float, scenario: str) -> dict:
        num_samples = samples_per_frame
        t = np.arange(num_samples) / sample_rate
        channels = rng.normal(0.0, 1.0, size=(num_channels, num_samples))
        alpha = alpha_amplitude * np.sin(2.0 * np.pi * 10.0 * t)
        channels[c4_idx] += alpha
        return make_test_frame(
            frame_index=frame_index,
            channels=channels,
            scenario=scenario,
            sample_rate_hz=sample_rate,
            samples_per_frame=samples_per_frame,
        )

    rest_erd_values: list[float] = []
    imagery_erd_values: list[float] = []

    for i in range(40):
        result = pipeline.process(build_frame(i, alpha_amplitude=20.0, scenario="rest"))
        validate_feature_vector(result, feature_vector_schema)
        if i >= 32:
            rest_erd_values.append(result["erd"]["alpha"][c4_idx])

    for i in range(40, 70):
        result = pipeline.process(
            build_frame(i, alpha_amplitude=4.0, scenario="motor_imagery_left")
        )
        validate_feature_vector(result, feature_vector_schema)
        imagery_erd_values.append(result["erd"]["alpha"][c4_idx])

    assert rest_erd_values
    assert imagery_erd_values
    mean_rest = float(np.mean(rest_erd_values))
    mean_imagery = float(np.mean(imagery_erd_values[-10:]))
    assert mean_imagery <= -15.0
    assert mean_imagery < mean_rest


def test_pipeline_calibrate_accepts_frames() -> None:
    pipeline = _pipeline()
    frames = [make_test_frame(frame_index=i) for i in range(5)]
    pipeline.calibrate(frames)
    result = pipeline.process(make_test_frame(frame_index=10))
    assert result["bandPowers"]["alpha"]
