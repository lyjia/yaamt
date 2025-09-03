
import os
import json
import shutil
import subprocess
import sys

import pytest
from mutagen.easyid3 import EasyID3

from src.main import SYS_RETURN_FILE_NOT_FOUND, SYS_RETURN_FILE_INVALID

# Fixture file to use for testing
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "fixtures/metadata/sample_dtmf_unicode.mp3")


def run_cli_command(args, timeout=5):
    """Helper function to run the CLI script with arguments and capture output."""
    command = [sys.executable, "src/main.py"] + args
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return result


class TestMainCli:
    def test_no_args_prints_help(self):
        """Verify that running with no arguments prints the help message."""
        result = run_cli_command([])
        assert "usage: main.py" in result.stdout
        assert "For the GUI, run: python src/gui.py" in result.stdout

    def test_read_metadata_text(self, tmp_path):
        """Verify reading metadata in plain text format."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        result = run_cli_command([str(test_file)])
        assert "Metadata for:" in result.stdout
        assert "artist: Lyjia" in result.stdout
        assert "album: pytest" in result.stdout

    def test_read_metadata_json(self, tmp_path):
        """Verify reading metadata in JSON format."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        result = run_cli_command([str(test_file), "--json"])
        data = json.loads(result.stdout)
        assert data["tags"]["artist"]["value"] == "Lyjia"
        assert data["tags"]["album"]["value"] == "pytest"

    def test_file_not_found(self):
        """Test handling of file not found errors."""
        result = run_cli_command(["non_existent_file.mp3"])
        assert "File not found" in result.stderr
        assert result.returncode == SYS_RETURN_FILE_NOT_FOUND

    def test_file_not_found_json(self):
        """Test handling of file not found errors with --json flag."""
        result = run_cli_command(["non_existent_file.mp3", "--json"])
        data = json.loads(result.stdout)
        assert "error" in data
        assert "File not found" in data["error"]
        assert result.returncode == SYS_RETURN_FILE_NOT_FOUND

    def test_update_single_tag(self, tmp_path):
        """Test updating a single tag."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        result = run_cli_command([str(test_file), "--update-tag", "artist", "New Artist"])
        assert result.returncode == 0

        audio = EasyID3(str(test_file))
        assert audio['artist'] == ['New Artist']

        # Verify that the output contains the updated metadata
        assert "Metadata for:" in result.stdout
        assert "artist: New Artist" in result.stdout

    def test_update_multiple_tags(self, tmp_path):
        """Test updating multiple tags at once."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        run_cli_command([
            str(test_file),
            "--update-tag", "artist", "New Artist",
            "--update-tag", "album", "New Album"
        ])
        result = run_cli_command([str(test_file), "--json"])
        data = json.loads(result.stdout)
        assert data["tags"]["artist"]["value"] == "New Artist"
        assert data["tags"]["album"]["value"] == "New Album"

    def test_update_tags_shortcut(self, tmp_path):
        """Test updating tags using shortcut arguments."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        run_cli_command([str(test_file), "--artist", "Shortcut Artist", "--album", "Shortcut Album"])
        result = run_cli_command([str(test_file), "--json"])
        data = json.loads(result.stdout)
        assert data["tags"]["artist"]["value"] == "Shortcut Artist"
        assert data["tags"]["album"]["value"] == "Shortcut Album"

    def test_update_internal_tag(self, tmp_path):
        """Test updating an internal tag."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        run_cli_command([str(test_file), "--update-internal-tag", "replaygain_track_gain", "-1.23 dB"])
        result = run_cli_command([str(test_file), "--json"])
        data = json.loads(result.stdout)
        assert data['internal']['replaygain_track_gain'] == '-1.23 dB'

    def test_corrupted_file(self, tmp_path):
        """Test handling of a corrupted file."""
        corrupted_file = tmp_path / "corrupted.mp3"
        with open(corrupted_file, "w") as f:
            f.write("this is not an mp3 file")

        result = run_cli_command([str(corrupted_file)])
        assert "File is not readable" in result.stderr
        assert result.returncode == SYS_RETURN_FILE_INVALID

    def test_corrupted_file_json(self, tmp_path):
        """Test handling of a corrupted file with --json flag."""
        corrupted_file = tmp_path / "corrupted.mp3"
        with open(corrupted_file, "w") as f:
            f.write("this is not an mp3 file")

        result = run_cli_command([str(corrupted_file), "--json"])
        data = json.loads(result.stdout)
        assert data.get('error') is not None

    def test_update_and_read_in_same_run(self, tmp_path):
        """Test updating and reading in the same run to ensure updates are applied before reading."""
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        result = run_cli_command([str(test_file), "--update-tag", "artist", "New Artist"])
        assert "Metadata for:" in result.stdout
        assert "artist: New Artist" in result.stdout
        assert result.returncode == 0
