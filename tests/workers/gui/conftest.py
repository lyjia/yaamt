"""
Shared fixtures for playback-related worker tests: a mocked audio stream,
a mocked MediaFile, a mocked miniaudio module, and a PlaybackWorker with
deterministic teardown.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import miniaudio
import pytest

from models.media_file import MediaFile
from providers.audio.base import AudioStreamBase
from workers.gui.playback_worker import PlaybackWorker, STOPPED


@pytest.fixture
def mock_audio_stream():
    """Fixture to create a mock AudioStreamBase instance."""
    mock_stream = MagicMock(spec=AudioStreamBase)
    mock_stream.sample_rate = 44100
    mock_stream.channels_qty = 2
    mock_stream.sample_width = 2
    mock_stream.duration_seconds = 10.0

    # Mock the read method to simulate audio data
    mock_stream.read.return_value = b'\x00' * 1024

    # Keep track of the current position
    mock_stream.current_frame = 0

    def seek_side_effect(frame_offset):
        mock_stream.current_frame = frame_offset

    mock_stream.seek.side_effect = seek_side_effect

    def current_position_seconds_side_effect():
        return mock_stream.current_frame / mock_stream.sample_rate

    type(mock_stream).current_position_seconds = PropertyMock(
        side_effect=current_position_seconds_side_effect)

    return mock_stream


@pytest.fixture
def mock_media_file(mock_audio_stream):
    """Fixture to create a mock MediaFile instance."""
    mock_mf = MagicMock(spec=MediaFile)
    mock_mf.file_path = "test.mp3"
    mock_mf.get_audio_stream.return_value = mock_audio_stream
    return mock_mf


@pytest.fixture
def playback_worker(qapp):
    """Fixture to create a PlaybackWorker instance."""
    worker = PlaybackWorker()
    yield worker
    # Deterministic teardown: a started position timer must not outlive the
    # test, or it fires into a destroyed QObject when a later test pumps the
    # event loop (intermittent segfault/bus error mid-suite).
    worker.timer.stop()
    worker.state = STOPPED


@pytest.fixture
def mock_miniaudio():
    """Fixture to mock miniaudio."""
    with patch('workers.gui.playback_worker.miniaudio') as mock_ma:
        # Mock the PlaybackDevice class
        mock_device = MagicMock()
        mock_ma.PlaybackDevice.return_value = mock_device

        # Mock SampleFormat enum
        mock_ma.SampleFormat.UNSIGNED8 = miniaudio.SampleFormat.UNSIGNED8
        mock_ma.SampleFormat.SIGNED16 = miniaudio.SampleFormat.SIGNED16
        mock_ma.SampleFormat.SIGNED24 = miniaudio.SampleFormat.SIGNED24
        mock_ma.SampleFormat.SIGNED32 = miniaudio.SampleFormat.SIGNED32

        yield {
            'miniaudio_mock': mock_ma,
            'device_mock': mock_device
        }
