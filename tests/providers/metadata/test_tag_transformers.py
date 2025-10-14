"""
Unit tests for tag value transformers.

Tests the core transformer functionality including:
- EmptyStringHandler
- WhitespaceTrimmer
- Transformer registry
"""

import pytest
from PySide6.QtCore import QSettings

from providers.metadata.tag_transformers import (
    TransformerBase,
    EmptyStringHandler,
    WhitespaceTrimmer,
    BPMFormatter,
    MusicalKeyFormatter,
    register_transformer,
    get_transformers_for_tag,
    apply_transformations,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Create a temporary QSettings instance for testing."""
    settings_file = tmp_path / "test_settings.ini"
    settings = QSettings(str(settings_file), QSettings.Format.IniFormat)
    yield settings
    settings.clear()


class TestEmptyStringHandler:
    """Tests for EmptyStringHandler transformer."""

    def test_none_to_empty_string(self, mock_settings):
        """Test that None values are converted to empty string."""
        handler = EmptyStringHandler(mock_settings)
        result = handler.transform(None, 'title')
        assert result == ""

    def test_empty_string_preserved(self, mock_settings):
        """Test that empty strings remain empty."""
        handler = EmptyStringHandler(mock_settings)
        result = handler.transform("", 'title')
        assert result == ""

    def test_whitespace_only_to_empty(self, mock_settings):
        """Test that whitespace-only strings become empty."""
        handler = EmptyStringHandler(mock_settings)
        assert handler.transform("   ", 'title') == ""
        assert handler.transform("\t\n", 'title') == ""
        assert handler.transform("  \t  \n  ", 'title') == ""

    def test_non_empty_string_preserved(self, mock_settings):
        """Test that non-empty strings are converted to string but not modified."""
        handler = EmptyStringHandler(mock_settings)
        result = handler.transform("Hello", 'title')
        assert result == "Hello"

    def test_integer_converted_to_string(self, mock_settings):
        """Test that integers are converted to strings."""
        handler = EmptyStringHandler(mock_settings)
        result = handler.transform(123, 'bpm')
        assert result == "123"

    def test_float_converted_to_string(self, mock_settings):
        """Test that floats are converted to strings."""
        handler = EmptyStringHandler(mock_settings)
        result = handler.transform(173.94, 'bpm')
        assert result == "173.94"

    def test_applicable_tags(self):
        """Test that EmptyStringHandler declares applicable tags."""
        assert 'title' in EmptyStringHandler.applicable_tags
        assert 'bpm' in EmptyStringHandler.applicable_tags
        assert 'key' in EmptyStringHandler.applicable_tags

    def test_priority(self):
        """Test that EmptyStringHandler has priority 5 (runs first)."""
        assert EmptyStringHandler.priority == 5


class TestWhitespaceTrimmer:
    """Tests for WhitespaceTrimmer transformer."""

    def test_trim_leading_whitespace(self, mock_settings):
        """Test trimming leading whitespace."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform("  Title", 'title') == "Title"
        assert trimmer.transform("\tArtist", 'artist') == "Artist"

    def test_trim_trailing_whitespace(self, mock_settings):
        """Test trimming trailing whitespace."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform("Title  ", 'title') == "Title"
        assert trimmer.transform("Artist\n", 'artist') == "Artist"

    def test_trim_both_sides(self, mock_settings):
        """Test trimming whitespace from both sides."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform("  Title  ", 'title') == "Title"
        assert trimmer.transform("\n\tAlbum\t\n", 'album') == "Album"

    def test_preserve_internal_whitespace(self, mock_settings):
        """Test that internal whitespace is preserved."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform("  My Song Title  ", 'title') == "My Song Title"
        assert trimmer.transform("Artist  Name", 'artist') == "Artist  Name"

    def test_empty_string(self, mock_settings):
        """Test handling of empty strings."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform("", 'title') == ""

    def test_none_value(self, mock_settings):
        """Test handling of None values."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform(None, 'title') == ""

    def test_numeric_values(self, mock_settings):
        """Test that numeric values are converted to strings."""
        trimmer = WhitespaceTrimmer(mock_settings)
        assert trimmer.transform(123, 'bpm') == "123"
        assert trimmer.transform(173.94, 'bpm') == "173.94"

    def test_applicable_tags(self):
        """Test that WhitespaceTrimmer declares applicable tags."""
        assert 'title' in WhitespaceTrimmer.applicable_tags
        assert 'artist' in WhitespaceTrimmer.applicable_tags
        assert 'bpm' in WhitespaceTrimmer.applicable_tags

    def test_priority(self):
        """Test that WhitespaceTrimmer has priority 10 (runs early)."""
        assert WhitespaceTrimmer.priority == 10


class TestTransformerRegistry:
    """Tests for the transformer registry system."""

    def test_registration(self):
        """Test that transformers are registered for their applicable tags."""
        transformers = get_transformers_for_tag('title')
        transformer_names = [t.name for t in transformers]
        assert 'Empty String Handler' in transformer_names
        assert 'Whitespace Trimmer' in transformer_names

    def test_priority_ordering(self):
        """Test that transformers are returned in priority order."""
        transformers = get_transformers_for_tag('title')
        # EmptyStringHandler (priority 5) should come before WhitespaceTrimmer (priority 10)
        assert transformers[0].priority < transformers[1].priority
        assert transformers[0] == EmptyStringHandler
        assert transformers[1] == WhitespaceTrimmer

    def test_no_transformers_for_unknown_tag(self):
        """Test that unknown tags return empty list."""
        transformers = get_transformers_for_tag('unknown_tag_12345')
        assert transformers == []


class TestApplyTransformations:
    """Tests for the apply_transformations function."""

    def test_apply_to_title_with_whitespace(self, mock_settings):
        """Test applying transformers to a title with whitespace."""
        result = apply_transformations('title', '  My Song  ', mock_settings)
        assert result == "My Song"

    def test_apply_to_none_value(self, mock_settings):
        """Test applying transformers to None value."""
        result = apply_transformations('title', None, mock_settings)
        assert result == ""

    def test_apply_to_empty_string(self, mock_settings):
        """Test applying transformers to empty string."""
        result = apply_transformations('title', '', mock_settings)
        assert result == ""

    def test_apply_to_whitespace_only(self, mock_settings):
        """Test applying transformers to whitespace-only string."""
        result = apply_transformations('title', '   ', mock_settings)
        assert result == ""

    def test_apply_to_numeric_value(self, mock_settings):
        """Test applying transformers to numeric values."""
        # BPM formatter is now applied with default 0 decimal places
        result = apply_transformations('bpm', 173.94, mock_settings)
        assert result == "174"

    def test_transformation_pipeline_order(self, mock_settings):
        """Test that transformers are applied in correct order."""
        # Input: "  123  " (string with whitespace)
        # EmptyStringHandler: "  123  " (not empty, converted to string)
        # WhitespaceTrimmer: "123" (whitespace removed)
        result = apply_transformations('bpm', '  123  ', mock_settings)
        assert result == "123"

    def test_unknown_tag_returns_string(self, mock_settings):
        """Test that unknown tags are just converted to string."""
        result = apply_transformations('unknown_tag', 'value', mock_settings)
        assert result == "value"

    def test_unknown_tag_none_returns_empty(self, mock_settings):
        """Test that unknown tags with None return empty string."""
        result = apply_transformations('unknown_tag', None, mock_settings)
        assert result == ""


class TestCustomTransformer:
    """Tests for custom transformer registration."""

    def test_custom_transformer_registration(self, mock_settings):
        """Test that custom transformers can be registered."""

        class CustomTransformer(TransformerBase):
            name = "Custom Test Transformer"
            description = "Test transformer"
            version = "1.0.0"
            applicable_tags = ['custom_tag']
            priority = 50

            def transform(self, value, tag_name):
                return f"custom_{value}"

        # Register the custom transformer
        register_transformer(CustomTransformer)

        # Verify it's registered
        transformers = get_transformers_for_tag('custom_tag')
        assert any(t.name == "Custom Test Transformer" for t in transformers)

        # Test applying transformations
        result = apply_transformations('custom_tag', 'test', mock_settings)
        assert result == "custom_test"


class TestBPMFormatter:
    """Tests for BPMFormatter transformer."""

    def test_format_integer_bpm_zero_decimals(self, mock_settings):
        """Test formatting integer BPM with 0 decimal places."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 0)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform(120, 'bpm') == "120"
        assert formatter.transform(173, 'bpm') == "173"

    def test_format_float_bpm_zero_decimals(self, mock_settings):
        """Test formatting float BPM with 0 decimal places (rounds)."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 0)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform(173.94, 'bpm') == "174"
        assert formatter.transform(120.4, 'bpm') == "120"
        assert formatter.transform(120.5, 'bpm') == "120"  # Python rounds to even
        assert formatter.transform(121.5, 'bpm') == "122"

    def test_format_bpm_one_decimal(self, mock_settings):
        """Test formatting BPM with 1 decimal place."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 1)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform(173.94, 'bpm') == "173.9"
        assert formatter.transform(120, 'bpm') == "120.0"
        assert formatter.transform(120.45, 'bpm') == "120.5"  # Python rounds to nearest even

    def test_format_bpm_two_decimals(self, mock_settings):
        """Test formatting BPM with 2 decimal places."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 2)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform(173.94, 'bpm') == "173.94"
        assert formatter.transform(120, 'bpm') == "120.00"
        assert formatter.transform(120.456, 'bpm') == "120.46"

    def test_format_bpm_three_decimals(self, mock_settings):
        """Test formatting BPM with 3 decimal places."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 3)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform(173.944, 'bpm') == "173.944"
        assert formatter.transform(120, 'bpm') == "120.000"

    def test_format_string_bpm(self, mock_settings):
        """Test formatting BPM from string input."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 0)
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform("173.94", 'bpm') == "174"
        assert formatter.transform("120", 'bpm') == "120"

    def test_invalid_bpm_raises_error(self, mock_settings):
        """Test that invalid BPM values raise ValueError."""
        formatter = BPMFormatter(mock_settings)
        with pytest.raises(ValueError):
            formatter.transform("not a number", 'bpm')
        with pytest.raises(ValueError):
            formatter.transform("120abc", 'bpm')

    def test_empty_bpm(self, mock_settings):
        """Test handling of empty BPM value."""
        formatter = BPMFormatter(mock_settings)
        assert formatter.transform("", 'bpm') == ""

    def test_default_decimal_places(self, mock_settings):
        """Test that default decimal places is 0."""
        # Don't set the preference, should default to 0
        formatter = BPMFormatter(mock_settings)
        assert formatter.decimal_places == 0
        assert formatter.transform(173.94, 'bpm') == "174"

    def test_clamp_invalid_decimal_places(self, mock_settings):
        """Test that invalid decimal places are clamped to valid range."""
        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", -1)
        formatter = BPMFormatter(mock_settings)
        assert formatter.decimal_places == 0

        mock_settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", 10)
        formatter = BPMFormatter(mock_settings)
        assert formatter.decimal_places == 3

    def test_applicable_tags(self):
        """Test that BPMFormatter declares bpm as applicable tag."""
        assert 'bpm' in BPMFormatter.applicable_tags

    def test_priority(self):
        """Test that BPMFormatter has default priority 50."""
        assert BPMFormatter.priority == 50


class TestMusicalKeyFormatter:
    """Tests for MusicalKeyFormatter transformer."""

    def test_parse_standard_abbrev(self, mock_settings):
        """Test parsing standard abbreviated notation."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("Cmin", 'key') == "Cmin"
        assert formatter.transform("Cmaj", 'key') == "Cmaj"
        assert formatter.transform("C#min", 'key') == "C#min"
        assert formatter.transform("Ebmin", 'key') == "Ebmin"

    def test_parse_standard_single(self, mock_settings):
        """Test parsing standard single-letter notation."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter = MusicalKeyFormatter(mock_settings)

        # Parse various formats and convert to standard_abbrev
        assert formatter.transform("Cm", 'key') == "Cmin"
        assert formatter.transform("C", 'key') == "Cmaj"
        assert formatter.transform("Am", 'key') == "Amin"
        assert formatter.transform("A", 'key') == "Amaj"

    def test_parse_long_names(self, mock_settings):
        """Test parsing long key names."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("C minor", 'key') == "Cmin"
        assert formatter.transform("C major", 'key') == "Cmaj"
        assert formatter.transform("A minor", 'key') == "Amin"

    def test_convert_to_camelot(self, mock_settings):
        """Test conversion to Camelot notation."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "camelot")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("Cmin", 'key') == "5A"
        assert formatter.transform("Cmaj", 'key') == "8B"
        assert formatter.transform("Amin", 'key') == "8A"
        assert formatter.transform("Amaj", 'key') == "11B"
        assert formatter.transform("Ebmin", 'key') == "2A"

    def test_convert_to_open_key(self, mock_settings):
        """Test conversion to Open Key notation."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "open_key")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("Cmin", 'key') == "5m"
        assert formatter.transform("Cmaj", 'key') == "8d"
        assert formatter.transform("Amin", 'key') == "8m"
        assert formatter.transform("Amaj", 'key') == "11d"

    def test_convert_to_standard_single(self, mock_settings):
        """Test conversion to standard single notation."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_single")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("Cmin", 'key') == "Cm"
        assert formatter.transform("Cmaj", 'key') == "C"
        assert formatter.transform("Amin", 'key') == "Am"
        assert formatter.transform("Amaj", 'key') == "A"

    def test_parse_camelot_input(self, mock_settings):
        """Test parsing Camelot notation as input."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("5A", 'key') == "Cmin"
        assert formatter.transform("8B", 'key') == "Cmaj"
        assert formatter.transform("8A", 'key') == "Amin"
        assert formatter.transform("11B", 'key') == "Amaj"

    def test_parse_open_key_input(self, mock_settings):
        """Test parsing Open Key notation as input."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter = MusicalKeyFormatter(mock_settings)

        assert formatter.transform("5m", 'key') == "Cmin"
        assert formatter.transform("8d", 'key') == "Cmaj"
        assert formatter.transform("8m", 'key') == "Amin"
        assert formatter.transform("11d", 'key') == "Amaj"

    def test_roundtrip_conversion(self, mock_settings):
        """Test that conversions are reversible."""
        # Convert standard -> camelot -> standard
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "camelot")
        formatter_camelot = MusicalKeyFormatter(mock_settings)
        camelot = formatter_camelot.transform("Cmin", 'key')

        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        formatter_standard = MusicalKeyFormatter(mock_settings)
        standard = formatter_standard.transform(camelot, 'key')

        assert standard == "Cmin"

    def test_empty_key(self, mock_settings):
        """Test handling of empty key value."""
        formatter = MusicalKeyFormatter(mock_settings)
        assert formatter.transform("", 'key') == ""
        assert formatter.transform(None, 'key') == ""

    def test_invalid_key_raises_error(self, mock_settings):
        """Test that invalid key notation raises ValueError."""
        formatter = MusicalKeyFormatter(mock_settings)
        with pytest.raises(ValueError):
            formatter.transform("invalid", 'key')
        with pytest.raises(ValueError):
            formatter.transform("Z minor", 'key')

    def test_default_notation_format(self, mock_settings):
        """Test that default notation format is standard_abbrev."""
        formatter = MusicalKeyFormatter(mock_settings)
        assert formatter.notation_format == "standard_abbrev"

    def test_invalid_notation_format_uses_default(self, mock_settings):
        """Test that invalid notation format falls back to default."""
        mock_settings.setValue("Analyzers/CategoryOptions/key/notation_format", "invalid_format")
        formatter = MusicalKeyFormatter(mock_settings)
        assert formatter.notation_format == "standard_abbrev"

    def test_applicable_tags(self):
        """Test that MusicalKeyFormatter declares applicable tags."""
        assert 'key' in MusicalKeyFormatter.applicable_tags
        assert 'musical_key' in MusicalKeyFormatter.applicable_tags

    def test_priority(self):
        """Test that MusicalKeyFormatter has default priority 50."""
        assert MusicalKeyFormatter.priority == 50
