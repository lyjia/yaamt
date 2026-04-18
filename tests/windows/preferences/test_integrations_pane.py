"""Tests for the Integrations preferences pane."""

import pytest

from util.const import IN_GITHUB_RUNNER, SETTINGS_ACOUSTID_API_KEY


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


@pytest.fixture
def pane(qapp, tmp_path, monkeypatch):
    """IntegrationsPane backed by an isolated QSettings store."""
    from PySide6.QtCore import QSettings
    from models import settings as settings_mod
    from windows.preferences import integrations_pane as ip_mod

    isolated = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    # Patch both where the function lives and where the pane module imported
    # it, so the pane's __init__ (which runs before monkeypatch takes effect
    # on the module attribute used at class instantiation time) still gets
    # the isolated instance.
    monkeypatch.setattr(settings_mod, "get_qsettings", lambda: isolated)
    monkeypatch.setattr(ip_mod, "get_qsettings", lambda: isolated)

    return ip_mod.IntegrationsPane()


def test_api_key_round_trip(pane):
    pane.acoustid_api_key_edit.setText("  my-acoustid-key  ")
    pane.save_to_settings()
    # Whitespace is trimmed on save.
    assert pane.settings.value(SETTINGS_ACOUSTID_API_KEY, "", type=str) == "my-acoustid-key"

    pane.acoustid_api_key_edit.clear()
    pane.load_from_settings()
    assert pane.acoustid_api_key_edit.text() == "my-acoustid-key"


def test_api_key_defaults_to_blank(pane):
    pane.load_from_settings()
    assert pane.acoustid_api_key_edit.text() == ""


def test_load_defaults_clears_api_key(pane):
    pane.acoustid_api_key_edit.setText("something")
    pane.load_defaults()
    assert pane.acoustid_api_key_edit.text() == ""


def test_api_key_uses_password_echo_mode(pane):
    from PySide6.QtWidgets import QLineEdit
    assert pane.acoustid_api_key_edit.echoMode() == QLineEdit.EchoMode.Password


def test_pane_metadata(pane):
    assert pane.get_name() == "Integrations"
    assert pane.get_icon() is not None
    assert pane.validate() == (True, "")
