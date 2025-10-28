"""
Unit tests for analyzer evaluation scoring logic.
"""

import pytest
from util.eval_scoring import (
    calculate_key_relationship,
    calculate_key_score,
    calculate_bpm_score
)


class TestKeyRelationship:
    """Test MIREX key relationship scoring."""

    def test_same_key_major(self):
        """Test exact match for major keys."""
        # C major == C major
        score, category = calculate_key_relationship(0, False, 0, False)
        assert score == 1.0
        assert category == 'same key'

    def test_same_key_minor(self):
        """Test exact match for minor keys."""
        # A minor == A minor
        score, category = calculate_key_relationship(9, True, 9, True)
        assert score == 1.0
        assert category == 'same key'

    def test_parallel_major_minor(self):
        """Test parallel major/minor relationship (same tonic, different mode)."""
        # C major vs C minor
        score, category = calculate_key_relationship(0, False, 0, True)
        assert score == 0.2
        assert category == 'parallel major/minor'

        # D minor vs D major
        score, category = calculate_key_relationship(2, True, 2, False)
        assert score == 0.2
        assert category == 'parallel major/minor'

    def test_relative_major_minor(self):
        """Test relative major/minor relationship (3 semitones apart, different mode)."""
        # C major (pitch 0) vs A minor (pitch 9) - distance is 3 semitones
        score, category = calculate_key_relationship(0, False, 9, True)
        assert score == 0.3
        assert category == 'relative major/minor'

        # A minor (pitch 9) vs C major (pitch 0) - distance is 3 semitones
        score, category = calculate_key_relationship(9, True, 0, False)
        assert score == 0.3
        assert category == 'relative major/minor'

        # D minor (pitch 2) vs F major (pitch 5) - distance is 3 semitones
        score, category = calculate_key_relationship(2, True, 5, False)
        assert score == 0.3
        assert category == 'relative major/minor'

    def test_perfect_fifth_major(self):
        """Test perfect fifth relationship for major keys (7 semitones, same mode)."""
        # C major (pitch 0) vs G major (pitch 7)
        score, category = calculate_key_relationship(0, False, 7, False)
        assert score == 0.5
        assert category == 'perfect fifth'

        # G major (pitch 7) vs C major (pitch 0) - also 7 semitones
        score, category = calculate_key_relationship(7, False, 0, False)
        assert score == 0.5
        assert category == 'perfect fifth'

    def test_perfect_fifth_minor(self):
        """Test perfect fifth relationship for minor keys (7 semitones, same mode)."""
        # A minor (pitch 9) vs E minor (pitch 4) - distance is 7 semitones
        score, category = calculate_key_relationship(9, True, 4, True)
        assert score == 0.5
        assert category == 'perfect fifth'

    def test_other_relationship(self):
        """Test unrelated keys."""
        # C major vs D major (2 semitones, same mode - not a perfect fifth)
        score, category = calculate_key_relationship(0, False, 2, False)
        assert score == 0.0
        assert category == 'other'

        # C major vs E minor (4 semitones, different mode - not relative)
        score, category = calculate_key_relationship(0, False, 4, True)
        assert score == 0.0
        assert category == 'other'

    def test_all_pitch_classes(self):
        """Test that all pitch classes work correctly."""
        # Test same key for all 12 pitch classes
        for pitch_class in range(12):
            score, category = calculate_key_relationship(pitch_class, False, pitch_class, False)
            assert score == 1.0
            assert category == 'same key'

            score, category = calculate_key_relationship(pitch_class, True, pitch_class, True)
            assert score == 1.0
            assert category == 'same key'


class TestKeyScore:
    """Test the key score wrapper function."""

    def test_returns_score_only(self):
        """Test that calculate_key_score returns only the score."""
        # Same key
        score = calculate_key_score(0, False, 0, False)
        assert score == 1.0

        # Perfect fifth
        score = calculate_key_score(0, False, 7, False)
        assert score == 0.5

        # Relative major/minor
        score = calculate_key_score(0, False, 9, True)
        assert score == 0.3

        # Parallel major/minor
        score = calculate_key_score(0, False, 0, True)
        assert score == 0.2

        # Other
        score = calculate_key_score(0, False, 2, False)
        assert score == 0.0


