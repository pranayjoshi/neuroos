"""Scenario configuration for BCI simulation paradigms."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    """Configuration for one BCI test scenario."""

    label: str
    duration_sec: float
    scenario_type: str
    stimulus_onset_sec: float | None = None
    emg_burst_probability: float = 0.0
    sequence: tuple[str, ...] | None = None
    segment_duration_sec: float = 5.0
    metadata: dict[str, object] = field(default_factory=dict)
