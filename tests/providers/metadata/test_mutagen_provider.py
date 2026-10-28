import shutil
from pathlib import Path
import mutagen
import pytest
from providers.metadata.mutagen_provider import MutagenProvider
from util.const import (KEY_INITIAL_KEY, KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM,
                        KEY_MUSICBRAINZ_RECORDING_ID, KEY_ACOUSTID_ID, KEY_ACOUSTID_FINGERPRINT,
                        KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN,
                        KEY_REPLAYGAIN_TRACK_PEAK, KEY_REPLAYGAIN_ALBUM_PEAK)

# Define the directory containing the test fixtures.
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "metadata"

# Discover all audio files in the fixture directory.
# This list will be used to parameterize the test function.
test_files = [p for p in FIXTURE_DIR.glob('*') if (p.suffix == '.mp3' or p.suffix == ".flac")]

MP3_FIXTURE = FIXTURE_DIR / "sample_dtmf_nometa.mp3"
FLAC_FIXTURE = FIXTURE_DIR / "sample_dtmf_nometa.flac"

SAMPLE_MBID = "e02a4d3a-0e87-4d46-9b63-8c8ed07e7f74"
SAMPLE_ACOUSTID = "b3e8c7d9-0a12-4f5e-9d6b-8a7c6e5d4c3b"
# Realistic Chromaprint output is base64; use an arbitrary long-ish string to
# exercise the long-TXXX path without pulling in fpcalc at test time.
SAMPLE_FINGERPRINT = "AQAD" + "A" * 1500


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


@pytest.mark.skipif(not MP3_FIXTURE.exists(), reason="MP3 fixture not present")
def test_mp3_mbid_and_acoustid_roundtrip(tmp_path):
    """MBID, AcoustID ID, and Chromaprint fingerprint round-trip through easy-mode
    and are written to the canonical Picard ID3 frames (UFID + TXXX)."""
    temp_media_path = tmp_path / MP3_FIXTURE.name
    shutil.copy(MP3_FIXTURE, temp_media_path)

    provider = MutagenProvider(str(temp_media_path))
    provider.set_tag(KEY_MUSICBRAINZ_RECORDING_ID, [SAMPLE_MBID])
    provider.set_tag(KEY_ACOUSTID_ID, [SAMPLE_ACOUSTID])
    provider.set_tag(KEY_ACOUSTID_FINGERPRINT, [SAMPLE_FINGERPRINT])
    provider.save()

    # Easy-mode readback
    provider_read = MutagenProvider(str(temp_media_path))
    assert provider_read.get_tag(KEY_MUSICBRAINZ_RECORDING_ID) == [SAMPLE_MBID]
    assert provider_read.get_tag(KEY_ACOUSTID_ID) == [SAMPLE_ACOUSTID]
    assert provider_read.get_tag(KEY_ACOUSTID_FINGERPRINT) == [SAMPLE_FINGERPRINT]

    # Raw ID3 readback: verify Picard-canonical frames are present.
    raw = mutagen.File(str(temp_media_path), easy=False)
    ufid = raw.get('UFID:http://musicbrainz.org')
    assert ufid is not None, "UFID:http://musicbrainz.org frame missing"
    assert ufid.data.decode('ascii') == SAMPLE_MBID

    txxx_mbid = raw.get('TXXX:MusicBrainz Track Id')
    assert txxx_mbid is not None, "TXXX:MusicBrainz Track Id frame missing"
    assert list(txxx_mbid.text) == [SAMPLE_MBID]

    txxx_aid = raw.get('TXXX:Acoustid Id')
    assert txxx_aid is not None, "TXXX:Acoustid Id frame missing"
    assert list(txxx_aid.text) == [SAMPLE_ACOUSTID]

    txxx_fp = raw.get('TXXX:Acoustid Fingerprint')
    assert txxx_fp is not None, "TXXX:Acoustid Fingerprint frame missing"
    assert list(txxx_fp.text) == [SAMPLE_FINGERPRINT]


