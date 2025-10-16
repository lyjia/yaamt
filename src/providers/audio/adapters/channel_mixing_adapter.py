"""
Channel mixing adapter for converting between mono and stereo.

This module provides the ChannelMixingAdapter class, which converts audio
streams between different channel counts (mono and stereo).
"""

import numpy as np
from typing import Dict
from .base import AdapterBase
from ..base import AudioStreamBase


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

        # Determine numpy dtype based on sample width
        self._dtype = self._get_dtype(source.sample_width)

    def _get_dtype(self, sample_width: int) -> np.dtype:
        """
        Get the appropriate numpy dtype for the given sample width.

        Args:
            sample_width: Sample width in bytes

        Returns:
            NumPy dtype for audio data

        Raises:
            ValueError: If sample_width is not supported
        """
        dtype_map: Dict[int, np.dtype] = {
            1: np.dtype('<i1'),   # 8-bit signed int
            2: np.dtype('<i2'),   # 16-bit signed int
            3: np.dtype('<i4'),   # 24-bit (stored as 32-bit int)
            4: np.dtype('<f4'),   # 32-bit float
        }

        if sample_width not in dtype_map:
            raise ValueError(
                f"Unsupported sample width: {sample_width} bytes"
            )

        return dtype_map[sample_width]

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

        # Convert bytes to numpy array
        audio_array = np.frombuffer(source_data, dtype=self._dtype)

        # Handle 24-bit audio specially (stored as 32-bit but only using 24 bits)
        if self._source.sample_width == 3:
            # Convert 24-bit data (in bytes) to proper int32 values
            # This is needed because 24-bit audio is typically stored as 3 bytes
            # but we need to work with proper int32 for calculations
            audio_bytes = np.frombuffer(source_data, dtype=np.uint8)
            audio_array = np.zeros(len(source_data) // 3, dtype=np.int32)

            for i in range(len(audio_array)):
                # Extract 3 bytes and convert to signed int32
                byte_offset = i * 3
                val = int(audio_bytes[byte_offset]) | \
                      (int(audio_bytes[byte_offset + 1]) << 8) | \
                      (int(audio_bytes[byte_offset + 2]) << 16)

                # Sign extend if negative (bit 23 is set)
                if val & 0x800000:
                    val = val - 0x1000000  # Convert to negative by subtracting 2^24

                audio_array[i] = val

        # Reshape to (n_frames, n_channels)
        audio_array = audio_array.reshape(-1, self._source.channels_qty)

        # Apply channel conversion
        if self._target_channels == 1:
            # Stereo to mono: average channels with 1/√2 scaling
            converted = audio_array.mean(axis=1) / np.sqrt(2)
        else:
            # Mono to stereo: duplicate channel
            converted = np.repeat(audio_array, 2, axis=1)

        # Convert back to appropriate dtype if needed
        if self._source.sample_width == 3:
            # Convert int32 back to 24-bit bytes
            converted = converted.astype(np.int32)
            output_bytes = bytearray()

            for val in converted.flat:
                # Clamp to 24-bit range
                val = np.clip(val, -8388608, 8388607)
                # Write as 3 bytes (little-endian)
                output_bytes.extend([
                    val & 0xFF,
                    (val >> 8) & 0xFF,
                    (val >> 16) & 0xFF
                ])

            return bytes(output_bytes)
        else:
            # For other formats, convert back to original dtype
            converted = converted.astype(self._dtype)
            return converted.tobytes()

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
