"""
Abstract base class for audio streams.

This module defines the AbstractAudioStream class, which provides a common
interface for reading and seeking within audio files, regardless of their
underlying format.
"""

from abc import ABC, abstractmethod


class AbstractAudioStream(ABC):
    """
    Abstract base class for audio streams.

    This class defines the interface that all audio stream implementations must
    adhere to. It provides methods for reading audio data, seeking within the
    stream, and closing the stream, as well as properties for accessing
    audio format information.
    """

    @abstractmethod
    def read(self, n_frames: int) -> bytes:
        """
        Reads a specified number of audio frames.

        Args:
            n_frames: The number of frames to read.

        Returns:
            A bytes object containing the audio data for the read frames.
            The number of bytes returned will be n_frames * nchannels * sample_width.
            If the end of the stream is reached, an empty bytes object is returned.
        """
        pass

    @abstractmethod
    def seek(self, frame_offset: int) -> None:
        """
        Seeks to a specific frame in the audio stream.

        Args:
            frame_offset: The frame offset to seek to. 0 represents the
                          beginning of the stream.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Closes the audio stream and releases any associated resources.

        This method should be called when the stream is no longer needed.
        """
        pass

    @property
    @abstractmethod
    def samplerate(self) -> int:
        """
        The sample rate of the audio stream in Hz (samples per second).

        Returns:
            An integer representing the sample rate.
        """
        pass

    @property
    @abstractmethod
    def nchannels(self) -> int:
        """
        The number of audio channels (e.g., 1 for mono, 2 for stereo).

        Returns:
            An integer representing the number of channels.
        """
        pass

    @property
    @abstractmethod
    def sample_width(self) -> int:
        """
        The width of each sample in bytes.

        For example, 2 for 16-bit audio, 4 for 32-bit audio.

        Returns:
            An integer representing the sample width in bytes.
        """
        pass