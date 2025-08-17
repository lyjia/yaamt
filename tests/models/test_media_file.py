from pathlib import Path

import pytest
from models.media_file import MediaFile

@pytest.fixture
def media_file():
     return MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_ansi.mp3" )

def test_to_dict(media_file):
    # media_file.title = "Test Title"
    # media_file.artist = "Test Artist"
    # media_file.album = "Test Album"
    # media_file.genre = "Test Genre"
    # media_file.bpm = 120.0
    # media_file.key = "C"

    expected_dict = {
        "parsed": {
            "title": {
                "value": "Test Title",
                "element_providers": ["mutagen"],
                "all_elements": ["Test Title"],
                "all_elements_providers": [0]
            },
            "artist": {
                "value": "Test Artist",
                "element_providers": ["mutagen"],
                "all_elements": ["Test Artist"],
                "all_elements_providers": [0]
            },
            "album": {
                "value": "Test Album",
                "element_providers": ["mutagen"],
                "all_elements": ["Test Album"],
                "all_elements_providers": [0]
            },
            "genre": {
                "value": "Test Genre",
                "element_providers": ["mutagen"],
                "all_elements": ["Test Genre"],
                "all_elements_providers": [0]
            },
            "bpm": {
                "value": 120.0,
                "element_providers": ["mutagen"],
                "all_elements": [120.0],
                "all_elements_providers": [0]
            },
            "key": {
                "value": "C",
                "element_providers": ["mutagen"],
                "all_elements": ["C"],
                "all_elements_providers": [0]
            }
        }
    }

    assert media_file.to_dict() == expected_dict