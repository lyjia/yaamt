"""
Concrete implementation of AbstractAudioStream using the miniaudio library.

This module provides the MiniaudioStream class, which uses miniaudio
to read and seek within audio files.
"""

import os
import sys
import miniaudio
from .base import AudioStreamBase
from util.logging import log

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

# Mapping of file extensions to miniaudio info functions for memory-based loading
_EXTENSION_INFO_FUNCTIONS = {
    '.mp3': miniaudio.mp3_get_info,
    '.wav': miniaudio.wav_get_info,
    '.flac': miniaudio.flac_get_info,
    '.ogg': miniaudio.vorbis_get_info,
}


def _resolve_path_for_c(file_path: str) -> str:
    """
    Returns a path that miniaudio's C backend can open.

    On Windows, miniaudio passes paths to C's fopen(), which uses the ANSI
    codepage and cannot handle Unicode characters. This function converts to
    the 8.3 short path form (pure ASCII) when available, which sidesteps the
    encoding issue entirely without any memory overhead.

    On other platforms the path is returned unchanged (fopen handles UTF-8).
    """
    if sys.platform != 'win32':
        return file_path
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        result = ctypes.windll.kernel32.GetShortPathNameW(file_path, buf, 32768)
        if result > 0:
            return buf.value
    except (OSError, AttributeError):
        pass
    return file_path


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

        On Windows, if file-based loading fails (e.g., Unicode characters in
        the path that C's fopen cannot handle), the constructor tries the 8.3
        short path. If that also fails, it falls back to memory-based loading.

        Args:
            file_path: The path to the audio file to stream.

        Raises:
            ValueError: If the source file's sample format is not supported.
        """
        self.file_path = file_path
        self._is_closed = False
        self._buffer = bytearray()
        self._memory_mode = False
        self._file_data: bytes | None = None

        try:
            self._init_file_mode(file_path)
        except miniaudio.DecodeError:
            # On Windows, try the 8.3 short path before falling back to memory
            safe_path = _resolve_path_for_c(file_path)
            if safe_path != file_path:
                try:
                    self._init_file_mode(safe_path)
                    log.info("Opened '%s' via 8.3 short path", file_path)
                    return
                except miniaudio.DecodeError:
                    pass
            # Last resort: load entire file into memory
            self._init_memory_mode()

    def _init_file_mode(self, path: str) -> None:
        """Initializes file-based streaming via miniaudio.stream_file()."""
        self.info = miniaudio.get_file_info(path)
        self._stream_output_format, self._stream_sample_width = (
            self._resolve_format(self.info.sample_format)
        )
        self.stream_generator = miniaudio.stream_file(
            path,
            output_format=self._stream_output_format,
            nchannels=self.info.nchannels,
            sample_rate=self.info.sample_rate,
        )
        # Store the resolved path so seek() can reopen the file
        self._resolved_path = path

    def _init_memory_mode(self) -> None:
        """
        Initializes memory-based streaming by reading the file via Python's I/O.

        This is a last-resort fallback when file-based loading fails (typically
        due to Unicode path issues on Windows where 8.3 short names are also
        unavailable). Python's open() uses wide Win32 APIs that handle Unicode
        paths correctly.
        """
        self._memory_mode = True
        log.info("Loading '%s' into memory (Unicode path fallback)", self.file_path)

        with open(self.file_path, 'rb') as f:
            self._file_data = f.read()

        ext = os.path.splitext(self.file_path)[1].lower()
        info_func = _EXTENSION_INFO_FUNCTIONS.get(ext)
        if info_func is None:
            raise miniaudio.DecodeError(
                f"Unsupported audio format for memory-based loading: {ext}"
            )

        self.info = info_func(self._file_data)
        self._stream_output_format, self._stream_sample_width = (
            self._resolve_format(self.info.sample_format)
        )
        self._create_memory_stream()

    @staticmethod
    def _resolve_format(
        sample_format: miniaudio.SampleFormat,
    ) -> tuple[miniaudio.SampleFormat, int]:
        """Maps a source sample format to a (streamable_format, width_bytes) pair."""
        mapping = _SOURCE_FORMAT_TO_STREAM.get(sample_format)
        if mapping is None:
            raise ValueError(f"Unsupported sample format: {sample_format}")
        return mapping

    def _create_memory_stream(self, seek_frame: int = 0) -> None:
        """Creates (or recreates) a memory-based stream generator."""
        self.stream_generator = miniaudio.stream_memory(
            self._file_data,
            output_format=self._stream_output_format,
            nchannels=self.info.nchannels,
            sample_rate=self.info.sample_rate,
        )
        if hasattr(self, '_generator_primed'):
            delattr(self, '_generator_primed')
        self._buffer.clear()

        if seek_frame > 0:
            self._skip_frames(seek_frame)

    def _skip_frames(self, n_frames: int) -> None:
        """
        Skips frames in the stream for memory-mode seeking.

        stream_memory() does not support seek_frame, so we consume and discard
        frames to reach the target position.
        """
        bytes_per_frame = self.info.nchannels * self._stream_sample_width
        bytes_to_skip = n_frames * bytes_per_frame
        bytes_skipped = 0
        try:
            while bytes_skipped < bytes_to_skip:
                if not hasattr(self, '_generator_primed'):
                    chunk = self.stream_generator.send(None)
                    self._generator_primed = True
                else:
                    frames_remaining = (bytes_to_skip - bytes_skipped) // bytes_per_frame
                    chunk = self.stream_generator.send(min(frames_remaining, 4096))
                if chunk is None or len(chunk) == 0:
                    break
                bytes_skipped += len(chunk) * chunk.itemsize
        except StopIteration:
            pass

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

        if self._memory_mode:
            self._create_memory_stream(seek_frame=frame_offset)
        else:
            self.stream_generator = miniaudio.stream_file(
                self._resolved_path,
                output_format=self._stream_output_format,
                nchannels=self.info.nchannels,
                sample_rate=self.info.sample_rate,
                seek_frame=frame_offset,
            )
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
            self._file_data = None
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