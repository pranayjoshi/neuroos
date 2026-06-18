"""Device simulator configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from data_generator.constants import DEFAULT_DEVICE_ID
from data_generator.scenarios.scenario import Scenario


@dataclass
class SimulatorConfig:
    """Configuration for the NeuroOS hardware simulator."""

    scenario: Scenario
    num_channels: int = 16
    sample_rate_hz: int = 160
    samples_per_frame: int = 10
    channel_labels: list[str] | None = None
    snr_db: float = 10.0
    random_seed: int | None = None
    device_id: str = DEFAULT_DEVICE_ID
    duration_sec: float | None = None
    emg_burst_probability: float | None = None
    driver_options: dict[str, object] = field(default_factory=dict)

    @property
    def frame_period_sec(self) -> float:
        return self.samples_per_frame / self.sample_rate_hz
