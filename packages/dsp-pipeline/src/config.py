"""Pipeline configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DSPConfig:
    """Configuration for the NeuroOS DSP pipeline."""

    gain_uv_per_unit: float = 0.022351744781086523
    offset_uv: float = 0.0
    baseline_window_sec: float = 0.5

    spatial_method: Literal["car", "laplacian", "csp"] = "car"
    n_csp_components: int = 6

    temporal_method: Literal[
        "bandpass_fir", "autoregressive", "p300_average", "slow_wave"
    ] = "autoregressive"
    bandpass_low_hz: float = 8.0
    bandpass_high_hz: float = 30.0
    bandpass_num_taps: int | None = None
    ar_order: int = 16
    ar_window_sec: float = 1.0
    ar_nfft: int = 256
    p300_epoch_start_sec: float = -0.1
    p300_epoch_end_sec: float = 0.8
    p300_num_averages: int = 15
    slow_wave_window_sec: float = 0.5
    slow_wave_baseline_sec: float = 2.0

    erd_baseline_sec: float = 2.0

    emg_threshold_sd: float = 3.0
    ocular_threshold_uv: float = 100.0
    saturation_clip_uv: float = 400.0
    motion_threshold_uv: float = 150.0

    max_latency_ms: float = 5.0
    enforce_latency: bool = True

    standard_16_channel_labels: list[str] = field(
        default_factory=lambda: [
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
    )

    @classmethod
    def default(cls) -> DSPConfig:
        return cls()
