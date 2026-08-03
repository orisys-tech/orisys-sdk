"""Signal filtering helpers for example force charts."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt

def lowpass_filter(data, cutoff_hz=5, sample_rate_hz=30, order=2) -> np.ndarray:
    """Zero-phase Butterworth low-pass filter for uniformly sampled 1-D data."""
    y = np.asarray(data, dtype=np.float64)
    if cutoff_hz == 0:
        return y.copy()
    if y.size == 0:
        return y

    nyquist = 0.5 * sample_rate_hz
    if cutoff_hz < 0 or cutoff_hz >= nyquist:
        raise ValueError(
            f"cutoff_hz must be in (0, {nyquist}) for sample_rate_hz={sample_rate_hz}"
        )

    b, a = butter(order, cutoff_hz / nyquist, btype="low")
    taplen = max(len(a), len(b))
    # scipy.signal.filtfilt requires len(x) > padlen (default 3 * taplen for recent scipy).
    padlen = 3 * taplen
    if y.size <= padlen:
        return y.copy()

    try:
        return filtfilt(b, a, y)
    except ValueError:
        return y.copy()
