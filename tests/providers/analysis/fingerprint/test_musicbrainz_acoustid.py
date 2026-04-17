"""
Unit tests for MusicBrainzAcoustIDAnalyzer.

The analyzer is fully mocked at the ``acoustid`` module boundary: we stub
``acoustid.fingerprint_file`` and ``acoustid.lookup`` so the tests do not
require fpcalc or network access.
"""

import shutil
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from models.media_file import MediaFile
from providers import get_analyzers_by_category
from providers.analysis import AnalyzerCategory
from providers.analysis.fingerprint.musicbrainz_acoustid import (
    MIN_DURATION_SECONDS,
    MusicBrainzAcoustIDAnalyzer,
)
from util.const import (
    KEY_ACOUSTID_FINGERPRINT,
    KEY_ACOUSTID_ID,
    KEY_COMMENT,
    KEY_MUSICBRAINZ_RECORDING_ID,
)


FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"

# Any playable fixture is fine for these tests — the fingerprint call is
# mocked so the audio content never leaves the file system.
MEDIA_FILE = FIXTURE_DIR / "sample_dtmf_original.flac"

SAMPLE_MBID = "e02a4d3a-0e87-4d46-9b63-8c8ed07e7f74"
SAMPLE_MBID_ALT = "00000000-0000-0000-0000-000000000001"
SAMPLE_ACOUSTID = "b3e8c7d9-0a12-4f5e-9d6b-8a7c6e5d4c3b"
SAMPLE_FINGERPRINT_BYTES = b"AQADtFIkREmiREkS" + b"A" * 1500
SAMPLE_DURATION = 180.5


def _fake_lookup_response(score: float, results_count: int = 1,
                          mbid: str = SAMPLE_MBID,
                          acoustid_uuid: str = SAMPLE_ACOUSTID) -> dict:
    """Build a fake AcoustID JSON response with N qualifying results."""
    results = []
    for i in range(results_count):
        results.append({
            "id": acoustid_uuid if i == 0 else f"00000000-0000-0000-0000-{i:012d}",
            "score": score,
            "recordings": [
                {"id": mbid if i == 0 else SAMPLE_MBID_ALT, "title": "Test Track"},
            ],
        })
    return {"status": "ok", "results": results}


@pytest.fixture
def media_file():
    if not MEDIA_FILE.exists():
        pytest.skip("Audio fixture not available")
    return MediaFile(str(MEDIA_FILE), enable_write=False)


@pytest.fixture
def media_file_with_mbid(tmp_path):
    """A copy of the fixture with an MBID tag preset, for skip-if-exists tests."""
    if not MEDIA_FILE.exists():
        pytest.skip("Audio fixture not available")
    temp = tmp_path / MEDIA_FILE.name
    shutil.copy(MEDIA_FILE, temp)
    mf = MediaFile(str(temp), enable_write=True)
    mf.save({"generic_tags": {KEY_MUSICBRAINZ_RECORDING_ID: SAMPLE_MBID}})
    # Re-open fresh to reflect the write on disk.
    return MediaFile(str(temp), enable_write=False)


@pytest.fixture
def stub_resolvers(monkeypatch):
    """Provide a deterministic fpcalc path and API key."""
    monkeypatch.setattr(
        "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_fpcalc_path",
        lambda: "/usr/bin/fpcalc",
    )
    monkeypatch.setattr(
        "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_api_key",
        lambda: "test-api-key",
    )


@pytest.fixture
def fake_acoustid(monkeypatch):
    """Install a fake ``acoustid`` module so the analyzer's lazy import succeeds."""
    mod = types.ModuleType("acoustid")
    mod.fingerprint_file = lambda path, force_fpcalc=None: (SAMPLE_DURATION, SAMPLE_FINGERPRINT_BYTES)
    mod.lookup = lambda api_key, fp, duration, meta=None: _fake_lookup_response(0.95)
    monkeypatch.setitem(sys.modules, "acoustid", mod)
    return mod


class TestRegistration:
    def test_analyzer_metadata(self):
        assert MusicBrainzAcoustIDAnalyzer.name == "MusicBrainz AcoustID"
        assert MusicBrainzAcoustIDAnalyzer.category == "fingerprint"

    def test_analyzer_discovered(self):
        analyzers = get_analyzers_by_category(AnalyzerCategory.FINGERPRINT)
        assert MusicBrainzAcoustIDAnalyzer in analyzers

    def test_options_metadata(self):
        options = {o.name: o for o in MusicBrainzAcoustIDAnalyzer.get_options_metadata()}
        assert options["min_score"].default == 0.85
        assert options["require_unique_match"].default is True
        assert options["store_fingerprint"].default is False
        assert options["append_to_comments"].default is False

    def test_thread_count_is_one(self):
        # AcoustID rate-limits; the analyzer must stay single-threaded.
        assert MusicBrainzAcoustIDAnalyzer.get_thread_count() == 1


