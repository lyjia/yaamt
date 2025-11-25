"""Tests for the file_browser utility module."""

import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from util.file_browser import open_in_file_browser, _open_windows, _open_macos, _open_linux


class TestOpenInFileBrowser:
    """Tests for the open_in_file_browser function."""

    def test_returns_false_for_nonexistent_path(self, tmp_path):
        """Should return False when the file doesn't exist."""
        nonexistent = tmp_path / "nonexistent_file.txt"
        result = open_in_file_browser(nonexistent)
        assert result is False

    def test_accepts_string_path(self, tmp_path):
        """Should accept a string path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with patch('util.file_browser._open_windows') as mock_win, \
             patch('util.file_browser._open_macos') as mock_mac, \
             patch('util.file_browser._open_linux') as mock_linux:

            mock_win.return_value = True
            mock_mac.return_value = True
            mock_linux.return_value = True

            # Should not raise
            result = open_in_file_browser(str(test_file))
            assert result is True

    def test_accepts_path_object(self, tmp_path):
        """Should accept a Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with patch('util.file_browser._open_windows') as mock_win, \
             patch('util.file_browser._open_macos') as mock_mac, \
             patch('util.file_browser._open_linux') as mock_linux:

            mock_win.return_value = True
            mock_mac.return_value = True
            mock_linux.return_value = True

            # Should not raise
            result = open_in_file_browser(test_file)
            assert result is True

    @patch('platform.system')
    @patch('util.file_browser._open_windows')
    def test_calls_windows_handler_on_windows(self, mock_handler, mock_system, tmp_path):
        """Should call _open_windows on Windows."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_system.return_value = "Windows"
        mock_handler.return_value = True

        result = open_in_file_browser(test_file)

        assert result is True
        mock_handler.assert_called_once()

    @patch('platform.system')
    @patch('util.file_browser._open_macos')
    def test_calls_macos_handler_on_darwin(self, mock_handler, mock_system, tmp_path):
        """Should call _open_macos on macOS."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_system.return_value = "Darwin"
        mock_handler.return_value = True

        result = open_in_file_browser(test_file)

        assert result is True
        mock_handler.assert_called_once()

    @patch('platform.system')
    @patch('util.file_browser._open_linux')
    def test_calls_linux_handler_on_linux(self, mock_handler, mock_system, tmp_path):
        """Should call _open_linux on Linux."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_system.return_value = "Linux"
        mock_handler.return_value = True

        result = open_in_file_browser(test_file)

        assert result is True
        mock_handler.assert_called_once()


class TestOpenWindows:
    """Tests for the _open_windows function."""

    @patch('subprocess.run')
    def test_calls_explorer_with_select(self, mock_run, tmp_path):
        """Should call explorer with /select, argument."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        _open_windows(test_file)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "explorer"
        assert args[1] == "/select,"
        assert str(test_file) in args[2]


class TestOpenMacos:
    """Tests for the _open_macos function."""

    @patch('subprocess.run')
    def test_calls_open_with_reveal(self, mock_run, tmp_path):
        """Should call open with -R argument."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        _open_macos(test_file)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "open"
        assert args[1] == "-R"


class TestOpenLinux:
    """Tests for the _open_linux function."""

    @patch('shutil.which')
    @patch('subprocess.Popen')
    def test_tries_nautilus_first(self, mock_popen, mock_which, tmp_path):
        """Should try nautilus first if available."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_which.side_effect = lambda x: x if x == "nautilus" else None

        result = _open_linux(test_file)

        assert result is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "nautilus"
        assert args[1] == "--select"

    @patch('shutil.which')
    @patch('subprocess.Popen')
    def test_falls_back_to_xdg_open(self, mock_popen, mock_which, tmp_path):
        """Should fall back to xdg-open if no file manager is found."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Only xdg-open is available
        mock_which.side_effect = lambda x: x if x == "xdg-open" else None

        result = _open_linux(test_file)

        assert result is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "xdg-open"
        # xdg-open should be called with the parent directory
        assert str(test_file.parent) in args[1]

    @patch('shutil.which')
    def test_returns_false_when_no_manager_found(self, mock_which, tmp_path):
        """Should return False if no file manager is available."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_which.return_value = None

        result = _open_linux(test_file)

        assert result is False
