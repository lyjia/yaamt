import os
import json
import shutil
import sys
from unittest.mock import patch, MagicMock
import pytest
from mutagen.easyid3 import EasyID3
from yaamt import main, SYS_RETURN_FILE_NOT_FOUND, SYS_RETURN_FILE_INVALID, SYS_RETURN_SUCCESS

# Fixture file to use for testing
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "fixtures/metadata/sample_dtmf_unicode.mp3")
SOURCE_FILE_NO_META = os.path.join(os.path.dirname(__file__), "fixtures/metadata/sample_dtmf_nometa.mp3")


@pytest.fixture
def mock_argv():
    """Fixture to mock sys.argv."""
    with patch.object(sys, 'argv', ['src/yaamt.py']):
        yield sys.argv


class TestMainCli:
    def test_no_args_prints_help(self, mock_argv, capsys):
        """Verify that running with no arguments prints the help message."""
        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS
        captured = capsys.readouterr()
        assert "YAAMT - Yet Another Audio Metadata Tool" in captured.out

    def test_read_metadata_text(self, tmp_path, mock_argv, capsys):
        """Verify reading metadata in plain text format."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)
        mock_argv.extend(['read', '-f', 'list', str(test_file)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS
        captured = capsys.readouterr()
        assert "Metadata for:" in captured.out
        assert "artist" in captured.out
        assert "Lyjia" in captured.out
        assert "album" in captured.out
        assert "pytest" in captured.out

    def test_read_metadata_json(self, tmp_path, mock_argv, capsys):
        """Verify reading metadata in JSON format."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)
        mock_argv.extend(['read', '-f', 'json', str(test_file)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["tags"]["artist"]["value"] == "Lyjia"
        assert data[0]["tags"]["album"]["value"] == "pytest"

    def test_file_not_found(self, mock_argv, capsys):
        """Test handling of file not found errors."""
        mock_argv.extend(['read', "non_existent_file.mp3"])
        exit_code = main()
        assert exit_code == SYS_RETURN_FILE_NOT_FOUND
        captured = capsys.readouterr()
        assert "No supported audio files found" in captured.err

    def test_update_single_tag(self, tmp_path, mock_argv, capsys):
        """Test updating a single tag."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)
        mock_argv.extend(['write', '--tag', 'artist=New Artist', str(test_file)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS

        audio = EasyID3(str(test_file))
        assert audio['artist'] == ['New Artist']

        captured = capsys.readouterr()
        assert "Successfully updated" in captured.out

    def test_update_multiple_tags(self, tmp_path, mock_argv):
        """Test updating multiple tags at once."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)
        mock_argv.extend([
            'write',
            '--tag', 'artist=New Artist',
            '--tag', 'album=New Album',
            str(test_file)
        ])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS

        audio = EasyID3(str(test_file))
        assert audio['artist'] == ['New Artist']
        assert audio['album'] == ['New Album']

    def test_update_tags_shortcut(self, tmp_path, mock_argv):
        """Test updating tags using shortcut arguments."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)
        mock_argv.extend([
            'write',
            '--artist', 'Shortcut Artist',
            '--album', 'Shortcut Album',
            str(test_file)
        ])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS

        audio = EasyID3(str(test_file))
        assert audio['artist'] == ['Shortcut Artist']
        assert audio['album'] == ['Shortcut Album']

    def test_update_internal_tag(self, tmp_path, mock_argv, capsys):
        """Test updating an internal tag (using encodedby as a regular tag)."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE_NO_META, test_file)
        # Note: In the new CLI, we write internal tags as regular tags
        # The old --update-internal-tag is no longer supported
        mock_argv.extend(['write', '--tag', 'encodedby=TestEncoder', str(test_file)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS

        audio = EasyID3(str(test_file))
        assert audio['encodedby'] == ['TestEncoder']

    def test_corrupted_file(self, tmp_path, mock_argv, capsys):
        """Test handling of a corrupted file."""
        corrupted_file = tmp_path / "corrupted.mp3"
        with open(corrupted_file, "w") as f:
            f.write("this is not an mp3 file")
        mock_argv.extend(['read', str(corrupted_file)])

        exit_code = main()
        assert exit_code == SYS_RETURN_FILE_INVALID
        captured = capsys.readouterr()
        assert "Failed to load" in captured.err

    def test_directory_processing(self, tmp_path, mock_argv, capsys):
        """Test processing a directory of files."""
        test_dir = tmp_path / "music"
        os.makedirs(test_dir)
        shutil.copy(SOURCE_FILE, test_dir / "test1.mp3")
        shutil.copy(SOURCE_FILE_NO_META, test_dir / "test2.mp3")
        mock_argv.extend(['read', '-f', 'json', str(test_dir)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2

    def test_directory_recursive(self, tmp_path, mock_argv, capsys):
        """Test recursive directory scanning."""
        test_dir = tmp_path / "music"
        sub_dir = test_dir / "subdir"
        os.makedirs(sub_dir)
        shutil.copy(SOURCE_FILE, test_dir / "test1.mp3")
        shutil.copy(SOURCE_FILE_NO_META, sub_dir / "test2.mp3")
        mock_argv.extend(['read', '-R', '-f', 'json', str(test_dir)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2

    def test_update_tags_directory(self, tmp_path, mock_argv):
        """Test updating tags for all files in a directory."""
        test_dir = tmp_path / "music"
        os.makedirs(test_dir)
        shutil.copy(SOURCE_FILE, test_dir / "test1.mp3")
        shutil.copy(SOURCE_FILE_NO_META, test_dir / "test2.mp3")
        mock_argv.extend(['write', '--artist', 'Same Artist', str(test_dir)])

        exit_code = main()
        assert exit_code == SYS_RETURN_SUCCESS

        audio1 = EasyID3(test_dir / "test1.mp3")
        assert audio1['artist'] == ['Same Artist']
        audio2 = EasyID3(test_dir / "test2.mp3")
        assert audio2['artist'] == ['Same Artist']
