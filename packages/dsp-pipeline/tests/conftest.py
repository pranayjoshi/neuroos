"""Shared fixtures for DSP pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FEATURE_VECTOR_SCHEMA_PATH = (
    REPO_ROOT / "jobs" / "00_shared_contracts" / "json-schema" / "FeatureVector.schema.json"
)

STANDARD_16_LABELS = [
    "Fp1",
    "Fp2",
    "F3",
    "F4",
    "C3",
    "C4",
    "P3",
    "P4",
    "O1",
    "O2",
    "F7",
    "F8",
    "T3",
    "T4",
    "T5",
    "T6",
]


@pytest.fixture(scope="session")
def feature_vector_schema() -> dict:
    return json.loads(FEATURE_VECTOR_SCHEMA_PATH.read_text())


def make_test_frame(
    *,
    num_channels: int = 16,
    samples_per_frame: int = 10,
    sample_rate_hz: float = 160.0,
    frame_index: int = 0,
    calibrated: bool = True,
    channel_labels: list[str] | None = None,
    channels: np.ndarray | None = None,
    scenario: str | None = None,
    event_markers: list[dict] | None = None,
) -> dict:
    labels = channel_labels or STANDARD_16_LABELS[:num_channels]
    if channels is None:
        channels = np.random.default_rng(frame_index).normal(
            0.0, 5.0, size=(num_channels, samples_per_frame)
        )
    frame = {
        "deviceId": "test:mock:TEST-001",
        "frameIndex": frame_index,
        "timestampNs": str(1_000_000_000_000_000_000 + frame_index * 62_500_000),
        "signalType": "EEG",
        "channels": np.asarray(channels, dtype=np.float64).tolist(),
        "samplesPerFrame": samples_per_frame,
        "sampleRateHz": sample_rate_hz,
        "channelLabels": labels,
        "calibrated": calibrated,
    }
    if scenario is not None:
        frame["scenario"] = scenario
    if event_markers is not None:
        frame["eventMarkers"] = event_markers
    return frame


def synthesize_band_signal(
    sample_rate_hz: float,
    num_samples: int,
    frequency_hz: float,
    amplitude_uv: float,
    rng: np.random.Generator,
    noise_uv: float = 1.0,
) -> np.ndarray:
    t = np.arange(num_samples) / sample_rate_hz
    signal = amplitude_uv * np.sin(2.0 * np.pi * frequency_hz * t)
    signal += rng.normal(0.0, noise_uv, size=num_samples)
    return signal


def validate_feature_vector(result: dict, schema: dict) -> None:
    import jsonschema

    jsonschema.validate(result, schema)
