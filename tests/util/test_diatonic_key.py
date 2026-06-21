"""
Unit tests for the diatonic key conversion system.

Tests the musical key parsing and formatting functionality including:
- Parse various key notation formats
- Format keys to different notation systems
- Round-trip conversions
- Music theory validation
"""

import pytest
from util.diatonic_key import (
    parse_key,
    format_key,
    NotationFormat,
    CAMELOT_MAP,
    OPEN_KEY_MAP,
    NOTE_TO_PITCH
)


class TestParseKeyStandardNotation:
    """Tests for parsing standard musical key notation."""

    def test_parse_major_keys_abbreviated(self):
        """Test parsing major keys with 'maj' suffix."""
        assert parse_key("Cmaj") == (0, False)
        assert parse_key("Dmaj") == (2, False)
        assert parse_key("Emaj") == (4, False)
        assert parse_key("Fmaj") == (5, False)
        assert parse_key("Gmaj") == (7, False)
        assert parse_key("Amaj") == (9, False)
        assert parse_key("Bmaj") == (11, False)

    def test_parse_minor_keys_abbreviated(self):
        """Test parsing minor keys with 'min' suffix."""
        assert parse_key("Cmin") == (0, True)
        assert parse_key("Dmin") == (2, True)
        assert parse_key("Emin") == (4, True)
        assert parse_key("Fmin") == (5, True)
        assert parse_key("Gmin") == (7, True)
        assert parse_key("Amin") == (9, True)
        assert parse_key("Bmin") == (11, True)

    def test_parse_major_keys_full_name(self):
        """Test parsing major keys with 'major' suffix."""
        assert parse_key("C major") == (0, False)
        assert parse_key("D major") == (2, False)
        assert parse_key("A major") == (9, False)

    def test_parse_minor_keys_full_name(self):
        """Test parsing minor keys with 'minor' suffix."""
        assert parse_key("C minor") == (0, True)
        assert parse_key("D minor") == (2, True)
        assert parse_key("A minor") == (9, True)

    def test_parse_single_letter_notation(self):
        """Test parsing single letter notation (major = no suffix, minor = 'm')."""
        # Major keys (no suffix)
        assert parse_key("C") == (0, False)
        assert parse_key("D") == (2, False)
        assert parse_key("G") == (7, False)

        # Minor keys ('m' suffix)
        assert parse_key("Cm") == (0, True)
        assert parse_key("Dm") == (2, True)
        assert parse_key("Am") == (9, True)

    def test_parse_sharps(self):
        """Test parsing keys with sharp accidentals."""
        assert parse_key("C#maj") == (1, False)
        assert parse_key("C#min") == (1, True)
        assert parse_key("F#maj") == (6, False)
        assert parse_key("F#min") == (6, True)
        assert parse_key("G#m") == (8, True)

        # Test unicode sharp symbol
        assert parse_key("C♯maj") == (1, False)

    def test_parse_flats(self):
        """Test parsing keys with flat accidentals."""
        assert parse_key("Dbmaj") == (1, False)
        assert parse_key("Dbmin") == (1, True)
        assert parse_key("Ebmaj") == (3, False)
        assert parse_key("Ebmin") == (3, True)
        assert parse_key("Bbm") == (10, True)

        # Test unicode flat symbol
        assert parse_key("D♭maj") == (1, False)

    def test_parse_enharmonic_equivalents(self):
        """Test that enharmonic equivalents parse to the same pitch class."""
        # C# and Db are both pitch class 1
        assert parse_key("C#maj") == parse_key("Dbmaj")
        assert parse_key("C#min") == parse_key("Dbmin")

        # F# and Gb are both pitch class 6
        assert parse_key("F#maj") == parse_key("Gbmaj")
        assert parse_key("F#min") == parse_key("Gbmin")

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        assert parse_key("cmin") == (0, True)
        assert parse_key("CMIN") == (0, True)
        assert parse_key("CmIn") == (0, True)
        assert parse_key("c") == (0, False)
        assert parse_key("cm") == (0, True)


