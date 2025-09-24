import pytest
import pyaudio
from unittest.mock import MagicMock, patch, PropertyMock

from PySide6.QtCore import QObject, Signal

from workers.gui.playback_worker import PlaybackWorker, PLAYING, PAUSED, STOPPED
from providers.audio.base import AudioStreamBase


class MockAudioStream(AudioStreamBase):
    """Mock implementation of AbstractAudioStream for testing."""
    def __init__(self, filepath: str, samplerate=44100, nchannels=2, sample_width=2, duration_seconds=10.0):
        self.filepath = filepath
        self._samplerate = samplerate
        self._nchannels = nchannels
        self._sample_width = sample_width
        self._duration_seconds = duration_seconds
        self._duration_frames = int(duration_seconds * samplerate)
        self._current_frame = 0
        self.closed = False

    def read(self, n_frames: int) -> bytes:
        if self.closed:
            return b''
        
        frames_to_read = min(n_frames, self._duration_frames - self._current_frame)
        if frames_to_read <= 0:
            return b''
        
        # Generate dummy audio data
        data = b'\x00' * (frames_to_read * self._nchannels * self._sample_width)
        self._current_frame += frames_to_read
        return data

    def seek(self, frame_offset: int) -> None:
        if self.closed:
            raise IOError("Stream is closed")
        self._current_frame = max(0, min(frame_offset, self._duration_frames))

    def close(self) -> None:
        self.closed = True

    @property
    def samplerate(self) -> int:
        return self._samplerate

    @property
    def nchannels(self) -> int:
        return self._nchannels

    @property
    def sample_width(self) -> int:
        return self._sample_width
    
    @property
    def current_position_seconds(self) -> float:
        return self._current_frame / self._samplerate

    @property
    def duration_seconds(self) -> float:
        return self._duration_seconds


@pytest.fixture
def playback_worker(qapp):
    """Fixture to create a PlaybackWorker instance."""
    return PlaybackWorker()


@pytest.fixture
def mock_audio_stream():
    """Fixture to create a MockAudioStream instance."""
    return MockAudioStream("test.mp3", duration_seconds=10.0)


@pytest.fixture
def mock_pyaudio():
    """Fixture to mock PyAudio."""
    with patch('workers.gui.playback_worker.pyaudio') as mock_pa:
        # Mock the PyAudio class
        mock_pa_instance = MagicMock()
        mock_pa.PyAudio.return_value = mock_pa_instance
        
        # Mock the output stream
        mock_output_stream = MagicMock()
        mock_pa_instance.open.return_value = mock_output_stream
        
        # Mock format_from_width
        mock_pa_instance.get_format_from_width.return_value = pyaudio.paInt16
        
        yield {
            'pyaudio_mock': mock_pa,
            'pyaudio_instance_mock': mock_pa_instance,
            'output_stream_mock': mock_output_stream
        }


