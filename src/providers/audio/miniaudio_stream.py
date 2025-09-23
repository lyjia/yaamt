"""
Concrete implementation of AbstractAudioStream using the miniaudio library.

This module provides the MiniaudioStream class, which uses miniaudio
to read and seek within audio files.
"""

import miniaudio
from .base import AbstractAudioStream


class MiniaudioStream(AbstractAudioStream):
    """
    Concrete implementation of AbstractAudioStream using the miniaudio library.

    This class uses miniaudio.stream_file() to open an audio file and provides
    methods to read, seek, and close the stream, as well as properties to
    access audio format information.
    """

    def __init__(self, file_path: str):
        """
        Initializes the MiniaudioStream with a file path.

        Args:
            file_path: The path to the audio file to stream.
        """
        self.file_path = file_path
        # miniaudio.stream_file returns a generator and a decoder
        self.stream_generator, self.decoder = miniaudio.stream_file(self.file_path)
        self._is_closed = False

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
        
        # The stream generator yields chunks of pcm data.
        # We need to read until we have enough frames or the stream ends.
        frames_to_read_bytes = n_frames * self.nchannels * self.sample_width
        audio_data = b""
        remaining_bytes = frames_to_read_bytes
        
        for chunk in self.stream_generator:
            audio_data += chunk
            remaining_bytes -= len(chunk)
            if remaining_bytes <= 0:
                break
        
        # If we've read all frames or the stream ended, return what we have.
        # The generator will be exhausted if the stream ended.
        return audio_data

    def seek(self, frame_offset: int) -> None:
        """
        Seeks to a specific frame in the audio stream using miniaudio's seek.

        Args:
            frame_offset: The frame offset to seek to. 0 represents the
                          beginning of the stream.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        
        # miniaudio's seek is sample-based, not frame-based.
        # A frame contains one sample per channel.
        # So, frame_offset * nchannels gives the sample offset.
        sample_offset = frame_offset * self.nchannels
        self.decoder.seek(sample_offset)
        # After seeking, the old generator is exhausted.
        # We need to create a new one to continue reading from the new position.
        # This is a bit of a workaround due to how miniaudio.stream_file works.
        # A more direct access to the stream's seek and read would be better,
        # but this aligns with how the generator is typically used.
        self.stream_generator, _ = miniaudio.stream_file(self.file_path, seek_frame=sample_offset // self.nchannels)


    def close(self) -> None:
        """
        Closes the audio stream and releases any associated resources.
        """
        if not self._is_closed:
            # The miniaudio stream generator doesn't have an explicit close method
            # in the same way a file object does. It's cleaned up by garbage collection.
            # We can mark it as closed and set references to None.
            self.stream_generator = None
            self.decoder = None
            self._is_closed = True

    @property
    def samplerate(self) -> int:
        """
        The sample rate of the audio stream in Hz (samples per second).
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return self.decoder.output_format.sample_rate

    @property
    def nchannels(self) -> int:
        """
        The number of audio channels (e.g., 1 for mono, 2 for stereo).
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        return self.decoder.output_format.num_channels

    @property
    def sample_width(self) -> int:
        """
        The width of each sample in bytes.
        """
        if self._is_closed:
            raise ValueError("Stream is closed.")
        # miniaudio's sample_width is in bits, so we divide by 8.
        return self.decoder.output_format.bits_per_sample // 8

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context related to this object and close the stream."""
        self.close()