"""Canonical signal band and type constants (Python mirror of shared contracts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BandName = Literal["delta", "theta", "alpha", "beta", "gamma", "high_gamma"]
SignalType = Literal["EEG", "EMG", "ECoG", "LFP", "SPIKE"]


@dataclass(frozen=True)
class BandDefinition:
    name: BandName
    low_hz: float
    high_hz: float
    description: str

    @property
    def center_hz(self) -> float:
        return (self.low_hz + self.high_hz) / 2.0


SIGNAL_BANDS: dict[BandName, BandDefinition] = {
    "delta": BandDefinition("delta", 0.5, 4.0, "Deep sleep, slow cortical potentials."),
    "theta": BandDefinition("theta", 4.0, 8.0, "Drowsiness, memory encoding."),
    "alpha": BandDefinition("alpha", 8.0, 12.0, "Sensorimotor idle rhythm (mu)."),
    "beta": BandDefinition("beta", 18.0, 26.0, "Active motor control."),
    "gamma": BandDefinition("gamma", 30.0, 80.0, "High-level cognitive binding."),
    "high_gamma": BandDefinition(
        "high_gamma", 80.0, 200.0, "Broadband high-gamma (ECoG)."
    ),
}

MOTOR_IMAGERY_BANDS: list[BandName] = ["alpha", "beta"]

EEG_AMPLITUDE_RANGE_UV: tuple[float, float] = (1.0, 100.0)
EMG_AMPLITUDE_RANGE_UV: tuple[float, float] = (50.0, 5000.0)

CHANNEL_LABELS_8: list[str] = ["Fp1", "F3", "C3", "P3", "Fz", "Cz", "Pz", "Oz"]

CHANNEL_LABELS_16: list[str] = [
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

CHANNEL_LABELS_64: list[str] = [
    "Fp1",
    "Fpz",
    "Fp2",
    "AF7",
    "AF3",
    "AFz",
    "AF4",
    "AF8",
    "F7",
    "F5",
    "F3",
    "F1",
    "Fz",
    "F2",
    "F4",
    "F6",
    "F8",
    "FT7",
    "FC5",
    "FC3",
    "FC1",
    "FCz",
    "FC2",
    "FC4",
    "FC6",
    "FT8",
    "T7",
    "C5",
    "C3",
    "C1",
    "Cz",
    "C2",
    "C4",
    "C6",
    "T8",
    "TP7",
    "CP5",
    "CP3",
    "CP1",
    "CPz",
    "CP2",
    "CP4",
    "CP6",
    "TP8",
    "P7",
    "P5",
    "P3",
    "P1",
    "Pz",
    "P2",
    "P4",
    "P6",
    "P8",
    "PO7",
    "PO3",
    "POz",
    "PO4",
    "PO8",
    "O1",
    "Oz",
    "O2",
    "Iz",
    "T3",
    "T4",
]

HIGH_CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("Fp1", "Fp2"),
    ("F3", "F4"),
    ("C3", "C4"),
    ("P3", "P4"),
    ("O1", "O2"),
    ("F3", "C3"),
    ("F4", "C4"),
    ("C3", "P3"),
    ("C4", "P4"),
]

DEFAULT_DEVICE_ID = "neuroos:simulator:SIM-001"
