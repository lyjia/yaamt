"""
Utility functions for converting audio streams to numpy arrays.

This module provides helper functions for converting AudioStreamBase instances
to numpy arrays in formats suitable for analysis libraries like librosa.

It also hosts shared low-level audio conversion primitives used by audio
adapters (bit depth, channel mixing, resampling) so that 24-bit packing and
dtype-mapping logic lives in exactly one place.
"""

import numpy as np
from typing import Literal, Optional, Tuple
from providers.audio.base import AudioStreamBase
from util.logging import log


# Sample width (in bytes) constants
SAMPLE_WIDTH_8BIT = 1
SAMPLE_WIDTH_16BIT = 2
SAMPLE_WIDTH_24BIT = 3
SAMPLE_WIDTH_32BIT = 4

# Signed integer magnitudes, used for normalizing integer PCM to [-1.0, 1.0]
INT16_MAX_MAGNITUDE = 32768.0        # 2^15
INT24_MAX_MAGNITUDE = 8388608.0      # 2^23
INT32_MAX_MAGNITUDE = 2147483648.0   # 2^31

# Clipping bounds for 24-bit signed PCM (stored as int32)
INT24_MIN = -8388608   # -2^23
INT24_MAX = 8388607    #  2^23 - 1

# Threshold used to distinguish already-normalized float32 audio from int32
# data accidentally read as float32: normalized float audio is in [-1, 1],
# so anything with magnitude > 2.0 is almost certainly raw integer samples.
FLOAT32_NORMALIZED_MAX_THRESHOLD = 2.0

# Type alias for sample format
SampleFormat = Literal['int', 'float', 'auto']


def get_numpy_dtype(sample_width: int, sample_format: SampleFormat = 'auto') -> np.dtype:
    """
    Return the NumPy dtype used to represent PCM samples of the given width.

    When ``sample_format`` is ``'auto'`` (the default), the format is inferred
    from the sample width using the convention that widths of 1, 2, or 3 bytes
    are signed integer PCM and 4 bytes is 32-bit float. Callers that need to
    distinguish 32-bit signed int from 32-bit float must pass ``'int'`` or
    ``'float'`` explicitly.

    24-bit samples do not have a native NumPy dtype, so they are represented
    as ``<i4`` (int32); use :func:`bytes_to_int32_24bit` and
    :func:`int32_to_bytes_24bit` to pack/unpack the on-wire 3-byte form.

    Args:
        sample_width: Sample width in bytes (1, 2, 3, or 4).
        sample_format: ``'int'``, ``'float'``, or ``'auto'`` (default).

    Returns:
        NumPy dtype for audio data in the requested format.

    Raises:
        ValueError: If the (width, format) combination is not supported.
    """
    if sample_format == 'auto':
        sample_format = 'int' if sample_width in (1, 2, 3) else 'float'

    if sample_format == 'int':
        int_dtype_map = {
            SAMPLE_WIDTH_8BIT: np.dtype('<i1'),   # 8-bit signed int
            SAMPLE_WIDTH_16BIT: np.dtype('<i2'),  # 16-bit signed int
            SAMPLE_WIDTH_24BIT: np.dtype('<i4'),  # 24-bit (stored as 32-bit int)
            SAMPLE_WIDTH_32BIT: np.dtype('<i4'),  # 32-bit signed int
        }
        if sample_width not in int_dtype_map:
            raise ValueError(
                f"Unsupported int sample width: {sample_width} bytes"
            )
        return int_dtype_map[sample_width]

    if sample_format == 'float':
        if sample_width != SAMPLE_WIDTH_32BIT:
            raise ValueError(
                f"Float format only supports 32-bit (4 bytes), "
                f"got {sample_width} bytes"
            )
        return np.dtype('<f4')

    raise ValueError(f"Invalid sample_format: {sample_format!r}")


def bytes_to_int32_24bit(data: bytes) -> np.ndarray:
    """
    Unpack little-endian 24-bit signed PCM bytes into an int32 numpy array.

    Every three consecutive bytes in ``data`` are treated as one 24-bit
    signed little-endian sample; the result is sign-extended into int32.

    Args:
        data: Raw audio bytes whose length is a multiple of 3.

    Returns:
        One-dimensional int32 array of samples.
    """
    audio_bytes = np.frombuffer(data, dtype=np.uint8)
    n_samples = len(audio_bytes) // 3
    if n_samples == 0:
        return np.zeros(0, dtype=np.int32)

    # Vectorized unpack: view the three byte planes and combine them.
    trimmed = audio_bytes[:n_samples * 3].reshape(n_samples, 3).astype(np.int32)
    audio_array = (
        trimmed[:, 0]
        | (trimmed[:, 1] << 8)
        | (trimmed[:, 2] << 16)
    )
    # Sign-extend: if bit 23 is set, subtract 2^24 to make negative.
    sign_mask = (audio_array & 0x800000).astype(bool)
    audio_array[sign_mask] -= 0x1000000
    return audio_array


