"""
Tests for BPM range adjustment logic.

This module tests the adjust_bpm_to_range() function which adjusts BPM values
to fit within a user-specified range by doubling or halving, and the
select_best_bpm() function for selecting from multiple BPM candidates.
"""

import pytest

from util.bpm import adjust_bpm_to_range, select_best_bpm, BpmCandidate


class TestAdjustBpmToRange:
    """Tests for the adjust_bpm_to_range function."""

    def test_no_constraints_returns_original(self):
        """BPM should be unchanged when no constraints are specified."""
        assert adjust_bpm_to_range(120.0, None, None) == 120.0
        assert adjust_bpm_to_range(60.0, None, None) == 60.0
        assert adjust_bpm_to_range(240.0, None, None) == 240.0

    def test_in_range_returns_original(self):
        """BPM already within range should be unchanged."""
        assert adjust_bpm_to_range(120.0, 80, 200) == 120.0
        assert adjust_bpm_to_range(80.0, 80, 200) == 80.0
        assert adjust_bpm_to_range(200.0, 80, 200) == 200.0
        assert adjust_bpm_to_range(128.5, 100, 140) == 128.5

    def test_below_minimum_doubles(self):
        """BPM below minimum should be doubled if result fits."""
        # 65 BPM -> 130 BPM (within 80-200 range)
        assert adjust_bpm_to_range(65.0, 80, 200) == 130.0
        # 75 BPM -> 150 BPM (within 100-180 range)
        assert adjust_bpm_to_range(75.0, 100, 180) == 150.0
        # 55 BPM -> 110 BPM (within 98-138 range, typical house/techno)
        assert adjust_bpm_to_range(55.0, 98, 138) == 110.0

    def test_above_maximum_halves(self):
        """BPM above maximum should be halved if result fits."""
        # 240 BPM -> 120 BPM (within 80-200 range)
        assert adjust_bpm_to_range(240.0, 80, 200) == 120.0
        # 300 BPM -> 150 BPM (within 100-180 range)
        assert adjust_bpm_to_range(300.0, 100, 180) == 150.0
        # 260 BPM -> 130 BPM (within 98-138 range)
        assert adjust_bpm_to_range(260.0, 98, 138) == 130.0

    def test_doubled_exceeds_max_no_adjustment(self):
        """If doubling would exceed max, return original."""
        # 110 BPM < 120 min, but 220 > 160 max
        result = adjust_bpm_to_range(110.0, 120, 160)
        assert result == 110.0  # No adjustment possible

    def test_halved_below_min_no_adjustment(self):
        """If halving would go below min, return original."""
        # 180 BPM > 140 max, but 90 < 100 min
        result = adjust_bpm_to_range(180.0, 100, 140)
        assert result == 180.0  # No adjustment possible

    def test_only_minimum_constraint(self):
        """Test with only minimum BPM constraint."""
        # 60 BPM doubled to 120 (no max constraint)
        assert adjust_bpm_to_range(60.0, 80, None) == 120.0
        # 100 BPM already >= 80 min
        assert adjust_bpm_to_range(100.0, 80, None) == 100.0
        # 240 BPM has no max constraint
        assert adjust_bpm_to_range(240.0, 80, None) == 240.0

    def test_only_maximum_constraint(self):
        """Test with only maximum BPM constraint."""
        # 240 BPM halved to 120 (no min constraint)
        assert adjust_bpm_to_range(240.0, None, 200) == 120.0
        # 150 BPM already <= 200 max
        assert adjust_bpm_to_range(150.0, None, 200) == 150.0
        # 60 BPM has no min constraint
        assert adjust_bpm_to_range(60.0, None, 200) == 60.0

    def test_genre_presets_hip_hop(self):
        """Test with Hip Hop / Trap range (55-118 BPM)."""
        # Typical hip-hop style double-time detection
        assert adjust_bpm_to_range(160.0, 55, 118) == 80.0  # Half
        assert adjust_bpm_to_range(90.0, 55, 118) == 90.0   # Already in range
        assert adjust_bpm_to_range(45.0, 55, 118) == 90.0   # Double

    def test_genre_presets_house_techno(self):
        """Test with House / Techno range (98-138 BPM)."""
        assert adjust_bpm_to_range(65.0, 98, 138) == 130.0  # Double
        assert adjust_bpm_to_range(122.0, 98, 138) == 122.0 # Already in range
        assert adjust_bpm_to_range(260.0, 98, 138) == 130.0 # Half

    def test_genre_presets_dnb(self):
        """Test with Drum & Bass range (149-181 BPM)."""
        # D&B often detected at half time
        assert adjust_bpm_to_range(85.0, 149, 181) == 170.0  # Double
        assert adjust_bpm_to_range(174.0, 149, 181) == 174.0 # Already in range
        # 350 would half to 175 which is in range
        assert adjust_bpm_to_range(350.0, 149, 181) == 175.0 # Half

    def test_float_precision(self):
        """Test that float precision is maintained."""
        result = adjust_bpm_to_range(63.25, 80, 200)
        assert result == 126.5  # 63.25 * 2

        result = adjust_bpm_to_range(247.5, 80, 200)
        assert result == 123.75  # 247.5 / 2

    def test_edge_cases(self):
        """Test edge cases."""
        # Very low BPM
        assert adjust_bpm_to_range(30.0, 80, 200) == 60.0  # Double, still below but can't double again

        # Very high BPM
        assert adjust_bpm_to_range(400.0, 80, 200) == 200.0  # Half to exactly max

    def test_zero_min_treated_as_none(self):
        """When min_bpm is 0, it should be treated the same as None.

        Note: The caller is responsible for converting 0 to None before calling
        this function. This test verifies the behavior when 0 is passed directly.
        """
        # 0 as min_bpm - BPM is above 0, so no doubling needed
        # This tests that the function handles 0 gracefully
        result = adjust_bpm_to_range(60.0, 0, 200)
        # 60 is above 0, so it's considered "in range" for min
        assert result == 60.0

    def test_zero_max_treated_correctly(self):
        """When max_bpm is 0, BPM is always above it.

        Note: The caller is responsible for converting 0 to None.
        """
        # This is a degenerate case - 0 as max means everything is above max
        # Halving 120 to 60 is still > 0, so adjustment happens
        result = adjust_bpm_to_range(120.0, 0, 0)
        # Both 0: min check says 120 >= 0 (ok), max check says 120 > 0 (needs halving)
        # Halved: 60 >= 0 (ok), so 60 is returned
        assert result == 60.0


