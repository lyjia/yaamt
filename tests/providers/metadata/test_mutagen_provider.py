import shutil
from pathlib import Path
import pytest
from providers.metadata.mutagen_provider import MutagenProvider
from util.const import KEY_MUSICAL_KEY, KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM

# Define the directory containing the test fixtures.
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "metadata"

# Discover all audio files in the fixture directory.
# This list will be used to parameterize the test function.
test_files = [p for p in FIXTURE_DIR.glob('*') if (p.suffix == '.mp3' or p.suffix == ".flac")]


@pytest.mark.parametrize("media_path", test_files)
def test_write_tags(media_path, tmp_path):
    """
    A parameterized test that verifies the write functionality of the MutagenProvider class.
    """
    # Create a temporary copy of the file to write to.
    temp_media_path = tmp_path / media_path.name
    shutil.copy(media_path, temp_media_path)

    # Create a MutagenProvider instance for the temporary file.
    provider = MutagenProvider(str(temp_media_path))

    # Define the new tags to write.
    new_tags = {
        KEY_TITLE: 'New Title',
        KEY_ARTIST: 'New Artist',
        KEY_ALBUM: 'New Album',
        KEY_GENRE: 'New Genre',
        KEY_BPM: '123',
        KEY_MUSICAL_KEY: 'C'
    }

    # Write the new tags to the file.
    for key, value in new_tags.items():
        provider.set_tag(key, value)
    provider.save()

    # Create a new MutagenProvider instance to read the tags back.
    provider_read = MutagenProvider(str(temp_media_path))

    # Verify that the tags were written correctly.
    for key, value in new_tags.items():
        assert provider_read.get_tag(key) == [value]