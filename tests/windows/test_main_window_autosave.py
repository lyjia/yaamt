"""
Tests for the main window's autosave handling: the persisted preference,
the Save/Reset action enablement, and the Reset Changes row refresh.

``windows.main_window.settings`` is patched explicitly to the isolated
store: the conftest's autouse fixture only rebinds aliases in modules
already imported when it runs, and this module imports main_window
lazily inside the tests (same pattern as the favorites test suite).
"""

import pytest
from unittest.mock import patch

from models.edit_manager import EditManager
from models.media_file import MediaFile
from util.const import (
    IN_GITHUB_RUNNER, PROJECT_ROOT, SETTINGS_AUTOSAVE, AUTOSAVE_DEFAULT, KEY_TITLE,
)


FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3"


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainWindowAutosave:

    @pytest.fixture
    def main_window(self, qapp, isolated_qsettings):
        import windows.main_window as main_window_mod

        with patch.object(main_window_mod, 'settings', isolated_qsettings):
            window = main_window_mod.MainWindow()
            yield window
            # Leave the singleton EditManager clean for other tests, and make
            # sure closeEvent doesn't open the blocking unsaved-changes dialog.
            window.edit_manager.reset_changes()
            window.edit_manager.set_autosave(True)
            window.close()

    def test_autosave_toggle_is_persisted(self, main_window, isolated_qsettings):
        main_window.action_autosave.setChecked(False)
        assert main_window.edit_manager.autosave is False
        assert isolated_qsettings.value(SETTINGS_AUTOSAVE, AUTOSAVE_DEFAULT, type=bool) is False

        main_window.action_autosave.setChecked(True)
        assert main_window.edit_manager.autosave is True
        assert isolated_qsettings.value(SETTINGS_AUTOSAVE, AUTOSAVE_DEFAULT, type=bool) is True

    def test_persisted_autosave_applied_at_startup(self, qapp, isolated_qsettings):
        import windows.main_window as main_window_mod

        isolated_qsettings.setValue(SETTINGS_AUTOSAVE, False)
        with patch.object(main_window_mod, 'settings', isolated_qsettings):
            window = main_window_mod.MainWindow()
            try:
                assert window.edit_manager.autosave is False
                assert window.action_autosave.isChecked() is False
            finally:
                window.edit_manager.reset_changes()
                window.edit_manager.set_autosave(True)
                window.close()

    def test_save_reset_actions_track_autosave_and_staged_state(self, main_window):
        edit_manager = main_window.edit_manager
        edit_manager.reset_changes()

        # Autosave on: always disabled, commits are automatic.
        edit_manager.set_autosave(True)
        assert not main_window.action_save.isEnabled()
        assert not main_window.action_reset.isEnabled()

        # Autosave off but nothing queued: still disabled.
        edit_manager.set_autosave(False)
        assert not main_window.action_save.isEnabled()
        assert not main_window.action_reset.isEnabled()

        # Autosave off with a queued edit: enabled.
        media_file = MediaFile(str(FIXTURE))  # read-only; never saved here
        edit_manager.register_media_files([media_file])
        edit_manager.stage_change([media_file], KEY_TITLE, "Queued")
        assert main_window.action_save.isEnabled()
        assert main_window.action_reset.isEnabled()

        # Reset drains the queue and disables the actions again.
        main_window.on_reset_changes()
        assert not edit_manager.has_staged_changes()
        assert not main_window.action_save.isEnabled()
        assert not main_window.action_reset.isEnabled()
