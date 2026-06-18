"""Tests for temporal filters."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

from constants.signal_bands import SIGNAL_BANDS
from temporal.ar_spectral import ARSpectralEstimator, estimate_psd_burg
from temporal.bandpass_fir import BandpassFIR
from temporal.p300_averager import P300Averager


def test_bandpass_fir_attenuates_out_of_band_energy() -> None:
    sample_rate = 160.0
    t = np.arange(320) / sample_rate
    signal = np.sin(2 * np.pi * 2.0 * t) + np.sin(2 * np.pi * 40.0 * t)
    data = signal.reshape(1, -1)
    filtered = BandpassFIR(8.0, 30.0, sample_rate).process(data)
    low_power = np.mean(filtered[:, :160] ** 2)
    assert low_power < np.mean(data[:, :160] ** 2)


def test_ar_alpha_power_correlates_with_welch() -> None:
    rng = np.random.default_rng(7)
    sample_rate = 160.0
    num_samples = 512
    t = np.arange(num_samples) / sample_rate
    alpha_band = SIGNAL_BANDS["alpha"]

    ar_powers: list[float] = []
    welch_powers: list[float] = []

    for i in range(30):
        phase = rng.random() * 2.0 * np.pi
        amplitude = 5.0 + rng.random() * 10.0
        alpha = amplitude * np.sin(2.0 * np.pi * 10.0 * t + phase)
        noise = rng.normal(0.0, 1.0, size=num_samples)
        signal = (alpha + noise).reshape(1, -1)

        freqs_ar, psd_ar = estimate_psd_burg(
            signal, order=16, nfft=256, sample_rate_hz=sample_rate
        )
        freqs_w, psd_w = welch(signal[0], fs=sample_rate, nperseg=256)

        ar_mask = (freqs_ar >= alpha_band.low_hz) & (freqs_ar <= alpha_band.high_hz)
        w_mask = (freqs_w >= alpha_band.low_hz) & (freqs_w <= alpha_band.high_hz)
        ar_powers.append(float(np.trapz(psd_ar[0, ar_mask], freqs_ar[ar_mask])))
        welch_powers.append(float(np.trapz(psd_w[w_mask], freqs_w[w_mask])))

    correlation = float(np.corrcoef(ar_powers, welch_powers)[0, 1])
    assert correlation >= 0.9


def test_p300_averager_accumulates_epochs() -> None:
    averager = P300Averager(sample_rate_hz=160.0)
    signal = np.ones((4, 256))
    onset = averager.pre_samples + 10
    assert averager.add_epoch(signal, stimulus_onset_sample=onset)
    assert averager.add_epoch(signal, stimulus_onset_sample=onset)
    average = averager.get_average()
    assert average is not None
    assert average.shape == (4, averager.epoch_length)


def test_ar_spectral_estimator_returns_psd() -> None:
    estimator = ARSpectralEstimator(sample_rate_hz=160.0)
    signal = np.random.randn(4, 128)
    psd = estimator.process(signal)
    assert psd.shape[0] == 4
    assert estimator.last_freqs is not None
