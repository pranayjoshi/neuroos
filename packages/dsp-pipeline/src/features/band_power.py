"""Per-band per-channel power extraction from spectral estimates."""

from __future__ import annotations

import numpy as np

from constants.signal_bands import BAND_NAMES, band_ranges


def compute_band_powers(
    psd: np.ndarray,
    freqs: np.ndarray,
    bands: dict[str, tuple[float, float]] | None = None,
) -> dict[str, np.ndarray]:
    """
    Integrate PSD over canonical frequency bands.

    psd: [channels, freq_bins]
    freqs: [freq_bins]
    Returns: {band_name: [channels] power array}
    """
    if bands is None:
        bands = band_ranges()

    result: dict[str, np.ndarray] = {}
    for name in BAND_NAMES:
        low, high = bands[name]
        mask = (freqs >= low) & (freqs <= high)
        if not np.any(mask):
            result[name] = np.zeros(psd.shape[0], dtype=np.float64)
            continue
        band_freqs = freqs[mask]
        band_psd = psd[:, mask]
        result[name] = np.trapz(band_psd, band_freqs, axis=1)
    return result
