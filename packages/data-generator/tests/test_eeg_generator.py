"""EEG generator waveform statistics tests."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

from data_generator.generators.eeg_generator import EEGGenerator
from data_generator.scenarios.scenario_library import SCENARIOS


def _alpha_power_uv2(samples: np.ndarray, sample_rate_hz: int) -> float:
    freqs, psd = welch(samples, fs=sample_rate_hz, nperseg=min(len(samples), 256))
    mask = (freqs >= 8.0) & (freqs <= 12.0)
    return float(np.trapz(psd[mask], freqs[mask]))


def test_motor_imagery_left_erd_at_c4() -> None:
    sample_rate_hz = 160
    samples_per_frame = 10
    num_frames = 160

    rest_gen = EEGGenerator.from_channel_count(
        16,
        sample_rate_hz=sample_rate_hz,
        snr_db=20.0,
        random_seed=42,
        samples_per_frame=samples_per_frame,
    )
    mi_gen = EEGGenerator.from_channel_count(
        16,
        sample_rate_hz=sample_rate_hz,
        snr_db=20.0,
        random_seed=42,
        samples_per_frame=samples_per_frame,
    )

    c4_idx = rest_gen.channel_labels.index("C4")

    rest_samples = []
    mi_samples = []
    for frame_idx in range(num_frames):
        rest_frame = rest_gen.generate_frame(SCENARIOS["rest"], frame_idx)
        mi_frame = mi_gen.generate_frame(SCENARIOS["motor_imagery_left"], frame_idx)
        rest_samples.extend(rest_frame["channels"][c4_idx])
        mi_samples.extend(mi_frame["channels"][c4_idx])

    rest_power = _alpha_power_uv2(np.asarray(rest_samples, dtype=np.float64), sample_rate_hz)
    mi_power = _alpha_power_uv2(np.asarray(mi_samples, dtype=np.float64), sample_rate_hz)

    reduction = 1.0 - (mi_power / rest_power)
    assert reduction >= 0.20, f"Expected >=20% alpha ERD at C4, got {reduction:.1%}"
