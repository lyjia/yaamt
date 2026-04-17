"""
Bit depth adapter for converting between different sample widths and formats.

This module provides the BitDepthAdapter class, which converts audio streams
between different bit depths (16-bit, 24-bit, 32-bit) and formats (int/float).
"""

import numpy as np
from typing import Literal
from .base import AdapterBase
from ..base import AudioStreamBase
from util.audio_numpy import (
    SAMPLE_WIDTH_8BIT, SAMPLE_WIDTH_16BIT, SAMPLE_WIDTH_24BIT, SAMPLE_WIDTH_32BIT,
    INT24_MIN, INT24_MAX, INT24_MAX_MAGNITUDE,
    bytes_to_int32_24bit, int32_to_bytes_24bit, get_numpy_dtype,
)


class BitDepthAdapter(AdapterBase):
    """
    Adapter for converting between different bit depths and sample formats.

    This adapter wraps an AudioStreamBase and converts the sample width
    and format. Supports conversions between:
    - Integer formats: 8-bit, 16-bit, 24-bit
    - Float formats: 32-bit float
    - Int to float and float to int conversions

    The adapter passes seeking through to the source stream since bit depth
    conversion doesn't affect frame positions.

    Conversion formulas:
    - Int→Float: float_val = int_val / 2^(bits-1)
    - Float→Int: int_val = clip(float_val * (2^(bits-1) - 1))
    - Int→Int: int_val = int_val * (2^(target_bits-1) - 1) / (2^(source_bits-1) - 1)

    Attributes:
        _target_sample_width: Target sample width in bytes
        _target_sample_format: Target sample format ('int' or 'float')
        _source_dtype: NumPy dtype for source audio data
        _target_dtype: NumPy dtype for target audio data
    """

    def __init__(
        self,
        source: AudioStreamBase,
        target_sample_width: int,
        target_sample_format: Literal['int', 'float']
    ):
        """
        Initialize the BitDepthAdapter.

        Args:
            source: The AudioStreamBase instance to wrap
            target_sample_width: Target sample width in bytes (1, 2, 3, or 4)
            target_sample_format: Target sample format ('int' or 'float')

        Raises:
            ValueError: If target_sample_width is not supported
            ValueError: If target_sample_format is not 'int' or 'float'
            ValueError: If source and target formats are the same
            ValueError: If combination is not supported (e.g., 8-bit float)
        """
        super().__init__(source)

        if target_sample_width not in (SAMPLE_WIDTH_8BIT, SAMPLE_WIDTH_16BIT,
                                       SAMPLE_WIDTH_24BIT, SAMPLE_WIDTH_32BIT):
            raise ValueError(
                f"target_sample_width must be 1, 2, 3, or 4 bytes, "
                f"got {target_sample_width}"
            )

        if target_sample_format not in ('int', 'float'):
            raise ValueError(
                f"target_sample_format must be 'int' or 'float', "
                f"got {target_sample_format}"
            )

        # Validate format combinations
        if target_sample_format == 'float' and target_sample_width != SAMPLE_WIDTH_32BIT:
            raise ValueError(
                f"Float format only supports 32-bit (4 bytes), "
                f"got {target_sample_width} bytes"
            )

        # Determine source format
        source_format = self._infer_source_format(source.sample_width)

        # Check if no conversion needed
        if (source.sample_width == target_sample_width and
                source_format == target_sample_format):
            raise ValueError(
                f"Source format ({source.sample_width} bytes, {source_format}) "
                f"matches target format. No adaptation needed."
            )

        self._target_sample_width = target_sample_width
        self._target_sample_format = target_sample_format

        # Get dtypes for conversion
        self._source_dtype = get_numpy_dtype(source.sample_width, source_format)
        self._target_dtype = get_numpy_dtype(target_sample_width, target_sample_format)

    def _infer_source_format(self, sample_width: int) -> Literal['int', 'float']:
        """
        Infer the sample format from the sample width.

        By convention:
        - 1, 2, 3 bytes: integer format
        - 4 bytes: float format (assumed to be 32-bit float)

        Args:
            sample_width: Sample width in bytes

        Returns:
            'int' or 'float'
        """
        if sample_width in (SAMPLE_WIDTH_8BIT, SAMPLE_WIDTH_16BIT, SAMPLE_WIDTH_24BIT):
            return 'int'
        elif sample_width == SAMPLE_WIDTH_32BIT:
            return 'float'
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")

    def _bytes_to_array(self, data: bytes, sample_width: int) -> np.ndarray:
        """
        Convert bytes to numpy array, handling 24-bit audio specially.

        Args:
            data: Audio data as bytes
            sample_width: Sample width in bytes

        Returns:
            NumPy array with audio samples
        """
        if sample_width == SAMPLE_WIDTH_24BIT:
            return bytes_to_int32_24bit(data)
        # Standard formats
        dtype = get_numpy_dtype(sample_width, self._infer_source_format(sample_width))
        return np.frombuffer(data, dtype=dtype)

    def _array_to_bytes(self, array: np.ndarray, sample_width: int) -> bytes:
        """
        Convert numpy array to bytes, handling 24-bit audio specially.

        Args:
            array: NumPy array with audio samples
            sample_width: Sample width in bytes

        Returns:
            Audio data as bytes
        """
        if sample_width == SAMPLE_WIDTH_24BIT:
            return int32_to_bytes_24bit(array)
        return array.tobytes()

    def _convert_audio(self, source_array: np.ndarray) -> np.ndarray:
        """
        Convert audio from source format to target format.

        Args:
            source_array: Audio data in source format

        Returns:
            Audio data in target format
        """
        source_format = self._infer_source_format(self._source.sample_width)
        target_format = self._target_sample_format

        # Get bit depths
        source_bits = self._source.sample_width * 8
        target_bits = self._target_sample_width * 8

        # Convert to float64 for processing to maintain precision
        working_array = source_array.astype(np.float64)

        # Normalize based on source format
        if source_format == 'int':
            # Normalize int to [-1.0, 1.0]
            if self._source.sample_width == SAMPLE_WIDTH_24BIT:
                working_array /= INT24_MAX_MAGNITUDE
            else:
                # Use 2^(bits-1) for normalization
                working_array /= (2 ** (source_bits - 1))
        else:
            # Already float, should be in [-1.0, 1.0]
            pass

        # Convert to target format
        if target_format == 'int':
            # Convert normalized float to target int range
            if self._target_sample_width == SAMPLE_WIDTH_24BIT:
                # 24-bit peak magnitude is 2^23 - 1
                working_array *= INT24_MAX
            else:
                # Use 2^(bits-1) - 1 for scaling
                working_array *= (2 ** (target_bits - 1) - 1)

            # Clip to valid range
            if self._target_sample_width == SAMPLE_WIDTH_8BIT:
                working_array = np.clip(working_array, -128, 127)
            elif self._target_sample_width == SAMPLE_WIDTH_16BIT:
                working_array = np.clip(working_array, -32768, 32767)
            elif self._target_sample_width == SAMPLE_WIDTH_24BIT:
                working_array = np.clip(working_array, INT24_MIN, INT24_MAX)
            elif self._target_sample_width == SAMPLE_WIDTH_32BIT:
                working_array = np.clip(working_array, -2147483648, 2147483647)

            # Convert to target integer dtype
            if self._target_sample_width == SAMPLE_WIDTH_24BIT:
                result = working_array.astype(np.int32)
            else:
                result = working_array.astype(self._target_dtype)
        else:
            # Target is float, working_array is already normalized to [-1.0, 1.0]
            result = working_array.astype(self._target_dtype)

        return result

    def read(self, n_frames: int) -> bytes:
        """
        Read audio data and convert bit depth.

        Args:
            n_frames: Number of frames to read in the ADAPTED format

        Returns:
            Audio data with target bit depth as bytes

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()

        # Read from source
        source_data = self._source.read(n_frames)
        if not source_data:
            return b''

        # Convert bytes to numpy array
        source_array = self._bytes_to_array(source_data, self._source.sample_width)

        # Convert to target format
        converted_array = self._convert_audio(source_array)

        # Convert back to bytes
        return self._array_to_bytes(converted_array, self._target_sample_width)

    def seek(self, frame_offset: int) -> None:
        """
        Seek to a specific frame position.

        Bit depth conversion doesn't affect frame positions, so this passes
        through directly to the source stream.

        Args:
            frame_offset: Frame position in the ADAPTED format

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()
        self._source.seek(frame_offset)

    @property
    def sample_width(self) -> int:
        """
        Get the sample width of the adapted stream.

        Returns:
            Target sample width in bytes
        """
        return self._target_sample_width
