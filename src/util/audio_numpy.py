"""
Utility functions for converting audio streams to numpy arrays.

This module provides helper functions for converting AudioStreamBase instances
to numpy arrays in formats suitable for analysis libraries like librosa.
"""

import numpy as np
from typing import Optional, Tuple
from providers.audio.base import AudioStreamBase
from util.logging import log


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
    if sample_width == 2:  # 16-bit integer
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        # Normalize to [-1.0, 1.0]
        samples = samples / 32768.0

    elif sample_width == 3:  # 24-bit integer (rare)
        # 24-bit audio needs special handling - not commonly supported
        log.warning("24-bit audio may not be fully supported - results may vary")
        samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
        samples = samples / 2147483648.0

    elif sample_width == 4:  # 32-bit (could be int or float)
        # Try to determine if it's int32 or float32
        # If the audio stream adapter already converted to float, use as-is
        try:
            # Try as float32 first
            samples = np.frombuffer(audio_bytes, dtype=np.float32)

            # Check if values are in reasonable float range [-1, 1]
            # If all values are much larger, it's probably int32
            if np.abs(samples).max() > 2.0:
                # Likely int32, not float32
                samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
                samples = samples / 2147483648.0
            # else: already float32, possibly already normalized

        except Exception as e:
            log.warning(f"Error interpreting 32-bit audio: {e}")
            # Fallback: treat as int32
            samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
            samples = samples / 2147483648.0
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


def audio_stream_to_mono_numpy(
    audio_stream: AudioStreamBase,
    max_duration: Optional[float] = None,
    chunk_size: int = 8192
) -> Tuple[np.ndarray, int]:
    """
    Convert an AudioStreamBase to a mono numpy array suitable for librosa.

    This is a convenience function that wraps audio_stream_to_numpy() and
    converts multi-channel audio to mono using librosa's to_mono() function.

    Args:
        audio_stream: The audio stream to read from
        max_duration: Optional maximum duration in seconds to read (None = entire file)
        chunk_size: Number of frames to read per iteration (default: 8192)

    Returns:
        Tuple of (audio_array, sample_rate) where:
            - audio_array is a mono numpy.float32 array with shape (n,)
            - sample_rate is the audio sample rate in Hz

    Example:
        >>> audio_stream = media_file.get_audio_stream()
        >>> y, sr = audio_stream_to_mono_numpy(audio_stream)
        >>> # y is guaranteed to be mono, shape (n,)
    """
    y, sr = audio_stream_to_numpy(audio_stream, max_duration, chunk_size)

    # Convert to mono if needed
    if len(y.shape) > 1:
        # Multi-channel - convert to mono
        # Use librosa if available, otherwise simple averaging
        try:
            import librosa
            y = librosa.to_mono(y)
        except ImportError:
            # Fallback: simple average across channels
            y = np.mean(y, axis=0)

    return y, sr
