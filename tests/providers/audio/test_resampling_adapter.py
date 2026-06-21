"""
Unit tests for ResamplingAdapter.

Tests the resampling adapter for converting between different sample rates.
"""

import pytest
import numpy as np
from providers.audio.adapters.resampling_adapter import ResamplingAdapter
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


class TestResamplingAdapterCreation:
    """Test creating ResamplingAdapter instances."""

    def test_create_downsample_adapter(self):
        """Test creating an adapter for downsampling."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        assert adapter.sample_rate == 22050
        assert adapter._target_sample_rate == 22050

    def test_create_upsample_adapter(self):
        """Test creating an adapter for upsampling."""
        source = MockAudioStream(sample_rate=22050)
        adapter = ResamplingAdapter(source, target_sample_rate=44100)

        assert adapter.sample_rate == 44100
        assert adapter._target_sample_rate == 44100

    def test_create_non_rational_ratio(self):
        """Test creating an adapter with non-standard ratio."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=48000)

        assert adapter.sample_rate == 48000

    def test_invalid_target_sample_rate(self):
        """Test that invalid sample rates raise an error."""
        source = MockAudioStream(sample_rate=44100)

        with pytest.raises(ValueError, match="target_sample_rate must be positive"):
            ResamplingAdapter(source, target_sample_rate=0)

        with pytest.raises(ValueError, match="target_sample_rate must be positive"):
            ResamplingAdapter(source, target_sample_rate=-44100)

    def test_same_source_and_target_rate(self):
        """Test that same source and target rates raise an error."""
        source = MockAudioStream(sample_rate=44100)

        with pytest.raises(ValueError, match="No adaptation needed"):
            ResamplingAdapter(source, target_sample_rate=44100)

    def test_custom_beta_parameter(self):
        """Test creating adapter with custom beta parameter."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050, beta=8.0)

        assert adapter._beta == 8.0


class TestResamplingAdapterProperties:
    """Test adapter properties."""

    def test_samplerate_returns_target(self):
        """Test that sample_rate returns the target rate."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        assert adapter.sample_rate == 22050

    def test_other_properties_delegate_to_source(self):
        """Test that other properties delegate to source."""
        source = MockAudioStream(
            sample_rate=44100,
            channels=2,
            width=2,
            duration=123.45
        )
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        assert adapter.channels_qty == 2
        assert adapter.sample_width == 2
        assert adapter.duration_seconds == 123.45

    def test_duration_unchanged_by_resampling(self):
        """Test that duration is unchanged by resampling."""
        source = MockAudioStream(sample_rate=44100, duration=60.0)
        adapter = ResamplingAdapter(source, target_sample_rate=48000)

        # Duration should remain the same (same audio content)
        assert adapter.duration_seconds == 60.0


class TestDownsampling:
    """Test downsampling (reducing sample rate)."""

    def test_downsample_exact_ratio_2_to_1(self):
        """Test downsampling with exact 2:1 ratio."""
        # Create a simple sine wave at source rate
        n_frames = 4410  # 0.1 seconds at 44100 Hz
        t = np.linspace(0, 0.1, n_frames, endpoint=False)
        frequency = 440  # A4 note
        sine_wave = (np.sin(2 * np.pi * frequency * t) * 32767 / 2).astype(np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = sine_wave.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Read the downsampled data
        result = adapter.read(2205)  # Should be approximately half the frames

        # Check we got data
        assert len(result) > 0

        # Convert to array
        result_array = np.frombuffer(result, dtype=np.int16)

        # Should have roughly 2205 frames (might be slightly different due to filtering)
        assert 2000 <= len(result_array) <= 2300

    def test_downsample_preserves_dc_offset(self):
        """Test that downsampling preserves DC offset."""
        # Create constant signal
        n_frames = 4410
        dc_value = 1000
        constant_signal = np.full(n_frames, dc_value, dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = constant_signal.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)
        result = adapter.read(2205)
        result_array = np.frombuffer(result, dtype=np.int16)

        # DC value should be preserved (within some tolerance due to filtering)
        mean_value = np.mean(result_array)
        np.testing.assert_allclose(mean_value, dc_value, rtol=0.1)

    def test_downsample_stereo(self):
        """Test downsampling with stereo audio."""
        # Create stereo test data
        n_frames = 4410
        left_channel = np.full(n_frames, 1000, dtype=np.int16)
        right_channel = np.full(n_frames, 2000, dtype=np.int16)

        stereo_data = np.empty(n_frames * 2, dtype=np.int16)
        stereo_data[0::2] = left_channel
        stereo_data[1::2] = right_channel

        source = MockAudioStream(sample_rate=44100, channels=2, width=2)
        source._test_data = stereo_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)
        result = adapter.read(2205)
        result_array = np.frombuffer(result, dtype=np.int16)

        # Extract channels
        left_resampled = result_array[0::2]
        right_resampled = result_array[1::2]

        # Check channels are preserved separately
        np.testing.assert_allclose(np.mean(left_resampled), 1000, rtol=0.1)
        np.testing.assert_allclose(np.mean(right_resampled), 2000, rtol=0.1)


