"""Tests for the Integrations preferences pane (AcoustID API key field)."""

import pytest

from util.const import IN_GITHUB_RUNNER, SETTINGS_ACOUSTID_API_KEY


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


@pytest.fixture
def pane(qapp, tmp_path, monkeypatch):
    """IntegrationsPane backed by an isolated QSettings store and a stub
    verifier so tests never make real network calls."""
    from PySide6.QtCore import QSettings
    from models import settings as settings_mod
    from windows.preferences import integrations_pane as ip_mod

    isolated = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(settings_mod, "get_qsettings", lambda: isolated)
    monkeypatch.setattr(ip_mod, "get_qsettings", lambda: isolated)

    # Replace the verifier callable so the field never reaches the network.
    monkeypatch.setattr(
        ip_mod, "verify_acoustid_api_key", lambda _key: (True, None)
    )

    return ip_mod.IntegrationsPane()


def test_persisted_key_is_loaded_and_marked_verified(pane):
    pane.settings.setValue(SETTINGS_ACOUSTID_API_KEY, "remembered")
    pane.load_from_settings()
    assert pane.acoustid_api_key_field.text() == "remembered"
    assert pane.acoustid_api_key_field.is_valid() is True
    assert pane.is_ready_to_save() is True


def test_save_writes_field_text(pane):
    pane.acoustid_api_key_field.setText("new-key")
    pane.acoustid_api_key_field.mark_verified("new-key")
    pane.save_to_settings()
    assert pane.settings.value(SETTINGS_ACOUSTID_API_KEY, "", type=str) == "new-key"


def test_unverified_key_blocks_save(pane):
    pane.acoustid_api_key_field.setText("typed-but-unverified")
    assert pane.is_ready_to_save() is False
    ok, message = pane.validate()
    assert ok is False
    assert "verified" in message.lower()


def test_empty_field_is_savable(pane):
    pane.acoustid_api_key_field.setText("")
    assert pane.is_ready_to_save() is True
    assert pane.validate() == (True, "")


def test_load_defaults_clears_field(pane):
    pane.acoustid_api_key_field.setText("a-key")
    pane.acoustid_api_key_field.mark_verified("a-key")
    pane.load_defaults()
    assert pane.acoustid_api_key_field.text() == ""


def test_field_validity_change_re_emits_pane_signal(pane):
    seen: list[bool] = []
    pane.validity_changed.connect(seen.append)
    pane.acoustid_api_key_field.setText("typed")
    pane.acoustid_api_key_field.line_edit.textEdited.emit("typed")
    assert False in seen