class TestBPMScore:
    """Test custom BPM scoring logic."""

    def test_exact_match(self):
        """Test exact BPM match (< 0.01 BPM difference)."""
        score, category = calculate_bpm_score(120.0, 120.0)
        assert score == 1.0
        assert category == 'exact'

        # Within 0.01 threshold
        score, category = calculate_bpm_score(120.0, 120.005)
        assert score == 1.0
        assert category == 'exact'

    def test_within_10_percent(self):
        """Test BPM within ±10%."""
        # 120 BPM ± 10% = 108-132 BPM
        score, category = calculate_bpm_score(120.0, 132.0)
        assert score == 0.5
        assert category == 'within_10pct'

        score, category = calculate_bpm_score(120.0, 108.0)
        assert score == 0.5
        assert category == 'within_10pct'

        # Just within 10%
        score, category = calculate_bpm_score(120.0, 120.0 + 12.0)  # +10%
        assert score == 0.5
        assert category == 'within_10pct'

        score, category = calculate_bpm_score(120.0, 120.0 - 12.0)  # -10%
        assert score == 0.5
        assert category == 'within_10pct'

    def test_within_20_percent(self):
        """Test BPM within ±20%."""
        # 120 BPM ± 20% = 96-144 BPM
        score, category = calculate_bpm_score(120.0, 144.0)
        assert score == 0.25
        assert category == 'within_20pct'

        score, category = calculate_bpm_score(120.0, 96.0)
        assert score == 0.25
        assert category == 'within_20pct'

        # Between 10% and 20%
        score, category = calculate_bpm_score(120.0, 135.0)
        assert score == 0.25
        assert category == 'within_20pct'

        score, category = calculate_bpm_score(120.0, 105.0)
        assert score == 0.25
        assert category == 'within_20pct'

    def test_outside_20_percent(self):
        """Test BPM outside ±20%."""
        # 120 BPM ± 20% = 96-144 BPM
        score, category = calculate_bpm_score(120.0, 150.0)
        assert score == 0.0
        assert category == 'other'

        score, category = calculate_bpm_score(120.0, 90.0)
        assert score == 0.0
        assert category == 'other'

    def test_rounding(self):
        """Test that values are rounded to 2 decimal places."""
        # Values should be rounded before comparison
        score, category = calculate_bpm_score(120.123, 120.125)
        assert score == 1.0  # Both round to 120.12
        assert category == 'exact'

    def test_various_bpm_ranges(self):
        """Test scoring across different BPM ranges."""
        # Test with drum and bass tempo (~174 BPM)
        score, category = calculate_bpm_score(174.0, 174.0)
        assert score == 1.0

        score, category = calculate_bpm_score(174.0, 191.4)  # +10%
        assert score == 0.5

        score, category = calculate_bpm_score(174.0, 208.8)  # +20%
        assert score == 0.25

        # Test with slower tempo (~90 BPM)
        score, category = calculate_bpm_score(90.0, 90.0)
        assert score == 1.0

        score, category = calculate_bpm_score(90.0, 99.0)  # +10%
        assert score == 0.5

        score, category = calculate_bpm_score(90.0, 108.0)  # +20%
        assert score == 0.25


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_key_relationship_boundaries(self):
        """Test boundary cases for key relationships."""
        # Wrap-around pitch classes (B to C)
        score, category = calculate_key_relationship(11, False, 0, False)
        # B to C is 1 semitone, not a recognized relationship
        assert category in ['other', 'perfect fifth', 'relative major/minor']

    def test_bpm_zero_difference(self):
        """Test BPM with exactly zero difference."""
        score, category = calculate_bpm_score(100.0, 100.0)
        assert score == 1.0
        assert category == 'exact'

    def test_bpm_boundary_values(self):
        """Test BPM at exact threshold boundaries."""
        # Exactly at 10% boundary
        score, category = calculate_bpm_score(100.0, 110.0)
        assert score == 0.5
        assert category == 'within_10pct'

        # Exactly at 20% boundary
        score, category = calculate_bpm_score(100.0, 120.0)
        assert score == 0.25
        assert category == 'within_20pct'

        # Just over 20% boundary
        score, category = calculate_bpm_score(100.0, 120.01)
        assert score == 0.0
        assert category == 'other'