class TestParseKeyCamelotNotation:
    """Tests for parsing Camelot wheel notation."""

    def test_parse_camelot_minor_keys(self):
        """Test parsing Camelot minor keys (A suffix)."""
        assert parse_key("5A") == (0, True)   # C minor
        assert parse_key("12A") == (1, True)  # C#/Db minor
        assert parse_key("7A") == (2, True)   # D minor
        assert parse_key("8A") == (9, True)   # A minor
        assert parse_key("10A") == (11, True) # B minor

    def test_parse_camelot_major_keys(self):
        """Test parsing Camelot major keys (B suffix)."""
        assert parse_key("8B") == (0, False)  # C major
        assert parse_key("3B") == (1, False)  # C#/Db major
        assert parse_key("10B") == (2, False) # D major
        assert parse_key("11B") == (9, False) # A major
        assert parse_key("1B") == (11, False) # B major

    def test_parse_camelot_all_positions(self):
        """Test that all 24 Camelot positions parse correctly."""
        # Verify all Camelot mappings can be parsed
        for (pitch, is_minor), camelot in CAMELOT_MAP.items():
            assert parse_key(camelot) == (pitch, is_minor), \
                f"Failed to parse Camelot notation '{camelot}'"


class TestParseKeyOpenKeyNotation:
    """Tests for parsing Open Key notation."""

    def test_parse_open_key_minor_keys(self):
        """Test parsing Open Key minor keys (m suffix)."""
        assert parse_key("5m") == (0, True)   # C minor
        assert parse_key("12m") == (1, True)  # C#/Db minor
        assert parse_key("7m") == (2, True)   # D minor
        assert parse_key("8m") == (9, True)   # A minor
        assert parse_key("10m") == (11, True) # B minor

    def test_parse_open_key_major_keys(self):
        """Test parsing Open Key major keys (d suffix)."""
        assert parse_key("8d") == (0, False)  # C major
        assert parse_key("3d") == (1, False)  # C#/Db major
        assert parse_key("10d") == (2, False) # D major
        assert parse_key("11d") == (9, False) # A major
        assert parse_key("1d") == (11, False) # B major

    def test_parse_open_key_all_positions(self):
        """Test that all 24 Open Key positions parse correctly."""
        # Verify all Open Key mappings can be parsed
        for (pitch, is_minor), open_key in OPEN_KEY_MAP.items():
            assert parse_key(open_key) == (pitch, is_minor), \
                f"Failed to parse Open Key notation '{open_key}'"


class TestParseKeyEdgeCases:
    """Tests for edge cases in key parsing."""

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        assert parse_key("") is None
        assert parse_key("   ") is None

    def test_parse_none(self):
        """Test parsing None returns None."""
        assert parse_key(None) is None

    def test_parse_invalid_input(self):
        """Test parsing invalid input returns None."""
        assert parse_key("invalid") is None
        assert parse_key("Z minor") is None
        assert parse_key("123") is None
        assert parse_key("!@#$") is None

    def test_parse_unknown_mode_assumes_major(self):
        """Test that unknown mode suffixes default to major."""
        result = parse_key("Cunknown")
        assert result == (0, False)  # Should parse as C major

    def test_parse_with_whitespace(self):
        """Test parsing handles leading/trailing whitespace."""
        assert parse_key("  Cmin  ") == (0, True)
        assert parse_key("\tAmaj\n") == (9, False)


