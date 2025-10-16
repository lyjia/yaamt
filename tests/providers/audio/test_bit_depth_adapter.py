"""
Unit tests for BitDepthAdapter.

Tests the bit depth adapter for converting between different sample widths
and formats (int/float).
"""

import pytest
import numpy as np
from providers.audio.adapters.bit_depth_adapter import BitDepthAdapter
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

        if self._test_data is not None:
            if self._position >= len(self._test_data):
                return b''

            bytes_per_frame = self._channels * self._width
            frames_available = min(
                n_frames,
                (len(self._test_data) - self._position * bytes_per_frame) // bytes_per_frame
            )
            start = self._position * bytes_per_frame
            end = start + (frames_available * bytes_per_frame)
            data = self._test_data[start:end]
            self._position += frames_available
            return data

        bytes_per_frame = self._channels * self._width
        return b'\x00' * (n_frames * bytes_per_frame)

    def seek(self, frame_offset: int) -> None:
        if self._closed:
            raise ValueError("Stream is closed")
        self._position = frame_offset

    def close(self) -> None:
        self._closed = True

    @property
    def samplerate(self) -> int:
        return self._sample_rate

    @property
    def nchannels(self) -> int:
        return self._channels

    @property
    def sample_width(self) -> int:
        return self._width

    @property
    def duration_seconds(self) -> float:
        return self._duration


class TestBitDepthAdapterCreation:
    """Test creating BitDepthAdapter instances."""

    def test_create_16bit_to_32bit_float_adapter(self):
        """Test creating an adapter for 16-bit int to 32-bit float."""
        source = MockAudioStream(width=2)  # 16-bit
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        assert adapter.sample_width == 4
        assert adapter._target_sample_format == 'float'

    def test_create_32bit_float_to_16bit_adapter(self):
        """Test creating an adapter for 32-bit float to 16-bit int."""
        source = MockAudioStream(width=4)  # 32-bit float
        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')

        assert adapter.sample_width == 2
        assert adapter._target_sample_format == 'int'

    def test_create_16bit_to_24bit_adapter(self):
        """Test creating an adapter for 16-bit to 24-bit."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=3, target_sample_format='int')

        assert adapter.sample_width == 3

    def test_invalid_target_sample_width(self):
        """Test that invalid sample widths raise an error."""
        source = MockAudioStream(width=2)

        with pytest.raises(ValueError, match="target_sample_width must be"):
            BitDepthAdapter(source, target_sample_width=5, target_sample_format='int')

    def test_invalid_target_sample_format(self):
        """Test that invalid sample formats raise an error."""
        source = MockAudioStream(width=2)

        with pytest.raises(ValueError, match="target_sample_format must be"):
            BitDepthAdapter(source, target_sample_width=2, target_sample_format='double')

    def test_invalid_float_width(self):
        """Test that non-32-bit float raises an error."""
        source = MockAudioStream(width=2)

        with pytest.raises(ValueError, match="Float format only supports 32-bit"):
            BitDepthAdapter(source, target_sample_width=2, target_sample_format='float')

    def test_same_source_and_target_format(self):
        """Test that same source and target formats raise an error."""
        source = MockAudioStream(width=2)  # 16-bit int

        with pytest.raises(ValueError, match="No adaptation needed"):
            BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')


class TestBitDepthAdapterProperties:
    """Test adapter properties."""

    def test_sample_width_returns_target(self):
        """Test that sample_width returns the target width."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        assert adapter.sample_width == 4

    def test_other_properties_delegate_to_source(self):
        """Test that other properties delegate to source."""
        source = MockAudioStream(
            sample_rate=48000,
            channels=2,
            width=2,
            duration=123.45
        )
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        assert adapter.samplerate == 48000
        assert adapter.nchannels == 2
        assert adapter.duration_seconds == 123.45


