"""Canonical EEG frequency band definitions — mirrors signal_bands.ts exactly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BandName = Literal["delta", "theta", "alpha", "beta", "gamma", "high_gamma"]


@dataclass(frozen=True)
class BandDefinition:
    name: BandName
    low_hz: float
    high_hz: float
    description: str


SIGNAL_BANDS: dict[BandName, BandDefinition] = {
    "delta": BandDefinition(
        name="delta",
        low_hz=0.5,
        high_hz=4.0,
        description="Deep sleep, slow cortical potentials (SCP). Used in SCP-BCI paradigms.",
    ),
    "theta": BandDefinition(
        name="theta",
        low_hz=4.0,
        high_hz=8.0,
        description="Drowsiness, memory encoding, frontal midline activity.",
    ),
    "alpha": BandDefinition(
        name="alpha",
        low_hz=8.0,
        high_hz=12.0,
        description=(
            "Sensorimotor idle rhythm (mu). ERD during motor imagery = left/right control."
        ),
    ),
    "beta": BandDefinition(
        name="beta",
        low_hz=18.0,
        high_hz=26.0,
        description="Active motor control, cognitive engagement. ERS after movement cessation.",
    ),
    "gamma": BandDefinition(
        name="gamma",
        low_hz=30.0,
        high_hz=80.0,
        description="High-level cognitive binding, attention. Sensitive to muscle artifact.",
    ),
    "high_gamma": BandDefinition(
        name="high_gamma",
        low_hz=80.0,
        high_hz=200.0,
        description=(
            "Broadband high-gamma: primary cortex activity in ECoG. "
            "Not reliably in scalp EEG."
        ),
    ),
}

MOTOR_IMAGERY_BANDS: list[BandName] = ["alpha", "beta"]
P300_BANDS: list[BandName] = ["delta", "theta"]
EMG_CONTAMINATED_BANDS: list[BandName] = ["gamma", "high_gamma"]

BAND_NAMES: list[BandName] = list(SIGNAL_BANDS.keys())


def band_ranges() -> dict[str, tuple[float, float]]:
    """Return {band_name: (low_hz, high_hz)} for spectral integration."""
    return {name: (band.low_hz, band.high_hz) for name, band in SIGNAL_BANDS.items()}
