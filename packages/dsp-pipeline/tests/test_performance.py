"""Processing latency budget tests."""

from __future__ import annotations

import time

import numpy as np

from config import DSPConfig
from conftest import make_test_frame
from pipeline import Pipeline


def test_mean_processing_latency_under_5ms() -> None:
    config = DSPConfig.default()
    config.enforce_latency = False
    pipeline = Pipeline(config)
    latencies_ms: list[float] = []

    for frame_index in range(1000):
        frame = make_test_frame(
            frame_index=frame_index,
            sample_rate_hz=160.0,
            samples_per_frame=10,
            num_channels=16,
        )
        start = time.perf_counter_ns()
        pipeline.process(frame)
        latencies_ms.append((time.perf_counter_ns() - start) / 1_000_000.0)

    mean_latency = float(np.mean(latencies_ms))
    assert mean_latency < 5.0, f"mean latency {mean_latency:.3f} ms exceeds 5 ms budget"