class TestUpsampling:
    """Test upsampling (increasing sample rate)."""

    def test_upsample_exact_ratio_1_to_2(self):
        """Test upsampling with exact 1:2 ratio."""
        # Create test data
        n_frames = 2205  # 0.1 seconds at 22050 Hz
        t = np.linspace(0, 0.1, n_frames, endpoint=False)
        frequency = 440
        sine_wave = (np.sin(2 * np.pi * frequency * t) * 32767 / 2).astype(np.int16)

        source = MockAudioStream(sample_rate=22050, channels=1, width=2)
        source._test_data = sine_wave.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=44100)

        # Read the upsampled data
        result = adapter.read(4410)

        # Check we got data
        assert len(result) > 0

        # Convert to array
        result_array = np.frombuffer(result, dtype=np.int16)

        # Should have roughly 4410 frames (might be slightly different)
        assert 4200 <= len(result_array) <= 4600

    def test_upsample_preserves_signal_properties(self):
        """Test that upsampling preserves signal properties."""
        # Create constant signal
        n_frames = 2205
        dc_value = 5000
        constant_signal = np.full(n_frames, dc_value, dtype=np.int16)

        source = MockAudioStream(sample_rate=22050, channels=1, width=2)
        source._test_data = constant_signal.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=44100)
        result = adapter.read(4410)
        result_array = np.frombuffer(result, dtype=np.int16)

        # DC value should be preserved
        mean_value = np.mean(result_array)
        np.testing.assert_allclose(mean_value, dc_value, rtol=0.1)


class TestNonRationalRatios:
    """Test resampling with non-rational ratios."""

    def test_44100_to_48000(self):
        """Test common conversion from 44.1kHz to 48kHz."""
        n_frames = 4410
        test_data = np.random.randint(-1000, 1000, n_frames, dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=48000)

        # Read data
        result = adapter.read(4800)  # Approximately 0.1s at 48kHz

        # Check we got data
        assert len(result) > 0

        result_array = np.frombuffer(result, dtype=np.int16)

        # Should have approximately the right number of frames
        assert 4600 <= len(result_array) <= 5000

    def test_48000_to_44100(self):
        """Test common conversion from 48kHz to 44.1kHz."""
        n_frames = 4800
        test_data = np.random.randint(-1000, 1000, n_frames, dtype=np.int16)

        source = MockAudioStream(sample_rate=48000, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=44100)

        # Read data
        result = adapter.read(4410)

        # Check we got data
        assert len(result) > 0

        result_array = np.frombuffer(result, dtype=np.int16)

        # Should have approximately the right number of frames
        assert 4200 <= len(result_array) <= 4600


class TestResamplingFactorCalculation:
    """Test the calculation of resampling factors."""

    def test_factor_calculation_exact_ratio(self):
        """Test factor calculation for exact ratios."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # 44100 -> 22050 should simplify to up=1, down=2
        assert adapter._up_factor == 1
        assert adapter._down_factor == 2

    def test_factor_calculation_simplification(self):
        """Test that factors are simplified using GCD."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=88200)

        # 44100 -> 88200 should simplify to up=2, down=1
        assert adapter._up_factor == 2
        assert adapter._down_factor == 1


