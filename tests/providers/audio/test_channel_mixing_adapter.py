"""
Unit tests for ChannelMixingAdapter.

Tests the channel mixing adapter for converting between mono and stereo audio.
"""

import pytest
import numpy as np
from providers.audio.adapters.channel_mixing_adapter import ChannelMixingAdapter
from providers.audio.base import AudioStreamBase


class MockAudioStream(AudioStreamBase):
    """Mock audio stream for testing with controllable audio data."""

    def __init__(self, sample_rate=44100, channels=2, width=2, duration=10.0):
        super().__init__()
        self._sample_rate = sample_rate
        self._channels = channels
        self._width = width
        self._duration = duration
        self._closed = False
        self._position = 0
        self._test_data = None  # Can be set to provide specific test data

    def read(self, n_frames: int) -> bytes:
        if self._closed:
            raise ValueError("Stream is closed")

        # If test data is provided, use it
        if self._test_data is not None:
            if self._position >= len(self._test_data):
                return b''

            frames_available = min(n_frames, len(self._test_data) - self._position)
            start = self._position * self._channels * self._width
            end = start + (frames_available * self._channels * self._width)
            data = self._test_data[start:end]
            self._position += frames_available
            return data

        # Otherwise, return dummy data
        bytes_per_frame = self._channels * self._width
        return b'\x00' * (n_frames * bytes_per_frame)

    def seek(self, frame_offset: int) -> None:
        if self._closed:
            raise ValueError("Stream is closed")
        self._position = frame_offset

    def close(self) -> None:
        self._closed = True

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels_qty(self) -> int:
        return self._channels

    @property
    def sample_width(self) -> int:
        return self._width

    @property
    def duration_seconds(self) -> float:
        return self._duration


class TestChannelMixingAdapterCreation:
    """Test creating ChannelMixingAdapter instances."""

    def test_create_stereo_to_mono_adapter(self):
        """Test creating an adapter for stereo to mono conversion."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        assert adapter.channels_qty == 1
        assert adapter._target_channels == 1

    def test_create_mono_to_stereo_adapter(self):
        """Test creating an adapter for mono to stereo conversion."""
        source = MockAudioStream(channels=1)
        adapter = ChannelMixingAdapter(source, target_channels=2)

        assert adapter.channels_qty == 2
        assert adapter._target_channels == 2

    def test_invalid_target_channels(self):
        """Test that invalid target channel counts raise an error."""
        source = MockAudioStream(channels=2)

        with pytest.raises(ValueError, match="target_channels must be 1 or 2"):
            ChannelMixingAdapter(source, target_channels=4)

    def test_invalid_source_channels(self):
        """Test that invalid source channel counts raise an error."""
        source = MockAudioStream(channels=6)  # 5.1 surround

        with pytest.raises(ValueError, match="Source must have 1 or 2 channels"):
            ChannelMixingAdapter(source, target_channels=2)

    def test_same_source_and_target_channels(self):
        """Test that same source and target channels raise an error."""
        source = MockAudioStream(channels=2)

        with pytest.raises(ValueError, match="No adaptation needed"):
            ChannelMixingAdapter(source, target_channels=2)


class TestChannelMixingAdapterProperties:
    """Test adapter properties."""

    def test_nchannels_returns_target(self):
        """Test that channels_qty returns the target channel count."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        assert adapter.channels_qty == 1

    def test_other_properties_delegate_to_source(self):
        """Test that other properties delegate to source."""
        source = MockAudioStream(
            sample_rate=48000,
            channels=2,
            width=4,
            duration=123.45
        )
        adapter = ChannelMixingAdapter(source, target_channels=1)

        assert adapter.sample_rate == 48000
        assert adapter.sample_width == 4
        assert adapter.duration_seconds == 123.45


