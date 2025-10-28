"""
Unit tests for analyzer evaluation scoring logic.
"""

import pytest
from util.eval_scoring import (
    calculate_key_relationship,
    calculate_key_score,
    calculate_bpm_score,
    KeyRelationship,
    BPMCategory
)


class TestKeyRelationship:
    """Test MIREX key relationship scoring."""

    def test_same_key_major(self):
        """Test exact match for major keys."""
        # C major == C major
        score, category = calculate_key_relationship(0, False, 0, False)
        assert score == 1.0
        assert category == KeyRelationship.SAME_KEY

    def test_same_key_minor(self):
        """Test exact match for minor keys."""
        # A minor == A minor
        score, category = calculate_key_relationship(9, True, 9, True)
        assert score == 1.0
        assert category == KeyRelationship.SAME_KEY

    def test_parallel_major_minor(self):
        """Test parallel major/minor relationship (same tonic, different mode)."""
        # C major vs C minor
        score, category = calculate_key_relationship(0, False, 0, True)
        assert score == 0.2
        assert category == KeyRelationship.PARALLEL_MAJOR_MINOR

        # D minor vs D major
        score, category = calculate_key_relationship(2, True, 2, False)
        assert score == 0.2
        assert category == KeyRelationship.PARALLEL_MAJOR_MINOR

    def test_relative_major_minor(self):
        """Test relative major/minor relationship (3 semitones apart, different mode)."""
        # C major (pitch 0) vs A minor (pitch 9) - distance is 3 semitones
        score, category = calculate_key_relationship(0, False, 9, True)
        assert score == 0.3
        assert category == KeyRelationship.RELATIVE_MAJOR_MINOR

        # A minor (pitch 9) vs C major (pitch 0) - distance is 3 semitones
        score, category = calculate_key_relationship(9, True, 0, False)
        assert score == 0.3
        assert category == KeyRelationship.RELATIVE_MAJOR_MINOR

        # D minor (pitch 2) vs F major (pitch 5) - distance is 3 semitones
        score, category = calculate_key_relationship(2, True, 5, False)
        assert score == 0.3
        assert category == KeyRelationship.RELATIVE_MAJOR_MINOR

    def test_perfect_fifth_major(self):
        """Test perfect fifth relationship for major keys (7 semitones, same mode)."""
        # C major (pitch 0) vs G major (pitch 7)
        score, category = calculate_key_relationship(0, False, 7, False)
        assert score == 0.5
        assert category == KeyRelationship.PERFECT_FIFTH

        # G major (pitch 7) vs C major (pitch 0) - also 7 semitones
        score, category = calculate_key_relationship(7, False, 0, False)
        assert score == 0.5
        assert category == KeyRelationship.PERFECT_FIFTH

    def test_perfect_fifth_minor(self):
        """Test perfect fifth relationship for minor keys (7 semitones, same mode)."""
        # A minor (pitch 9) vs E minor (pitch 4) - distance is 7 semitones
        score, category = calculate_key_relationship(9, True, 4, True)
        assert score == 0.5
        assert category == KeyRelationship.PERFECT_FIFTH

    def test_other_relationship(self):
        """Test unrelated keys."""
        # C major vs D major (2 semitones, same mode - not a perfect fifth)
        score, category = calculate_key_relationship(0, False, 2, False)
        assert score == 0.0
        assert category == KeyRelationship.OTHER

        # C major vs E minor (4 semitones, different mode - not relative)
        score, category = calculate_key_relationship(0, False, 4, True)
        assert score == 0.0
        assert category == KeyRelationship.OTHER

    def test_all_pitch_classes(self):
        """Test that all pitch classes work correctly."""
        # Test same key for all 12 pitch classes
        for pitch_class in range(12):
            score, category = calculate_key_relationship(pitch_class, False, pitch_class, False)
            assert score == 1.0
            assert category == KeyRelationship.SAME_KEY

            score, category = calculate_key_relationship(pitch_class, True, pitch_class, True)
            assert score == 1.0
            assert category == KeyRelationship.SAME_KEY


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
    """Test custom BPM scoring logic with absolute differences."""

    def test_exact_match(self):
        """Test exact BPM match (< 0.01 BPM difference)."""
        score, category = calculate_bpm_score(120.0, 120.0)
        assert score == 1.0
        assert category == BPMCategory.EXACT

        # Within 0.01 threshold (rounds to 120.00 and 120.00)
        score, category = calculate_bpm_score(120.0, 120.004)
        assert score == 1.0
        assert category == BPMCategory.EXACT

        # Just below 0.01 threshold after rounding (120.00 vs 120.00)
        score, category = calculate_bpm_score(120.001, 120.003)
        assert score == 1.0
        assert category == BPMCategory.EXACT

    def test_nearly_exact_match(self):
        """Test nearly exact BPM match (< 0.02 BPM difference)."""
        # At 0.01 boundary (should be nearly_exact)
        score, category = calculate_bpm_score(120.0, 120.01)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        # Within 0.02 threshold (rounds to 120.00 vs 120.01)
        score, category = calculate_bpm_score(120.0, 120.014)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        score, category = calculate_bpm_score(120.0, 119.99)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        # Just below 0.02 threshold after rounding (120.00 vs 120.01)
        score, category = calculate_bpm_score(120.001, 120.011)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

    def test_very_close_match(self):
        """Test very close BPM match (< 0.05 BPM difference)."""
        # At 0.02 boundary (should be very_close)
        score, category = calculate_bpm_score(120.0, 120.02)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        # Within 0.05 threshold
        score, category = calculate_bpm_score(120.0, 120.03)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        score, category = calculate_bpm_score(120.0, 119.97)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        # Just below 0.05 threshold after rounding (120.00 vs 120.04)
        score, category = calculate_bpm_score(120.0, 120.044)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

    def test_close_match(self):
        """Test close BPM match (< 0.1 BPM difference)."""
        # Just above 0.05 threshold (should be close)
        score, category = calculate_bpm_score(120.0, 120.06)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        # Within 0.1 threshold
        score, category = calculate_bpm_score(120.0, 120.08)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        score, category = calculate_bpm_score(120.0, 119.93)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        # Just below 0.1 threshold after rounding (120.00 vs 120.09)
        score, category = calculate_bpm_score(120.0, 120.094)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

    def test_outside_threshold(self):
        """Test BPM outside all thresholds."""
        # At 0.1 boundary (diff = 0.1, which is NOT < 0.1, so it's "other")
        score, category = calculate_bpm_score(120.0, 120.1)
        assert score == 0.0
        assert category == BPMCategory.OTHER

        # Well beyond threshold
        score, category = calculate_bpm_score(120.0, 121.0)
        assert score == 0.0
        assert category == BPMCategory.OTHER

        score, category = calculate_bpm_score(120.0, 119.5)
        assert score == 0.0
        assert category == BPMCategory.OTHER

    def test_rounding(self):
        """Test that values are rounded to 2 decimal places."""
        # Values should be rounded before comparison
        score, category = calculate_bpm_score(120.123, 120.125)
        assert score == 1.0  # Both round to 120.12
        assert category == BPMCategory.EXACT

    def test_various_bpm_ranges(self):
        """Test scoring across different BPM ranges with absolute differences."""
        # Test with drum and bass tempo (~174 BPM)
        score, category = calculate_bpm_score(174.0, 174.0)
        assert score == 1.0
        assert category == BPMCategory.EXACT

        score, category = calculate_bpm_score(174.0, 174.01)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        score, category = calculate_bpm_score(174.0, 174.03)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        score, category = calculate_bpm_score(174.0, 174.08)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        score, category = calculate_bpm_score(174.0, 174.5)
        assert score == 0.0
        assert category == BPMCategory.OTHER

        # Test with slower tempo (~90 BPM)
        score, category = calculate_bpm_score(90.0, 90.0)
        assert score == 1.0
        assert category == BPMCategory.EXACT

        score, category = calculate_bpm_score(90.0, 90.01)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        score, category = calculate_bpm_score(90.0, 90.04)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        score, category = calculate_bpm_score(90.0, 90.09)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        score, category = calculate_bpm_score(90.0, 90.5)
        assert score == 0.0
        assert category == BPMCategory.OTHER


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_key_relationship_boundaries(self):
        """Test boundary cases for key relationships."""
        # Wrap-around pitch classes (B to C)
        score, category = calculate_key_relationship(11, False, 0, False)
        # B to C is 1 semitone, not a recognized relationship
        assert category in [KeyRelationship.OTHER, KeyRelationship.PERFECT_FIFTH, KeyRelationship.RELATIVE_MAJOR_MINOR]

    def test_bpm_zero_difference(self):
        """Test BPM with exactly zero difference."""
        score, category = calculate_bpm_score(100.0, 100.0)
        assert score == 1.0
        assert category == BPMCategory.EXACT

    def test_bpm_boundary_values(self):
        """Test BPM at exact threshold boundaries with absolute differences."""
        # Exactly at 0.01 boundary (diff = 0.01, NOT < 0.01, goes to next tier)
        score, category = calculate_bpm_score(100.0, 100.01)
        assert score == 0.75
        assert category == BPMCategory.NEARLY_EXACT

        # Exactly at 0.02 boundary (diff = 0.02, NOT < 0.02, goes to next tier)
        score, category = calculate_bpm_score(100.0, 100.02)
        assert score == 0.5
        assert category == BPMCategory.VERY_CLOSE

        # Exactly at 0.05 boundary (diff = 0.05, NOT < 0.05, goes to next tier)
        score, category = calculate_bpm_score(100.0, 100.05)
        assert score == 0.25
        assert category == BPMCategory.CLOSE

        # Exactly at 0.1 boundary (diff = 0.1, NOT < 0.1, goes to default)
        score, category = calculate_bpm_score(100.0, 100.1)
        assert score == 0.0
        assert category == BPMCategory.OTHER

        # Just over 0.1 boundary
        score, category = calculate_bpm_score(100.0, 100.11)
        assert score == 0.0
        assert category == BPMCategory.OTHER