@pytest.mark.skipif(not MP3_FIXTURE.exists(), reason="MP3 fixture not present")
def test_mp3_mbid_delete_removes_both_frames(tmp_path):
    """Deleting the MBID generic key must remove both UFID and TXXX frames."""
    temp_media_path = tmp_path / MP3_FIXTURE.name
    shutil.copy(MP3_FIXTURE, temp_media_path)

    provider = MutagenProvider(str(temp_media_path))
    provider.set_tag(KEY_MUSICBRAINZ_RECORDING_ID, [SAMPLE_MBID])
    provider.save()

    provider = MutagenProvider(str(temp_media_path))
    # Setting to empty string deletes via the custom mbid_set handler.
    provider.set_tag(KEY_MUSICBRAINZ_RECORDING_ID, [""])
    provider.save()

    raw = mutagen.File(str(temp_media_path), easy=False)
    assert raw.get('UFID:http://musicbrainz.org') is None
    assert raw.get('TXXX:MusicBrainz Track Id') is None


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_mbid_and_acoustid_roundtrip(tmp_path):
    """MBID, AcoustID ID, and fingerprint round-trip through FLAC Vorbis-comment keys."""
    temp_media_path = tmp_path / FLAC_FIXTURE.name
    shutil.copy(FLAC_FIXTURE, temp_media_path)

    provider = MutagenProvider(str(temp_media_path))
    provider.set_tag(KEY_MUSICBRAINZ_RECORDING_ID, [SAMPLE_MBID])
    provider.set_tag(KEY_ACOUSTID_ID, [SAMPLE_ACOUSTID])
    provider.set_tag(KEY_ACOUSTID_FINGERPRINT, [SAMPLE_FINGERPRINT])
    provider.save()

    provider_read = MutagenProvider(str(temp_media_path))
    assert provider_read.get_tag(KEY_MUSICBRAINZ_RECORDING_ID) == [SAMPLE_MBID]
    assert provider_read.get_tag(KEY_ACOUSTID_ID) == [SAMPLE_ACOUSTID]
    assert provider_read.get_tag(KEY_ACOUSTID_FINGERPRINT) == [SAMPLE_FINGERPRINT]

    # Raw Vorbis readback: keys are case-insensitive, canonically uppercase.
    raw = mutagen.File(str(temp_media_path), easy=False)
    assert raw.get('MUSICBRAINZ_RECORDINGID') == [SAMPLE_MBID] or \
           raw.get('musicbrainz_recordingid') == [SAMPLE_MBID]
    assert raw.get('ACOUSTID_ID') == [SAMPLE_ACOUSTID] or \
           raw.get('acoustid_id') == [SAMPLE_ACOUSTID]
    assert raw.get('ACOUSTID_FINGERPRINT') == [SAMPLE_FINGERPRINT] or \
           raw.get('acoustid_fingerprint') == [SAMPLE_FINGERPRINT]

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


# --- Per-container writability (only offer edits the file can store) ---

WAV_FIXTURE = FIXTURE_DIR / "lyjia_house_claves_delay_120bpm.wav"


@pytest.mark.parametrize("media_path", [MP3_FIXTURE, FLAC_FIXTURE])
def test_easy_containers_report_supported_tags_writable(media_path):
    provider = MutagenProvider(str(media_path))
    writable = {t.internal_tag_name for t in provider.available_internal_tags() if t.is_writable}
    assert {KEY_TITLE, KEY_INITIAL_KEY, KEY_MUSICBRAINZ_RECORDING_ID, KEY_REPLAYGAIN_TRACK_GAIN} <= writable


def test_wav_reports_no_tags_writable():
    """WAV has no easy-mode wrapper, so easy-style writes raise (issue #74).
    Until that is fixed the provider must not advertise any tag as writable,
    including the raw frames the file already carries."""
    provider = MutagenProvider(str(WAV_FIXTURE))
    tag_infos = provider.available_internal_tags()
    assert tag_infos
    assert not any(t.is_writable for t in tag_infos)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is needed to create an M4A file")
def test_m4a_reports_only_tags_easymp4_can_store(tmp_path):
    import subprocess
    m4a_path = tmp_path / "tone.m4a"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2",
                    "-c:a", "aac", str(m4a_path)], check=True)
    provider = MutagenProvider(str(m4a_path))
    writable = {t.internal_tag_name for t in provider.available_internal_tags() if t.is_writable}
    assert {KEY_TITLE, KEY_BPM, KEY_REPLAYGAIN_TRACK_GAIN} <= writable
    # EasyMP4 has no atom mapping for these.
    assert KEY_INITIAL_KEY not in writable
    assert KEY_MUSICBRAINZ_RECORDING_ID not in writable


FLAC_KEY_ALIAS = 'INITIAL KEY'


