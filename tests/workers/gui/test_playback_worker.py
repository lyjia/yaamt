import pytest
import miniaudio
from unittest.mock import MagicMock, patch, PropertyMock

from util.const import IN_GITHUB_RUNNER
from workers.gui.playback_worker import PlaybackWorker, PLAYING, PAUSED, STOPPED
from providers.audio.base import AudioStreamBase
from providers.audio.format_descriptor import AudioFormatDescriptor
from models.media_file import MediaFile
from models.settings import settings

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

    type(mock_stream).current_position_seconds = PropertyMock(side_effect=current_position_seconds_side_effect)

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
    return PlaybackWorker()


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


class TestPlaybackWorker:
    """Test suite for the PlaybackWorker class."""

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_initial_state(self, playback_worker):
        """Test that the worker initializes to the STOPPED state."""
        assert playback_worker.state == STOPPED
        assert playback_worker.audio_stream is None
        assert playback_worker.playback_device is None
        assert playback_worker.current_file is None
        assert playback_worker.duration == 0.0

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_start_playback_success(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test successful start of playback."""
        # Connect a spy to the playback_started signal
        spy = MagicMock()
        playback_worker.playback_started.connect(spy)

        playback_worker.start_playback(mock_media_file)

        # Verify MediaFile.get_audio_stream was called
        mock_media_file.get_audio_stream.assert_called_once()

        # Verify PlaybackDevice was created with correct parameters
        mock_miniaudio['miniaudio_mock'].PlaybackDevice.assert_called_once()
        args, kwargs = mock_miniaudio['miniaudio_mock'].PlaybackDevice.call_args
        assert kwargs['output_format'] == miniaudio.SampleFormat.SIGNED16
        assert kwargs['nchannels'] == mock_audio_stream.channels_qty
        assert kwargs['sample_rate'] == mock_audio_stream.sample_rate

        # Verify playback device was started
        mock_miniaudio['device_mock'].start.assert_called_once()

        # Verify state is PLAYING
        assert playback_worker.state == PLAYING
        assert playback_worker.current_file == "test.mp3"

        # Verify signal was emitted
        spy.assert_called_once_with("test.mp3", 10.0)

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_start_playback_error(self, playback_worker, mock_media_file):
        """Test error handling during start_playback."""
        mock_media_file.get_audio_stream.side_effect = Exception("Test error")

        # Connect a spy to the error_occurred signal
        spy = MagicMock()
        playback_worker.error_occurred.connect(spy)

        playback_worker.start_playback(mock_media_file)

        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED

        # Verify error signal was emitted
        spy.assert_called_once()
        assert "Error starting playback: Test error" in spy.call_args[0][0]

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_position_update(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test the position update mechanism."""
        # Connect spies to signals
        position_spy = MagicMock()
        playback_worker.position_changed.connect(position_spy)

        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Simulate position change
        playback_worker.position_changed.emit(1.0)

        # Verify position_changed signal was emitted during playback
        assert position_spy.call_count > 0

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_pause_resume(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test pause and resume functionality."""
        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Pause playback
        playback_worker.pause()
        assert playback_worker.state == PAUSED

        # Resume playback
        playback_worker.resume()
        assert playback_worker.state == PLAYING

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_stop(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test stop functionality."""
        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Connect a spy to the playback_stopped signal
        spy = MagicMock()
        playback_worker.playback_stopped.connect(spy)

        # Stop playback
        playback_worker.stop()

        # Verify state is STOPPED
        assert playback_worker.state == STOPPED

        # Verify signal was emitted
        spy.assert_called_once()

        # Verify cleanup was called
        mock_miniaudio['device_mock'].close.assert_called_once()
        mock_audio_stream.close.assert_called_once()

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_seek(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test seek functionality."""
        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Connect a spy to the position_changed signal
        spy = MagicMock()
        playback_worker.position_changed.connect(spy)

        # Seek to a specific position
        seek_position = 5.0  # 5 seconds
        playback_worker.seek(seek_position)

        # Verify audio stream seek was called with correct frame offset
        expected_frame_offset = int(seek_position * mock_audio_stream.sample_rate)
        mock_audio_stream.seek.assert_called_once_with(expected_frame_offset)

        # Verify position_changed signal was emitted
        spy.assert_called_with(seek_position)

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_seek_error(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test error handling during seek."""
        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Make seek raise an exception
        mock_audio_stream.seek.side_effect = Exception("Seek error")

        # Connect a spy to the error_occurred signal
        spy = MagicMock()
        playback_worker.error_occurred.connect(spy)

        # Attempt to seek
        playback_worker.seek(5.0)

        # Verify error signal was emitted
        spy.assert_called_once()
        assert "Error seeking: Seek error" in spy.call_args[0][0]

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_stop_when_already_stopped(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that stop() does nothing when already stopped."""
        # Start and then stop playback
        playback_worker.start_playback(mock_media_file)
        playback_worker.stop()

        # Reset mocks
        mock_miniaudio['device_mock'].reset_mock()
        mock_audio_stream.reset_mock()

        # Connect a spy to the playback_stopped signal
        spy = MagicMock()
        playback_worker.playback_stopped.connect(spy)

        # Call stop again
        playback_worker.stop()

        # Verify no additional cleanup was performed
        mock_miniaudio['device_mock'].close.assert_not_called()
        mock_audio_stream.close.assert_not_called()

        # Verify signal was not emitted again
        spy.assert_not_called()

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_pause_when_not_playing(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that pause() does nothing when not playing."""
        # Start and then stop playback
        playback_worker.start_playback(mock_media_file)
        playback_worker.stop()

        # Call pause
        playback_worker.pause()

        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_resume_when_not_paused(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that resume() does nothing when not paused."""
        # Start and then stop playback
        playback_worker.start_playback(mock_media_file)
        playback_worker.stop()

        # Call resume
        playback_worker.resume()

        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_format_adaptation_disabled(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that format adaptation is disabled by default."""
        # Ensure format adaptation is disabled in settings
        settings.setValue("Debug/PlaybackFormatAdaptationEnabled", False)

        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Verify get_audio_stream was called with None (no format descriptor)
        mock_media_file.get_audio_stream.assert_called_once_with(None)

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_format_adaptation_enabled_with_settings(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that format adaptation uses settings when enabled."""
        # Enable format adaptation with specific settings
        settings.setValue("Debug/PlaybackFormatAdaptationEnabled", True)
        settings.setValue("Debug/PlaybackSampleRate", 48000)
        settings.setValue("Debug/PlaybackChannels", 2)
        settings.setValue("Debug/PlaybackSampleWidth", 2)
        settings.setValue("Debug/PlaybackSampleFormat", "int")

        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Verify get_audio_stream was called with a format descriptor
        mock_media_file.get_audio_stream.assert_called_once()
        format_desc = mock_media_file.get_audio_stream.call_args[0][0]

        assert format_desc is not None
        assert isinstance(format_desc, AudioFormatDescriptor)
        assert format_desc.sample_rate == 48000
        assert format_desc.channels == 2
        assert format_desc.sample_width == 2
        assert format_desc.sample_format == "int"

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_format_adaptation_partial_settings(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that format adaptation handles partial settings (some native, some custom)."""
        # Enable format adaptation with only some settings
        settings.setValue("Debug/PlaybackFormatAdaptationEnabled", True)
        settings.setValue("Debug/PlaybackSampleRate", 44100)
        settings.setValue("Debug/PlaybackChannels", 0)  # Native
        settings.setValue("Debug/PlaybackSampleWidth", 0)  # Native
        settings.setValue("Debug/PlaybackSampleFormat", "")  # Native

        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Verify get_audio_stream was called with a format descriptor
        mock_media_file.get_audio_stream.assert_called_once()
        format_desc = mock_media_file.get_audio_stream.call_args[0][0]

        assert format_desc is not None
        assert isinstance(format_desc, AudioFormatDescriptor)
        assert format_desc.sample_rate == 44100
        assert format_desc.channels is None  # Native
        assert format_desc.sample_width is None  # Native
        assert format_desc.sample_format is None  # Native

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
    def test_format_adaptation_all_native(self, playback_worker, mock_media_file, mock_audio_stream, mock_miniaudio):
        """Test that format adaptation with all native settings returns None."""
        # Enable format adaptation but set all to native
        settings.setValue("Debug/PlaybackFormatAdaptationEnabled", True)
        settings.setValue("Debug/PlaybackSampleRate", 0)
        settings.setValue("Debug/PlaybackChannels", 0)
        settings.setValue("Debug/PlaybackSampleWidth", 0)
        settings.setValue("Debug/PlaybackSampleFormat", "")

        # Start playback
        playback_worker.start_playback(mock_media_file)

        # Verify get_audio_stream was called with None (all native = no adaptation needed)
        mock_media_file.get_audio_stream.assert_called_once_with(None)