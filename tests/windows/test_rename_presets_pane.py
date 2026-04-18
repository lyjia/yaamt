"""Tests for the Rename Presets preferences pane."""
import pytest

from util.const import IN_GITHUB_RUNNER, RENAME_PRESETS_DEFAULTS


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_pane_roundtrips_presets_through_settings(qapp, tmp_path, monkeypatch):
    from models.settings import get_qsettings
    from PySide6.QtCore import QSettings
    from windows.preferences.rename_presets_pane import RenamePresetsPane
    from windows.rename.setup_dialog import load_presets_from_settings

    # Redirect QSettings to a per-test ini file so we don't pollute real settings.
    settings_path = tmp_path / "yaamt_test.ini"
    monkeypatch.setattr(
        "models.settings.get_qsettings",
        lambda: QSettings(str(settings_path), QSettings.Format.IniFormat),
    )
    # Also ensure the pane's load path uses the same.
    monkeypatch.setattr(
        "windows.preferences.rename_presets_pane.load_presets_from_settings",
        lambda: load_presets_from_settings(),
    )

    pane = RenamePresetsPane()
    pane.load_defaults()
    assert pane._collect_presets() == list(RENAME_PRESETS_DEFAULTS)

    # Append a custom preset and save.
    pane._add_item("%GENRE% - %ARTIST% - %TITLE%")
    pane.save_to_settings()

    # Loading again should preserve the extra preset.
    saved = load_presets_from_settings()
    assert saved[:-1] == list(RENAME_PRESETS_DEFAULTS)
    assert saved[-1] == "%GENRE% - %ARTIST% - %TITLE%"

    # Remove via UI path and save -> the list shrinks.
    pane.list_widget.setCurrentRow(0)
    pane._on_remove()
    pane.save_to_settings()

    saved = load_presets_from_settings()
    assert saved[0] != RENAME_PRESETS_DEFAULTS[0] or len(saved) == len(RENAME_PRESETS_DEFAULTS)

    # Validation always returns OK for this pane.
    ok, msg = pane.validate()
    assert ok is True
    assert msg == ""


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_pane_move_up_down(qapp):
    from windows.preferences.rename_presets_pane import RenamePresetsPane

    pane = RenamePresetsPane()
    pane._populate_list(["a", "b", "c"])

    pane.list_widget.setCurrentRow(0)
    pane._move(+1)
    assert [pane.list_widget.item(i).text() for i in range(3)] == ["b", "a", "c"]

    pane.list_widget.setCurrentRow(2)
    pane._move(-1)
    assert [pane.list_widget.item(i).text() for i in range(3)] == ["b", "c", "a"]

    # Move past edge is a no-op.
    pane.list_widget.setCurrentRow(0)
    pane._move(-1)
    assert [pane.list_widget.item(i).text() for i in range(3)] == ["b", "c", "a"]
