"""DataRecorder round-trip tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from data_generator.device.data_recorder import DataRecorder
from data_generator.device.device_simulator import DeviceSimulator
from data_generator.device.simulator_config import SimulatorConfig
from data_generator.scenarios.scenario_library import SCENARIOS


@pytest.mark.asyncio
async def test_ndf_round_trip_bit_identical(tmp_path: Path) -> None:
    config = SimulatorConfig(
        scenario=SCENARIOS["motor_imagery_left"],
        num_channels=8,
        sample_rate_hz=160,
        samples_per_frame=10,
        duration_sec=0.3,
        random_seed=99,
    )
    simulator = DeviceSimulator(config)
    device_info = await simulator.connect()
    await simulator.start_recording()

    original_frames: list[dict] = []
    async for frame in simulator.frame_stream():
        original_frames.append(frame)

    await simulator.disconnect()

    ndf_path = tmp_path / "session.ndf"
    recorder = DataRecorder()
    session_metadata = {
        "sessionId": "test-session",
        "sessionName": "round-trip",
        "subjectId": "sim",
        "state": "active",
        "startedAtMs": 1_700_000_000_000,
        "endedAtMs": None,
        "totalFrames": 0,
        "droppedFrames": 0,
        "deviceInfo": device_info,
        "samplesPerFrame": config.samples_per_frame,
        "pipelineConfig": {},
        "notes": "",
        "neuroosVersion": "0.1.0",
    }
    recorder.start_recording(session_metadata, str(ndf_path))
    for frame in original_frames:
        recorder.write_frame(frame)
    recorder.stop_recording()

    replayed_frames: list[dict] = []
    async for frame in DataRecorder.replay(str(ndf_path), realtime=False):
        replayed_frames.append(frame)

    assert len(replayed_frames) == len(original_frames)

    with ndf_path.open("rb") as handle:
        raw_bytes = handle.read()

    for original, replayed in zip(original_frames, replayed_frames, strict=True):
        assert original == replayed

        for orig_ch, replay_ch in zip(original["channels"], replayed["channels"], strict=True):
            for orig_sample, replay_sample in zip(orig_ch, replay_ch, strict=True):
                assert orig_sample == replay_sample

    assert b"\r\n\r\n" in raw_bytes
    frames_path = ndf_path.with_suffix(ndf_path.suffix + ".frames")
    assert frames_path.exists()
    assert frames_path.read_text(encoding="ascii").strip()
