"""
Concrete implementation of AbstractAudioStream using the miniaudio library.

This module provides the MiniaudioStream class, which uses miniaudio
to read and seek within audio files.
"""

import os
import miniaudio
from .base import AudioStreamBase


# Mapping of file extensions to miniaudio info functions for memory-based loading
_EXTENSION_INFO_FUNCTIONS = {
    '.mp3': miniaudio.mp3_get_info,
    '.wav': miniaudio.wav_get_info,
    '.flac': miniaudio.flac_get_info,
    '.ogg': miniaudio.vorbis_get_info,
}


class MiniaudioStream(AudioStreamBase):
    """
    Concrete implementation of AbstractAudioStream using the miniaudio library.

    This class uses miniaudio.stream_file() to open an audio file and provides
    methods to read, seek, and close the stream, as well as properties to
    access audio format information.

    When file-based loading fails (e.g., due to special characters in the
    filename on Windows), it falls back to memory-based loading using Python's
    file I/O which correctly handles Unicode paths on all platforms.
    """

    def __init__(self, file_path: str):
        """
        Initializes the MiniaudioStream with a file path.

        Args:
            file_path: The path to the audio file to stream.
        """
        self.file_path = file_path
        self._is_closed = False
        self._buffer = bytearray()  # Buffer for handling variable frame requests
        self._memory_mode = False  # Whether we're using memory-based streaming
        self._file_data: bytes | None = None  # File data for memory-based streaming
        self._seek_frame_offset = 0  # Current seek position for memory mode

        try:
            # Try file-based loading first (efficient for ASCII paths)
            self.info = miniaudio.get_file_info(file_path)
            self.stream_generator = miniaudio.stream_file(self.file_path)
        except miniaudio.DecodeError:
            # Fall back to memory-based loading for Unicode path issues
            self._init_memory_mode()

    def _init_memory_mode(self) -> None:
        """
        Initializes memory-based streaming by reading the file using Python's I/O.

        This method is used as a fallback when file-based loading fails, typically
        due to special characters in the filename on Windows. Python's file I/O
        correctly handles Unicode paths on all platforms.
        """
        self._memory_mode = True

        # Read file using Python's I/O (handles Unicode paths correctly)
        with open(self.file_path, 'rb') as f:
            self._file_data = f.read()

        # Determine file format from extension
        ext = os.path.splitext(self.file_path)[1].lower()
        info_func = _EXTENSION_INFO_FUNCTIONS.get(ext)

        if info_func is None:
            raise miniaudio.DecodeError(
                f"Unsupported audio format for memory-based loading: {ext}"
            )

        # Get file info from memory data
        self.info = info_func(self._file_data)

        # Create memory-based stream with native format
        self._create_memory_stream()

    def _create_memory_stream(self, seek_frame: int = 0) -> None:
        """
        Creates a memory-based stream generator.

        Args:
            seek_frame: The frame offset to start streaming from.
        """
        self._seek_frame_offset = seek_frame
        self.stream_generator = miniaudio.stream_memory(
            self._file_data,
            output_format=self.info.sample_format,
            nchannels=self.info.nchannels,
            sample_rate=self.info.sample_rate,
        )

        # Reset generator state
        if hasattr(self, '_generator_primed'):
            delattr(self, '_generator_primed')
        self._buffer.clear()

        # Skip frames to reach seek position
        if seek_frame > 0:
            self._skip_frames(seek_frame)

    def _skip_frames(self, n_frames: int) -> None:
        """
        Skips a specified number of frames in the stream.

        Used for seeking in memory mode since stream_memory doesn't support seek_frame.

        Args:
            n_frames: Number of frames to skip.
        """
        bytes_per_frame = self.info.nchannels * self.info.sample_width
        bytes_to_skip = n_frames * bytes_per_frame
        bytes_skipped = 0

        try:
            while bytes_skipped < bytes_to_skip:
                if not hasattr(self, '_generator_primed'):
                    chunk = self.stream_generator.send(None)
                    self._generator_primed = True
                else:
                    # Request frames in chunks
                    frames_remaining = (bytes_to_skip - bytes_skipped) // bytes_per_frame
                    chunk = self.stream_generator.send(min(frames_remaining, 4096))

                if chunk is None or len(chunk) == 0:
                    break
                bytes_skipped += len(chunk) * chunk.itemsize
        except StopIteration:
            pass  # Reached end of stream while seeking

    def read(self, n_frames: int) -> bytes:
        """
        Reads a specified number of audio frames from the miniaudio stream.

        Args:
            n_frames: The number of frames to read.

        Returns:
            A bytes object containing the audio data for the read frames.
            If the end of the stream is reached, an empty bytes object is returned.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")

        try:
            bytes_per_frame = self.info.nchannels * self.info.sample_width
            bytes_needed = n_frames * bytes_per_frame

            # Use buffered data first
            while len(self._buffer) < bytes_needed:
                # Need more data - request from generator
                if not hasattr(self, '_generator_primed'):
                    # Prime generator on first call
                    chunk = self.stream_generator.send(None)
                    self._generator_primed = True
                else:
                    # Request specific number of frames
                    chunk = self.stream_generator.send(n_frames)

                if chunk is None or len(chunk) == 0:
                    break
                self._buffer.extend(chunk.tobytes())

            # Return requested amount from buffer
            if len(self._buffer) == 0:
                return b""

            result = bytes(self._buffer[:bytes_needed])
            self._buffer = self._buffer[bytes_needed:]
            return result

        except StopIteration:
            # End of stream - return any remaining buffered data
            if len(self._buffer) > 0:
                result = bytes(self._buffer)
                self._buffer.clear()
                return result
            return b""

    def seek(self, frame_offset: int) -> None:
        """
        Seeks to a specific frame in the audio stream using miniaudio's seek.

        Args:
            frame_offset: The frame offset to seek to. 0 represents the
                          beginning of the stream.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")

        if self._memory_mode:
            # Memory mode: recreate stream and skip frames
            self._create_memory_stream(seek_frame=frame_offset)
        else:
            # File mode: use miniaudio's native seek
            self.stream_generator = miniaudio.stream_file(
                self.file_path, seek_frame=frame_offset
            )
            # Reset the generator priming flag and buffer since we have a new generator
            if hasattr(self, '_generator_primed'):
                delattr(self, '_generator_primed')
            self._buffer.clear()


    def close(self) -> None:
        """
        Closes the audio stream and releases any associated resources.
        """
        if not self._is_closed:
            # The miniaudio stream generator doesn't have an explicit close method
            # in the same way a file object does. It's cleaned up by garbage collection.
            # We can mark it as closed and set references to None.
            self.stream_generator = None
            self.info = None
            self._file_data = None  # Release memory buffer if in memory mode
            self._is_closed = True

    @property
    def sample_rate(self) -> int:
        """
        The sample rate of the audio stream in Hz (samples per second).
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return self.info.sample_rate

    @property
    def channels_qty(self) -> int:
        """
        The number of audio channels (e.g., 1 for mono, 2 for stereo).
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        # Note: info.nchannels is from miniaudio library (we don't control that naming)
        return self.info.nchannels

    @property
    def sample_width(self) -> int:
        """
        The width of each sample in bytes.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return self.info.sample_width

    @property
    def duration_seconds(self) -> float:
        """
        The total duration of the audio file in seconds.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return float(self.info.num_frames) / self.info.sample_rate

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context related to this object and close the stream."""
        self.close()