class TestEarlyExits:
    def test_missing_pyacoustid(self, media_file, stub_resolvers, monkeypatch):
        monkeypatch.setitem(sys.modules, "acoustid", None)
        result = MusicBrainzAcoustIDAnalyzer(media_file).analyze()
        assert result.success is False
        assert "pyacoustid" in result.error.lower()

    def test_missing_fpcalc(self, media_file, fake_acoustid, monkeypatch):
        monkeypatch.setattr(
            "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_fpcalc_path",
            lambda: None,
        )
        monkeypatch.setattr(
            "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_api_key",
            lambda: "test-api-key",
        )
        result = MusicBrainzAcoustIDAnalyzer(media_file).analyze()
        assert result.success is False
        assert "fpcalc" in result.error.lower()

    def test_missing_api_key(self, media_file, fake_acoustid, monkeypatch):
        monkeypatch.setattr(
            "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_fpcalc_path",
            lambda: "/usr/bin/fpcalc",
        )
        monkeypatch.setattr(
            "providers.analysis.fingerprint.musicbrainz_acoustid._resolve_api_key",
            lambda: "",
        )
        result = MusicBrainzAcoustIDAnalyzer(media_file).analyze()
        assert result.success is False
        assert "api key" in result.error.lower()

    def test_cancellation_short_circuits(self, media_file, stub_resolvers, fake_acoustid):
        analyzer = MusicBrainzAcoustIDAnalyzer(media_file)
        analyzer.cancel()
        result = analyzer.analyze()
        assert result.success is False
        assert "cancel" in result.error.lower()

    def test_skip_if_mbid_exists(self, media_file_with_mbid, stub_resolvers, fake_acoustid):
        analyzer = MusicBrainzAcoustIDAnalyzer(
            media_file_with_mbid, {"skip_if_tag_exists": True}
        )
        result = analyzer.analyze()
        assert result.success is True
        assert result.skipped is True


class TestMatchArbitration:
    def test_no_confident_match(self, media_file, stub_resolvers, monkeypatch):
        fake = types.ModuleType("acoustid")
        fake.fingerprint_file = lambda p, force_fpcalc=None: (SAMPLE_DURATION, SAMPLE_FINGERPRINT_BYTES)
        fake.lookup = lambda a, f, d, meta=None: _fake_lookup_response(0.50)
        monkeypatch.setitem(sys.modules, "acoustid", fake)

        result = MusicBrainzAcoustIDAnalyzer(media_file, {"min_score": 0.85}).analyze()
        assert result.skipped is True
        assert "no acoustid match" in result.error.lower()

    def test_multiple_matches_ambiguous(self, media_file, stub_resolvers, monkeypatch):
        fake = types.ModuleType("acoustid")
        fake.fingerprint_file = lambda p, force_fpcalc=None: (SAMPLE_DURATION, SAMPLE_FINGERPRINT_BYTES)
        fake.lookup = lambda a, f, d, meta=None: _fake_lookup_response(0.95, results_count=2)
        monkeypatch.setitem(sys.modules, "acoustid", fake)

        result = MusicBrainzAcoustIDAnalyzer(media_file, {"require_unique_match": True}).analyze()
        assert result.skipped is True
        assert "ambiguous" in result.error.lower()

    def test_multiple_matches_allowed_when_not_unique(self, media_file, stub_resolvers, monkeypatch):
        fake = types.ModuleType("acoustid")
        fake.fingerprint_file = lambda p, force_fpcalc=None: (SAMPLE_DURATION, SAMPLE_FINGERPRINT_BYTES)
        fake.lookup = lambda a, f, d, meta=None: _fake_lookup_response(0.95, results_count=3)
        monkeypatch.setitem(sys.modules, "acoustid", fake)

        result = MusicBrainzAcoustIDAnalyzer(media_file, {"require_unique_match": False}).analyze()
        # Takes the top-scored result.
        assert result.success is True
        assert result.skipped is False
        assert result.data[KEY_MUSICBRAINZ_RECORDING_ID] == SAMPLE_MBID

    def test_acoustid_error_response(self, media_file, stub_resolvers, monkeypatch):
        fake = types.ModuleType("acoustid")
        fake.fingerprint_file = lambda p, force_fpcalc=None: (SAMPLE_DURATION, SAMPLE_FINGERPRINT_BYTES)
        fake.lookup = lambda a, f, d, meta=None: {
            "status": "error",
            "error": {"message": "invalid api key"},
        }
        monkeypatch.setitem(sys.modules, "acoustid", fake)

        result = MusicBrainzAcoustIDAnalyzer(media_file).analyze()
        assert result.success is False
        assert "invalid api key" in result.error.lower()


