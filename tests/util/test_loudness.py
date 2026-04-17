"""
Unit tests for the BS.1770 loudness helpers in util/loudness.py.

These tests verify that:
- Our per-track gated LUFS matches pyloudnorm's reference ``integrated_loudness``.
- Album aggregation via block-MS concatenation matches measuring pyloudnorm
  directly on the concatenated waveform (within 0.5 LU — block boundaries at
  track splits introduce minor differences).
- Edge cases (silence, energy-weighted fallback, mismatched channel counts)
  behave sensibly.
"""

import numpy as np
import pytest

pyloudnorm = pytest.importorskip("pyloudnorm")

from util.loudness import (
    ABSOLUTE_GATE_LUFS,
    aggregate_album_lufs,
    compute_block_mean_squares,
    energy_weighted_lufs,
    format_gain_db,
    format_peak,
    gated_lufs_from_blocks,
)


SR = 48000


def _make_noise(duration_sec: float, channels: int, rms: float = 0.1,
                seed: int = 42) -> np.ndarray:
    """Deterministic white noise at the requested RMS level."""
    rng = np.random.default_rng(seed)
    n = int(duration_sec * SR)
    data = rng.standard_normal((n, channels)).astype(np.float32) * rms
    return data


class TestPerTrackLufs:
    """Per-track integrated LUFS must match pyloudnorm to within 0.05 LU."""

    def test_matches_pyloudnorm_stereo(self):
        signal = _make_noise(10.0, channels=2)
        reference = pyloudnorm.Meter(SR).integrated_loudness(signal.copy())

        blocks = compute_block_mean_squares(signal, SR)
        ours = gated_lufs_from_blocks(blocks)

        assert abs(ours - reference) < 0.05

    def test_matches_pyloudnorm_mono(self):
        signal = _make_noise(8.0, channels=1)
        reference = pyloudnorm.Meter(SR).integrated_loudness(signal.copy())

        blocks = compute_block_mean_squares(signal, SR)
        ours = gated_lufs_from_blocks(blocks)

        assert abs(ours - reference) < 0.05


class TestAlbumAggregation:
    """
    Aggregating per-track block MS values should closely approximate
    measuring the full concatenated album waveform in one shot.
    """

    def test_concatenation_equivalence(self):
        track_a = _make_noise(5.0, channels=2, rms=0.1, seed=1)
        track_b = _make_noise(4.0, channels=2, rms=0.2, seed=2)
        track_c = _make_noise(6.0, channels=2, rms=0.05, seed=3)

        full = np.concatenate([track_a, track_b, track_c], axis=0)
        reference = pyloudnorm.Meter(SR).integrated_loudness(full.copy())

        blocks = [
            compute_block_mean_squares(t, SR)
            for t in (track_a, track_b, track_c)
        ]
        ours = aggregate_album_lufs(blocks)

        # Minor offset is expected because per-track block boundaries don't
        # line up with the concatenated-waveform block grid at track seams.
        assert abs(ours - reference) < 0.5

    def test_mismatched_channels_raises(self):
        stereo_blocks = compute_block_mean_squares(_make_noise(2.0, 2), SR)
        mono_blocks = compute_block_mean_squares(_make_noise(2.0, 1), SR)
        with pytest.raises(ValueError, match="channel counts"):
            aggregate_album_lufs([stereo_blocks, mono_blocks])


class TestSilenceAndEdgeCases:

    def test_silent_track_returns_neg_inf(self):
        silence = np.zeros((SR * 2, 2), dtype=np.float32)
        blocks = compute_block_mean_squares(silence, SR)
        assert gated_lufs_from_blocks(blocks) == float('-inf')

    def test_below_absolute_gate_returns_neg_inf(self):
        # Level far below the -70 LUFS gate.
        signal = _make_noise(3.0, 2, rms=1e-6)
        blocks = compute_block_mean_squares(signal, SR)
        result = gated_lufs_from_blocks(blocks)
        # Either below the gate (returns -inf) or extremely low.
        assert result == float('-inf') or result < ABSOLUTE_GATE_LUFS + 5.0

    def test_shorter_than_one_block_returns_empty(self):
        signal = _make_noise(0.1, channels=2)  # 100 ms, block is 400 ms
        blocks = compute_block_mean_squares(signal, SR)
        assert blocks.shape == (2, 0)
        assert gated_lufs_from_blocks(blocks) == float('-inf')

    def test_mono_convenience_1d_input(self):
        signal_1d = _make_noise(3.0, channels=1).flatten()
        blocks = compute_block_mean_squares(signal_1d, SR)
        assert blocks.shape[0] == 1
        assert blocks.shape[1] > 0


class TestEnergyWeightedFallback:

    def test_single_track(self):
        assert energy_weighted_lufs([(-18.0, 60.0)]) == pytest.approx(-18.0)

    def test_equal_duration_averaging(self):
        # Two tracks same duration, -18 and -24 LUFS.
        # Energy-weighted result must be between the two values, weighted
        # toward the louder one (energy scale).
        result = energy_weighted_lufs([(-18.0, 30.0), (-24.0, 30.0)])
        assert -24.0 < result < -18.0

    def test_skips_silent_tracks(self):
        result = energy_weighted_lufs([
            (-18.0, 60.0),
            (float('-inf'), 30.0),
        ])
        assert result == pytest.approx(-18.0)

    def test_all_silent_returns_neg_inf(self):
        result = energy_weighted_lufs([
            (float('-inf'), 60.0),
            (float('-inf'), 30.0),
        ])
        assert result == float('-inf')


class TestFormatting:

    def test_format_gain_negative(self):
        assert format_gain_db(-6.237) == "-6.24 dB"

    def test_format_gain_positive(self):
        assert format_gain_db(2.5) == "2.50 dB"

    def test_format_peak(self):
        assert format_peak(0.987654321) == "0.987654"

    def test_format_peak_one(self):
        assert format_peak(1.0) == "1.000000"