class TestStereoToMono:
    """Test stereo to mono conversion."""

    def test_stereo_to_mono_16bit(self):
        """Test stereo to mono conversion with 16-bit audio."""
        # Create stereo test data: left=1000, right=2000
        left_channel = np.array([1000, 1000, 1000], dtype=np.int16)
        right_channel = np.array([2000, 2000, 2000], dtype=np.int16)

        # Interleave channels: [L, R, L, R, L, R]
        stereo_data = np.empty(6, dtype=np.int16)
        stereo_data[0::2] = left_channel
        stereo_data[1::2] = right_channel

        source = MockAudioStream(channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=1)

        # Read 3 frames
        mono_data = adapter.read(3)
        mono_array = np.frombuffer(mono_data, dtype=np.int16)

        # Expected: (1000 + 2000) / sqrt(2) ≈ 2121 for each frame
        expected = 1500 / np.sqrt(2)
        assert len(mono_array) == 3
        np.testing.assert_allclose(mono_array, expected, rtol=0.01)

    def test_stereo_to_mono_applies_correct_formula(self):
        """Test that stereo to mono uses (L+R)/2/sqrt(2) formula."""
        # Create stereo test data with constant known values
        n_frames = 1000
        left_value = 1000
        right_value = 2000

        left_channel = np.full(n_frames, left_value, dtype=np.int16)
        right_channel = np.full(n_frames, right_value, dtype=np.int16)

        stereo_data = np.empty(n_frames * 2, dtype=np.int16)
        stereo_data[0::2] = left_channel
        stereo_data[1::2] = right_channel

        source = MockAudioStream(channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=1)
        mono_data = adapter.read(n_frames)
        mono_array = np.frombuffer(mono_data, dtype=np.int16)

        # Expected: (1000 + 2000) / 2 / sqrt(2) = 1500 / sqrt(2) ≈ 1061
        expected_value = (left_value + right_value) / 2.0 / np.sqrt(2)

        # All mono samples should be approximately this value
        np.testing.assert_allclose(mono_array, expected_value, rtol=0.01)

    def test_stereo_to_mono_32bit_float(self):
        """Test stereo to mono conversion with 32-bit float audio."""
        # Create stereo test data
        left_channel = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        right_channel = np.array([0.3, 0.3, 0.3], dtype=np.float32)

        stereo_data = np.empty(6, dtype=np.float32)
        stereo_data[0::2] = left_channel
        stereo_data[1::2] = right_channel

        source = MockAudioStream(channels=2, width=4)
        source._test_data = stereo_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=1)
        mono_data = adapter.read(3)
        mono_array = np.frombuffer(mono_data, dtype=np.float32)

        # Expected: (0.5 + 0.3) / sqrt(2) ≈ 0.5657
        expected = 0.4 / np.sqrt(2)
        assert len(mono_array) == 3
        np.testing.assert_allclose(mono_array, expected, rtol=0.01)


class TestMonoToStereo:
    """Test mono to stereo conversion."""

    def test_mono_to_stereo_16bit(self):
        """Test mono to stereo conversion with 16-bit audio."""
        # Create mono test data
        mono_data = np.array([1000, 2000, 3000], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = mono_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=2)

        # Read 3 frames
        stereo_data = adapter.read(3)
        stereo_array = np.frombuffer(stereo_data, dtype=np.int16)

        # Should be duplicated: [1000, 1000, 2000, 2000, 3000, 3000]
        expected = np.array([1000, 1000, 2000, 2000, 3000, 3000], dtype=np.int16)
        np.testing.assert_array_equal(stereo_array, expected)

    def test_mono_to_stereo_32bit_float(self):
        """Test mono to stereo conversion with 32-bit float audio."""
        # Create mono test data
        mono_data = np.array([0.5, -0.3, 0.7], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = mono_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=2)

        # Read 3 frames
        stereo_data = adapter.read(3)
        stereo_array = np.frombuffer(stereo_data, dtype=np.float32)

        # Should be duplicated: [0.5, 0.5, -0.3, -0.3, 0.7, 0.7]
        expected = np.array([0.5, 0.5, -0.3, -0.3, 0.7, 0.7], dtype=np.float32)
        np.testing.assert_allclose(stereo_array, expected)

    def test_mono_to_stereo_channels_identical(self):
        """Test that mono to stereo produces identical left and right channels."""
        n_frames = 1000
        mono_data = np.random.randint(-32768, 32767, n_frames, dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = mono_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=2)
        stereo_data = adapter.read(n_frames)
        stereo_array = np.frombuffer(stereo_data, dtype=np.int16)

        # Extract left and right channels
        left_channel = stereo_array[0::2]
        right_channel = stereo_array[1::2]

        # Channels should be identical
        np.testing.assert_array_equal(left_channel, right_channel)
        # Both should match original mono
        np.testing.assert_array_equal(left_channel, mono_data)


