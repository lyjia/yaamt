
import json
import pytest
from models.media_file import MediaFile
from models.qt.metadata_model import MetadataTableModel
from util.const import (
    PROJECT_ROOT, KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_CTIME,
    KEY_FILE_TYPE, KEY_FILE_TYPE_HUMAN, KEY_FORMAT, KEY_TITLE, KEY_ARTIST,
    KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY, KEY_IS_MEDIA, KEY_FILE_ID
)

# Define the directory containing the test fixtures.
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "metadata"

# Discover all audio files in the fixture directory.
# This list will be used to parameterize the test function.
test_files = [p for p in FIXTURE_DIR.glob('*') if (p.suffix == '.mp3' or p.suffix == ".flac")]


def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@pytest.mark.parametrize("media_path", test_files)
def test_get_metadata_from_media_file(media_path):
    '''
    A parameterized test that verifies the get_metadata_from_media_file() method of the MetadataTableModel class.
    '''
    # Construct the path to the JSON file with the expected results.
    expected_json_path = media_path.with_suffix(media_path.suffix + '.json')

    # Load the expected results from the JSON file.
    with open(expected_json_path, 'r', encoding='utf-8') as f:
        expected_dict_nested = json.load(f)

    # Flatten the expected dictionary
    expected_dict = flatten_dict(expected_dict_nested)

    # Initialize the MediaFile object with the path to the test file.
    media_file = MediaFile(media_path)

    # Get the actual dictionary from the MetadataTableModel.
    actual_dict = MetadataTableModel.get_metadata_from_media_file(media_file)

    # Map the keys from the JSON file to the keys used in the application
    key_mapping = {
        'tags_artist_value': KEY_ARTIST,
        'tags_album_value': KEY_ALBUM,
        'tags_title_value': KEY_TITLE,
        'tags_genre_value': KEY_GENRE,
        'tags_bpm_value': KEY_BPM,
        'tags_key_value': KEY_MUSICAL_KEY,
        'streaminfo_format_value': KEY_FILE_TYPE_HUMAN,
        'internal_is_media_value': KEY_IS_MEDIA,
    }

    # Create the expected dictionary with the correct keys
    expected_mapped = {}
    for json_key, app_key in key_mapping.items():
        if json_key in expected_dict:
            expected_mapped[app_key] = expected_dict[json_key]

    # Assert that the values for the mapped keys are equal
    for key, value in expected_mapped.items():
        assert actual_dict.get(key) == value, f"Mismatch for key {key}"