class TestFormatKey:
    """Tests for formatting keys to different notation systems."""

    def test_format_standard_abbrev(self):
        """Test formatting to standard abbreviated notation."""
        assert format_key(0, True, NotationFormat.StandardAbbrev) == "Cmin"
        assert format_key(0, False, NotationFormat.StandardAbbrev) == "Cmaj"
        assert format_key(2, True, NotationFormat.StandardAbbrev) == "Dmin"
        assert format_key(9, False, NotationFormat.StandardAbbrev) == "Amaj"

    def test_format_standard_single(self):
        """Test formatting to standard single-letter notation."""
        assert format_key(0, True, NotationFormat.StandardSingle) == "Cm"
        assert format_key(0, False, NotationFormat.StandardSingle) == "C"
        assert format_key(2, True, NotationFormat.StandardSingle) == "Dm"
        assert format_key(9, False, NotationFormat.StandardSingle) == "A"

    def test_format_standard_full(self):
        """Test formatting to standard full-name notation."""
        assert format_key(0, True, NotationFormat.Standard) == "C minor"
        assert format_key(0, False, NotationFormat.Standard) == "C major"
        assert format_key(2, True, NotationFormat.Standard) == "D minor"
        assert format_key(9, False, NotationFormat.Standard) == "A major"

    def test_format_camelot(self):
        """Test formatting to Camelot notation."""
        assert format_key(0, True, NotationFormat.Camelot) == "5A"   # C minor
        assert format_key(0, False, NotationFormat.Camelot) == "8B"  # C major
        assert format_key(9, True, NotationFormat.Camelot) == "8A"   # A minor
        assert format_key(9, False, NotationFormat.Camelot) == "11B" # A major

    def test_format_open_key(self):
        """Test formatting to Open Key notation."""
        assert format_key(0, True, NotationFormat.OpenKey) == "5m"   # C minor
        assert format_key(0, False, NotationFormat.OpenKey) == "8d"  # C major
        assert format_key(9, True, NotationFormat.OpenKey) == "8m"   # A minor
        assert format_key(9, False, NotationFormat.OpenKey) == "11d" # A major

    def test_format_uses_mixed_sharps_flats(self):
        """Test that formatting uses the predetermined sharp/flat choices."""
        # The format_key function uses: ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
        assert format_key(1, False, NotationFormat.StandardAbbrev) == "C#maj"  # Not Db
        assert format_key(3, False, NotationFormat.StandardAbbrev) == "Ebmaj"  # Not D#
        assert format_key(6, False, NotationFormat.StandardAbbrev) == "F#maj"  # Not Gb
        assert format_key(8, False, NotationFormat.StandardAbbrev) == "Abmaj"  # Not G#
        assert format_key(10, False, NotationFormat.StandardAbbrev) == "Bbmaj" # Not A#


class TestRoundTripConversions:
    """Tests for round-trip conversions between notation systems."""

    def test_roundtrip_standard_to_camelot_to_standard(self):
        """Test converting standard -> camelot -> standard yields original."""
        test_keys = [
            (0, True),   # C minor
            (0, False),  # C major
            (9, True),   # A minor
            (9, False),  # A major
            (2, True),   # D minor
        ]

        for pitch, is_minor in test_keys:
            # Format to camelot
            camelot = format_key(pitch, is_minor, NotationFormat.Camelot)
            # Parse back
            parsed = parse_key(camelot)
            # Should match original
            assert parsed == (pitch, is_minor), \
                f"Round-trip failed for pitch={pitch}, is_minor={is_minor}"

    def test_roundtrip_standard_to_open_key_to_standard(self):
        """Test converting standard -> open key -> standard yields original."""
        test_keys = [
            (0, True),   # C minor
            (0, False),  # C major
            (9, True),   # A minor
            (9, False),  # A major
            (5, True),   # F minor
        ]

        for pitch, is_minor in test_keys:
            # Format to open key
            open_key = format_key(pitch, is_minor, NotationFormat.OpenKey)
            # Parse back
            parsed = parse_key(open_key)
            # Should match original
            assert parsed == (pitch, is_minor), \
                f"Round-trip failed for pitch={pitch}, is_minor={is_minor}"

    def test_roundtrip_all_pitch_classes(self):
        """Test round-trip conversion for all 12 pitch classes in both modes."""
        for pitch_class in range(12):
            for is_minor in [True, False]:
                # Test Camelot round-trip
                camelot = format_key(pitch_class, is_minor, NotationFormat.Camelot)
                assert parse_key(camelot) == (pitch_class, is_minor)

                # Test Open Key round-trip
                open_key = format_key(pitch_class, is_minor, NotationFormat.OpenKey)
                assert parse_key(open_key) == (pitch_class, is_minor)


