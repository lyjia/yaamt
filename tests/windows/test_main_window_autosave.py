"""
Tests for the main window's autosave handling: the persisted preference,
the Save/Reset action enablement, and the Reset Changes row refresh.

``windows.main_window.settings`` is patched explicitly to the isolated
store: the conftest's autouse fixture only rebinds aliases in modules
already imported when it runs, and this module imports main_window
lazily inside the tests (same pattern as the favorites test suite).
"""

import shutil

import pytest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox

from models.edit_manager import EditManager
from models.media_file import MediaFile
from util.const import (
    IN_GITHUB_RUNNER, PROJECT_ROOT, SETTINGS_AUTOSAVE, AUTOSAVE_DEFAULT, KEY_TITLE, KEY_REMIXER,
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

    def test_partly_failed_commit_still_refreshes_written_rows(self, main_window, qapp, tmp_path):
        """A commit where some tags cannot be written reports an error, but the
        file did change on disk and its row must be refreshed (issue #79)."""
        temp_path = tmp_path / FIXTURE.name
        shutil.copy(FIXTURE, temp_path)
        media_file = MediaFile(str(temp_path), enable_write=True)
        edit_manager = main_window.edit_manager
        edit_manager.set_autosave(True)
        edit_manager.register_media_files([media_file])
        edit_manager.stage_change([media_file], KEY_TITLE, "Written")
        # Bypass the staging guard: simulates the file changing on disk
        # between staging and saving.
        with patch.object(media_file, 'can_write_tag', return_value=True):
            edit_manager.stage_change([media_file], KEY_REMIXER, "Unwritable")

        # Patched on the class: MainWindows left over from earlier tests are
        # still connected to the singleton EditManager and would otherwise
        # open a real, blocking error dialog.
        with patch.object(main_window.file_model, 'refresh_files') as refresh, \
                patch.object(QMessageBox, 'exec') as show_error:
            assert edit_manager.commit_changes() is True
            assert edit_manager.wait_for_pending_commit()
            qapp.processEvents()

        assert show_error.called
        refresh.assert_called_once_with([media_file.file_id], edit_manager)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainWindowQuitFlow:
    """closeEvent ordering (issue #84): prompt first, tear down after, and
    never exit while a background commit is still writing."""

    @pytest.fixture
    def main_window(self, qapp, isolated_qsettings):
        import windows.main_window as main_window_mod

        with patch.object(main_window_mod, 'settings', isolated_qsettings):
            window = main_window_mod.MainWindow()
            yield window
            window.edit_manager.reset_changes()
            window.edit_manager.set_autosave(True)
            if window.playback_thread.isRunning():
                window.close()

    @pytest.fixture
    def staged_file(self, main_window, tmp_path):
        """A writable temp copy of the fixture with a queued title edit."""
        temp_path = tmp_path / FIXTURE.name
        shutil.copy(FIXTURE, temp_path)
        media_file = MediaFile(str(temp_path), enable_write=True)
        main_window.edit_manager.register_media_files([media_file])
        main_window.edit_manager.stage_change([media_file], KEY_TITLE, "Quit Flow")
        return media_file

    def test_cancel_keeps_window_alive(self, main_window, staged_file):
        main_window.edit_manager.set_autosave(False)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Cancel):
            assert main_window.close() is False
        # Nothing was torn down: playback still works and the edit is still queued.
        assert main_window.playback_thread.isRunning()
        assert main_window.edit_manager.has_staged_changes()

    def test_discard_closes_without_writing(self, main_window, staged_file):
        main_window.edit_manager.set_autosave(False)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Discard):
            assert main_window.close() is True
        assert not main_window.playback_thread.isRunning()
        assert MediaFile(staged_file.file_path).get_tag_simple(KEY_TITLE) != "Quit Flow"

    def test_quit_waits_for_commit_in_flight(self, main_window, staged_file):
        edit_manager = main_window.edit_manager
        edit_manager.set_autosave(True)
        assert edit_manager.commit_changes() is True  # background thread started
        with patch.object(QMessageBox, 'question', side_effect=AssertionError("must not prompt")):
            assert main_window.close() is True
        assert edit_manager.wait_for_pending_commit(0)
        assert not edit_manager.has_staged_changes()
        assert MediaFile(staged_file.file_path).get_tag_simple(KEY_TITLE) == "Quit Flow"
