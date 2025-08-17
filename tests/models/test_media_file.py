from pathlib import Path

import pytest
from models.media_file import MediaFile


def test_to_dict_ansi_mp3():
    # media_file.title = "Test Title"
    # media_file.artist = "Test Artist"
    # media_file.album = "Test Album"
    # media_file.genre = "Test Genre"
    # media_file.bpm = 120.0
    # media_file.key = "C"
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_ansi.mp3" )

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

# TODO: fix reason for stream info not appearing on files with no meta
def test_to_dict_nometadata_flac():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_nometa.flac" )
    expected_dict = {
        "stream_info": {
            "bitrate": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "length": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "sample_rate": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "channels": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "bits_per_sample": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "total_samples": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "encoding": {
                "value": None,
                "provider": "MutagenProvider"
            }
        },
        "tags": {}
    }


    assert media_file.to_dict() == expected_dict

# TODO: fix reason for stream info not appearing on files with no meta
def test_to_dict_nometadata_mp3():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_nometa.mp3" )
    expected_dict = {
        "stream_info": {
            "bitrate": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "length": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "sample_rate": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "channels": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "bits_per_sample": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "total_samples": {
                "value": None,
                "provider": "MutagenProvider"
            },
            "encoding": {
                "value": None,
                "provider": "MutagenProvider"
            }
        },
        "tags": {}
    }


    assert media_file.to_dict() == expected_dict


def test_to_dict_original_flac():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_original.flac" )
    expected_dict = {
        "stream_info": {
            "bitrate": {
                "value": 272440,
                "provider": "MutagenProvider"
            },
            "length": {
                "value": 1.2,
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
                "value": 16,
                "provider": "MutagenProvider"
            },
            "total_samples": {
                "value": 2.4,
                "provider": "MutagenProvider"
            },
            "encoding": {
                "value": "FLAC",
                "provider": "MutagenProvider"
            }
        },
        "tags": {
            "title": {
                "value": "DTMF Sample Original",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Original"
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



def test_to_dict_unicode_mp3():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3" )
    expected_dict = {
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
                "value": "DTMF Sample Unicode",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode"
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


def test_to_dict_unicode_bigendian_mp3():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_unicode_bigendian.mp3" )
    expected_dict = {
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
                "value": "DTMF Sample Unicode",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode"
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



def test_to_dict_unicode_foobar2000_mp3():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_unicode_foobar2000.mp3" )
    expected_dict = {
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
                "value": "DTMF Sample Unicode foobar2000",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode foobar2000"
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

def test_to_dict_unicode_unicode_with_bpm_and_key_from_serato_mp3():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_unicode_with_bpm_and_key_from_serato.mp3" )
    expected_dict = {
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
            "bpm": {
                "value": "125",
                "provider": "MutagenProvider",
                "all_values": [
                    "125"
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
                "value": "DTMF Sample Unicode",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode"
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



def test_to_dict_with_bpm_and_key_from_serato_flac():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_with_bpm_and_key_from_serato.flac" )
    expected_dict = {
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
            "bpm": {
                "value": "125",
                "provider": "MutagenProvider",
                "all_values": [
                    "125"
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
                "value": "DTMF Sample Unicode",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode"
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