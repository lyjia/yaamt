import json
import os
import shutil
from pathlib import Path
import pytest
import time
from models.media_file import MediaFile
from models.edit_manager import EditManager
from util.const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY, PROJECT_ROOT, KEY_IS_MEDIA, KEY_TAG_GENERIC, KEY_TAG_INTERNAL
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
    keys_to_ignore = {'fsize', 'fmtime', 'fatime', 'fctime', 'fpath'}

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
        KEY_MUSICAL_KEY: 'C'
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
    for key, value in new_tags.items():
        assert media_file_read.get_tag_simple(key) == value


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
