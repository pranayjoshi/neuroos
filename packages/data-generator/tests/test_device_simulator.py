"""Device simulator timing and schema compliance tests."""

from __future__ import annotations

import asyncio
import time

import pytest

from data_generator.device.device_simulator import DeviceSimulator
from data_generator.device.simulator_config import SimulatorConfig
from data_generator.scenarios.scenario_library import SCENARIOS


@pytest.mark.asyncio
async def test_frame_stream_timing_and_schema(schema_validator) -> None:
    sample_rate_hz = 256
    samples_per_frame = 16
    expected_period_ms = 1000.0 * samples_per_frame / sample_rate_hz
    duration_sec = 0.5

    config = SimulatorConfig(
        scenario=SCENARIOS["rest"],
        num_channels=8,
        sample_rate_hz=sample_rate_hz,
        samples_per_frame=samples_per_frame,
        duration_sec=duration_sec,
        random_seed=11,
    )
    simulator = DeviceSimulator(config)
    await simulator.connect()
    await simulator.start_recording()

    timestamps: list[float] = []
    frames: list[dict] = []

    async for frame in simulator.frame_stream():
        timestamps.append(time.perf_counter())
        frames.append(frame)

    await simulator.disconnect()

    assert len(frames) >= 3
    for frame in frames:
        schema_validator.validate(frame)

    intervals_ms = [
        (timestamps[i] - timestamps[i - 1]) * 1000.0 for i in range(1, len(timestamps))
    ]
    for interval_ms in intervals_ms:
        assert abs(interval_ms - expected_period_ms) <= 5.0, (
            f"Frame interval {interval_ms:.2f} ms outside ±5 ms of {expected_period_ms:.2f} ms"
        )
