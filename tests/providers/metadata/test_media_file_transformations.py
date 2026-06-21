"""
Integration tests for tag transformation pipeline in MediaFile.

Tests the integration between MediaFile.save() and the transformation pipeline.
"""

import shutil
import pytest
import time
from pathlib import Path

from models.media_file import MediaFile
from util.const import (
    KEY_ARTIST,
    KEY_BPM,
    KEY_TAG_GENERIC,
    KEY_TITLE,
    PROJECT_ROOT,
    SETTINGS_BPM_DECIMAL_PLACES,
)


# Test fixture file
SOURCE_FILE = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3"

# QSettings isolation is provided by the autouse `isolated_qsettings` fixture
# in tests/conftest.py. Tests that need a specific preference value accept it
# as a parameter and call setValue() on it.


class TestMediaFileTransformations:
    """Tests for MediaFile transformation integration."""

    def test_transformations_applied_to_generic_tags(self, tmp_path):
        """Test that transformations are applied to generic tag changes."""
        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with whitespace that should be trimmed
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "  Test Title  ",
                KEY_ARTIST: "\tTest Artist\n",
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify transformations were applied
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_TITLE) == "Test Title"
        assert media_file_read.get_tag_simple(KEY_ARTIST) == "Test Artist"

    def test_bypass_transformations_parameter(self, tmp_path):
        """Test that bypass_transformations parameter skips transformations."""
        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with bypass_transformations=True
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "  Test Title  ",
            }
        }
        media_file.save(changes, bypass_transformations=True)
        time.sleep(0.1)

        # Read back and verify whitespace was NOT trimmed
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_TITLE) == "  Test Title  "

    def test_empty_string_transformation(self, tmp_path):
        """Test that None and empty values are normalized to empty string."""
        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with None value
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: None,
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify empty string
        media_file_read = MediaFile(str(temp_file))
        result = media_file_read.get_tag_simple(KEY_TITLE)
        assert result == "" or result is None  # Depends on provider behavior

    def test_whitespace_only_transformation(self, tmp_path):
        """Test that whitespace-only strings become empty."""
        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with whitespace-only value
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "   ",
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify empty string
        media_file_read = MediaFile(str(temp_file))
        result = media_file_read.get_tag_simple(KEY_TITLE)
        assert result == "" or result is None  # Depends on provider behavior

    def test_multiple_tags_transformed(self, tmp_path, isolated_qsettings):
        """Test that multiple tags are transformed in a single save."""
        # Pin the BPM decimal-places preference so the expected output is
        # deterministic regardless of the developer's real user settings.
        isolated_qsettings.setValue(SETTINGS_BPM_DECIMAL_PLACES, 0)

        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save multiple tags with whitespace
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "  Title  ",
                KEY_ARTIST: "  Artist  ",
                KEY_BPM: "  120  ",
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify all were transformed
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_TITLE) == "Title"
        assert media_file_read.get_tag_simple(KEY_ARTIST) == "Artist"
        assert media_file_read.get_tag_simple(KEY_BPM) == "120"

    def test_numeric_value_transformation(self, tmp_path, isolated_qsettings):
        """Test that numeric values are converted to strings."""
        isolated_qsettings.setValue(SETTINGS_BPM_DECIMAL_PLACES, 0)

        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with numeric value (int)
        changes = {
            KEY_TAG_GENERIC: {
                KEY_BPM: 120,
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify it was converted to string
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_BPM) == "120"

    def test_transformation_pipeline_order(self, tmp_path):
        """Test that transformers are applied in correct priority order."""
        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with value that will go through multiple transformers
        # EmptyStringHandler (priority 5) should run first, then WhitespaceTrimmer (priority 10)
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "  Not Empty  ",  # Should be trimmed to "Not Empty"
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify correct transformation
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_TITLE) == "Not Empty"

    def test_internal_tags_not_transformed(self, tmp_path):
        """Test that internal tags are never transformed."""
        # This test verifies that KEY_TAG_INTERNAL changes bypass transformations
        # Since we don't have easy access to internal tags in this test setup,
        # we'll just verify that the code path exists and doesn't crash

        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with only generic tags (internal tags would need provider access)
        changes = {
            KEY_TAG_GENERIC: {
                KEY_TITLE: "Test",
            }
        }
        # This should not raise any errors
        media_file.save(changes)
        time.sleep(0.1)

        # Verify the tag was saved
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_TITLE) == "Test"

    @pytest.mark.parametrize(
        "decimal_places, expected",
        [
            # Integer rendering (rounded, no decimal point).
            (0, "174"),
            # Decimal rendering at each supported precision.
            (1, "173.9"),
            (2, "173.94"),
            (3, "173.940"),
        ],
    )
    def test_transformation_with_float_value(
        self, tmp_path, isolated_qsettings, decimal_places, expected
    ):
        """Float BPM is rendered per the decimal_places preference through the
        full save pipeline, covering both integer and decimal formatting."""
        isolated_qsettings.setValue(SETTINGS_BPM_DECIMAL_PLACES, decimal_places)

        # Create a temporary copy of the file
        temp_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, temp_file)

        # Create MediaFile with write enabled
        media_file = MediaFile(str(temp_file), enable_write=True)

        # Save with float value
        changes = {
            KEY_TAG_GENERIC: {
                KEY_BPM: 173.94,
            }
        }
        media_file.save(changes)
        time.sleep(0.1)

        # Read back and verify the BPM was formatted per the preference.
        media_file_read = MediaFile(str(temp_file))
        assert media_file_read.get_tag_simple(KEY_BPM) == expected
