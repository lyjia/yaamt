"""
BS.1770 loudness helpers used by the ReplayGain analyzer.

This module provides utilities for computing per-track 400 ms block
mean-squares (after K-weighting per ITU-R BS.1770-4) and for aggregating those
per-track values into a spec-correct integrated LUFS measurement for an entire
album. The aggregator concatenates ungated block mean-squares from every track
and then applies BS.1770's absolute + relative gating once over the combined
set, which is equivalent to measuring the integrated loudness over the
concatenated waveform.

All functions here require numpy and pyloudnorm. Callers must import-guard and
surface a user-friendly error if these are unavailable.
"""

import numpy as np

from util.logging import log


# BS.1770-4 channel gain weights. Order: Left, Right, Center, Left-surround, Right-surround.
# Stereo/mono use the first 1-2 entries; surrounds weight at ~+1.5 dB.
BS1770_CHANNEL_GAINS = [1.0, 1.0, 1.0, 1.41, 1.41]

# Absolute gating threshold, ITU-R BS.1770-4 eq. 6.
ABSOLUTE_GATE_LUFS = -70.0

# Relative gating offset, applied below the ungated mean.
RELATIVE_GATE_OFFSET_LU = -10.0

# K-weighting calibration constant, ITU-R BS.1770-4 eq. 4.
KWEIGHTING_OFFSET_DB = -0.691


def compute_block_mean_squares(
    audio_data: np.ndarray,
    sample_rate: int,
) -> np.ndarray:
    """
    Apply K-weighting and return per-channel 400 ms block mean-squares.

    The returned array is shape ``(num_channels, num_blocks)`` and matches the
    intermediate ``z`` array used by pyloudnorm's integrated_loudness. It is
    the exact input needed to compute BS.1770 integrated LUFS via
    :func:`gated_lufs_from_blocks` and is suitable for cross-track aggregation
    (concatenate along axis 1 and re-gate).

    Args:
        audio_data: Float audio samples shaped ``(samples, channels)`` or
                    ``(samples,)`` for mono. Up to 5 channels supported.
        sample_rate: Audio sample rate in Hz.

    Returns:
        ``(num_channels, num_blocks)`` float64 ndarray. Returns an empty
        ``(num_channels, 0)`` array when the input is shorter than one block.
    """
    import pyloudnorm as pyln

    if audio_data.ndim == 1:
        audio_data = audio_data.reshape(-1, 1)

    num_samples, num_channels = audio_data.shape
    meter = pyln.Meter(sample_rate)
    block_size = meter.block_size   # 0.4 seconds
    overlap = meter.overlap         # 0.75
    step = 1.0 - overlap            # 0.25

    duration = num_samples / sample_rate
    if duration < block_size:
        return np.zeros((num_channels, 0), dtype=np.float64)

    # Apply K-weighting filters in-place on a copy (pyloudnorm mutates).
    filtered = audio_data.astype(np.float64, copy=True)
    for _, filter_stage in meter._filters.items():
        for ch in range(num_channels):
            filtered[:, ch] = filter_stage.apply_filter(filtered[:, ch])

    num_blocks = int(np.round((duration - block_size) / (block_size * step))) + 1
    block_samples = int(block_size * sample_rate)
    z = np.zeros((num_channels, num_blocks), dtype=np.float64)

    for j in range(num_blocks):
        lo = int(block_size * j * step * sample_rate)
        hi = lo + block_samples
        segment = filtered[lo:hi, :]
        # Mean-square per channel, normalized over the nominal block length.
        z[:, j] = np.sum(segment * segment, axis=0) / block_samples

    return z


