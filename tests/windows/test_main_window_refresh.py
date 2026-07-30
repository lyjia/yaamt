"""
Tests for the main window's manual refresh feature (F5 / View > Refresh)
and the View menu construction it depends on.

``windows.main_window.settings`` is patched explicitly to the isolated
store: the conftest's autouse fixture only rebinds aliases in modules
already imported when it runs, and this module imports main_window
lazily inside the tests (same pattern as the autosave test suite).
"""

import pytest
from unittest.mock import patch

from util.const import IN_GITHUB_RUNNER, KEY_FILE_PATH


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

        main_window._reset_column_settings()

        actions_after = main_window.view_menu.actions()
        assert main_window.action_show_playback_panel in actions_after
        # The column submenu and Reset Columns entry must still be present.
        assert main_window.column_menu.menuAction() in actions_after
        assert any(a.text() == "Reset Columns" for a in actions_after)