def _flac_copy(tmp_path, alias_value: str | None = None) -> Path:
    """Temp copy of the FLAC fixture, optionally with the key in the alias field."""
    temp_media_path = tmp_path / FLAC_FIXTURE.name
    shutil.copy(FLAC_FIXTURE, temp_media_path)
    if alias_value is not None:
        raw = mutagen.File(str(temp_media_path))
        raw[FLAC_KEY_ALIAS] = [alias_value]
        raw.save()
    return temp_media_path


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_key_reads_from_alias(tmp_path):
    """A key stored only in 'INITIAL KEY' reads as the generic key (#89)."""
    provider = MutagenProvider(str(_flac_copy(tmp_path, 'Gmin')))
    assert provider.get_tag(KEY_INITIAL_KEY) == ['Gmin']


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_key_write_updates_existing_alias(tmp_path):
    path = _flac_copy(tmp_path, 'Gmin')
    provider = MutagenProvider(str(path))
    provider.set_tag(KEY_INITIAL_KEY, ['6A'])
    provider.save()

    raw = mutagen.File(str(path))
    assert raw.get('INITIALKEY') == ['6A']
    assert raw.get(FLAC_KEY_ALIAS) == ['6A']


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_key_write_creates_alias(tmp_path):
    """Both names are written so foobar2000 conversions carry the new key (#89)."""
    path = _flac_copy(tmp_path)
    provider = MutagenProvider(str(path))
    provider.set_tag(KEY_INITIAL_KEY, ['6A'])
    provider.save()

    raw = mutagen.File(str(path))
    assert raw.get('INITIALKEY') == ['6A']
    assert raw.get(FLAC_KEY_ALIAS) == ['6A']


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_key_delete_removes_alias(tmp_path):
    path = _flac_copy(tmp_path, 'Gmin')
    provider = MutagenProvider(str(path))
    provider.set_tag(KEY_INITIAL_KEY, ['6A'])
    provider.save()

    provider = MutagenProvider(str(path))
    provider.delete_tag(KEY_INITIAL_KEY)
    provider.save()

    raw = mutagen.File(str(path))
    assert 'INITIALKEY' not in raw
    assert FLAC_KEY_ALIAS not in raw


@pytest.mark.skipif(not FLAC_FIXTURE.exists(), reason="FLAC fixture not present")
def test_flac_key_alias_not_listed_as_tag(tmp_path):
    provider = MutagenProvider(str(_flac_copy(tmp_path, 'Gmin')))
    names = [info.internal_tag_name for info in provider.available_internal_tags()]
    assert FLAC_KEY_ALIAS.lower() not in names
    assert KEY_INITIAL_KEY in names


SERATO_MP3_FIXTURE = FIXTURE_DIR / "sample_dtmf_unicode_with_bpm_and_key_from_serato.mp3"
MP3_KEY_ALIAS_FRAME = 'TXXX:INITIALKEY'


def _serato_mp3_copy(tmp_path, alias_value: str | None = None) -> Path:
    """Temp copy of the Serato MP3 fixture, optionally with a stale TXXX key frame."""
    temp_media_path = tmp_path / SERATO_MP3_FIXTURE.name
    shutil.copy(SERATO_MP3_FIXTURE, temp_media_path)
    if alias_value is not None:
        raw = mutagen.File(str(temp_media_path))
        raw.tags.add(mutagen.id3.TXXX(encoding=3, desc='INITIALKEY', text=[alias_value]))
        raw.save()
    return temp_media_path


@pytest.mark.skipif(not SERATO_MP3_FIXTURE.exists(), reason="Serato MP3 fixture not present")
def test_mp3_key_write_updates_existing_txxx_alias(tmp_path):
    path = _serato_mp3_copy(tmp_path, 'Gmin')
    provider = MutagenProvider(str(path))
    provider.set_tag(KEY_INITIAL_KEY, ['6A'])
    provider.save()

    raw = mutagen.File(str(path))
    assert list(raw['TKEY'].text) == ['6A']
    assert list(raw[MP3_KEY_ALIAS_FRAME].text) == ['6A']
    assert MutagenProvider(str(path)).get_tag(KEY_INITIAL_KEY) == ['6A']


@pytest.mark.skipif(not SERATO_MP3_FIXTURE.exists(), reason="Serato MP3 fixture not present")
def test_mp3_key_write_does_not_create_txxx_alias(tmp_path):
    path = _serato_mp3_copy(tmp_path)
    provider = MutagenProvider(str(path))
    provider.set_tag(KEY_INITIAL_KEY, ['6A'])
    provider.save()

    raw = mutagen.File(str(path))
    assert list(raw['TKEY'].text) == ['6A']
    assert not any(frame.startswith('TXXX:INITIAL') for frame in raw.keys())


@pytest.mark.skipif(not SERATO_MP3_FIXTURE.exists(), reason="Serato MP3 fixture not present")
def test_mp3_key_delete_removes_txxx_alias(tmp_path):
    path = _serato_mp3_copy(tmp_path, 'Gmin')
    provider = MutagenProvider(str(path))
    provider.delete_tag(KEY_INITIAL_KEY)
    provider.save()

    raw = mutagen.File(str(path))
    assert 'TKEY' not in raw
    assert MP3_KEY_ALIAS_FRAME not in raw


@pytest.mark.skipif(not SERATO_MP3_FIXTURE.exists(), reason="Serato MP3 fixture not present")
def test_mp3_key_txxx_alias_not_listed_as_tag(tmp_path):
    provider = MutagenProvider(str(_serato_mp3_copy(tmp_path, 'Gmin')))
    names = [info.internal_tag_name for info in provider.available_internal_tags()]
    assert not any('INITIAL' in name.upper() and name != KEY_INITIAL_KEY for name in names)
    assert KEY_INITIAL_KEY in names
