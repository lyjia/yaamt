"""
Channel mixing adapter for converting between mono and stereo.

This module provides the ChannelMixingAdapter class, which converts audio
streams between different channel counts (mono and stereo).
"""

import numpy as np
from .base import AdapterBase
from ..base import AudioStreamBase
from util.audio_numpy import (
    SAMPLE_WIDTH_24BIT,
    bytes_to_int32_24bit, int32_to_bytes_24bit, get_numpy_dtype,
)


class ChannelMixingAdapter(AdapterBase):
    """
    Adapter for converting between mono and stereo audio.

    This adapter wraps an AudioStreamBase and converts the channel count.
    Supports:
    - Stereo to mono: Averages channels with 1/√2 scaling to preserve RMS power
    - Mono to stereo: Duplicates mono channel to both left and right

    The adapter passes seeking through to the source stream since channel
    mixing doesn't affect frame positions.

    Attributes:
        _target_channels: Number of channels in the adapted output
        _dtype: NumPy dtype for audio data based on sample width
    """

    def __init__(self, source: AudioStreamBase, target_channels: int):
        """
        Initialize the ChannelMixingAdapter.

        Args:
            source: The AudioStreamBase instance to wrap
            target_channels: Target number of channels (1 for mono, 2 for stereo)

        Raises:
            ValueError: If target_channels is not 1 or 2
            ValueError: If source channels is not 1 or 2
            ValueError: If source and target channels are the same
        """
        super().__init__(source)

        if target_channels not in (1, 2):
            raise ValueError(
                f"target_channels must be 1 or 2, got {target_channels}"
            )

        if source.channels_qty not in (1, 2):
            raise ValueError(
                f"Source must have 1 or 2 channels, got {source.channels_qty}"
            )

        if source.channels_qty == target_channels:
            raise ValueError(
                f"Source channels ({source.channels_qty}) matches target channels "
                f"({target_channels}). No adaptation needed."
            )

        self._target_channels = target_channels

        # Determine numpy dtype based on sample width. 'auto' follows the
        # convention that 4-byte samples are float32 (see util.audio_numpy).
        self._dtype = get_numpy_dtype(source.sample_width, 'auto')

    def read(self, n_frames: int) -> bytes:
        """
        Read audio data and convert channels.

        Args:
            n_frames: Number of frames to read in the ADAPTED format

        Returns:
            Audio data with target channel count as bytes

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()

        # Read from source
        source_data = self._source.read(n_frames)
        if not source_data:
            return b''

        # Convert bytes to numpy array. 24-bit audio is unpacked from its
        # wire format (3 bytes per sample) into sign-extended int32.
        if self._source.sample_width == SAMPLE_WIDTH_24BIT:
            audio_array = bytes_to_int32_24bit(source_data)
        else:
            audio_array = np.frombuffer(source_data, dtype=self._dtype)

        # Reshape to (n_frames, n_channels)
        audio_array = audio_array.reshape(-1, self._source.channels_qty)

        # Apply channel conversion
        if self._target_channels == 1:
            # Stereo to mono: average channels with 1/√2 scaling
            converted = audio_array.mean(axis=1) / np.sqrt(2)
        else:
            # Mono to stereo: duplicate channel
            converted = np.repeat(audio_array, 2, axis=1)

        # Convert back to appropriate dtype / wire format
        if self._source.sample_width == SAMPLE_WIDTH_24BIT:
            return int32_to_bytes_24bit(converted)
        return converted.astype(self._dtype).tobytes()

    def seek(self, frame_offset: int) -> None:
        """
        Seek to a specific frame position.

        Channel mixing doesn't affect frame positions, so this passes
        through directly to the source stream.

        Args:
            frame_offset: Frame position in the ADAPTED format

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()
        self._source.seek(frame_offset)

    @property
    def channels_qty(self) -> int:
        """
        Get the number of channels in the adapted stream.

        Returns:
            Target number of channels
        """
        return self._target_channels
