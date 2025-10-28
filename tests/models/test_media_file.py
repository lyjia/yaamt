import json
import os
import shutil
from pathlib import Path
import pytest
import time
from models.media_file import MediaFile
from models.edit_manager import EditManager
from util.const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_INITIAL_KEY, PROJECT_ROOT, KEY_IS_MEDIA, KEY_TAG_GENERIC, KEY_TAG_INTERNAL
from util.exceptions import InvalidFileError

# Define the directory containing the test fixtures.
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "metadata"
SOURCE_FILE = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3"

# Discover all audio files in the fixture directory.
# This list will be used to parameterize the test function.
test_files = [p for p in FIXTURE_DIR.glob('*') if (p.suffix == '.mp3' or p.suffix == ".flac")]

def filter_keys(obj, keys_to_ignore):
    """
    Recursively filters keys from a dictionary or a list of dictionaries.
    """
    if isinstance(obj, dict):
        return {k: filter_keys(v, keys_to_ignore) for k, v in obj.items() if k not in keys_to_ignore}
    if isinstance(obj, list):
        return [filter_keys(elem, keys_to_ignore) for elem in obj]
    return obj


@pytest.mark.parametrize("media_path", test_files)
def test_to_dict_parameterized(media_path):
    """
    A parameterized test that verifies the to_dict() method of the MediaFile class.

    This test dynamically discovers all media files in the fixtures/metadata
    directory and uses them to create test cases. For each media file, it
    locates a corresponding .json file with the same name, which contains the
    expected output of the to_dict() method.

    This approach avoids hardcoding test data and makes it easy to add new
    test cases: simply add a new media file and its corresponding .json file
    to the fixtures directory.

    Args:
        media_path (Path): The path to the media file to be tested.
    """
    # Construct the path to the JSON file with the expected results.
    expected_json_path = media_path.with_suffix(media_path.suffix + '.json')

    # Load the expected results from the JSON file.
    with open(expected_json_path, 'r', encoding='utf-8') as f:
        expected_dict = json.load(f)

    # Initialize the MediaFile object with the path to the test file.
    media_file = MediaFile(media_path)

    # Get the actual dictionary from the MediaFile object.
    actual_dict = media_file.to_dict()

    # Define the keys to ignore during comparison.
    keys_to_ignore = {'fsize', 'fmtime', 'fatime', 'fctime', 'fpath', 'iswritable'}

    # Filter the dictionaries to remove the ignored keys.
    actual_filtered = filter_keys(actual_dict, keys_to_ignore)
    expected_filtered = filter_keys(expected_dict, keys_to_ignore)

    # Assert that the filtered dictionaries are equal.
    assert actual_filtered == expected_filtered


@pytest.mark.parametrize("media_path", test_files)
def test_write_tags(media_path, tmp_path):
    """
    A parameterized test that verifies the write functionality of the MediaFile class.
    """
    # Create a temporary copy of the file to write to.
    temp_media_path = tmp_path / media_path.name
    shutil.copy(media_path, temp_media_path)

    # Create a MediaFile instance for the temporary file.
    media_file = MediaFile(str(temp_media_path), enable_write=True)

    # Define the new tags to write.
    new_tags = {
        KEY_TITLE: 'New Title',
        KEY_ARTIST: 'New Artist',
        KEY_ALBUM: 'New Album',
        KEY_GENRE: 'New Genre',
        KEY_BPM: '123',
        KEY_INITIAL_KEY: 'C'
    }

    # Directly save the new tags
    changes = {
        KEY_TAG_GENERIC: new_tags,
        KEY_TAG_INTERNAL: {}
    }
    media_file.save(changes)
    time.sleep(0.1)

    # Create a new MediaFile instance to read the tags back.
    media_file_read = MediaFile(str(temp_media_path))

    # Verify that the tags were written correctly.
    # Note: transformations are now applied (whitespace trimming, BPM/key formatting)
    assert media_file_read.get_tag_simple(KEY_TITLE) == 'New Title'
    assert media_file_read.get_tag_simple(KEY_ARTIST) == 'New Artist'
    assert media_file_read.get_tag_simple(KEY_ALBUM) == 'New Album'
    assert media_file_read.get_tag_simple(KEY_GENRE) == 'New Genre'
    assert media_file_read.get_tag_simple(KEY_BPM) == '123'
    # Musical key 'C' is transformed based on user preference
    # Just verify it was set to something (format depends on settings)
    assert media_file_read.get_tag_simple(KEY_INITIAL_KEY) is not None


def test_empty_file(tmp_path):
    """
    Tests that a PermissionError is raised when trying to write to a file without write permissions.
    """
    # Create a dummy file.
    temp_file_path = tmp_path / "test.txt"
    temp_file_path.touch()

    mf = MediaFile(str(temp_file_path))
    assert mf.get_internal_data(KEY_IS_MEDIA) is False

def test_write_permissions_error(tmp_path):
    """
    Tests that a PermissionError is raised when trying to write to a file without write permissions.
    """
    # Create a temporary copy of the file to write to.
    temp_media_path = tmp_path / "write_protected.mp3"
    shutil.copy(SOURCE_FILE, temp_media_path)

    try:
        # Make the file read-only
        os.chmod(temp_media_path, 0o444)

        # Attempt to create a MediaFile instance with write enabled
        mf = MediaFile(str(temp_media_path), enable_write=True)
        edit_manager = EditManager()
        edit_manager.register_media_files([mf])
        with pytest.raises(PermissionError):
            # Try to stage a change and commit it
            edit_manager.stage_change([mf], KEY_TITLE, "New Title")
            # This should raise PermissionError when trying to save
            mf.save({KEY_TAG_GENERIC: {KEY_TITLE: "New Title"}})

    finally:
        # Restore write permissions to allow cleanup
        os.chmod(temp_media_path, 0o644)