class TestChannelMixingAdapterSeek:
    """Test seeking behavior."""

    def test_seek_passes_through_to_source(self):
        """Test that seek passes through to source stream."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        adapter.seek(1000)

        assert source._position == 1000

    def test_seek_after_close_raises_error(self):
        """Test that seeking after close raises an error."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        adapter.close()

        with pytest.raises(ValueError):
            adapter.seek(0)

    def test_read_after_seek(self):
        """Test reading after seeking works correctly."""
        # Create test data with different values
        stereo_data = np.array([100, 100, 200, 200, 300, 300], dtype=np.int16)

        source = MockAudioStream(channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=1)

        # Seek to frame 1
        adapter.seek(1)

        # Read should start from frame 1
        mono_data = adapter.read(2)
        mono_array = np.frombuffer(mono_data, dtype=np.int16)

        # Expected: frames 1 and 2 converted to mono
        # Frame 1: (200 + 200) / sqrt(2) ≈ 283
        # Frame 2: (300 + 300) / sqrt(2) ≈ 424
        expected_frame1 = 200 / np.sqrt(2)
        expected_frame2 = 300 / np.sqrt(2)

        assert len(mono_array) == 2
        np.testing.assert_allclose(mono_array[0], expected_frame1, rtol=0.01)
        np.testing.assert_allclose(mono_array[1], expected_frame2, rtol=0.01)


class TestChannelMixingAdapterClose:
    """Test close behavior."""

    def test_close_closes_source(self):
        """Test that closing the adapter closes the source."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        adapter.close()

        assert adapter._closed
        assert source._closed

    def test_read_after_close_raises_error(self):
        """Test that reading after close raises an error."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        adapter.close()

        with pytest.raises(ValueError):
            adapter.read(1024)


class TestChannelMixingAdapterContextManager:
    """Test context manager usage."""

    def test_context_manager_closes_adapter(self):
        """Test that context manager closes the adapter."""
        source = MockAudioStream(channels=2)

        with ChannelMixingAdapter(source, target_channels=1) as adapter:
            assert not adapter._closed
            adapter.read(100)

        assert adapter._closed
        assert source._closed


class TestChannelMixingAdapterEdgeCases:
    """Test edge cases."""

    def test_read_zero_frames(self):
        """Test reading zero frames."""
        source = MockAudioStream(channels=2)
        adapter = ChannelMixingAdapter(source, target_channels=1)

        data = adapter.read(0)

        assert len(data) == 0

    def test_read_empty_source(self):
        """Test reading when source returns empty."""
        source = MockAudioStream(channels=2)
        source._test_data = b''  # Empty source

        adapter = ChannelMixingAdapter(source, target_channels=1)

        data = adapter.read(1024)

        assert len(data) == 0

    def test_multiple_reads(self):
        """Test multiple sequential reads."""
        # Create longer test data
        n_frames = 10
        stereo_data = np.arange(n_frames * 2, dtype=np.int16)

        source = MockAudioStream(channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = ChannelMixingAdapter(source, target_channels=1)

        # Read in chunks
        chunk1 = adapter.read(3)
        chunk2 = adapter.read(3)
        chunk3 = adapter.read(4)

        assert len(np.frombuffer(chunk1, dtype=np.int16)) == 3
        assert len(np.frombuffer(chunk2, dtype=np.int16)) == 3
        assert len(np.frombuffer(chunk3, dtype=np.int16)) == 4
