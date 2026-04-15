"""
Resampling adapter for converting sample rates.

This module provides the ResamplingAdapter class, which converts audio streams
between different sample rates using scipy.signal.resample_poly.
"""

import numpy as np
from scipy.signal import resample_poly
from .base import AdapterBase
from ..base import AudioStreamBase
from util.audio_numpy import (
    SAMPLE_WIDTH_24BIT,
    bytes_to_int32_24bit, int32_to_bytes_24bit, get_numpy_dtype,
)


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

        if source.sample_rate == target_sample_rate:
            raise ValueError(
                f"Source sample rate ({source.sample_rate}) matches target "
                f"sample rate ({target_sample_rate}). No adaptation needed."
            )

        self._target_sample_rate = target_sample_rate
        self._beta = beta

        # Calculate up/down factors for resample_poly
        # Use GCD to simplify the ratio
        self._up_factor, self._down_factor = self._calculate_resample_factors(
            source.sample_rate, target_sample_rate
        )

        # Internal buffer for handling filter edge effects
        # Store as numpy array for easier manipulation
        self._buffer = np.array([], dtype=self._get_numpy_dtype())

    def _calculate_resample_factors(
        self,
        source_rate: int,
        target_rate: int
    ) -> tuple[int, int]:
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

        Uses the 'auto' convention from :func:`util.audio_numpy.get_numpy_dtype`
        where 4-byte samples are interpreted as float32.

        Returns:
            NumPy dtype for audio data
        """
        return get_numpy_dtype(self._source.sample_width, 'auto')

    def _bytes_to_array(self, data: bytes) -> np.ndarray:
        """
        Convert bytes to numpy array, handling 24-bit audio specially.

        Args:
            data: Audio data as bytes

        Returns:
            NumPy array with audio samples
        """
        if self._source.sample_width == SAMPLE_WIDTH_24BIT:
            return bytes_to_int32_24bit(data)
        return np.frombuffer(data, dtype=self._get_numpy_dtype())

    def _array_to_bytes(self, array: np.ndarray) -> bytes:
        """
        Convert numpy array to bytes, handling 24-bit audio specially.

        Args:
            array: NumPy array with audio samples

        Returns:
            Audio data as bytes
        """
        if self._source.sample_width == SAMPLE_WIDTH_24BIT:
            return int32_to_bytes_24bit(array)
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
        n_channels = self._source.channels_qty
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
            np.ceil(n_frames * self._source.sample_rate / self._target_sample_rate)
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
                n_channels = self._source.channels_qty
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
        n_channels = self._source.channels_qty
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
            frame_offset * self._source.sample_rate / self._target_sample_rate
        )

        # Seek source stream
        self._source.seek(source_frame)

        # Clear buffer
        self._buffer = np.array([], dtype=self._get_numpy_dtype())

    @property
    def sample_rate(self) -> int:
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
