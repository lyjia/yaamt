"""Tests for PreferencesWindow — specifically the ``select_pane`` helper
used by deep-links from elsewhere in the app (e.g. the MusicBrainz
AcoustID analyzer's Requirements section)."""

import pytest

from util.const import IN_GITHUB_RUNNER


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


@pytest.fixture
def prefs(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from models import settings as settings_mod
    import windows.preferences_window as pref_mod
    import windows.preferences.integrations_pane as ip_mod
    import windows.preferences.resources_pane as rp_mod
    import windows.preferences.general_pane as gp_mod
    import windows.preferences.metadata_pane as mp_mod

    isolated = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    # Patch every pane module's imported get_qsettings so widget setup
    # doesn't touch the user's real QSettings.
    for mod in (settings_mod, pref_mod, ip_mod, rp_mod, gp_mod, mp_mod):
        if hasattr(mod, "get_qsettings"):
            monkeypatch.setattr(mod, "get_qsettings", lambda: isolated)

    return pref_mod.PreferencesWindow()


def test_select_pane_switches_to_matching_pane(prefs):
    assert prefs.select_pane("Integrations") is True
    current_index = prefs.category_list.currentRow()
    current_pane = prefs.panes[current_index]
    assert current_pane.get_name() == "Integrations"


def test_select_pane_returns_false_for_unknown_name(prefs):
    assert prefs.select_pane("NoSuchPane") is False


def test_select_pane_targets_resources(prefs):
    assert prefs.select_pane("Resources") is True
    idx = prefs.category_list.currentRow()
    assert prefs.panes[idx].get_name() == "Resources"


def test_save_disabled_when_a_pane_is_not_ready(prefs):
    integrations = next(p for p in prefs.panes if p.get_name() == "Integrations")
    integrations.acoustid_api_key_field.setText("typed-but-unverified")
    integrations.acoustid_api_key_field.line_edit.textEdited.emit("typed-but-unverified")
    assert prefs.save_button.isEnabled() is False


def test_save_re_enabled_when_pane_becomes_ready(prefs):
    integrations = next(p for p in prefs.panes if p.get_name() == "Integrations")
    integrations.acoustid_api_key_field.setText("typed")
    integrations.acoustid_api_key_field.line_edit.textEdited.emit("typed")
    assert prefs.save_button.isEnabled() is False
    integrations.acoustid_api_key_field.mark_verified("typed")
    assert prefs.save_button.isEnabled() is True


def test_save_re_enabled_when_field_cleared(prefs):
    integrations = next(p for p in prefs.panes if p.get_name() == "Integrations")
    integrations.acoustid_api_key_field.setText("typed")
    integrations.acoustid_api_key_field.line_edit.textEdited.emit("typed")
    assert prefs.save_button.isEnabled() is False
    integrations.acoustid_api_key_field.setText("")
    assert prefs.save_button.isEnabled() is True
