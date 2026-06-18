"""EMG artifact burst statistics tests."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

from data_generator.generators.eeg_generator import EEGGenerator
from data_generator.generators.emg_generator import EMGGenerator
from data_generator.scenarios.scenario_library import SCENARIOS


def test_emg_burst_statistics() -> None:
    sample_rate_hz = 160
    eeg = EEGGenerator.from_channel_count(
        16,
        sample_rate_hz=sample_rate_hz,
        random_seed=7,
        samples_per_frame=10,
    )
    t3_idx = eeg.channel_labels.index("T3")
    emg = EMGGenerator(
        affected_channels=[t3_idx],
        burst_probability=0.5,
        amplitude_uv=(200, 2000),
        sample_rate_hz=sample_rate_hz,
        random_seed=7,
    )

    burst_peak_amplitudes: list[float] = []
    burst_high_freq_powers: list[float] = []

    for frame_idx in range(200):
        frame = eeg.generate_frame(SCENARIOS["artifact_heavy"], frame_idx)
        before = np.asarray(frame["channels"][t3_idx], dtype=np.float64)
        emg.apply_artifact(frame, frame_idx)
        after = np.asarray(frame["channels"][t3_idx], dtype=np.float64)
        increment = after - before
        increment_peak = float(np.max(np.abs(increment)))

        if increment_peak > 50.0:
            burst_peak_amplitudes.append(increment_peak)
            freqs, psd = welch(increment, fs=sample_rate_hz, nperseg=len(increment))
            hf_mask = (freqs >= 30.0) & (freqs <= sample_rate_hz / 2.0)
            burst_high_freq_powers.append(float(np.trapz(psd[hf_mask], freqs[hf_mask])))

    assert emg.burst_rate > 0.2
    assert burst_peak_amplitudes, "Expected at least one EMG burst"
    assert min(burst_peak_amplitudes) >= 200.0
    assert max(burst_peak_amplitudes) <= 2500.0
    assert np.mean(burst_high_freq_powers) > 0.0
