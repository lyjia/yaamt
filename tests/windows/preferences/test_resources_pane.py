"""Tests for the Resources preferences pane — specifically the new fpcalc
path and AcoustID API-key rows added for the MusicBrainz fingerprint
analyzer."""

import pytest

from util.const import IN_GITHUB_RUNNER, SETTINGS_ACOUSTID_API_KEY, SETTINGS_FPCALC_PATH


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


@pytest.fixture
def pane(qapp, tmp_path, monkeypatch):
    """Return a ResourcesPane backed by an isolated QSettings store."""
    from PySide6.QtCore import QSettings
    from models import settings as settings_mod
    from windows.preferences import resources_pane as rp_mod

    # Isolate QSettings to an INI file under tmp_path so tests don't touch
    # the user's real preferences.
    ini_path = tmp_path / "settings.ini"
    isolated = QSettings(str(ini_path), QSettings.Format.IniFormat)
    monkeypatch.setattr(settings_mod, "get_qsettings", lambda: isolated)
    monkeypatch.setattr(rp_mod, "get_qsettings", lambda: isolated)

    from windows.preferences.resources_pane import ResourcesPane
    return ResourcesPane()


def test_fpcalc_status_ok_when_file_exists(pane, tmp_path):
    fpcalc = tmp_path / "fpcalc"
    fpcalc.write_text("")
    pane._set_fpcalc_path(str(fpcalc))
    assert pane.fpcalc_path_edit.text() == str(fpcalc)
    assert "OK" in pane.fpcalc_status_label.text()
    # Path was persisted to QSettings.
    assert pane.settings.value(SETTINGS_FPCALC_PATH, "", type=str) == str(fpcalc)


def test_fpcalc_status_not_found_when_path_missing(pane, tmp_path):
    missing = tmp_path / "does-not-exist"
    pane._set_fpcalc_path(str(missing))
    assert "not found" in pane.fpcalc_status_label.text().lower()


def test_fpcalc_status_not_configured_when_empty(pane):
    pane._update_fpcalc_status("")
    assert "not configured" in pane.fpcalc_status_label.text().lower()


def test_detect_without_fpcalc_on_path(pane, monkeypatch):
    from windows.preferences import resources_pane as rp_mod
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(rp_mod.shutil, "which", lambda _name: None)
    called = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *args, **kwargs: called.setdefault("info", True),
    )
    pane._on_detect_fpcalc()
    assert called.get("info") is True
    # Nothing was persisted.
    assert pane.settings.value(SETTINGS_FPCALC_PATH, "", type=str) == ""


def test_detect_picks_up_fpcalc_on_path(pane, tmp_path, monkeypatch):
    from windows.preferences import resources_pane as rp_mod

    fpcalc = tmp_path / "fpcalc"
    fpcalc.write_text("")
    monkeypatch.setattr(rp_mod.shutil, "which", lambda _name: str(fpcalc))
    pane._on_detect_fpcalc()
    assert pane.fpcalc_path_edit.text() == str(fpcalc)
    assert pane.settings.value(SETTINGS_FPCALC_PATH, "", type=str) == str(fpcalc)


def test_api_key_roundtrip_through_save_and_load(pane):
    pane.acoustid_api_key_edit.setText("   super-secret-key   ")
    pane.save_to_settings()
    # Whitespace is trimmed on save.
    assert pane.settings.value(SETTINGS_ACOUSTID_API_KEY, "", type=str) == "super-secret-key"

    # Clearing the widget and re-loading restores the value from settings.
    pane.acoustid_api_key_edit.clear()
    pane.load_from_settings()
    assert pane.acoustid_api_key_edit.text() == "super-secret-key"


def test_load_defaults_clears_fpcalc_and_api_key(pane, tmp_path):
    fpcalc = tmp_path / "fpcalc"
    fpcalc.write_text("")
    pane._set_fpcalc_path(str(fpcalc))
    pane.acoustid_api_key_edit.setText("some-key")

    pane.load_defaults()

    assert pane.fpcalc_path_edit.text() == ""
    assert pane.acoustid_api_key_edit.text() == ""
    assert "not configured" in pane.fpcalc_status_label.text().lower()
