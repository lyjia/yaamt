import shutil
from pathlib import Path
import pytest
from providers.metadata.mutagen_provider import MutagenProvider
from util.const import (
    KEY_INITIAL_KEY, KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM,
    KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK, KEY_REPLAYGAIN_ALBUM_PEAK,
)

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
        KEY_INITIAL_KEY: 'C'
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


@pytest.mark.parametrize("media_path", test_files)
def test_write_replaygain_tags(media_path, tmp_path):
    """
    Round-trip test for the four canonical ReplayGain tags across MP3 (TXXX)
    and FLAC (vorbis comment) fixtures. Values are ReplayGain-standard strings.
    """
    temp_media_path = tmp_path / media_path.name
    shutil.copy(media_path, temp_media_path)

    provider = MutagenProvider(str(temp_media_path))

    rg_tags = {
        KEY_REPLAYGAIN_TRACK_GAIN: '-6.24 dB',
        KEY_REPLAYGAIN_ALBUM_GAIN: '-5.18 dB',
        KEY_REPLAYGAIN_TRACK_PEAK: '0.987654',
        KEY_REPLAYGAIN_ALBUM_PEAK: '0.995123',
    }

    for key, value in rg_tags.items():
        provider.set_tag(key, [value])
    provider.save()

    provider_read = MutagenProvider(str(temp_media_path))
    for key, value in rg_tags.items():
        assert provider_read.get_tag(key) == [value], (
            f"ReplayGain tag {key} did not round-trip on {media_path.name}"
        )