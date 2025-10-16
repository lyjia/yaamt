"""
Base class for audio stream adapters.

This module provides the AdapterBase class, which implements the decorator
pattern to wrap AudioStreamBase instances and transform their output.
"""

from abc import abstractmethod
from typing import Optional
from ..base import AudioStreamBase


class AdapterBase(AudioStreamBase):
    """
    Abstract base class for audio stream adapters.

    Implements the decorator pattern to wrap an existing AudioStreamBase and
    transform its output. All adapters must inherit from this class and
    implement the abstract read() method.

    The adapter maintains the AudioStreamBase interface, allowing adapters
    to be chained together transparently.

    Attributes:
        _source: The wrapped AudioStreamBase instance
        _closed: Whether this adapter has been closed
    """

    def __init__(self, source: AudioStreamBase):
        """
        Initialize the adapter with a source stream.

        Args:
            source: The AudioStreamBase instance to wrap and adapt
        """
        super().__init__()
        self._source = source
        self._closed = False

    @abstractmethod
    def read(self, n_frames: int) -> bytes:
        """
        Read audio data from the source and apply adaptation.

        This method must be implemented by subclasses to perform the actual
        format conversion.

        Args:
            n_frames: Number of frames to read in the ADAPTED format

        Returns:
            Audio data in the adapted format as bytes

        Raises:
            ValueError: If the adapter is closed
        """
        pass

    def seek(self, frame_offset: int) -> None:
        """
        Seek to a specific frame position.

        The default implementation raises NotImplementedError. Subclasses
        should override this if they support seeking, translating the adapted
        frame position to the source frame position as needed.

        Args:
            frame_offset: Frame position in the ADAPTED format

        Raises:
            NotImplementedError: If seeking is not supported by this adapter
            ValueError: If the adapter is closed
        """
        if self._closed:
            raise ValueError("Cannot seek on closed adapter")

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support seeking"
        )

    def close(self) -> None:
        """
        Close this adapter and the wrapped source stream.

        This method ensures that all resources are properly released,
        including the source stream.
        """
        if not self._closed:
            self._closed = True
            self._source.close()

    @property
    def sample_rate(self) -> int:
        """
        Get the sample rate of the adapted stream.

        Default implementation returns the source sample rate. Subclasses
        that modify sample rate should override this.

        Returns:
            Sample rate in Hz
        """
        return self._source.sample_rate

    @property
    def channels_qty(self) -> int:
        """
        Get the number of channels in the adapted stream.

        Default implementation returns the source channel count. Subclasses
        that modify channels should override this.

        Returns:
            Number of channels
        """
        return self._source.channels_qty

    @property
    def sample_width(self) -> int:
        """
        Get the sample width of the adapted stream.

        Default implementation returns the source sample width. Subclasses
        that modify sample width should override this.

        Returns:
            Sample width in bytes
        """
        return self._source.sample_width

    @property
    def duration_seconds(self) -> float:
        """
        Get the duration of the audio stream in seconds.

        Default implementation returns the source duration. Most adapters
        don't change duration, but subclasses can override if needed.

        Returns:
            Duration in seconds
        """
        return self._source.duration_seconds

    def __enter__(self) -> 'AdapterBase':
        """
        Enter the context manager.

        Returns:
            This adapter instance
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the context manager and close the adapter.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        self.close()

    def _check_closed(self) -> None:
        """
        Check if the adapter is closed and raise an error if so.

        Raises:
            ValueError: If the adapter is closed
        """
        if self._closed:
            raise ValueError(f"{self.__class__.__name__} is closed")
