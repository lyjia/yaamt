import os
import threading

import miniaudio
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from typing import Optional, Generator

from models.media_file import MediaFile
from models.settings import settings
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.const import (
    SETTINGS_DEBUG_PLAYBACK_ADAPTATION, SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE,
    SETTINGS_DEBUG_PLAYBACK_CHANNELS, SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH,
    SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT,
)
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
    file_released = Signal()               # emitted after file lock released for writing

    def __init__(self):
        super().__init__()
        self.state = STOPPED
        self.audio_stream = None
        self.playback_device = None
        self.current_file = None
        self.duration = 0.0
        self.total_frames_read = 0
        self.chunk_size = 1024
        self._playback_finished_flag = False

        # State for release/reacquire coordination during file writes
        self._release_saved_position: float = 0.0
        self._release_was_playing: bool = False
        self._release_file_path: str | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_position)

    def _get_format_descriptor(self) -> Optional[AudioFormatDescriptor]:
        """
        Get the format descriptor from settings for audio playback adaptation.

        Returns:
            AudioFormatDescriptor if format adaptation is enabled, None otherwise
        """
        # Check if format adaptation is enabled in settings
        enabled = settings.value(SETTINGS_DEBUG_PLAYBACK_ADAPTATION, False, type=bool)
        if not enabled:
            return None

        # Read format settings from QSettings
        sample_rate = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE, None, type=int)
        channels = settings.value(SETTINGS_DEBUG_PLAYBACK_CHANNELS, None, type=int)
        sample_width = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH, None, type=int)
        sample_format = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT, None, type=str)

        # Convert empty strings or 0 to None
        if sample_rate == 0:
            sample_rate = None
        if channels == 0:
            channels = None
        if sample_width == 0:
            sample_width = None
        if not sample_format:
            sample_format = None

        # If all parameters are None, return None (native format)
        if all(v is None for v in [sample_rate, channels, sample_width, sample_format]):
            return None

        return AudioFormatDescriptor(
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            sample_format=sample_format
        )

    def _audio_generator(self) -> Generator[bytes, int, None]:
        """
        Generator function that yields audio data for playback.
        This is called by the miniaudio PlaybackDevice.

        Yields:
            Audio data as bytes.
        """
        try:
            # Prime the generator
            num_frames = yield b""

            while True:
                # Check if we should stop
                if self._playback_finished_flag or self.state == STOPPED:
                    break

                # Wait if paused
                if self.state == PAUSED:
                    num_frames = yield b"\x00" * (num_frames * self.audio_stream.sample_width * self.audio_stream.channels_qty)
                    continue

                # Read audio data
                data = self.audio_stream.read(num_frames)

                if not data:
                    # End of stream
                    self._playback_finished_flag = True
                    self.playback_finished.emit()
                    break

                # Track position
                frames_read = len(data) // (self.audio_stream.sample_width * self.audio_stream.channels_qty)
                self.total_frames_read += frames_read

                # Yield the audio data and get next frame count request
                num_frames = yield data

        except Exception as e:
            log.error(f"Error in audio generator: {str(e)}")
            self.error_occurred.emit(f"Error during playback: {str(e)}")

    def _update_position(self):
        """
        Timer callback to emit position updates during playback.
        """
        if self.state == PLAYING and self.audio_stream:
            current_position = self.total_frames_read / self.audio_stream.sample_rate
            self.position_changed.emit(current_position)

    @Slot(object)
    def start_playback(self, media_file: MediaFile, start_position: float = 0.0):
        """
        Start playback of the specified audio file.

        Args:
            media_file: MediaFile instance to play.
            start_position: Position in seconds to begin playback from (default 0.0).
        """
        try:
            if self.state != STOPPED:
                self.stop()

            self.current_file = media_file.file_path
            log.info(f"Starting playback of {media_file.file_path}")

            # Get format descriptor from settings
            format_descriptor = self._get_format_descriptor()
            if format_descriptor:
                log.info(f"Using format adaptation for playback: {format_descriptor}")

            # Get audio stream with optional format adaptation
            self.audio_stream = media_file.get_audio_stream(format_descriptor)

            # Map stream width to miniaudio SampleFormat for the PlaybackDevice.
            # Width 4 is ambiguous (int32 vs float32). When the debug format
            # descriptor explicitly requests int at width 4, honour that;
            # otherwise default to FLOAT32 (the MiniaudioStream invariant).
            stream_width = self.audio_stream.sample_width
            if stream_width == 1:
                sample_format = miniaudio.SampleFormat.UNSIGNED8
            elif stream_width == 2:
                sample_format = miniaudio.SampleFormat.SIGNED16
            elif stream_width == 3:
                sample_format = miniaudio.SampleFormat.SIGNED24
            elif stream_width == 4:
                if (format_descriptor
                        and format_descriptor.sample_format == 'int'):
                    sample_format = miniaudio.SampleFormat.SIGNED32
                else:
                    sample_format = miniaudio.SampleFormat.FLOAT32
            else:
                raise ValueError(f"Unsupported sample width: {stream_width}")

            self.duration = self.audio_stream.duration_seconds
            self.total_frames_read = 0
            self._playback_finished_flag = False

            # Seek the stream before creating the device so playback starts
            # at the requested position without briefly playing from the beginning.
            if start_position > 0:
                frame_offset = int(start_position * self.audio_stream.sample_rate)
                self.audio_stream.seek(frame_offset)
                self.total_frames_read = frame_offset

            # Create playback device
            self.playback_device = miniaudio.PlaybackDevice(
                output_format=sample_format,
                nchannels=self.audio_stream.channels_qty,
                sample_rate=self.audio_stream.sample_rate
            )

            # Set state to PLAYING before starting the device so the audio generator
            # does not see STOPPED and exit immediately on its first callback.
            self.state = PLAYING

            # Create and prime the generator before starting playback
            generator = self._audio_generator()
            next(generator)  # Prime the generator
            self.playback_device.start(generator)

            # Set up position update timer (update every 50ms)
            self.timer.setInterval(50)
            self.timer.start()

            self.playback_started.emit(self.current_file, self.duration)

        except Exception as e:
            log.error(f"Error starting playback: {str(e)}")
            self.state = STOPPED
            self.error_occurred.emit(f"Error starting playback: {str(e)}")
            self.cleanup()

    @Slot()
    def pause(self):
        """
        Pause the current playback.
        """
        if self.state == PLAYING:
            self.state = PAUSED
            # The generator will output silence when paused
            self.playback_paused.emit(self.current_file, self.duration)

    @Slot()
    def resume(self):
        """
        Resume paused playback.
        """
        if self.state == PAUSED:
            self.state = PLAYING
            # The generator will resume outputting audio data
            self.playback_resumed.emit(self.current_file, self.duration)

    @Slot()
    def stop(self):
        """
        Stop the current playback and clean up resources.
        """
        if self.state != STOPPED:
            self.state = STOPPED
            self._release_file_path = None  # Cancel any pending reacquire
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
                frame_offset = int(position_seconds * self.audio_stream.sample_rate)
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
            if self.playback_device:
                self.playback_device.close()
                self.playback_device = None

            if self.audio_stream:
                self.audio_stream.close()
                self.audio_stream = None

        except Exception as e:
            log.error(f"Error during cleanup: {str(e)}")

    @Slot(str, object)
    def release_for_write(self, file_path: str, event: threading.Event) -> None:
        """
        Temporarily release the currently playing file so it can be written to.
        Called via signal from PlaybackCoordinator (executes on the playback thread).

        Args:
            file_path: The file path that needs to be released.
            event: A threading.Event to set once the file is released, unblocking the save thread.
        """
        normalized_request = os.path.normcase(os.path.abspath(file_path))
        normalized_current = (
            os.path.normcase(os.path.abspath(self.current_file))
            if self.current_file else None
        )

        if normalized_current != normalized_request:
            event.set()
            return

        log.info(f"Releasing file for write: {file_path}")

        # Save playback state for later reacquire
        self._release_was_playing = (self.state == PLAYING)
        self._release_saved_position = (
            self.total_frames_read / self.audio_stream.sample_rate
            if self.audio_stream and self.audio_stream.sample_rate
            else 0.0
        )
        self._release_file_path = self.current_file

        # Release the file: stop timer, close device and stream
        self.timer.stop()
        self.state = STOPPED
        self.cleanup()

        log.debug(f"File released (was_playing={self._release_was_playing}, "
                   f"position={self._release_saved_position:.2f}s)")

        self.file_released.emit()
        event.set()

    @Slot()
    def reacquire_after_write(self) -> None:
        """
        Reopen and resume playback of a file that was temporarily released for writing.
        Called via signal from PlaybackCoordinator (executes on the playback thread).
        """
        if self._release_file_path is None:
            return  # Nothing to reacquire (user stopped playback during save)

        file_path = self._release_file_path
        saved_position = self._release_saved_position
        was_playing = self._release_was_playing

        # Clear release state before reacquiring
        self._release_file_path = None
        self._release_saved_position = 0.0
        self._release_was_playing = False

        log.info(f"Reacquiring file after write: {file_path} at position {saved_position:.2f}s")

        media_file = MediaFile(file_path)
        self.start_playback(media_file, start_position=saved_position)

        if not was_playing:
            self.pause()