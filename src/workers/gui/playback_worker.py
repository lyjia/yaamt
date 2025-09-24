import pyaudio
from PySide6.QtCore import QObject, Signal, Slot

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
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = STOPPED
        self.audio_stream = None
        self.pyaudio = None
        self.output_stream = None
        self.current_file = None
        self.duration = 0.0

    @Slot(str)
    def start_playback(self, filepath: str):
        """
        Start playback of the specified audio file.
        
        Args:
            filepath: Path to the audio file to play.
        """
        try:
            # Stop any current playback
            if self.state != STOPPED:
                self.stop()
            
            self.current_file = filepath
            log.info(f"Starting playback of {filepath}")
            
            # Get audio stream from provider
            self.audio_stream = AudioStreamProvider.get_stream(filepath)
            
            # Initialize PyAudio
            self.pyaudio = pyaudio.PyAudio()
            
            # Open output stream
            self.output_stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(self.audio_stream.sample_width),
                channels=self.audio_stream.nchannels,
                rate=self.audio_stream.samplerate,
                output=True
            )
            
            # Calculate duration (approximate)
            # This is a rough estimate since we don't have the exact duration without reading the entire file
            self.duration = 0.0  # Will be updated as we play
            
            # Set state to playing
            self.state = PLAYING
            
            # Emit signal that playback has started
            self.playback_started.emit(filepath, self.duration)
            
            # Start the playback loop
            self._playback_loop()
            
        except Exception as e:
            log.error(f"Error starting playback: {str(e)}")
            self.error_occurred.emit(f"Error starting playback: {str(e)}")
            self.cleanup()

    def _playback_loop(self):
        """
        The main playback loop that reads from the audio stream and writes to the output device.
        """
        chunk_size = 1024
        total_frames_read = 0
        
        try:
            while self.state == PLAYING:
                # Read a chunk of data
                data = self.audio_stream.read(chunk_size)
                
                if not data:
                    # End of file
                    self.playback_finished.emit()
                    self.stop()
                    break
                
                # Write to output stream
                self.output_stream.write(data)
                
                # Update position
                frames_read = len(data) / (self.audio_stream.sample_width * self.audio_stream.nchannels)
                total_frames_read += frames_read
                current_position = total_frames_read / self.audio_stream.samplerate
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
            if self.output_stream:
                self.output_stream.stop_stream()

    @Slot()
    def resume(self):
        """
        Resume paused playback.
        """
        if self.state == PAUSED:
            self.state = PLAYING
            if self.output_stream:
                self.output_stream.start_stream()
            self._playback_loop()

    @Slot()
    def stop(self):
        """
        Stop the current playback and clean up resources.
        """
        if self.state != STOPPED:
            self.state = STOPPED
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
                # Convert seconds to frames
                frame_offset = int(position_seconds * self.audio_stream.samplerate)
                self.audio_stream.seek(frame_offset)
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