class TestBpmCandidate:
    """Tests for the BpmCandidate dataclass."""

    def test_creation_with_defaults(self):
        """Test creating a BpmCandidate with default certainty."""
        candidate = BpmCandidate(bpm=120.0)
        assert candidate.bpm == 120.0
        assert candidate.certainty == 0.0

    def test_creation_with_certainty(self):
        """Test creating a BpmCandidate with explicit certainty."""
        candidate = BpmCandidate(bpm=128.5, certainty=0.95)
        assert candidate.bpm == 128.5
        assert candidate.certainty == 0.95

    def test_repr(self):
        """Test string representation of BpmCandidate."""
        candidate = BpmCandidate(bpm=120.0, certainty=0.85)
        repr_str = repr(candidate)
        assert "120.00" in repr_str
        assert "0.8500" in repr_str


class TestSelectBestBpm:
    """Tests for the select_best_bpm function."""

    def test_empty_candidates_returns_none(self):
        """Empty candidates list should return None."""
        result = select_best_bpm([], min_bpm=80, max_bpm=200)
        assert result is None

    def test_single_candidate_in_range(self):
        """Single candidate in range should be returned unchanged."""
        candidates = [BpmCandidate(bpm=120.0, certainty=0.9)]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        assert result == 120.0

    def test_single_candidate_needs_doubling(self):
        """Single candidate below range should be doubled."""
        candidates = [BpmCandidate(bpm=65.0, certainty=0.9)]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        assert result == 130.0  # 65 * 2

    def test_single_candidate_needs_halving(self):
        """Single candidate above range should be halved."""
        candidates = [BpmCandidate(bpm=240.0, certainty=0.9)]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        assert result == 120.0  # 240 / 2

    def test_selects_highest_certainty(self):
        """Should select candidate with highest certainty."""
        candidates = [
            BpmCandidate(bpm=100.0, certainty=0.5),
            BpmCandidate(bpm=120.0, certainty=0.9),  # Highest certainty
            BpmCandidate(bpm=140.0, certainty=0.7),
        ]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        assert result == 120.0

    def test_highest_certainty_adjusted(self):
        """Highest certainty candidate should be adjusted if out of range."""
        candidates = [
            BpmCandidate(bpm=120.0, certainty=0.5),  # In range, lower certainty
            BpmCandidate(bpm=65.0, certainty=0.9),   # Out of range, highest certainty
        ]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        # Should select 65 (highest certainty) and double to 130
        assert result == 130.0

    def test_no_constraints(self):
        """With no constraints, highest certainty candidate is returned as-is."""
        candidates = [
            BpmCandidate(bpm=65.0, certainty=0.9),
            BpmCandidate(bpm=120.0, certainty=0.5),
        ]
        result = select_best_bpm(candidates, min_bpm=None, max_bpm=None)
        assert result == 65.0  # No adjustment

    def test_zero_certainty_candidates(self):
        """Candidates with zero certainty should still work (use first by sort order)."""
        candidates = [
            BpmCandidate(bpm=100.0, certainty=0.0),
            BpmCandidate(bpm=120.0, certainty=0.0),
            BpmCandidate(bpm=140.0, certainty=0.0),
        ]
        result = select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        # All have same certainty (0.0), should pick first in stable sort order
        assert result in [100.0, 120.0, 140.0]

    def test_multiple_candidates_various_certainties(self):
        """Test with various candidates and certainties."""
        candidates = [
            BpmCandidate(bpm=85.0, certainty=0.6),
            BpmCandidate(bpm=170.0, certainty=0.8),  # Second highest
            BpmCandidate(bpm=128.0, certainty=0.95), # Highest
            BpmCandidate(bpm=64.0, certainty=0.4),
        ]
        result = select_best_bpm(candidates, min_bpm=100, max_bpm=160)
        # Highest certainty is 128.0 - already in range
        assert result == 128.0
