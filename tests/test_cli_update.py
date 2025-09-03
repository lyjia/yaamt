import os
import shutil
import subprocess
import sys
import pytest
from mutagen.easyid3 import EasyID3

SOURCE_FILE = os.path.join(os.path.dirname(__file__), "fixtures/metadata/sample_dtmf_unicode.mp3")

def run_cli_command(args, timeout=5):
    command = [sys.executable, "src/main.py"] + args
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return result

class TestCliUpdate:
    def test_update_single_tag(self, tmp_path):
        test_file = tmp_path / "test.mp3"
        shutil.copy(SOURCE_FILE, test_file)

        result = run_cli_command([str(test_file), "--update-tag", "artist", "New Artist"])
        assert result.returncode == 0

        audio = EasyID3(str(test_file))
        assert audio['artist'] == ['New Artist']
