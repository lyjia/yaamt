from pathlib import Path

import pytest
from models.media_file import MediaFile


def test_to_dict_ansi_mp3():
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
                "value": "DTMF Sample Unicode Big Endian",
                "provider": "MutagenProvider",
                "all_values": [
                    "DTMF Sample Unicode Big Endian"
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

    assert media_file.to_dict() == expected_dict



def test_to_dict_with_bpm_and_key_from_serato_flac():
    media_file = MediaFile( Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_with_bpm_and_key_from_serato.flac" )
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
            "initialkey": {
                "value": "Fm",
                "provider": "MutagenProvider",
                "all_values": [
                    "Fm"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "serato_playcount": {
                "value": "0",
                "provider": "MutagenProvider",
                "all_values": [
                    "0"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "serato_analysis": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQW5hbHlzaXMAAAEA",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQW5hbHlzaXMAAAEA"
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
            "serato_overview": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gT3ZlcnZpZXcAAQUBAQEBAQYMNxIw\nAQEBAQEBAQEBAQEBMAw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQE2DDcMAQEBAQEB\nAQEBAQEBDDcMMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNhIwAQEBAQEBAQEBAQEB\nNgw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEGDDYSMAEB\nAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEBAQEBAQEBNgw3DAEBAQEBAQEB\nAQEBAQw3DDABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEBDDcMMAEBAQEBAQEBAQEBATYM\nNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEBAQEBAQEBMAw3DAEBAQEBAQEBAQEBAQw3EjABAQEB\nAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEBDDcMMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEB\nAQEMNhIwAQEBAQEBAQEBAQEBNgw3DAEBAQEBAQEBAQEBAQw3DDABAQEBAQEBAQEBAQE2DDcM\nAQEBAQEBAQEBAQEBDDcSMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEB\nAQEBAQEBNgw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEB\nDDcMMAEBAQEBAQEBAQEBATYMNwwBAQEBAQEBAQEBAQEMNxIwAQEBAQEBAQEBAQEBNgw3DAEB\nAQEBAQEBAQEBAQw3DDABAQEBAQEBAQEBAQEGBisBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEB\nAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB\n3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEB\nAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEB\nAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQEGAQEBAQEBAQEBAQEBAQEMPQEBAQEBAQEBAQEBAQESPRI3AQEBAQEBAQEBAQEB\nNxM3EgEBAQEBAQEBAQEBARM3NzcBAQEBAQEBAQEBAQE3EzcSAQEBAQEBAQEBAQEBEj0TNwEB\nAQEBAQEBAQEBATcSPRIBAQEBAQEBAQEBAQESNzc3AQEBAQEBAQEBAQEBNxM3EgEBAQEBAQEB\nAQEBARI3EzcBAQEBAQEBAQEBAQY3Ej0MAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEBAQEBATcT\nNxIBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxI9DAEBAQEBAQEBAQEBARI9EzcBAQEB\nAQEBAQEBAQE3EzcSAQEBAQEBAQEBAQEBEjc9DQEBAQEBAQEBAQEBATcTNxIBAQEBAQEBAQEB\nAQETPRI3AQEBAQEBAQEBAQEBNxM9DAEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3EzcS\nAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEBAQEBATcMPQwBAQEBAQEBAQEBAQESNxM3AQEBAQEB\nAQEBAQEBNxM3EgEBAQEBAQEBAQEBARI3NzcBAQEBAQEBAQEBAQE3Ez0SAQEBAQEBAQEBAQEB\nEz0SNwEBAQEBAQEBAQEBATcTPRIBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM3EgEB\nAQEBAQEBAQEBARI9EzcBAQEBAQEBAQEBAQE3Ej0SAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEB\nAQEBATcTNxIBAQEBAQEBAQEBAQESNxM3AQEBAQEBAQEBAQEBNxI9DAEBAQEBAQEBAQEBARM3\nEzcBAQEBAQEBAQEBAQExBjEGAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEB\nAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEB\nAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQwGNwYBAQEBAQEBAQEBAQETNzc3AQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEB\nAQEBARM3EzcBAQEBAQEBAQEBAQE3Ez0NAQEBAQEBAQEBAQEBDT0TNwEBAQEBAQEBAQEBATcT\nPQ0BAQEBAQEBAQEBAQETPRM3AQEBAQEBAQEBAQEBNxM9DAEBAQEBAQEBAQEBARM3EzcBAQEB\nAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEBEzcTNwEBAQEBAQEBAQEBATcTNxMBAQEBAQEBAQEB\nAQETNxM3AQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM9EzcBAQEBAQEBAQEBAQE3Ez0T\nAQEBAQEBAQEBAQEBEz0TNwEBAQEBAQEBAQEBATcTPQwBAQEBAQEBAQEBAQETNxM3AQEBAQEB\nAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEB\nEzc3NwEBAQEBAQEBAQEBATcTNxMBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM3EwEB\nAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3Ez0MAQEBAQEBAQEBAQEBEz0TNwEBAQEBAQEB\nAQEBBjcTPQ0BAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM9DQEBAQEBAQEBAQEBARM3\nEzcBAQEBAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEMEzc3NwEBAQEBAQEBAQEBATcTNxMBAQEB\nAQEBAQEBAQETNzcxAQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEB\nAQExDDcMAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEB\nAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEB\nNwEBAQEBAQEBAQEBAQEGDAwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBBgwxDAwBAQEB\nAQEBAQEBAQExDDEMAQEBAQEBAQEBAQEGDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEB\nAQEMMQwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwxDAwBAQEBAQEBAQEBAQEMDDEM\nAQEBAQEBAQEBAQEBDDcMDAEBAQEBAQEBAQEBAQwMMQwBAQEBAQEBAQEBAQEMDAwMAQEBAQEB\nAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQEMDDEMAQEBAQEBAQEBAQEB\nDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEBAQEMMQwMAQEBAQEBAQEBAQEBDAwxDAEB\nAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQEMDDEMAQEBAQEBAQEBAQEBDDcMDAEBAQEBAQEB\nAQEBATEMMQwBAQEBAQEBAQEBAQEMMQwMAQEBAQEBAQEBAQEBDAw3DAEBAQEBAQEBAQEBAQwx\nDAwBAQEBAQEBAQEBAQExDDEMAQEBAQEBAQEBAQEGDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEB\nAQEBAQEBAQYMNwwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEB\nAQEMDDEMAQEBAQEBAQEBAQEBDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEBAQEMMQwM\nAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQExDDEGAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEB\nAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEB\nKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEB\nAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQGD",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gT3ZlcnZpZXcAAQUBAQEBAQYMNxIw\nAQEBAQEBAQEBAQEBMAw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQE2DDcMAQEBAQEB\nAQEBAQEBDDcMMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNhIwAQEBAQEBAQEBAQEB\nNgw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEGDDYSMAEB\nAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEBAQEBAQEBNgw3DAEBAQEBAQEB\nAQEBAQw3DDABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEBDDcMMAEBAQEBAQEBAQEBATYM\nNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEBAQEBAQEBMAw3DAEBAQEBAQEBAQEBAQw3EjABAQEB\nAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEBDDcMMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEB\nAQEMNhIwAQEBAQEBAQEBAQEBNgw3DAEBAQEBAQEBAQEBAQw3DDABAQEBAQEBAQEBAQE2DDcM\nAQEBAQEBAQEBAQEBDDcSMAEBAQEBAQEBAQEBATAMNwwBAQEBAQEBAQEBAQEMNwwwAQEBAQEB\nAQEBAQEBNgw3DAEBAQEBAQEBAQEBAQw3EjABAQEBAQEBAQEBAQEwDDcMAQEBAQEBAQEBAQEB\nDDcMMAEBAQEBAQEBAQEBATYMNwwBAQEBAQEBAQEBAQEMNxIwAQEBAQEBAQEBAQEBNgw3DAEB\nAQEBAQEBAQEBAQw3DDABAQEBAQEBAQEBAQEGBisBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEB\nAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB\n3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEB\nAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEB\nAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQEGAQEBAQEBAQEBAQEBAQEMPQEBAQEBAQEBAQEBAQESPRI3AQEBAQEBAQEBAQEB\nNxM3EgEBAQEBAQEBAQEBARM3NzcBAQEBAQEBAQEBAQE3EzcSAQEBAQEBAQEBAQEBEj0TNwEB\nAQEBAQEBAQEBATcSPRIBAQEBAQEBAQEBAQESNzc3AQEBAQEBAQEBAQEBNxM3EgEBAQEBAQEB\nAQEBARI3EzcBAQEBAQEBAQEBAQY3Ej0MAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEBAQEBATcT\nNxIBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxI9DAEBAQEBAQEBAQEBARI9EzcBAQEB\nAQEBAQEBAQE3EzcSAQEBAQEBAQEBAQEBEjc9DQEBAQEBAQEBAQEBATcTNxIBAQEBAQEBAQEB\nAQETPRI3AQEBAQEBAQEBAQEBNxM9DAEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3EzcS\nAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEBAQEBATcMPQwBAQEBAQEBAQEBAQESNxM3AQEBAQEB\nAQEBAQEBNxM3EgEBAQEBAQEBAQEBARI3NzcBAQEBAQEBAQEBAQE3Ez0SAQEBAQEBAQEBAQEB\nEz0SNwEBAQEBAQEBAQEBATcTPRIBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM3EgEB\nAQEBAQEBAQEBARI9EzcBAQEBAQEBAQEBAQE3Ej0SAQEBAQEBAQEBAQEBEjcTNwEBAQEBAQEB\nAQEBATcTNxIBAQEBAQEBAQEBAQESNxM3AQEBAQEBAQEBAQEBNxI9DAEBAQEBAQEBAQEBARM3\nEzcBAQEBAQEBAQEBAQExBjEGAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEB\nAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEB\nAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQwGNwYBAQEBAQEBAQEBAQETNzc3AQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEB\nAQEBARM3EzcBAQEBAQEBAQEBAQE3Ez0NAQEBAQEBAQEBAQEBDT0TNwEBAQEBAQEBAQEBATcT\nPQ0BAQEBAQEBAQEBAQETPRM3AQEBAQEBAQEBAQEBNxM9DAEBAQEBAQEBAQEBARM3EzcBAQEB\nAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEBEzcTNwEBAQEBAQEBAQEBATcTNxMBAQEBAQEBAQEB\nAQETNxM3AQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM9EzcBAQEBAQEBAQEBAQE3Ez0T\nAQEBAQEBAQEBAQEBEz0TNwEBAQEBAQEBAQEBATcTPQwBAQEBAQEBAQEBAQETNxM3AQEBAQEB\nAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEB\nEzc3NwEBAQEBAQEBAQEBATcTNxMBAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM3EwEB\nAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEBAQE3Ez0MAQEBAQEBAQEBAQEBEz0TNwEBAQEBAQEB\nAQEBBjcTPQ0BAQEBAQEBAQEBAQETNxM3AQEBAQEBAQEBAQEBNxM9DQEBAQEBAQEBAQEBARM3\nEzcBAQEBAQEBAQEBAQE3EzcTAQEBAQEBAQEBAQEMEzc3NwEBAQEBAQEBAQEBATcTNxMBAQEB\nAQEBAQEBAQETNzcxAQEBAQEBAQEBAQEBNxM3EwEBAQEBAQEBAQEBARM3EzcBAQEBAQEBAQEB\nAQExDDcMAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8B\nAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEB\nAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEB\nNwEBAQEBAQEBAQEBAQEGDAwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBBgwxDAwBAQEB\nAQEBAQEBAQExDDEMAQEBAQEBAQEBAQEGDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEB\nAQEMMQwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwxDAwBAQEBAQEBAQEBAQEMDDEM\nAQEBAQEBAQEBAQEBDDcMDAEBAQEBAQEBAQEBAQwMMQwBAQEBAQEBAQEBAQEMDAwMAQEBAQEB\nAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQEMDDEMAQEBAQEBAQEBAQEB\nDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEBAQEMMQwMAQEBAQEBAQEBAQEBDAwxDAEB\nAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQEMDDEMAQEBAQEBAQEBAQEBDDcMDAEBAQEBAQEB\nAQEBATEMMQwBAQEBAQEBAQEBAQEMMQwMAQEBAQEBAQEBAQEBDAw3DAEBAQEBAQEBAQEBAQwx\nDAwBAQEBAQEBAQEBAQExDDEMAQEBAQEBAQEBAQEGDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEB\nAQEBAQEBAQYMNwwMAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEB\nAQEMDDEMAQEBAQEBAQEBAQEBDDEMDAEBAQEBAQEBAQEBAQwMNwwBAQEBAQEBAQEBAQEMMQwM\nAQEBAQEBAQEBAQEBDAwxDAEBAQEBAQEBAQEBAQwMDAwBAQEBAQEBAQEBAQExDDEGAQEBAQEB\nAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEB\nAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEB\nAQEBAQEBAQEBAQEBKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEB\nAQEBAQEB3wEBAQEBAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEB\nKwEBAQEBAQEBAQEBAQEBAd8BAQEBAQEBAQEBAQEBAQErAQEBAQEBAQEBAQEBAQEB3wEBAQEB\nAQEBAQEBAQEBASsBAQEBAQEBAQEBAQEBAQHfAQEBAQEBAQEBAQEBAQEBKwEBAQEBAQGD"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "serato_markers_v2": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gTWFya2VyczIAAQFBUUZEVDB4UFVn\nQUFBQUFFQVAvLy8wSlFUVXhQUTBzQUFBQUFBUUFBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAO",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gTWFya2VyczIAAQFBUUZEVDB4UFVn\nQUFBQUFFQVAvLy8wSlFUVXhQUTBzQUFBQUFBUUFBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nAAAAAAAAAAAAAAAAAAAAAO"
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
            },
            "serato_relvol": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gUmVsVm9sQWQAAQEBAAAA",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gUmVsVm9sQWQAAQEBAAAA"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
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
            "serato_beatgrid": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQmVhdEdyaWQAAQAAAAAAAJ",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQmVhdEdyaWQAAQAAAAAAAJ"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "serato_autogain": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQXV0b3RhZ3MAAQExMjUuMDAALTAu\nMDAxADAuMDAwAA",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gQXV0b3RhZ3MAAQExMjUuMDAALTAu\nMDAxADAuMDAwAA"
                ],
                "all_providers": [
                    "MutagenProvider"
                ]
            },
            "serato_video_assoc": {
                "value": "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gVmlkQXNzb2MAAQEBAO+kgOmFv24A\nA",
                "provider": "MutagenProvider",
                "all_values": [
                    "YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtAABTZXJhdG8gVmlkQXNzb2MAAQEBAO+kgOmFv24A\nA"
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
            }
        }
    }


    assert media_file.to_dict() == expected_dict