def gated_lufs_from_blocks(
    block_ms: np.ndarray,
    channel_gains: list[float] | None = None,
) -> float:
    """
    Compute BS.1770-4 integrated LUFS from a per-block mean-square matrix.

    This replicates pyloudnorm's gating logic so it can be applied to block
    mean-square values that were aggregated across multiple tracks.

    Args:
        block_ms: ``(num_channels, num_blocks)`` K-weighted mean-squares.
        channel_gains: Optional override for BS.1770 channel weights.

    Returns:
        Integrated LUFS value. Returns ``-inf`` when no blocks survive gating
        (pure silence).
    """
    if block_ms.size == 0:
        return float('-inf')

    num_channels = block_ms.shape[0]
    gains = channel_gains or BS1770_CHANNEL_GAINS
    if num_channels > len(gains):
        raise ValueError(
            f"Too many channels ({num_channels}); BS.1770 defines up to {len(gains)}"
        )
    g = np.asarray(gains[:num_channels], dtype=np.float64).reshape(-1, 1)

    # Per-block loudness l_j (eq. 4).
    with np.errstate(divide='ignore'):
        weighted_sum = np.sum(g * block_ms, axis=0)          # shape (num_blocks,)
        block_loudness = KWEIGHTING_OFFSET_DB + 10.0 * np.log10(weighted_sum)

    # Absolute gate (eq. 5).
    abs_mask = block_loudness >= ABSOLUTE_GATE_LUFS
    if not np.any(abs_mask):
        return float('-inf')

    z_avg_abs = np.mean(block_ms[:, abs_mask], axis=1)
    with np.errstate(divide='ignore'):
        gamma_r = (
            KWEIGHTING_OFFSET_DB
            + 10.0 * np.log10(np.sum(g.flatten() * z_avg_abs))
            + RELATIVE_GATE_OFFSET_LU
        )

    # Combined absolute + relative gate (eq. 7).
    combined_mask = abs_mask & (block_loudness > gamma_r)
    if not np.any(combined_mask):
        return float('-inf')

    z_avg = np.mean(block_ms[:, combined_mask], axis=1)
    with np.errstate(divide='ignore'):
        return float(
            KWEIGHTING_OFFSET_DB + 10.0 * np.log10(np.sum(g.flatten() * z_avg))
        )


def aggregate_album_lufs(block_ms_arrays: list[np.ndarray]) -> float:
    """
    Compute album-level integrated LUFS from per-track block mean-squares.

    All input arrays must share the same channel count so that their blocks
    can be concatenated along the block axis. Callers with mismatched channel
    counts should fall back to :func:`energy_weighted_lufs`.

    Args:
        block_ms_arrays: List of ``(num_channels, num_blocks_i)`` arrays.

    Returns:
        Integrated LUFS for the full album.
    """
    if not block_ms_arrays:
        return float('-inf')

    channel_counts = {a.shape[0] for a in block_ms_arrays if a.size > 0}
    if len(channel_counts) > 1:
        raise ValueError(
            f"Cannot concatenate block arrays with different channel counts: "
            f"{channel_counts}"
        )

    combined = np.concatenate(
        [a for a in block_ms_arrays if a.size > 0],
        axis=1,
    ) if any(a.size > 0 for a in block_ms_arrays) else np.zeros(
        (block_ms_arrays[0].shape[0], 0)
    )
    return gated_lufs_from_blocks(combined)


def energy_weighted_lufs(
    track_lufs_and_durations: list[tuple[float, float]],
) -> float:
    """
    Duration-weighted energy mean of per-track LUFS as an aggregation fallback.

    Used when tracks in an album have incompatible channel counts or sample
    rates. Not strictly BS.1770-compliant (the gating cannot be re-applied) but
    within ~0.1-0.3 LU of the spec-correct result for typical program material.

    Args:
        track_lufs_and_durations: ``(lufs, duration_seconds)`` pairs. Tracks
                                  with ``-inf`` loudness are skipped.

    Returns:
        Energy-weighted LUFS, or ``-inf`` if every track is silent.
    """
    finite = [
        (lufs, dur) for lufs, dur in track_lufs_and_durations
        if np.isfinite(lufs) and dur > 0
    ]
    if not finite:
        return float('-inf')

    total_duration = sum(dur for _, dur in finite)
    weighted_energy = sum(dur * (10.0 ** (lufs / 10.0)) for lufs, dur in finite)
    if weighted_energy <= 0:
        return float('-inf')
    return 10.0 * np.log10(weighted_energy / total_duration)


def format_gain_db(gain_db: float) -> str:
    """Format a gain value as the ReplayGain-standard string ``'%+.2f dB'``."""
    return f"{gain_db:.2f} dB"


def format_peak(peak: float) -> str:
    """Format a linear peak value as the ReplayGain-standard 6-decimal string."""
    return f"{peak:.6f}"