class TestInt16ToFloat32:
    """Test conversion from 16-bit int to 32-bit float."""

    def test_int16_to_float32_zero(self):
        """Test conversion of zero."""
        source_data = np.array([0, 0, 0], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')
        result = adapter.read(3)
        result_array = np.frombuffer(result, dtype=np.float32)

        expected = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        np.testing.assert_allclose(result_array, expected, atol=1e-6)

    def test_int16_to_float32_max(self):
        """Test conversion of maximum value."""
        source_data = np.array([32767], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')
        result = adapter.read(1)
        result_array = np.frombuffer(result, dtype=np.float32)

        # Should be approximately 1.0 (32767 / 32768)
        np.testing.assert_allclose(result_array[0], 1.0, rtol=0.001)

    def test_int16_to_float32_min(self):
        """Test conversion of minimum value."""
        source_data = np.array([-32768], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')
        result = adapter.read(1)
        result_array = np.frombuffer(result, dtype=np.float32)

        # Should be exactly -1.0
        np.testing.assert_allclose(result_array[0], -1.0, atol=1e-6)

    def test_int16_to_float32_range(self):
        """Test conversion preserves normalized range."""
        # Test various values
        source_data = np.array([0, 16384, 32767, -16384, -32768], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')
        result = adapter.read(5)
        result_array = np.frombuffer(result, dtype=np.float32)

        # Check all values are in [-1.0, 1.0]
        assert np.all(result_array >= -1.0)
        assert np.all(result_array <= 1.0)

        # Check specific values
        np.testing.assert_allclose(result_array[0], 0.0, atol=1e-6)
        np.testing.assert_allclose(result_array[1], 0.5, rtol=0.01)
        np.testing.assert_allclose(result_array[2], 1.0, rtol=0.001)
        np.testing.assert_allclose(result_array[3], -0.5, rtol=0.01)
        np.testing.assert_allclose(result_array[4], -1.0, atol=1e-6)


class TestFloat32ToInt16:
    """Test conversion from 32-bit float to 16-bit int."""

    def test_float32_to_int16_zero(self):
        """Test conversion of zero."""
        source_data = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(3)
        result_array = np.frombuffer(result, dtype=np.int16)

        expected = np.array([0, 0, 0], dtype=np.int16)
        np.testing.assert_array_equal(result_array, expected)

    def test_float32_to_int16_max(self):
        """Test conversion of maximum value."""
        source_data = np.array([1.0], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(1)
        result_array = np.frombuffer(result, dtype=np.int16)

        # Should be 32767 (maximum 16-bit value)
        assert result_array[0] == 32767

    def test_float32_to_int16_min(self):
        """Test conversion of minimum value."""
        source_data = np.array([-1.0], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(1)
        result_array = np.frombuffer(result, dtype=np.int16)

        # Should be -32767 (scaled from -1.0)
        assert result_array[0] == -32767

    def test_float32_to_int16_clipping(self):
        """Test that out-of-range values are clipped."""
        source_data = np.array([1.5, -1.5, 2.0, -2.0], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(4)
        result_array = np.frombuffer(result, dtype=np.int16)

        # All should be clipped to max/min values
        assert result_array[0] == 32767  # Clipped to max
        assert result_array[1] == -32768  # Clipped to min
        assert result_array[2] == 32767  # Clipped to max
        assert result_array[3] == -32768  # Clipped to min

    def test_float32_to_int16_range(self):
        """Test conversion preserves relative values."""
        source_data = np.array([0.0, 0.5, -0.5, 0.25, -0.25], dtype=np.float32)

        source = MockAudioStream(channels=1, width=4)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(5)
        result_array = np.frombuffer(result, dtype=np.int16)

        # Check approximate values (allowing for rounding)
        assert result_array[0] == 0
        np.testing.assert_allclose(result_array[1], 16383, atol=1)
        np.testing.assert_allclose(result_array[2], -16383, atol=1)
        np.testing.assert_allclose(result_array[3], 8191, atol=1)
        np.testing.assert_allclose(result_array[4], -8191, atol=1)


class TestInt16ToInt24:
    """Test conversion from 16-bit to 24-bit."""

    def test_int16_to_int24_zero(self):
        """Test conversion of zero."""
        source_data = np.array([0, 0, 0], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=3, target_sample_format='int')
        result = adapter.read(3)

        # Parse 24-bit data
        result_bytes = np.frombuffer(result, dtype=np.uint8)
        result_array = np.zeros(3, dtype=np.int32)
        for i in range(3):
            offset = i * 3
            val = int(result_bytes[offset]) | \
                  (int(result_bytes[offset + 1]) << 8) | \
                  (int(result_bytes[offset + 2]) << 16)
            if val & 0x800000:
                val = val - 0x1000000
            result_array[i] = val

        expected = np.array([0, 0, 0], dtype=np.int32)
        np.testing.assert_array_equal(result_array, expected)

    def test_int16_to_int24_scaling(self):
        """Test that 16-bit values are properly scaled to 24-bit."""
        # Max 16-bit: 32767 should scale to roughly max 24-bit: 8388607
        source_data = np.array([32767, -32768], dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=3, target_sample_format='int')
        result = adapter.read(2)

        # Parse 24-bit data
        result_bytes = np.frombuffer(result, dtype=np.uint8)
        result_array = np.zeros(2, dtype=np.int32)
        for i in range(2):
            offset = i * 3
            val = int(result_bytes[offset]) | \
                  (int(result_bytes[offset + 1]) << 8) | \
                  (int(result_bytes[offset + 2]) << 16)
            if val & 0x800000:
                val = val - 0x1000000
            result_array[i] = val

        # Check scaling: should be approximately 8388607 and -8388607
        np.testing.assert_allclose(result_array[0], 8388607, rtol=0.001)
        np.testing.assert_allclose(result_array[1], -8388607, rtol=0.001)


class TestInt24ToInt16:
    """Test conversion from 24-bit to 16-bit."""

    def test_int24_to_int16_scaling(self):
        """Test that 24-bit values are properly scaled down to 16-bit."""
        # Create 24-bit test data
        test_values = [8388607, -8388608, 0]  # Max, min, zero
        source_bytes = bytearray()

        for val in test_values:
            source_bytes.extend([
                val & 0xFF,
                (val >> 8) & 0xFF,
                (val >> 16) & 0xFF
            ])

        source = MockAudioStream(channels=1, width=3)
        source._test_data = bytes(source_bytes)

        adapter = BitDepthAdapter(source, target_sample_width=2, target_sample_format='int')
        result = adapter.read(3)
        result_array = np.frombuffer(result, dtype=np.int16)

        # Check approximate scaling
        np.testing.assert_allclose(result_array[0], 32767, atol=1)
        np.testing.assert_allclose(result_array[1], -32767, atol=1)
        assert result_array[2] == 0


class TestBitDepthAdapterSeek:
    """Test seeking behavior."""

    def test_seek_passes_through_to_source(self):
        """Test that seek passes through to source stream."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        adapter.seek(1000)

        assert source._position == 1000

    def test_seek_after_close_raises_error(self):
        """Test that seeking after close raises an error."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        adapter.close()

        with pytest.raises(ValueError):
            adapter.seek(0)


class TestBitDepthAdapterClose:
    """Test close behavior."""

    def test_close_closes_source(self):
        """Test that closing the adapter closes the source."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        adapter.close()

        assert adapter._closed
        assert source._closed

    def test_read_after_close_raises_error(self):
        """Test that reading after close raises an error."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        adapter.close()

        with pytest.raises(ValueError):
            adapter.read(1024)


class TestBitDepthAdapterContextManager:
    """Test context manager usage."""

    def test_context_manager_closes_adapter(self):
        """Test that context manager closes the adapter."""
        source = MockAudioStream(width=2)

        with BitDepthAdapter(source, target_sample_width=4, target_sample_format='float') as adapter:
            assert not adapter._closed
            adapter.read(100)

        assert adapter._closed
        assert source._closed


class TestBitDepthAdapterEdgeCases:
    """Test edge cases."""

    def test_read_zero_frames(self):
        """Test reading zero frames."""
        source = MockAudioStream(width=2)
        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        data = adapter.read(0)

        assert len(data) == 0

    def test_read_empty_source(self):
        """Test reading when source returns empty."""
        source = MockAudioStream(width=2)
        source._test_data = b''

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        data = adapter.read(1024)

        assert len(data) == 0

    def test_multiple_reads(self):
        """Test multiple sequential reads."""
        source_data = np.arange(100, dtype=np.int16)

        source = MockAudioStream(channels=1, width=2)
        source._test_data = source_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        # Read in chunks
        chunk1 = adapter.read(30)
        chunk2 = adapter.read(30)
        chunk3 = adapter.read(40)

        assert len(np.frombuffer(chunk1, dtype=np.float32)) == 30
        assert len(np.frombuffer(chunk2, dtype=np.float32)) == 30
        assert len(np.frombuffer(chunk3, dtype=np.float32)) == 40

    def test_stereo_conversion(self):
        """Test that bit depth conversion works with stereo audio."""
        # Create stereo 16-bit data
        stereo_data = np.array([1000, 2000, 3000, 4000, 5000, 6000], dtype=np.int16)

        source = MockAudioStream(channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = BitDepthAdapter(source, target_sample_width=4, target_sample_format='float')

        result = adapter.read(3)  # 3 frames = 6 samples
        result_array = np.frombuffer(result, dtype=np.float32)

        # Should have 6 samples (3 frames * 2 channels)
        assert len(result_array) == 6

        # All should be in valid range
        assert np.all(result_array >= -1.0)
        assert np.all(result_array <= 1.0)
