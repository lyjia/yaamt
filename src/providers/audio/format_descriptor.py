"""
Audio format descriptor for specifying desired audio stream format.

This module provides the AudioFormatDescriptor class, which describes the
desired audio format parameters for stream adaptation.
"""

from typing import Optional, Literal


class AudioFormatDescriptor:
    """
    Describes desired audio format parameters for stream adaptation.

    None values indicate "accept native format" for that parameter.
    This allows consumers to specify only the parameters they care about
    while accepting the source file's native format for others.

    Attributes:
        sample_rate: Desired sample rate in Hz (None = accept native)
        channels: Desired number of channels (None = accept native)
        sample_width: Desired sample width in bytes (None = accept native)
        sample_format: 'int' or 'float' (None = accept native)
    """

    def __init__(
        self,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        sample_width: Optional[int] = None,
        sample_format: Optional[Literal['int', 'float']] = None
    ):
        """
        Initialize an AudioFormatDescriptor.

        Args:
            sample_rate: Desired sample rate in Hz, or None to accept native
            channels: Desired number of channels, or None to accept native
            sample_width: Desired sample width in bytes, or None to accept native
            sample_format: 'int' or 'float', or None to accept native
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.sample_format = sample_format

    def matches(self, other: 'AudioFormatDescriptor') -> bool:
        """
        Check if this descriptor matches another descriptor.

        None values in either descriptor are treated as wildcards that match
        any value. Two descriptors match if all their specified (non-None)
        values are equal.

        Args:
            other: The other AudioFormatDescriptor to compare against

        Returns:
            True if the descriptors match, False otherwise

        Examples:
            >>> desc1 = AudioFormatDescriptor(sample_rate=44100, channels=1)
            >>> desc2 = AudioFormatDescriptor(sample_rate=44100)
            >>> desc1.matches(desc2)  # True - desc2's channels=None is wildcard
            True

            >>> desc3 = AudioFormatDescriptor(sample_rate=48000, channels=1)
            >>> desc1.matches(desc3)  # False - different sample rates
            False
        """
        # Check each parameter - None acts as wildcard
        if self.sample_rate is not None and other.sample_rate is not None:
            if self.sample_rate != other.sample_rate:
                return False

        if self.channels is not None and other.channels is not None:
            if self.channels != other.channels:
                return False

        if self.sample_width is not None and other.sample_width is not None:
            if self.sample_width != other.sample_width:
                return False

        if self.sample_format is not None and other.sample_format is not None:
            if self.sample_format != other.sample_format:
                return False

        return True

    def __repr__(self) -> str:
        """
        Return a human-readable string representation of this descriptor.

        Returns:
            A string describing the format parameters
        """
        parts = []

        if self.sample_rate is not None:
            parts.append(f"{self.sample_rate}Hz")

        if self.channels is not None:
            channel_desc = "mono" if self.channels == 1 else f"{self.channels}ch"
            parts.append(channel_desc)

        if self.sample_width is not None:
            parts.append(f"{self.sample_width * 8}bit")

        if self.sample_format is not None:
            parts.append(self.sample_format)

        if not parts:
            return "AudioFormatDescriptor(native)"

        return f"AudioFormatDescriptor({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        """
        Check exact equality between two descriptors.

        Unlike matches(), this checks for exact equality including None values.

        Args:
            other: The other object to compare against

        Returns:
            True if all attributes are exactly equal, False otherwise
        """
        if not isinstance(other, AudioFormatDescriptor):
            return False

        return (
            self.sample_rate == other.sample_rate
            and self.channels == other.channels
            and self.sample_width == other.sample_width
            and self.sample_format == other.sample_format
        )