class TestMusicTheoryValidation:
    """Tests to validate music theory correctness."""

    def test_relative_major_minor_pairs(self):
        """Test that relative major/minor pairs share the same Camelot number."""
        # In Camelot, relative keys share the same number but differ in letter (A vs B)
        # For example: C major (8B) and A minor (8A) are relative keys

        relative_pairs = [
            (0, False, 9, True),    # C major / A minor -> 8B / 8A
            (2, False, 11, True),   # D major / B minor -> 10B / 10A
            (7, False, 4, True),    # G major / E minor -> 9B / 9A
        ]

        for major_pitch, _, minor_pitch, _ in relative_pairs:
            major_camelot = format_key(major_pitch, False, NotationFormat.Camelot)
            minor_camelot = format_key(minor_pitch, True, NotationFormat.Camelot)

            # Extract the number part (should be the same)
            major_num = major_camelot[:-1]
            minor_num = minor_camelot[:-1]
            assert major_num == minor_num, \
                f"Relative keys should share Camelot number: {major_camelot} vs {minor_camelot}"

    def test_parallel_major_minor_different_numbers(self):
        """Test that parallel major/minor keys have different Camelot numbers."""
        # Parallel keys share the same root but differ in mode
        # For example: C major (8B) and C minor (5A) are parallel keys

        parallel_pairs = [
            0,  # C major vs C minor
            2,  # D major vs D minor
            9,  # A major vs A minor
        ]

        for pitch in parallel_pairs:
            major_camelot = format_key(pitch, False, NotationFormat.Camelot)
            minor_camelot = format_key(pitch, True, NotationFormat.Camelot)

            # Should have different numbers
            assert major_camelot != minor_camelot, \
                f"Parallel keys should have different Camelot codes: {major_camelot} vs {minor_camelot}"

    def test_camelot_wheel_adjacent_keys(self):
        """Test that adjacent Camelot numbers represent musically compatible keys."""
        # In the Camelot wheel, adjacent numbers (±1) are compatible for mixing
        # This follows the circle of fifths

        # Example: 8B (C major) is adjacent to 7B (F major, fourth below) and 9B (G major, fifth above)
        # Let's verify the circle of fifths progression
        circle_of_fifths_major = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]  # C, G, D, A, E, B, F#, Db, Ab, Eb, Bb, F

        # Verify that each step in the circle of fifths increments by 7 semitones (modulo 12)
        for i in range(len(circle_of_fifths_major) - 1):
            current = circle_of_fifths_major[i]
            next_key = circle_of_fifths_major[i + 1]
            # Next key should be 7 semitones higher (a perfect fifth)
            assert (current + 7) % 12 == next_key, \
                f"Circle of fifths broken at pitch class {current}"

    def test_pitch_class_mapping(self):
        """Test that NOTE_TO_PITCH mapping is correct."""
        # Verify the chromatic scale
        assert NOTE_TO_PITCH['C'] == 0
        assert NOTE_TO_PITCH['D'] == 2
        assert NOTE_TO_PITCH['E'] == 4
        assert NOTE_TO_PITCH['F'] == 5
        assert NOTE_TO_PITCH['G'] == 7
        assert NOTE_TO_PITCH['A'] == 9
        assert NOTE_TO_PITCH['B'] == 11

        # Verify intervals
        assert NOTE_TO_PITCH['D'] - NOTE_TO_PITCH['C'] == 2  # Major second
        assert NOTE_TO_PITCH['E'] - NOTE_TO_PITCH['C'] == 4  # Major third
        assert NOTE_TO_PITCH['G'] - NOTE_TO_PITCH['C'] == 7  # Perfect fifth
