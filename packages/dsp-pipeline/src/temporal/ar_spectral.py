"""Autoregressive (Burg) spectral estimation."""

from __future__ import annotations

import numpy as np

from base_operator import SignalOperator


class ARSpectralEstimator(SignalOperator):
    """Estimate power spectral density via Burg AR modeling."""

    def __init__(
        self,
        sample_rate_hz: float,
        order: int = 16,
        nfft: int = 256,
    ) -> None:
        super().__init__()
        self.sample_rate_hz = sample_rate_hz
        self.order = order
        self.nfft = nfft
        self._last_freqs: np.ndarray | None = None
        self._last_psd: np.ndarray | None = None

    @property
    def operator_name(self) -> str:
        return "ar_spectral"

    @property
    def last_freqs(self) -> np.ndarray | None:
        return self._last_freqs

    @property
    def last_psd(self) -> np.ndarray | None:
        return self._last_psd

    def fit(self, calibration_data: np.ndarray) -> None:
        return

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    def _process_impl(self, signal: np.ndarray) -> np.ndarray:
        freqs, psd = estimate_psd_burg(signal, self.order, self.nfft, self.sample_rate_hz)
        self._last_freqs = freqs
        self._last_psd = psd
        return psd

    def estimate(self, signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (freqs, psd) without updating operator timing."""
        return estimate_psd_burg(signal, self.order, self.nfft, self.sample_rate_hz)


def burg_ar(x: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """Burg's method for AR parameter estimation on a 1-D signal."""
    x = x.astype(np.float64, copy=False)
    n = len(x)
    if n <= order:
        return np.zeros(order), float(np.dot(x, x) / max(n, 1))

    ef = x.copy()
    eb = x.copy()
    a = np.zeros(order, dtype=np.float64)
    p = float(np.dot(x, x) / n)

    for m in range(order):
        num = -2.0 * np.dot(eb[m + 1 :], ef[m : n - 1])
        den = np.dot(ef[m : n - 1], ef[m : n - 1]) + np.dot(eb[m + 1 :], eb[m + 1 :])
        km = num / (den + 1e-10)
        ef_new = ef[m : n - 1] + km * eb[m + 1 :]
        eb_new = eb[m + 1 :] + km * ef[m : n - 1]
        ef[m : n - 1] = ef_new
        eb[m + 1 :] = eb_new
        a_new = np.zeros(m + 1, dtype=np.float64)
        if m > 0:
            a_new[:m] = a[:m] + km * a[:m][::-1]
        a_new[m] = km
        a = a_new
        p *= 1.0 - km**2

    return a, p


def ar_psd(
    a: np.ndarray,
    sigma2: float,
    nfft: int,
    sample_rate_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Power spectral density from AR coefficients."""
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate_hz)
    z = np.exp(1j * 2.0 * np.pi * freqs / sample_rate_hz)
    if len(a) == 0:
        psd = np.full_like(freqs, sigma2, dtype=np.float64)
        return freqs, psd

    denom = np.ones_like(freqs, dtype=np.complex128)
    for k, coeff in enumerate(a):
        denom += coeff * z ** (-(k + 1))
    psd = (sigma2 * sample_rate_hz) / (np.abs(denom) ** 2 + 1e-20)
    return freqs, psd.real


def estimate_psd_burg(
    signal: np.ndarray,
    order: int,
    nfft: int,
    sample_rate_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate PSD for each channel using Burg AR. Returns (freqs, psd[channels, bins])."""
    channels, samples = signal.shape
    if samples < order + 1:
        freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate_hz)
        return freqs, np.zeros((channels, len(freqs)), dtype=np.float64)

    psd_rows = []
    freqs: np.ndarray | None = None
    for ch in range(channels):
        coeffs, variance = burg_ar(signal[ch], order)
        ch_freqs, ch_psd = ar_psd(coeffs, variance, nfft, sample_rate_hz)
        freqs = ch_freqs
        psd_rows.append(ch_psd)
    assert freqs is not None
    return freqs, np.vstack(psd_rows)
