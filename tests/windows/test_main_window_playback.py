import os

import pytest
from unittest.mock import patch
from PySide6.QtCore import QModelIndex, QSettings
from PySide6.QtTest import QSignalSpy

from util.const import IN_GITHUB_RUNNER, KEY_FILE_PATH, KEY_IS_MEDIA

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "metadata")
MEDIA_FIXTURE = os.path.abspath(os.path.join(FIXTURES_DIR, "sample_dtmf_nometa.mp3"))
NON_MEDIA_FIXTURE = os.path.abspath(os.path.join(FIXTURES_DIR, "sample_dtmf_nometa.mp3.json"))


@pytest.fixture
def test_settings():
    """Clean QSettings instance so tests do not touch real user settings."""
    settings = QSettings("LyjiaTest", "Audio Metadata Tool Test")
    settings.clear()
    yield settings
    settings.clear()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainWindowPlaybackBinds:
    """Playback initiation from the files view (double-click) and the menu action."""

    @pytest.fixture
    def main_window(self, qapp, test_settings):
        with patch('windows.main_window.settings', test_settings):
            from windows.main_window import MainWindow
            window = MainWindow()
            # Detach the worker so no audio device is touched; the emitted
            # signal is observed with a QSignalSpy instead.
            window.start_playback_signal.disconnect(window.playback_worker.start_playback)
            window.file_model.set_entire_data([
                {KEY_FILE_PATH: MEDIA_FIXTURE, KEY_IS_MEDIA: True},
                {KEY_FILE_PATH: NON_MEDIA_FIXTURE, KEY_IS_MEDIA: False},
            ])
            yield window
            window.close()

    def _proxy_index_for_row(self, main_window, row: int) -> QModelIndex:
        return main_window.proxy_model.mapFromSource(main_window.file_model.index(row, 0))

    def test_double_click_on_media_row_starts_playback(self, main_window):
        spy = QSignalSpy(main_window.start_playback_signal)
        main_window.playback_panel.hide()

        main_window.on_files_view_double_clicked(self._proxy_index_for_row(main_window, 0))

        assert spy.count() == 1
        media_file = spy.at(0)[0]
        assert media_file.file_path == MEDIA_FIXTURE
        assert not main_window.playback_panel.isHidden()

    def test_double_click_on_non_media_row_does_nothing(self, main_window):
        spy = QSignalSpy(main_window.start_playback_signal)

        main_window.on_files_view_double_clicked(self._proxy_index_for_row(main_window, 1))

        assert spy.count() == 0

    def test_double_click_with_invalid_index_does_nothing(self, main_window):
        spy = QSignalSpy(main_window.start_playback_signal)

        main_window.on_files_view_double_clicked(QModelIndex())

        assert spy.count() == 0

    def test_play_action_with_single_selection_starts_playback(self, main_window):
        spy = QSignalSpy(main_window.start_playback_signal)
        main_window.files_view.selectionModel().select(
            self._proxy_index_for_row(main_window, 0),
            main_window.files_view.selectionModel().SelectionFlag.ClearAndSelect
            | main_window.files_view.selectionModel().SelectionFlag.Rows,
        )

        main_window.on_play_file_requested()

        assert spy.count() == 1
        assert spy.at(0)[0].file_path == MEDIA_FIXTURE

    def test_play_action_with_multi_selection_does_nothing(self, main_window):
        spy = QSignalSpy(main_window.start_playback_signal)
        sel_model = main_window.files_view.selectionModel()
        flags = sel_model.SelectionFlag.Select | sel_model.SelectionFlag.Rows
        sel_model.select(self._proxy_index_for_row(main_window, 0), flags)
        sel_model.select(self._proxy_index_for_row(main_window, 1), flags)

        main_window.on_play_file_requested()

        assert spy.count() == 0
