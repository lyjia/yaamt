"""
Resampling adapter for converting sample rates.

This module provides the ResamplingAdapter class, which converts audio streams
between different sample rates using scipy.signal.resample_poly.
"""

import numpy as np
from scipy.signal import resample_poly
from typing import Tuple
from .base import AdapterBase
from ..base import AudioStreamBase


class ResamplingAdapter(AdapterBase):
    """
    Adapter for converting sample rates.

    This adapter wraps an AudioStreamBase and converts the sample rate using
    scipy.signal.resample_poly, which is efficient for rational conversion ratios.

    The adapter maintains a small internal buffer to handle filter edge effects
    and supports seeking with approximate frame accuracy (±1-2 frames).

    Quality parameters:
    - Uses Kaiser window with beta=5.0 for good quality
    - For critical quality, beta=8.0 or higher can be used (future enhancement)

    Attributes:
        _target_sample_rate: Target sample rate in Hz
        _up_factor: Upsampling factor for resample_poly
        _down_factor: Downsampling factor for resample_poly
        _buffer: Internal buffer for filter edge effects
        _beta: Kaiser window beta parameter for quality control
    """

    def __init__(
        self,
        source: AudioStreamBase,
        target_sample_rate: int,
        beta: float = 5.0
    ):
        """
        Initialize the ResamplingAdapter.

        Args:
            source: The AudioStreamBase instance to wrap
            target_sample_rate: Target sample rate in Hz
            beta: Kaiser window beta parameter for quality (default: 5.0)

        Raises:
            ValueError: If target_sample_rate is invalid
            ValueError: If source and target sample rates are the same
        """
        super().__init__(source)

        if target_sample_rate <= 0:
            raise ValueError(
                f"target_sample_rate must be positive, got {target_sample_rate}"
            )

        if source.samplerate == target_sample_rate:
            raise ValueError(
                f"Source sample rate ({source.samplerate}) matches target "
                f"sample rate ({target_sample_rate}). No adaptation needed."
            )

        self._target_sample_rate = target_sample_rate
        self._beta = beta

        # Calculate up/down factors for resample_poly
        # Use GCD to simplify the ratio
        self._up_factor, self._down_factor = self._calculate_resample_factors(
            source.samplerate, target_sample_rate
        )

        # Internal buffer for handling filter edge effects
        # Store as numpy array for easier manipulation
        self._buffer = np.array([], dtype=self._get_numpy_dtype())

    def _calculate_resample_factors(
        self,
        source_rate: int,
        target_rate: int
    ) -> Tuple[int, int]:
        """
        Calculate simplified up/down factors for resampling.

        Uses GCD to simplify the ratio for efficiency.

        Args:
            source_rate: Source sample rate in Hz
            target_rate: Target sample rate in Hz

        Returns:
            Tuple of (up_factor, down_factor)
        """
        from math import gcd

        # Simplify the ratio
        divisor = gcd(target_rate, source_rate)
        up = target_rate // divisor
        down = source_rate // divisor

        return up, down

    def _get_numpy_dtype(self) -> np.dtype:
        """
        Get the numpy dtype for audio data based on sample width.

        Returns:
            NumPy dtype for audio data
        """
        if self._source.sample_width == 1:
            return np.dtype('<i1')
        elif self._source.sample_width == 2:
            return np.dtype('<i2')
        elif self._source.sample_width == 3:
            return np.dtype('<i4')  # 24-bit stored as 32-bit
        elif self._source.sample_width == 4:
            return np.dtype('<f4')  # 32-bit float
        else:
            raise ValueError(
                f"Unsupported sample width: {self._source.sample_width} bytes"
            )

    def _bytes_to_array(self, data: bytes) -> np.ndarray:
        """
        Convert bytes to numpy array, handling 24-bit audio specially.

        Args:
            data: Audio data as bytes

        Returns:
            NumPy array with audio samples
        """
        if self._source.sample_width == 3:
            # Handle 24-bit audio: convert 3 bytes to int32
            audio_bytes = np.frombuffer(data, dtype=np.uint8)
            n_samples = len(audio_bytes) // 3
            audio_array = np.zeros(n_samples, dtype=np.int32)

            for i in range(n_samples):
                byte_offset = i * 3
                val = int(audio_bytes[byte_offset]) | \
                      (int(audio_bytes[byte_offset + 1]) << 8) | \
                      (int(audio_bytes[byte_offset + 2]) << 16)

                # Sign extend if negative (bit 23 is set)
                if val & 0x800000:
                    val = val - 0x1000000  # Convert to negative by subtracting 2^24

                audio_array[i] = val

            return audio_array
        else:
            # Standard formats
            return np.frombuffer(data, dtype=self._get_numpy_dtype())

    def _array_to_bytes(self, array: np.ndarray) -> bytes:
        """
        Convert numpy array to bytes, handling 24-bit audio specially.

        Args:
            array: NumPy array with audio samples

        Returns:
            Audio data as bytes
        """
        if self._source.sample_width == 3:
            # Handle 24-bit audio: convert int32 to 3 bytes
            array = array.astype(np.int32)
            output_bytes = bytearray()

            for val in array.flat:
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
            # Standard formats
            return array.astype(self._get_numpy_dtype()).tobytes()

    def _resample_audio(self, audio_array: np.ndarray) -> np.ndarray:
        """
        Resample audio data using scipy.signal.resample_poly.

        Args:
            audio_array: Audio data as numpy array (flat, interleaved)

        Returns:
            Resampled audio data
        """
        if len(audio_array) == 0:
            return audio_array

        # Reshape to (n_frames, n_channels) if multi-channel
        n_channels = self._source.nchannels
        if n_channels > 1:
            n_frames = len(audio_array) // n_channels
            audio_array = audio_array.reshape(n_frames, n_channels)

            # Resample each channel separately
            resampled_channels = []
            for ch in range(n_channels):
                channel_data = audio_array[:, ch]
                resampled_channel = resample_poly(
                    channel_data,
                    self._up_factor,
                    self._down_factor,
                    window=('kaiser', self._beta)
                )
                resampled_channels.append(resampled_channel)

            # Interleave channels back
            resampled_array = np.column_stack(resampled_channels)
            resampled_array = resampled_array.flatten()
        else:
            # Mono: resample directly
            resampled_array = resample_poly(
                audio_array,
                self._up_factor,
                self._down_factor,
                window=('kaiser', self._beta)
            )

        return resampled_array

    def read(self, n_frames: int) -> bytes:
        """
        Read audio data and resample to target sample rate.

        Args:
            n_frames: Number of frames to read in the ADAPTED format

        Returns:
            Resampled audio data as bytes

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()

        if n_frames == 0:
            return b''

        # Calculate how many source frames we need to read
        # to produce the requested number of output frames
        # Formula: source_frames = output_frames * source_rate / target_rate
        source_frames_needed = int(
            np.ceil(n_frames * self._source.samplerate / self._target_sample_rate)
        )

        # Add some extra frames for filter overlap (helps with edge effects)
        # This is a heuristic: use about 10% extra or at least 100 frames
        overlap_frames = max(100, source_frames_needed // 10)
        source_frames_to_read = source_frames_needed + overlap_frames

        # Read from source
        source_data = self._source.read(source_frames_to_read)
        if not source_data:
            # If we have buffered data, return what we can
            if len(self._buffer) > 0:
                n_channels = self._source.nchannels
                output_samples = min(n_frames * n_channels, len(self._buffer))
                output_array = self._buffer[:output_samples]
                self._buffer = self._buffer[output_samples:]
                return self._array_to_bytes(output_array)
            return b''

        # Convert to numpy array
        source_array = self._bytes_to_array(source_data)

        # Combine with any buffered data
        if len(self._buffer) > 0:
            source_array = np.concatenate([self._buffer, source_array])
            self._buffer = np.array([], dtype=self._get_numpy_dtype())

        # Resample the audio
        resampled_array = self._resample_audio(source_array)

        # Extract the requested number of samples
        n_channels = self._source.nchannels
        output_samples = n_frames * n_channels

        if len(resampled_array) >= output_samples:
            # We have enough data - return what's needed and buffer the rest
            output_array = resampled_array[:output_samples]
            self._buffer = resampled_array[output_samples:]
        else:
            # We don't have enough data - return what we have
            output_array = resampled_array

        return self._array_to_bytes(output_array)

    def seek(self, frame_offset: int) -> None:
        """
        Seek to a specific frame position.

        Calculates the corresponding source frame position and seeks there.
        Clears the internal buffer to ensure clean playback from the new position.

        Note: Frame accuracy may be ±1-2 frames due to filter edge effects.

        Args:
            frame_offset: Frame position in the ADAPTED format

        Raises:
            ValueError: If the adapter is closed
        """
        self._check_closed()

        # Calculate corresponding source frame position
        # Formula: source_frame = output_frame * source_rate / target_rate
        source_frame = int(
            frame_offset * self._source.samplerate / self._target_sample_rate
        )

        # Seek source stream
        self._source.seek(source_frame)

        # Clear buffer
        self._buffer = np.array([], dtype=self._get_numpy_dtype())

    @property
    def samplerate(self) -> int:
        """
        Get the sample rate of the adapted stream.

        Returns:
            Target sample rate in Hz
        """
        return self._target_sample_rate

    @property
    def duration_seconds(self) -> float:
        """
        Get the duration of the audio stream in seconds.

        Duration doesn't change with resampling (same audio content, different rate).

        Returns:
            Duration in seconds
        """
        return self._source.duration_seconds
