"""
Concrete implementation of AbstractAudioStream using the miniaudio library.

This module provides the MiniaudioStream class, which uses miniaudio
to read and seek within audio files.
"""

import miniaudio
from .base import AudioStreamBase

# Maps the source file's native sample_format (from get_file_info) to a
# (streamable_output_format, reported_sample_width_bytes) pair. SIGNED24 is
# not streamable by miniaudio, and we never stream as SIGNED32, so int sources
# wider than 16 bits are promoted to FLOAT32. This keeps the codebase-wide
# "width 4 == float" heuristic valid.
_SOURCE_FORMAT_TO_STREAM = {
    miniaudio.SampleFormat.UNSIGNED8: (miniaudio.SampleFormat.SIGNED16, 2),
    miniaudio.SampleFormat.SIGNED16:  (miniaudio.SampleFormat.SIGNED16, 2),
    miniaudio.SampleFormat.SIGNED24:  (miniaudio.SampleFormat.FLOAT32,  4),
    miniaudio.SampleFormat.SIGNED32:  (miniaudio.SampleFormat.FLOAT32,  4),
    miniaudio.SampleFormat.FLOAT32:   (miniaudio.SampleFormat.FLOAT32,  4),
}


class MiniaudioStream(AudioStreamBase):
    """
    Concrete implementation of AbstractAudioStream using the miniaudio library.

    This class uses miniaudio.stream_file() to open an audio file and provides
    methods to read, seek, and close the stream, as well as properties to
    access audio format information.
    """

    def __init__(self, file_path: str):
        """
        Initializes the MiniaudioStream with a file path.

        The stream decodes at the source file's native sample rate and channel
        count. The sample format is mapped to a streamable output format that
        preserves the codebase-wide "width 4 == float" heuristic — see
        _SOURCE_FORMAT_TO_STREAM for the mapping.

        Args:
            file_path: The path to the audio file to stream.

        Raises:
            ValueError: If the source file's sample format is not supported.
        """
        self.file_path = file_path
        self.info = miniaudio.get_file_info(file_path)

        # Determine streamable output format from source's native format
        mapping = _SOURCE_FORMAT_TO_STREAM.get(self.info.sample_format)
        if mapping is None:
            raise ValueError(
                f"Unsupported sample format: {self.info.sample_format} "
                f"in {file_path}"
            )
        self._stream_output_format, self._stream_sample_width = mapping

        self.stream_generator = miniaudio.stream_file(
            self.file_path,
            output_format=self._stream_output_format,
            nchannels=self.info.nchannels,
            sample_rate=self.info.sample_rate,
        )
        self._is_closed = False
        self._buffer = bytearray()  # Buffer for handling variable frame requests

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
            bytes_per_frame = self.channels_qty * self.sample_width
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

        self.stream_generator = miniaudio.stream_file(
            self.file_path,
            output_format=self._stream_output_format,
            nchannels=self.info.nchannels,
            sample_rate=self.info.sample_rate,
            seek_frame=frame_offset,
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
        The width of each sample in bytes, matching the streamed output format.

        This returns the width of the format actually being streamed, which may
        differ from the source file's native width (e.g., 24-bit sources are
        promoted to float32, so sample_width returns 4 instead of 3).
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return self._stream_sample_width

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