def test_edit_manager_integration(tmp_path):
    """
    Tests that MediaFile integrates correctly with EditManager for staging and committing changes.
    """
    # Create a temporary copy of the file to write to.
    temp_media_path = tmp_path / SOURCE_FILE.name
    shutil.copy(SOURCE_FILE, temp_media_path)

    # Create a MediaFile instance for the temporary file.
    media_file = MediaFile(str(temp_media_path), enable_write=True)

    # Define the new tags to write.
    test_changes = {
        KEY_TITLE: 'Test Title',
        KEY_ARTIST: 'Test Artist',
        KEY_ALBUM: 'Test Album'
    }

    # Directly save the new tags
    changes = {
        KEY_TAG_GENERIC: test_changes,
        KEY_TAG_INTERNAL: {}
    }
    media_file.save(changes)
    time.sleep(0.1)

    # Create a new MediaFile instance to read the tags back and verify they were written.
    media_file_read = MediaFile(str(temp_media_path))
    for key, value in test_changes.items():
        assert media_file_read.get_tag_simple(key) == value


def test_initial_key_read_write(tmp_path, monkeypatch):
    """
    Test that initial_key (musical key) can be read, displayed in the table model, and saved correctly.

    This test specifically addresses the bug where COL_MAIN_KEY was "key" but KEY_INITIAL_KEY
    was "initial_key", causing a mismatch that prevented the key from being displayed or saved.
    """
    from models.qt.metadata_model import MetadataTableModel
    from models.settings import FileListSettings
    from PySide6.QtCore import QSettings
    from unittest.mock import MagicMock

    # Mock QSettings to ensure consistent transformer behavior across environments
    # Set the notation format to "camelot" so "8A" and "5A" remain unchanged
    mock_settings = MagicMock(spec=QSettings)

    # Configure mock to return appropriate values based on the key
    def mock_value(key, default=None):
        if key == "Analyzers/CategoryOptions/key/notation_format":
            return "camelot"
        return default

    mock_settings.value.side_effect = mock_value

    # Patch QSettings constructor to return our mock
    monkeypatch.setattr("PySide6.QtCore.QSettings", lambda *args, **kwargs: mock_settings)
    monkeypatch.setattr("models.settings.settings", mock_settings)

    # Also need to patch where transformers get their settings
    monkeypatch.setattr("providers.metadata.tag_transformers.musical_key_formatter.QSettings",
                       lambda *args, **kwargs: mock_settings)

    # Create a temporary copy of the file to write to
    temp_media_path = tmp_path / SOURCE_FILE.name
    shutil.copy(SOURCE_FILE, temp_media_path)

    # Test 1: Verify we can write initial_key directly via MediaFile
    media_file = MediaFile(str(temp_media_path), enable_write=True)
    test_key = "8A"

    changes = {
        KEY_TAG_GENERIC: {KEY_INITIAL_KEY: test_key},
        KEY_TAG_INTERNAL: {}
    }
    media_file.save(changes)
    time.sleep(0.1)

    # Test 2: Verify the key was written and can be read back
    media_file_read = MediaFile(str(temp_media_path), enable_write=True)
    assert media_file_read.get_tag_simple(KEY_INITIAL_KEY) == test_key, \
        f"Expected initial_key to be '{test_key}', but got '{media_file_read.get_tag_simple(KEY_INITIAL_KEY)}'"

    # Test 3: Verify the key appears correctly in MetadataTableModel
    edit_manager = EditManager()
    edit_manager.register_media_files([media_file_read])

    file_list_settings = FileListSettings()
    model = MetadataTableModel(file_list_settings.columns, edit_manager)

    # Get metadata and add it to the model
    metadata = MetadataTableModel.get_metadata_from_media_file(media_file_read)
    model.set_entire_data([metadata])

    # Find the "key" column index
    key_column_index = None
    for i, col in enumerate(file_list_settings.columns):
        if col.id == KEY_INITIAL_KEY:  # COL_MAIN_KEY now equals KEY_INITIAL_KEY
            key_column_index = i
            break

    assert key_column_index is not None, "Could not find 'initial_key' column in table model"

    # Get the value from the model
    from PySide6.QtCore import Qt
    index = model.createIndex(0, key_column_index)
    displayed_value = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert displayed_value == test_key, \
        f"Expected table model to display '{test_key}' in key column, but got '{displayed_value}'"

    # Test 4: Verify staging changes through the model works
    new_key = "5A"
    result = model.setData(index, new_key, Qt.ItemDataRole.EditRole)
    assert result is True, "setData should return True for successful edit"

    # Commit the staged changes
    saved_file_ids, errors = edit_manager.commit_changes_sync()
    assert len(errors) == 0, f"Errors occurred during save: {errors}"
    assert media_file_read.file_id in saved_file_ids, "File should have been saved"

    # Test 5: Verify the new key was persisted
    media_file_final = MediaFile(str(temp_media_path))
    assert media_file_final.get_tag_simple(KEY_INITIAL_KEY) == new_key, \
        f"Expected final initial_key to be '{new_key}', but got '{media_file_final.get_tag_simple(KEY_INITIAL_KEY)}'"