def int32_to_bytes_24bit(array: np.ndarray) -> bytes:
    """
    Pack an int32 numpy array into little-endian 24-bit signed PCM bytes.

    Values outside the 24-bit signed range are clipped before packing.

    Args:
        array: NumPy array of samples (any shape; flattened before packing).

    Returns:
        Raw audio bytes, three bytes per sample.
    """
    clipped = np.clip(array.astype(np.int32).ravel(), INT24_MIN, INT24_MAX)
    # Take the three lowest bytes (little-endian) of the int32 representation.
    as_uint = clipped.astype(np.uint32)
    byte0 = (as_uint & 0xFF).astype(np.uint8)
    byte1 = ((as_uint >> 8) & 0xFF).astype(np.uint8)
    byte2 = ((as_uint >> 16) & 0xFF).astype(np.uint8)
    packed = np.stack([byte0, byte1, byte2], axis=1)
    return packed.tobytes()


def audio_stream_to_numpy(
    audio_stream: AudioStreamBase,
    max_duration: Optional[float] = None,
    chunk_size: int = 8192
) -> Tuple[np.ndarray, int]:
    """
    Convert an AudioStreamBase to a numpy array suitable for librosa.

    Reads the entire audio stream (or up to max_duration) and converts it to
    a float32 numpy array normalized to [-1.0, 1.0] range, which is the format
    expected by librosa and similar analysis libraries.

    Args:
        audio_stream: The audio stream to read from
        max_duration: Optional maximum duration in seconds to read (None = entire file)
        chunk_size: Number of frames to read per iteration (default: 8192)

    Returns:
        Tuple of (audio_array, sample_rate) where:
            - audio_array is a numpy.float32 array with shape (n,) for mono
              or (channels, n) for multi-channel, normalized to [-1, 1]
            - sample_rate is the audio sample rate in Hz

    Raises:
        ValueError: If the stream is closed or has invalid properties

    Example:
        >>> audio_stream = media_file.get_audio_stream()
        >>> y, sr = audio_stream_to_numpy(audio_stream)
        >>> # y is now ready for librosa.beat.beat_track(y=y, sr=sr)
    """
    if audio_stream.sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {audio_stream.sample_rate}")

    sample_rate = audio_stream.sample_rate
    channels = audio_stream.channels_qty
    sample_width = audio_stream.sample_width

    # Calculate max frames to read if duration is specified
    max_frames = None
    if max_duration is not None and max_duration > 0:
        max_frames = int(max_duration * sample_rate)

    # Read audio data in chunks
    audio_bytes = bytearray()
    frames_read = 0

    while True:
        # Calculate frames to read this iteration
        frames_to_read = chunk_size
        if max_frames is not None:
            remaining_frames = max_frames - frames_read
            if remaining_frames <= 0:
                break
            frames_to_read = min(frames_to_read, remaining_frames)

        chunk = audio_stream.read(frames_to_read)
        if not chunk:
            break

        audio_bytes.extend(chunk)

        # Track frames read (bytes / (channels * sample_width))
        chunk_frames = len(chunk) // (channels * sample_width)
        frames_read += chunk_frames

        # Check if we've hit the max duration
        if max_frames is not None and frames_read >= max_frames:
            break

    if len(audio_bytes) == 0:
        # Empty stream - return empty array
        log.warning("Audio stream returned no data")
        return np.array([], dtype=np.float32), sample_rate

    # Convert bytes to numpy array based on sample width
    if sample_width == SAMPLE_WIDTH_16BIT:
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        # Normalize to [-1.0, 1.0]
        samples = samples / INT16_MAX_MAGNITUDE

    elif sample_width == SAMPLE_WIDTH_24BIT:
        # 24-bit audio needs special handling - not commonly supported
        log.warning("24-bit audio may not be fully supported - results may vary")
        samples = bytes_to_int32_24bit(bytes(audio_bytes)).astype(np.float32)
        samples = samples / INT24_MAX_MAGNITUDE

    elif sample_width == SAMPLE_WIDTH_32BIT:
        # 32-bit could be int or float. If the audio stream adapter already
        # converted to float, use as-is. Otherwise, treat as int32.
        try:
            # Try as float32 first
            samples = np.frombuffer(audio_bytes, dtype=np.float32)

            # If any value is far outside [-1, 1], it's almost certainly int32
            # samples reinterpreted as float32 rather than real float audio.
            if np.abs(samples).max() > FLOAT32_NORMALIZED_MAX_THRESHOLD:
                samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
                samples = samples / INT32_MAX_MAGNITUDE
            # else: already float32, possibly already normalized

        except Exception as e:
            log.warning(f"Error interpreting 32-bit audio: {e}")
            # Fallback: treat as int32
            samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
            samples = samples / INT32_MAX_MAGNITUDE
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bytes")

    # Ensure normalization to [-1, 1] (in case float32 wasn't normalized)
    max_val = np.abs(samples).max()
    if max_val > 1.0:
        log.debug(f"Normalizing audio: max value was {max_val}")
        samples = samples / max_val

    # Reshape for multi-channel audio
    # librosa expects shape (channels, n) for multi-channel
    if channels > 1:
        # Current shape: (total_samples,) where total_samples = n * channels
        # Target shape: (channels, n)
        total_samples = len(samples)
        n_frames = total_samples // channels
        samples = samples[:n_frames * channels]  # Trim any incomplete frames
        samples = samples.reshape(n_frames, channels).T  # Reshape and transpose

    return samples, sample_rate
