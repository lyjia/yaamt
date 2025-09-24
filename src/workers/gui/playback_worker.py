import pyaudio
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from providers.audio.provider import AudioStreamProvider
from util.logging import log

# Playback states
PLAYING = "playing"
PAUSED = "paused"
STOPPED = "stopped"

class PlaybackWorker(QObject):
    """
    Worker object that handles audio playback in a separate thread.
    """
    # Signals
    playback_started = Signal(str, float)  # filename, duration in seconds
    position_changed = Signal(float)       # current position in seconds
    playback_finished = Signal()
    playback_stopped = Signal()
    playback_paused = Signal(str, float)
    playback_resumed = Signal(str, float)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = STOPPED
        self.audio_stream = None
        self.pyaudio = None
        self.output_stream = None
        self.current_file = None
        self.duration = 0.0
        self.total_frames_read = 0
        self.chunk_size = 1024

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._playback_loop)

    @Slot(str)
    def start_playback(self, filepath: str):
        """
        Start playback of the specified audio file.
        
        Args:
            filepath: Path to the audio file to play.
        """
        try:
            if self.state != STOPPED:
                self.stop()
            
            self.current_file = filepath
            log.info(f"Starting playback of {filepath}")
            
            self.audio_stream = AudioStreamProvider.get_stream(filepath)
            self.pyaudio = pyaudio.PyAudio()
            
            self.output_stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(self.audio_stream.sample_width),
                channels=self.audio_stream.nchannels,
                rate=self.audio_stream.samplerate,
                output=True
            )
            
            self.duration = self.audio_stream.duration
            self.total_frames_read = 0

            # Dynamically set timer interval
            chunk_duration_ms = (self.chunk_size / self.audio_stream.samplerate) * 1000
            self.timer.setInterval(chunk_duration_ms / 2)  # Update at twice the speed of chunk playback
            
            self.state = PLAYING
            self.playback_started.emit(filepath, self.duration)
            self.timer.start()
            
        except Exception as e:
            log.error(f"Error starting playback: {str(e)}")
            self.error_occurred.emit(f"Error starting playback: {str(e)}")
            self.cleanup()

    def _playback_loop(self):
        """
        The main playback loop that reads from the audio stream and writes to the output device.
        This is called by the QTimer.
        """
        if self.state != PLAYING:
            return

        try:
            data = self.audio_stream.read(self.chunk_size)
            
            if not data:
                self.playback_finished.emit()
                self.stop()
                return
            
            self.output_stream.write(data)
            
            frames_read = len(data) / (self.audio_stream.sample_width * self.audio_stream.nchannels)
            self.total_frames_read += frames_read
            current_position = self.total_frames_read / self.audio_stream.samplerate
            self.position_changed.emit(current_position)
            
        except Exception as e:
            log.error(f"Error during playback: {str(e)}")
            self.error_occurred.emit(f"Error during playback: {str(e)}")
            self.stop()

    @Slot()
    def pause(self):
        """
        Pause the current playback.
        """
        if self.state == PLAYING:
            self.state = PAUSED
            self.timer.stop()
            if self.output_stream:
                self.output_stream.stop_stream()
            self.playback_paused.emit(self.current_file, self.duration)

    @Slot()
    def resume(self):
        """
        Resume paused playback.
        """
        if self.state == PAUSED:
            self.state = PLAYING
            if self.output_stream:
                self.output_stream.start_stream()
            self.timer.start()
            self.playback_resumed.emit(self.current_file, self.duration)

    @Slot()
    def stop(self):
        """
        Stop the current playback and clean up resources.
        """
        if self.state != STOPPED:
            self.state = STOPPED
            self.timer.stop()
            self.playback_stopped.emit()
            self.cleanup()

    @Slot(float)
    def seek(self, position_seconds: float):
        """
        Seek to a specific position in the audio file.
        
        Args:
            position_seconds: Position in seconds to seek to.
        """
        if self.audio_stream:
            try:
                frame_offset = int(position_seconds * self.audio_stream.samplerate)
                self.audio_stream.seek(frame_offset)
                self.total_frames_read = frame_offset
                self.position_changed.emit(position_seconds)
            except Exception as e:
                log.error(f"Error seeking: {str(e)}")
                self.error_occurred.emit(f"Error seeking: {str(e)}")

    def cleanup(self):
        """
        Clean up resources used by the playback worker.
        """
        try:
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
                
            if self.pyaudio:
                self.pyaudio.terminate()
                self.pyaudio = None
                
            if self.audio_stream:
                self.audio_stream.close()
                self.audio_stream = None
                
        except Exception as e:
            log.error(f"Error during cleanup: {str(e)}")