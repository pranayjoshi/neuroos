"""Canned BCI test scenarios."""

from __future__ import annotations

from data_generator.scenarios.scenario import Scenario

SCENARIOS: dict[str, Scenario] = {
    "rest": Scenario(
        label="motor_imagery_rest",
        duration_sec=10.0,
        scenario_type="rest",
    ),
    "motor_imagery_left": Scenario(
        label="motor_imagery_left",
        duration_sec=4.0,
        scenario_type="motor_imagery_left",
    ),
    "motor_imagery_right": Scenario(
        label="motor_imagery_right",
        duration_sec=4.0,
        scenario_type="motor_imagery_right",
    ),
    "p300_target": Scenario(
        label="p300_target",
        duration_sec=2.0,
        scenario_type="p300_target",
        stimulus_onset_sec=0.5,
    ),
    "artifact_heavy": Scenario(
        label="idle",
        duration_sec=5.0,
        scenario_type="artifact_heavy",
        emg_burst_probability=0.4,
    ),
    "mixed_sequence": Scenario(
        label="mixed_sequence",
        duration_sec=30.0,
        scenario_type="mixed_sequence",
        sequence=(
            "rest",
            "motor_imagery_left",
            "motor_imagery_right",
            "p300_target",
            "artifact_heavy",
        ),
        segment_duration_sec=5.0,
    ),
}


def resolve_active_scenario(scenario: Scenario, elapsed_sec: float) -> Scenario:
    """Return the active sub-scenario for mixed sequences."""
    if scenario.sequence is None:
        return scenario

    segment = max(scenario.segment_duration_sec, 0.001)
    cycle_index = int(elapsed_sec / segment) % len(scenario.sequence)
    key = scenario.sequence[cycle_index]
    base = SCENARIOS[key]
    return Scenario(
        label=base.label,
        duration_sec=scenario.duration_sec,
        scenario_type=base.scenario_type,
        stimulus_onset_sec=base.stimulus_onset_sec,
        emg_burst_probability=base.emg_burst_probability,
        sequence=None,
        segment_duration_sec=scenario.segment_duration_sec,
    )
