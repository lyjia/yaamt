"""
Tests for the main window's manual refresh feature (F5 / View > Refresh)
and the View menu construction it depends on.

``windows.main_window.settings`` is patched explicitly to the isolated
store: the conftest's autouse fixture only rebinds aliases in modules
already imported when it runs, and this module imports main_window
lazily inside the tests (same pattern as the autosave test suite).
"""

import shutil
from pathlib import Path

import pytest
from unittest.mock import patch

from util.const import IN_GITHUB_RUNNER, KEY_FILE_PATH, KEY_TITLE, PROJECT_ROOT


FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3"


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainWindowRefresh:

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

    @staticmethod
    def _complete_load(main_window, directory, file_paths, restore_selection=None):
        """
        Drive _load_directory through a synchronous fake of the async load:
        the thread pool is stubbed out, rows are injected by hand, and the
        worker-finished handler is invoked directly.
        """
        with patch.object(main_window.thread_pool, "start"):
            main_window._load_directory(str(directory), restore_selection=restore_selection)
            main_window.file_model.add_rows([{KEY_FILE_PATH: p} for p in file_paths])
            main_window.on_worker_finished(main_window._current_worker_id)

    def test_refresh_restores_selection_after_load(self, main_window, tmp_path):
        paths = [str(tmp_path / f"track{i}.mp3") for i in range(3)]

        self._complete_load(main_window, tmp_path, paths,
                            restore_selection=[paths[0], paths[2]])

        assert sorted(main_window._get_selected_file_paths()) == sorted([paths[0], paths[2]])
        assert main_window._pending_selection_paths is None

    def test_normal_navigation_does_not_restore_selection(self, main_window, tmp_path):
        paths = [str(tmp_path / f"track{i}.mp3") for i in range(2)]
        # A stale pending list from an earlier refresh must be discarded by
        # plain navigation.
        main_window._pending_selection_paths = paths

        self._complete_load(main_window, tmp_path, paths)

        assert main_window._get_selected_file_paths() == []
        assert main_window._pending_selection_paths is None

    def test_stale_worker_does_not_restore_selection(self, main_window, tmp_path):
        paths = [str(tmp_path / "track0.mp3")]

        with patch.object(main_window.thread_pool, "start"):
            main_window._load_directory(str(tmp_path), restore_selection=paths)
            main_window.file_model.add_rows([{KEY_FILE_PATH: p} for p in paths])
            # A finished signal from a superseded worker must be ignored.
            main_window.on_worker_finished(main_window._current_worker_id - 1)

        assert main_window._get_selected_file_paths() == []
        assert main_window._pending_selection_paths == paths

    def test_view_menu_survives_reset_columns(self, main_window):
        actions_before = main_window.view_menu.actions()
        assert main_window.action_show_playback_panel in actions_before
        assert main_window.action_refresh in actions_before

        main_window._reset_column_settings()

        actions_after = main_window.view_menu.actions()
        assert main_window.action_show_playback_panel in actions_after
        assert main_window.action_refresh in actions_after
        # The column submenu and Reset Columns entry must still be present.
        assert main_window.column_menu.menuAction() in actions_after
        assert any(a.text() == "Reset Columns" for a in actions_after)

    def test_refresh_action_wiring(self, main_window):
        from PySide6.QtGui import QKeySequence

        # One action, two surfaces: toolbar and View menu.
        assert main_window.action_refresh in main_window.toolbar.actions()
        assert main_window.action_refresh in main_window.view_menu.actions()
        assert QKeySequence("F5") in main_window.action_refresh.shortcuts()

        with patch.object(main_window, 'on_refresh_requested') as handler:
            main_window.action_refresh.trigger()
        handler.assert_called_once()

    def test_refresh_ignored_when_directory_unavailable(self, main_window, tmp_path):
        gone = tmp_path / "gone"
        gone.mkdir()
        with patch.object(main_window.thread_pool, "start"):
            main_window._load_directory(str(gone))
            gone.rmdir()
            worker_id_before = main_window._current_worker_id
            main_window.on_refresh_requested()
        assert main_window._current_worker_id == worker_id_before

    def test_directory_pane_rebuild_restores_current_and_reconnects(self, main_window, tmp_path):
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        dir_b = tmp_path / "b"
        dir_b.mkdir()

        with patch.object(main_window.thread_pool, "start"):
            main_window._load_directory(str(dir_a))
            old_model = main_window.dir_model
            worker_id_before = main_window._current_worker_id

            main_window._refresh_directory_pane()

            # Fresh model installed on the view, current directory restored,
            # and the signal-blocked restore did not start a competing load.
            assert main_window.dir_model is not old_model
            assert main_window.directory_tree.model() is main_window.dir_model
            current = main_window.directory_tree.currentIndex()
            # QFileSystemModel.filePath returns forward slashes on Windows;
            # compare as Paths to stay separator-agnostic.
            assert Path(main_window.dir_model.filePath(current)) == dir_a
            assert main_window._current_worker_id == worker_id_before

            # Real navigation must still reach on_directory_changed through
            # the recreated selection model.
            main_window.directory_tree.setCurrentIndex(main_window.dir_model.index(str(dir_b)))
            assert Path(main_window._current_path) == dir_b
            assert main_window._current_worker_id == worker_id_before + 1

    def test_staged_edits_survive_refresh(self, main_window, tmp_path):
        from models.media_file import MediaFile

        target = tmp_path / "sample.mp3"
        shutil.copy(FIXTURE, target)

        edit_manager = main_window.edit_manager
        edit_manager.set_autosave(False)
        media_file = MediaFile(str(target))  # read-only; never saved here
        edit_manager.register_media_files([media_file])
        edit_manager.stage_change([media_file], KEY_TITLE, "Queued Title")
        assert edit_manager.has_staged_changes()

        with patch.object(main_window.thread_pool, "start"):
            main_window._load_directory(str(tmp_path))
            main_window.on_refresh_requested()

        assert edit_manager.has_staged_changes()
        assert edit_manager.get_staged_value(media_file.file_id, KEY_TITLE) == "Queued Title"