class TestResamplingAdapterSeek:
    """Test seeking behavior."""

    def test_seek_calculates_correct_source_position(self):
        """Test that seek calculates the correct source position."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Seek to frame 1000 in adapted format (22050 Hz)
        adapter.seek(1000)

        # Source should be at frame 2000 (44100 Hz)
        assert source._position == 2000

    def test_seek_clears_buffer(self):
        """Test that seek clears the internal buffer."""
        n_frames = 4410
        test_data = np.full(n_frames, 1000, dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Read some data to populate buffer
        adapter.read(100)

        # Seek should clear buffer
        adapter.seek(0)

        # Buffer should be empty
        assert len(adapter._buffer) == 0

    def test_seek_after_close_raises_error(self):
        """Test that seeking after close raises an error."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        adapter.close()

        with pytest.raises(ValueError):
            adapter.seek(0)

    def test_read_after_seek(self):
        """Test reading after seeking."""
        # Create data with different values in different sections
        section1 = np.full(1000, 100, dtype=np.int16)
        section2 = np.full(1000, 200, dtype=np.int16)
        section3 = np.full(1000, 300, dtype=np.int16)
        test_data = np.concatenate([section1, section2, section3])

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Read from beginning
        result1 = adapter.read(100)
        array1 = np.frombuffer(result1, dtype=np.int16)

        # Seek to middle section
        adapter.seek(500)  # Frame 500 at 22050 Hz = frame 1000 at 44100 Hz

        # Read should get data from section2
        result2 = adapter.read(100)
        array2 = np.frombuffer(result2, dtype=np.int16)

        # First read should be around 100
        np.testing.assert_allclose(np.mean(array1), 100, atol=50)

        # Second read should be around 200
        np.testing.assert_allclose(np.mean(array2), 200, atol=50)


class TestResamplingAdapterClose:
    """Test close behavior."""

    def test_close_closes_source(self):
        """Test that closing the adapter closes the source."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        adapter.close()

        assert adapter._closed
        assert source._closed

    def test_read_after_close_raises_error(self):
        """Test that reading after close raises an error."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        adapter.close()

        with pytest.raises(ValueError):
            adapter.read(1024)


class TestResamplingAdapterContextManager:
    """Test context manager usage."""

    def test_context_manager_closes_adapter(self):
        """Test that context manager closes the adapter."""
        source = MockAudioStream(sample_rate=44100)

        with ResamplingAdapter(source, target_sample_rate=22050) as adapter:
            assert not adapter._closed
            adapter.read(100)

        assert adapter._closed
        assert source._closed


class TestResamplingAdapterEdgeCases:
    """Test edge cases."""

    def test_read_zero_frames(self):
        """Test reading zero frames."""
        source = MockAudioStream(sample_rate=44100)
        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        data = adapter.read(0)

        assert len(data) == 0

    def test_read_empty_source(self):
        """Test reading when source returns empty."""
        source = MockAudioStream(sample_rate=44100)
        source._test_data = b''

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        data = adapter.read(1024)

        assert len(data) == 0

    def test_multiple_reads(self):
        """Test multiple sequential reads."""
        n_frames = 10000
        test_data = np.arange(n_frames, dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Read in chunks
        chunk1 = adapter.read(1000)
        chunk2 = adapter.read(1000)
        chunk3 = adapter.read(1000)

        # All chunks should have data
        assert len(chunk1) > 0
        assert len(chunk2) > 0
        assert len(chunk3) > 0

    def test_very_short_file(self):
        """Test with a very short audio file."""
        # Create very short test data (10 frames)
        test_data = np.array([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Should still be able to read (though output may be shorter than requested)
        result = adapter.read(100)

        # Should get some data
        assert len(result) > 0

    def test_read_more_than_available(self):
        """Test reading more frames than available."""
        n_frames = 100
        test_data = np.full(n_frames, 1000, dtype=np.int16)

        source = MockAudioStream(sample_rate=44100, channels=1, width=2)
        source._test_data = test_data.tobytes()

        adapter = ResamplingAdapter(source, target_sample_rate=22050)

        # Request way more than available
        result = adapter.read(10000)

        # Should get whatever is available (not exact, but less than requested)
        result_array = np.frombuffer(result, dtype=np.int16)
        assert 0 < len(result_array) < 10000
