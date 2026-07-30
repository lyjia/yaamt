"""
Tests that MiniaudioStream releases its underlying file resources
deterministically on close() and seek(), rather than relying on garbage
collection. This matters when another component (metadata save, rename)
needs the file to be genuinely closed before touching it on disk.
"""

import os
import shutil
import sys

import pytest

from providers.audio.miniaudio_stream import MiniaudioStream
from util.const import PROJECT_ROOT

FIXTURE_AUDIO_FILE = os.path.join(
    PROJECT_ROOT, 'tests', 'fixtures', 'metadata', 'sample_dtmf_original.flac'
)


class _GeneratorRecorder:
    """Wraps a stream generator and records whether close() was called."""

    def __init__(self, generator):
        self._generator = generator
        self.closed = False

    def send(self, value):
        return self._generator.send(value)

    def close(self):
        self.closed = True
        self._generator.close()


@pytest.fixture
def tmp_audio_file(tmp_path):
    """A throwaway copy of a fixture audio file (never touch the original)."""
    dest = tmp_path / os.path.basename(FIXTURE_AUDIO_FILE)
    shutil.copyfile(FIXTURE_AUDIO_FILE, dest)
    return str(dest)


def _wrap_generator(stream: MiniaudioStream) -> _GeneratorRecorder:
    recorder = _GeneratorRecorder(stream.stream_generator)
    stream.stream_generator = recorder
    return recorder


def test_close_closes_generator(tmp_audio_file):
    stream = MiniaudioStream(tmp_audio_file)
    recorder = _wrap_generator(stream)

    stream.close()

    assert recorder.closed
    assert stream.stream_generator is None


def test_seek_closes_previous_generator(tmp_audio_file):
    stream = MiniaudioStream(tmp_audio_file)
    try:
        recorder = _wrap_generator(stream)

        stream.seek(0)

        assert recorder.closed
        # The replacement generator must still be readable.
        data = stream.read(512)
        assert len(data) > 0
    finally:
        stream.close()


def test_close_is_idempotent(tmp_audio_file):
    stream = MiniaudioStream(tmp_audio_file)
    stream.close()
    stream.close()  # Must not raise.


@pytest.mark.skipif(sys.platform != 'linux',
                    reason="/proc/self/fd is Linux-specific")
def test_close_releases_os_file_handle(tmp_audio_file):
    def open_fd_count(path: str) -> int:
        count = 0
        for fd in os.listdir('/proc/self/fd'):
            try:
                if os.readlink(f'/proc/self/fd/{fd}') == path:
                    count += 1
            except OSError:
                continue
        return count

    stream = MiniaudioStream(tmp_audio_file)
    assert open_fd_count(tmp_audio_file) >= 1

    stream.close()

    assert open_fd_count(tmp_audio_file) == 0