class TestPlaybackWorker:
    """Test suite for the PlaybackWorker class."""

    def test_initial_state(self, playback_worker):
        """Test that the worker initializes to the STOPPED state."""
        assert playback_worker.state == STOPPED
        assert playback_worker.audio_stream is None
        assert playback_worker.pyaudio is None
        assert playback_worker.output_stream is None
        assert playback_worker.current_file is None
        assert playback_worker.duration == 0.0

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_start_playback_success(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test successful start of playback."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Connect a spy to the playback_started signal
        spy = MagicMock()
        playback_worker.playback_started.connect(spy)
        
        playback_worker.start_playback("test.mp3")
        
        # Verify AudioStreamBase.get_stream was called
        mock_get_stream.assert_called_once_with("test.mp3")
        
        # Verify PyAudio was initialized
        mock_pyaudio['pyaudio_mock'].PyAudio.assert_called_once()
        
        # Verify output stream was opened with correct parameters
        mock_pyaudio['pyaudio_instance_mock'].open.assert_called_once()
        args, kwargs = mock_pyaudio['pyaudio_instance_mock'].open.call_args
        assert kwargs['format'] == mock_pyaudio['pyaudio_instance_mock'].get_format_from_width(mock_audio_stream.sample_width)
        assert kwargs['channels'] == mock_audio_stream.nchannels
        assert kwargs['rate'] == mock_audio_stream.samplerate
        assert kwargs['output'] is True
        
        # Verify state is PLAYING
        assert playback_worker.state == PLAYING
        assert playback_worker.current_file == "test.mp3"
        
        # Verify signal was emitted
        spy.assert_called_once_with("test.mp3", 0.0)

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_start_playback_error(self, mock_get_stream, playback_worker):
        """Test error handling during start_playback."""
        mock_get_stream.side_effect = Exception("Test error")
        
        # Connect a spy to the error_occurred signal
        spy = MagicMock()
        playback_worker.error_occurred.connect(spy)
        
        playback_worker.start_playback("test.mp3")
        
        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED
        
        # Verify error signal was emitted
        spy.assert_called_once()
        assert "Error starting playback: Test error" in spy.call_args[0][0]

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_playback_loop(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test the main playback loop."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Connect spies to signals
        position_spy = MagicMock()
        finished_spy = MagicMock()
        stopped_spy = MagicMock()
        playback_worker.position_changed.connect(position_spy)
        playback_worker.playback_finished.connect(finished_spy)
        playback_worker.playback_stopped.connect(stopped_spy)
        
        # Start playback
        playback_worker.start_playback("test.mp3")
        
        # Verify position_changed signal was emitted during playback
        assert position_spy.call_count > 0
        
        # Simulate end of file by calling _playback_loop again
        # This is a bit of a hack since _playback_loop is designed to run in a thread
        # We'll manually set the state to PLAYING and call the method
        playback_worker.state = PLAYING
        # Mock read to return empty data to simulate end of file
        mock_audio_stream.read = MagicMock(return_value=b'')
        playback_worker._playback_loop()
        
        # Verify playback_finished and playback_stopped signals were emitted
        finished_spy.assert_called_once()
        stopped_spy.assert_called_once()
        
        # Verify state is STOPPED
        assert playback_worker.state == STOPPED

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_pause_resume(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test pause and resume functionality."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start playback
        playback_worker.start_playback("test.mp3")
        
        # Pause playback
        playback_worker.pause()
        assert playback_worker.state == PAUSED
        mock_pyaudio['output_stream_mock'].stop_stream.assert_called_once()
        
        # Resume playback
        # We need to mock the _playback_loop to prevent it from actually running
        with patch.object(playback_worker, '_playback_loop'):
            playback_worker.resume()
            assert playback_worker.state == PLAYING
            mock_pyaudio['output_stream_mock'].start_stream.assert_called_once()

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_stop(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test stop functionality."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start playback
        playback_worker.start_playback("test.mp3")
        
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
        mock_pyaudio['output_stream_mock'].stop_stream.assert_called_once()
        mock_pyaudio['output_stream_mock'].close.assert_called_once()
        mock_pyaudio['pyaudio_instance_mock'].terminate.assert_called_once()
        mock_audio_stream.close.assert_called_once()

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_seek(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test seek functionality."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start playback
        playback_worker.start_playback("test.mp3")
        
        # Connect a spy to the position_changed signal
        spy = MagicMock()
        playback_worker.position_changed.connect(spy)
        
        # Seek to a specific position
        seek_position = 5.0  # 5 seconds
        playback_worker.seek(seek_position)
        
        # Verify audio stream seek was called with correct frame offset
        expected_frame_offset = int(seek_position * mock_audio_stream.samplerate)
        mock_audio_stream.seek.assert_called_once_with(expected_frame_offset)
        
        # Verify position_changed signal was emitted
        spy.assert_called_with(seek_position)

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_seek_error(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test error handling during seek."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start playback
        playback_worker.start_playback("test.mp3")
        
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

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_cleanup_on_exception_during_playback(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test that cleanup is called when an exception occurs during playback."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Make read raise an exception during playback
        mock_audio_stream.read.side_effect = Exception("Playback error")
        
        # Connect spies to signals
        error_spy = MagicMock()
        stopped_spy = MagicMock()
        playback_worker.error_occurred.connect(error_spy)
        playback_worker.playback_stopped.connect(stopped_spy)
        
        # Start playback, which will trigger the exception
        playback_worker.start_playback("test.mp3")
        
        # Verify error and stopped signals were emitted
        error_spy.assert_called_once()
        assert "Error during playback: Playback error" in error_spy.call_args[0][0]
        stopped_spy.assert_called_once()
        
        # Verify state is STOPPED
        assert playback_worker.state == STOPPED
        
        # Verify cleanup was called
        mock_pyaudio['output_stream_mock'].stop_stream.assert_called()
        mock_pyaudio['output_stream_mock'].close.assert_called()
        mock_pyaudio['pyaudio_instance_mock'].terminate.assert_called()
        mock_audio_stream.close.assert_called()

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_stop_when_already_stopped(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test that stop() does nothing when already stopped."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start and then stop playback
        playback_worker.start_playback("test.mp3")
        playback_worker.stop()
        
        # Reset mocks
        mock_pyaudio['output_stream_mock'].reset_mock()
        mock_pyaudio['pyaudio_instance_mock'].reset_mock()
        mock_audio_stream.reset_mock()
        
        # Connect a spy to the playback_stopped signal
        spy = MagicMock()
        playback_worker.playback_stopped.connect(spy)
        
        # Call stop again
        playback_worker.stop()
        
        # Verify no additional cleanup was performed
        mock_pyaudio['output_stream_mock'].stop_stream.assert_not_called()
        mock_pyaudio['output_stream_mock'].close.assert_not_called()
        mock_pyaudio['pyaudio_instance_mock'].terminate.assert_not_called()
        mock_audio_stream.close.assert_not_called()
        
        # Verify signal was not emitted again
        spy.assert_not_called()

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_pause_when_not_playing(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test that pause() does nothing when not playing."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start and then stop playback
        playback_worker.start_playback("test.mp3")
        playback_worker.stop()
        
        # Reset mocks
        mock_pyaudio['output_stream_mock'].reset_mock()
        
        # Call pause
        playback_worker.pause()
        
        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED
        
        # Verify no pause action was performed
        mock_pyaudio['output_stream_mock'].stop_stream.assert_not_called()

    @patch('workers.gui.playback_worker.AudioStreamBase.get_stream')
    def test_resume_when_not_paused(self, mock_get_stream, playback_worker, mock_audio_stream, mock_pyaudio):
        """Test that resume() does nothing when not paused."""
        mock_get_stream.return_value = mock_audio_stream
        
        # Start and then stop playback
        playback_worker.start_playback("test.mp3")
        playback_worker.stop()
        
        # Reset mocks
        mock_pyaudio['output_stream_mock'].reset_mock()
        
        # Call resume
        with patch.object(playback_worker, '_playback_loop'):
            playback_worker.resume()
        
        # Verify state is still STOPPED
        assert playback_worker.state == STOPPED
        
        # Verify no resume action was performed
        mock_pyaudio['output_stream_mock'].start_stream.assert_not_called()