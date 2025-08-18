import json
from pathlib import Path
import pytest
from models.media_file import MediaFile

# Define the directory containing the test fixtures.
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "metadata"

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