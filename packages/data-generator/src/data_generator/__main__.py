"""
Entry point: python -m data_generator

Streams JSONL RawSignalFrame dicts to stdout for downstream NeuroOS services.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

import click
import yaml

from data_generator.constants import DEFAULT_DEVICE_ID
from data_generator.device.data_recorder import DataRecorder
from data_generator.device.device_simulator import DeviceSimulator
from data_generator.device.simulator_config import SimulatorConfig
from data_generator.generators.eeg_generator import _labels_for_count
from data_generator.scenarios.scenario_library import SCENARIOS


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "default_config.yaml"


def _load_config(config_path: Path | None) -> dict:
    path = config_path or _default_config_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _build_session_metadata(config: SimulatorConfig, device_info: dict) -> dict:
    return {
        "sessionId": str(uuid.uuid4()),
        "sessionName": config.scenario.label,
        "subjectId": "sim-subject-001",
        "state": "active",
        "startedAtMs": 0,
        "endedAtMs": None,
        "totalFrames": 0,
        "droppedFrames": 0,
        "deviceInfo": device_info,
        "samplesPerFrame": config.samples_per_frame,
        "pipelineConfig": {
            "dsp": {
                "spatialFilterType": "car",
                "temporalFilterType": "bandpass_fir",
                "bandpassHz": [0.5, 40.0],
                "windowLengthSec": 1.0,
                "windowStepSec": 0.25,
            },
            "intent": {
                "classifierType": "csp_lda",
                "modelPath": None,
                "inferenceRateHz": 4.0,
                "confidenceThreshold": 0.6,
            },
            "paradigm": {
                "type": "motor_imagery",
                "trialLengthSec": config.scenario.duration_sec,
                "itiSec": 1.0,
            },
        },
        "notes": "",
        "neuroosVersion": "0.1.0",
    }


async def _run_simulation(
    config: SimulatorConfig,
    *,
    record_path: str | None = None,
) -> None:
    simulator = DeviceSimulator(config)
    device_info = await simulator.connect()
    await simulator.start_recording()

    recorder: DataRecorder | None = None
    if record_path is not None:
        recorder = DataRecorder()
        recorder.start_recording(_build_session_metadata(config, device_info), record_path)

    async for frame in simulator.frame_stream():
        sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        if recorder is not None:
            recorder.write_frame(frame)

    await simulator.stop_recording()
    await simulator.disconnect()

    if recorder is not None:
        recorder.stop_recording()


async def _run_replay(ndf_path: str, realtime: bool) -> None:
    async for frame in DataRecorder.replay(ndf_path, realtime=realtime):
        sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
        sys.stdout.flush()


@click.command()
@click.option("--scenario", default="rest", help="Scenario key from the scenario library.")
@click.option(
    "--channels",
    "num_channels",
    default="16",
    type=click.Choice(["8", "16", "64"], case_sensitive=False),
)
@click.option("--duration", "duration_sec", default=None, type=float, help="Duration in seconds.")
@click.option("--sample-rate", "sample_rate_hz", default=None, type=click.Choice(["160", "256"]))
@click.option("--replay", "replay_path", default=None, type=click.Path(exists=True))
@click.option("--list-scenarios", is_flag=True, help="List available scenarios and exit.")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True))
@click.option("--record", "record_path", default=None, type=click.Path())
@click.option("--seed", "random_seed", default=None, type=int)
def main(
    scenario: str,
    num_channels: str,
    duration_sec: float | None,
    sample_rate_hz: str | None,
    replay_path: str | None,
    list_scenarios: bool,
    config_path: str | None,
    record_path: str | None,
    random_seed: int | None,
) -> None:
    """NeuroOS EEG/EMG dummy data generator."""
    if list_scenarios:
        for key, item in SCENARIOS.items():
            click.echo(f"{key}: {item.label} ({item.duration_sec}s)")
        return

    if replay_path is not None:
        asyncio.run(_run_replay(replay_path, realtime=True))
        return

    file_config = _load_config(Path(config_path) if config_path else None)
    scenario_key = scenario or file_config.get("scenario", "rest")
    if scenario_key not in SCENARIOS:
        raise click.ClickException(f"Unknown scenario: {scenario_key}")

    resolved_channels = int(num_channels or file_config.get("num_channels", 16))
    resolved_rate = int(sample_rate_hz or file_config.get("sample_rate_hz", 160))
    samples_per_frame = int(file_config.get("samples_per_frame", 10 if resolved_rate == 160 else 16))
    resolved_duration = duration_sec
    if resolved_duration is None:
        resolved_duration = file_config.get("duration_sec", SCENARIOS[scenario_key].duration_sec)

    labels = file_config.get("channel_labels")
    if labels is None:
        labels = _labels_for_count(resolved_channels)
    elif resolved_channels != len(labels):
        labels = _labels_for_count(resolved_channels)

    config = SimulatorConfig(
        scenario=SCENARIOS[scenario_key],
        num_channels=resolved_channels,
        sample_rate_hz=resolved_rate,
        samples_per_frame=samples_per_frame,
        channel_labels=list(labels),
        snr_db=float(file_config.get("snr_db", 10.0)),
        random_seed=random_seed if random_seed is not None else file_config.get("random_seed"),
        device_id=str(file_config.get("device_id", DEFAULT_DEVICE_ID)),
        duration_sec=float(resolved_duration) if resolved_duration else None,
    )

    asyncio.run(_run_simulation(config, record_path=record_path))


if __name__ == "__main__":
    main()
