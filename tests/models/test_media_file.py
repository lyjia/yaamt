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

    expected_dict ={
        "stream_info": {
            "bitrate": {
                "value": 320000,
                "provider": "MutagenProvider"
            },
            "length": {
                "value": 1.256,
                "provider": "MutagenProvider"
            },
            "sample_rate": {
                "value": 44100,
                "provider": "MutagenProvider"
            },
            "channels": {
                "value": 2,
                "provider": "MutagenProvider"
            },
            "bits_per_sample": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "total_samples": {
                "value": 2.512,
                "provider": "MutagenProvider"
            },
            "encoding": {
                "value": "MPEG 1 layer 3",
                "provider": "MutagenProvider"
            }
        },
        "tags": {
            "album": {
                "value": "pytest",
                "provider": "MutagenProvider",
                "all_values": [
                    "pytest"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "copyright": {
                "value": "2025",
                "provider": "MutagenProvider",
                "all_values": [
                    "2025"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "title": {
                "value": "DTMF Sample ANSI",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample ANSI"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "artist": {
                "value": "Lyjia",
                "provider": "MutagenProvider",
                "all_values": [
                    "Lyjia"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "tracknumber": {
                "value": "99",
                "provider": "MutagenProvider",
                "all_values": [
                    "99"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "genre": {
                "value": "Power Ballad",
                "provider": "MutagenProvider",
                "all_values": [
                    "Power Ballad"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            }
        }
    }


    assert media_file.to_dict() == expected_dict