class TestSuccessPath:
    def test_single_match_writes_mbid_and_acoustid(self, media_file, stub_resolvers, fake_acoustid):
        result = MusicBrainzAcoustIDAnalyzer(media_file).analyze()
        assert result.success is True
        assert result.skipped is False
        assert result.data[KEY_MUSICBRAINZ_RECORDING_ID] == SAMPLE_MBID
        assert result.data[KEY_ACOUSTID_ID] == SAMPLE_ACOUSTID
        # Fingerprint is opt-in — must be absent by default.
        assert KEY_ACOUSTID_FINGERPRINT not in result.data

    def test_store_fingerprint_opt_in(self, media_file, stub_resolvers, fake_acoustid):
        result = MusicBrainzAcoustIDAnalyzer(
            media_file, {"store_fingerprint": True}
        ).analyze()
        assert result.success is True
        assert KEY_ACOUSTID_FINGERPRINT in result.data
        # Chromaprint bytes must be decoded to a plain string before writing.
        assert isinstance(result.data[KEY_ACOUSTID_FINGERPRINT], str)
        assert result.data[KEY_ACOUSTID_FINGERPRINT] == SAMPLE_FINGERPRINT_BYTES.decode("ascii")

    def test_append_to_comments_marker_append(self, media_file, stub_resolvers, fake_acoustid):
        result = MusicBrainzAcoustIDAnalyzer(
            media_file, {"append_to_comments": True}
        ).analyze()
        assert result.success is True
        # No existing comment on the fixture -> comment is just the MBID line.
        assert result.data[KEY_COMMENT] == f"MBID: {SAMPLE_MBID}"

    def test_append_to_comments_marker_replace(self, tmp_path, stub_resolvers, fake_acoustid):
        temp = tmp_path / MEDIA_FILE.name
        shutil.copy(MEDIA_FILE, temp)
        mf_writable = MediaFile(str(temp), enable_write=True)
        mf_writable.save({"generic_tags": {KEY_COMMENT: f"Peak: -3.14 dBFS\nMBID: old-uuid"}})
        mf = MediaFile(str(temp), enable_write=False)

        result = MusicBrainzAcoustIDAnalyzer(
            mf, {"append_to_comments": True}
        ).analyze()
        assert result.success is True
        expected = f"Peak: -3.14 dBFS\nMBID: {SAMPLE_MBID}"
        assert result.data[KEY_COMMENT] == expected


class TestValidateFile:
    def test_unreadable_file_rejected(self):
        class _FakeMediaFile:
            def is_readable(self):
                return False
            def get_stream_info_value(self, key):
                return None
        ok, reason = MusicBrainzAcoustIDAnalyzer.validate_file(_FakeMediaFile())
        assert ok is False
        assert "not readable" in reason.lower()

    def test_short_file_rejected(self):
        class _FakeMediaFile:
            def is_readable(self):
                return True
            def get_stream_info_value(self, key):
                return MIN_DURATION_SECONDS - 1
        ok, reason = MusicBrainzAcoustIDAnalyzer.validate_file(_FakeMediaFile())
        assert ok is False
        assert "shorter than" in reason.lower()

    def test_long_enough_file_accepted(self):
        class _FakeMediaFile:
            def is_readable(self):
                return True
            def get_stream_info_value(self, key):
                return 120.0
        ok, reason = MusicBrainzAcoustIDAnalyzer.validate_file(_FakeMediaFile())
        assert ok is True
        assert reason is None


class TestFpcalcResolution:
    def test_settings_override_wins(self, tmp_path, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        fake_fpcalc = tmp_path / "fpcalc"
        fake_fpcalc.write_text("")

        class FakeQSettings:
            def value(self, key, default, type=None):
                return str(fake_fpcalc)
        monkeypatch.setattr(mod, "get_qsettings", lambda: FakeQSettings())
        assert mod._resolve_fpcalc_path() == str(fake_fpcalc)

    def test_env_var_fallback(self, tmp_path, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        fake_fpcalc = tmp_path / "fpcalc"
        fake_fpcalc.write_text("")

        class FakeQSettings:
            def value(self, key, default, type=None):
                return ""
        monkeypatch.setattr(mod, "get_qsettings", lambda: FakeQSettings())
        monkeypatch.setenv("FPCALC", str(fake_fpcalc))
        assert mod._resolve_fpcalc_path() == str(fake_fpcalc)

    def test_which_fallback(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        class FakeQSettings:
            def value(self, key, default, type=None):
                return ""
        monkeypatch.setattr(mod, "get_qsettings", lambda: FakeQSettings())
        monkeypatch.delenv("FPCALC", raising=False)
        with patch.object(mod.shutil, "which", return_value="/tmp/fpcalc-from-path"):
            assert mod._resolve_fpcalc_path() == "/tmp/fpcalc-from-path"

    def test_none_when_nothing_found(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        class FakeQSettings:
            def value(self, key, default, type=None):
                return ""
        monkeypatch.setattr(mod, "get_qsettings", lambda: FakeQSettings())
        monkeypatch.delenv("FPCALC", raising=False)
        with patch.object(mod.shutil, "which", return_value=None):
            assert mod._resolve_fpcalc_path() is None
