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

from util.const import IN_GITHUB_RUNNER


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

    def test_view_menu_survives_reset_columns(self, main_window):
        actions_before = main_window.view_menu.actions()
        assert main_window.action_show_playback_panel in actions_before

        main_window._reset_column_settings()

        actions_after = main_window.view_menu.actions()
        assert main_window.action_show_playback_panel in actions_after
        # The column submenu and Reset Columns entry must still be present.
        assert main_window.column_menu.menuAction() in actions_after
        assert any(a.text() == "Reset Columns" for a in actions_after)
