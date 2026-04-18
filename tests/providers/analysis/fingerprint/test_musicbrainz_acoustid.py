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
    """Tests for ``_resolve_fpcalc_path`` — the priority chain is
    ResourceManager custom location → FPCALC env var → ``shutil.which``."""

    def test_custom_location_wins(self, tmp_path, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        fake = tmp_path / "fpcalc"
        fake.write_text("")

        class FakeRM:
            def get_custom_location(self, rid):
                return fake
        monkeypatch.setattr(mod, "get_resource_manager", lambda: FakeRM())
        monkeypatch.setenv("FPCALC", "/should/not/be/used")
        assert mod._resolve_fpcalc_path() == str(fake)

    def test_env_var_fallback(self, tmp_path, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        fake = tmp_path / "fpcalc"
        fake.write_text("")

        class FakeRM:
            def get_custom_location(self, rid):
                return None
        monkeypatch.setattr(mod, "get_resource_manager", lambda: FakeRM())
        monkeypatch.setenv("FPCALC", str(fake))
        assert mod._resolve_fpcalc_path() == str(fake)

    def test_path_fallback(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        class FakeRM:
            def get_custom_location(self, rid):
                return None
        monkeypatch.setattr(mod, "get_resource_manager", lambda: FakeRM())
        monkeypatch.delenv("FPCALC", raising=False)
        with patch.object(mod.shutil, "which", return_value="/tmp/fpcalc-from-path"):
            assert mod._resolve_fpcalc_path() == "/tmp/fpcalc-from-path"

    def test_none_when_nothing_found(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        class FakeRM:
            def get_custom_location(self, rid):
                return None
        monkeypatch.setattr(mod, "get_resource_manager", lambda: FakeRM())
        monkeypatch.delenv("FPCALC", raising=False)
        with patch.object(mod.shutil, "which", return_value=None):
            assert mod._resolve_fpcalc_path() is None


class TestResourceRegistration:
    """The analyzer must register Chromaprint's fpcalc binary so it shows up
    in Preferences > Resources alongside other downloadable resources."""

    def test_get_required_resources_declares_fpcalc(self):
        resources = MusicBrainzAcoustIDAnalyzer.get_required_resources()
        assert len(resources) == 1
        fpcalc = resources[0]
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            FPCALC_BINARY_NAME, FPCALC_RESOURCE_ID,
        )
        assert fpcalc.resource_id == FPCALC_RESOURCE_ID
        assert fpcalc.filename == FPCALC_BINARY_NAME
        assert fpcalc.download_type == "browser"
        assert fpcalc.discovery_executable == "fpcalc"
        assert fpcalc.required_by == "MusicBrainzAcoustIDAnalyzer"

    def test_fpcalc_registered_with_resource_manager(self):
        # Importing the manifest runs the @analyzer decorator which in turn
        # registers each analyzer's resources with the global ResourceManager.
        import providers.analysis._manifest  # noqa: F401
        from providers.analysis.fingerprint.musicbrainz_acoustid import FPCALC_RESOURCE_ID
        from util.resource_manager import get_resource_manager
        rm = get_resource_manager()
        registered = rm.get_all_registered_resources()
        assert FPCALC_RESOURCE_ID in registered


class TestRequirementsStatusHelpers:
    """HTML helpers that render the status of the analyzer's two
    requirements (fpcalc, AcoustID API key) in the settings widget."""

    def test_fpcalc_ok_html(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        monkeypatch.setattr(mod, "_resolve_fpcalc_path", lambda: "/usr/bin/fpcalc")
        html = mod._fpcalc_status_html()
        assert "&#x2713;" in html
        assert "/usr/bin/fpcalc" in html
        assert "Configure" not in html

    def test_fpcalc_missing_html_has_configure_link(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        monkeypatch.setattr(mod, "_resolve_fpcalc_path", lambda: None)
        html = mod._fpcalc_status_html()
        assert "&#x2717;" in html
        assert "Configure" in html
        assert 'href="#prefs"' in html

    def test_api_key_ok_html(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        monkeypatch.setattr(mod, "_resolve_api_key", lambda: "abc-123")
        html = mod._api_key_status_html()
        assert "&#x2713;" in html
        # The literal key value must never appear in the UI string.
        assert "abc-123" not in html
        assert "Configure" not in html

    def test_api_key_missing_html_has_configure_link(self, monkeypatch):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        monkeypatch.setattr(mod, "_resolve_api_key", lambda: "")
        html = mod._api_key_status_html()
        assert "&#x2717;" in html
        assert "Configure" in html
        assert 'href="#prefs"' in html


@pytest.mark.skipif(
    __import__("util.const", fromlist=["IN_GITHUB_RUNNER"]).IN_GITHUB_RUNNER,
    reason="Qt widgets crash in GitHub Actions runner",
)
class TestSettingsWidgetRequirements:
    """The Requirements group is wired into the settings widget and its
    links deep-link to the correct preference pane."""

    def test_widget_contains_requirements_group(self, qapp, monkeypatch):
        from PySide6.QtWidgets import QGroupBox, QLabel
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        monkeypatch.setattr(mod, "_resolve_fpcalc_path", lambda: None)
        monkeypatch.setattr(mod, "_resolve_api_key", lambda: "")

        widget = MusicBrainzAcoustIDAnalyzer.get_settings_widget()
        groups = [g.title() for g in widget.findChildren(QGroupBox)]
        assert "Requirements" in groups

        labels = {
            lbl.objectName(): lbl
            for lbl in widget.findChildren(QLabel)
            if lbl.objectName().startswith("requirement_")
        }
        assert "requirement_fpcalc" in labels
        assert "requirement_acoustid_api_key" in labels
        # Both should show the fail mark since nothing is configured.
        assert "&#x2717;" in labels["requirement_fpcalc"].text()
        assert "&#x2717;" in labels["requirement_acoustid_api_key"].text()

    def test_widget_reflects_configured_state(self, qapp, monkeypatch, tmp_path):
        from PySide6.QtWidgets import QLabel
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        fake = tmp_path / "fpcalc"
        fake.write_text("")
        monkeypatch.setattr(mod, "_resolve_fpcalc_path", lambda: str(fake))
        monkeypatch.setattr(mod, "_resolve_api_key", lambda: "my-key")

        widget = MusicBrainzAcoustIDAnalyzer.get_settings_widget()
        labels = {
            lbl.objectName(): lbl
            for lbl in widget.findChildren(QLabel)
            if lbl.objectName().startswith("requirement_")
        }
        assert "&#x2713;" in labels["requirement_fpcalc"].text()
        assert str(fake) in labels["requirement_fpcalc"].text()
        assert "&#x2713;" in labels["requirement_acoustid_api_key"].text()

    def test_link_click_opens_preferences_on_correct_pane(self, qapp, monkeypatch):
        """Clicking the Configure... link inside a requirement row should
        open PreferencesWindow.exec() after selecting the matching pane."""
        from PySide6.QtWidgets import QLabel
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod

        monkeypatch.setattr(mod, "_resolve_fpcalc_path", lambda: None)
        monkeypatch.setattr(mod, "_resolve_api_key", lambda: "")

        calls: list[str] = []

        class FakePreferencesWindow:
            def __init__(self, parent=None):
                pass

            def select_pane(self, name: str) -> bool:
                calls.append(name)
                return True

            def exec(self) -> int:
                return 0

        # Install the fake so the link handler picks it up via the lazy import.
        import windows.preferences_window as pref_mod
        monkeypatch.setattr(pref_mod, "PreferencesWindow", FakePreferencesWindow)

        widget = MusicBrainzAcoustIDAnalyzer.get_settings_widget()
        labels = {
            lbl.objectName(): lbl
            for lbl in widget.findChildren(QLabel)
            if lbl.objectName().startswith("requirement_")
        }

        labels["requirement_fpcalc"].linkActivated.emit("#prefs")
        labels["requirement_acoustid_api_key"].linkActivated.emit("#prefs")

        assert calls == ["Resources", "Integrations"]


class TestVerifyAcoustidApiKey:
    """Tests for ``verify_acoustid_api_key`` — the helper passed to
    ``ApiKeyField`` as its verifier callable."""

    def _patch_urlopen(self, monkeypatch, payload=None, raises=None):
        from providers.analysis.fingerprint import musicbrainz_acoustid as mod
        import io
        import json
        import urllib.request

        class _FakeResponse:
            def __init__(self, body: bytes):
                self._buf = io.BytesIO(body)

            def read(self):
                return self._buf.read()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(url, timeout=None):
            if raises is not None:
                raise raises
            return _FakeResponse(json.dumps(payload).encode("utf-8"))

        monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen) \
            if hasattr(mod, "urllib") else \
            monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    def test_empty_key_rejected_without_network(self, monkeypatch):
        # If the verifier ever calls the network with an empty key, this
        # assertion explodes.
        import urllib.request
        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no network for empty key")),
        )
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            verify_acoustid_api_key,
        )
        ok, error = verify_acoustid_api_key("")
        assert ok is False
        assert error and "empty" in error.lower()

    def test_status_ok_means_valid_key(self, monkeypatch):
        self._patch_urlopen(monkeypatch, payload={"status": "ok", "results": []})
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            verify_acoustid_api_key,
        )
        ok, error = verify_acoustid_api_key("good-key")
        assert ok is True
        assert error is None

    def test_error_code_4_means_invalid_key(self, monkeypatch):
        self._patch_urlopen(
            monkeypatch,
            payload={"status": "error", "error": {"code": 4, "message": "invalid api key"}},
        )
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            verify_acoustid_api_key,
        )
        ok, error = verify_acoustid_api_key("bad-key")
        assert ok is False
        assert "Invalid API key" in error

    def test_other_error_codes_surface_message(self, monkeypatch):
        self._patch_urlopen(
            monkeypatch,
            payload={"status": "error", "error": {"code": 99, "message": "rate limited"}},
        )
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            verify_acoustid_api_key,
        )
        ok, error = verify_acoustid_api_key("some-key")
        assert ok is False
        assert "rate limited" in error

    def test_network_failure_returns_clear_error(self, monkeypatch):
        import urllib.error
        self._patch_urlopen(
            monkeypatch,
            raises=urllib.error.URLError("Connection refused"),
        )
        from providers.analysis.fingerprint.musicbrainz_acoustid import (
            verify_acoustid_api_key,
        )
        ok, error = verify_acoustid_api_key("some-key")
        assert ok is False
        assert "Network error" in error
