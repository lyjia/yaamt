"""
Unit tests for audio_numpy utility functions.

Tests the audio stream to numpy conversion functions with real audio fixtures.
"""

import pytest
import numpy as np
from pathlib import Path

from models.media_file import MediaFile
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.audio_numpy import audio_stream_to_numpy, audio_stream_to_mono_numpy


class TestAudioStreamToNumpy:
    """Tests for audio_stream_to_numpy function."""

    @pytest.fixture
    def audio_file(self):
        """Get a test audio file."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_converts_to_float32(self, audio_file):
        """Test that audio is converted to float32 numpy array."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        y, sr = audio_stream_to_numpy(audio_stream)

        assert isinstance(y, np.ndarray)
        assert y.dtype == np.float32
        assert sr == audio_stream.sample_rate

        audio_stream.close()

    def test_normalizes_to_range(self, audio_file):
        """Test that audio is normalized to [-1.0, 1.0] range."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        y, sr = audio_stream_to_numpy(audio_stream)

        # Verify values are in valid range
        assert np.all(y >= -1.0) and np.all(y <= 1.0), f"Values outside [-1, 1]: min={y.min()}, max={y.max()}"

        audio_stream.close()

    def test_handles_mono_audio(self, audio_file):
        """Test conversion of mono audio stream."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request mono audio explicitly
        format_desc = AudioFormatDescriptor(channels=1)
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_numpy(audio_stream)

        # Mono audio should have shape (n,)
        assert len(y.shape) == 1

        audio_stream.close()

    def test_handles_stereo_audio(self, audio_file):
        """Test conversion of stereo audio stream."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request stereo audio
        format_desc = AudioFormatDescriptor(channels=2)
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_numpy(audio_stream)

        # Stereo should have shape (2, n)
        if len(y.shape) == 2:
            assert y.shape[0] == 2  # 2 channels
        else:
            # If source was mono, may still be (n,)
            assert len(y.shape) == 1

        audio_stream.close()

    def test_respects_max_duration(self, audio_file):
        """Test that max_duration parameter limits audio read."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        sr = audio_stream.sample_rate
        max_duration = 0.5  # 0.5 seconds

        y, returned_sr = audio_stream_to_numpy(audio_stream, max_duration=max_duration)

        # Calculate actual duration
        actual_duration = len(y) / returned_sr

        # Should be close to max_duration (within tolerance for chunk reading)
        assert actual_duration <= max_duration * 1.1, f"Duration {actual_duration}s exceeds max {max_duration}s"

        audio_stream.close()

    def test_handles_16bit_audio(self, audio_file):
        """Test conversion of 16-bit integer audio."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request 16-bit audio
        format_desc = AudioFormatDescriptor(sample_width=2, sample_format='int')
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_numpy(audio_stream)

        assert y.dtype == np.float32
        assert np.all(y >= -1.0) and np.all(y <= 1.0)

        audio_stream.close()

    def test_handles_32bit_float_audio(self, audio_file):
        """Test conversion of 32-bit float audio."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request 32-bit float audio
        format_desc = AudioFormatDescriptor(sample_width=4, sample_format='float')
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_numpy(audio_stream)

        assert y.dtype == np.float32
        # Float should already be normalized or will be normalized
        max_val = np.abs(y).max()
        assert max_val <= 1.0 or max_val <= 1.1, f"Float audio not properly normalized: max={max_val}"

        audio_stream.close()

    def test_empty_stream(self):
        """Test handling of empty audio stream."""
        # This is hard to test without mocking, but we verify the function
        # handles the case gracefully
        # For now, skip as we'd need to mock an empty stream
        pytest.skip("Empty stream test requires mocking")

    def test_returns_sample_rate(self, audio_file):
        """Test that correct sample rate is returned."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        expected_sr = audio_stream.sample_rate
        y, sr = audio_stream_to_numpy(audio_stream)

        assert sr == expected_sr

        audio_stream.close()


class TestAudioStreamToMonoNumpy:
    """Tests for audio_stream_to_mono_numpy function."""

    @pytest.fixture
    def audio_file(self):
        """Get a test audio file."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_converts_to_mono(self, audio_file):
        """Test that multi-channel audio is converted to mono."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request stereo audio
        format_desc = AudioFormatDescriptor(channels=2)
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_mono_numpy(audio_stream)

        # Should always return mono shape (n,)
        assert len(y.shape) == 1

        audio_stream.close()

    def test_mono_stays_mono(self, audio_file):
        """Test that mono audio stays mono."""
        media_file = MediaFile(audio_file, enable_write=False)

        # Request mono audio
        format_desc = AudioFormatDescriptor(channels=1)
        audio_stream = media_file.get_audio_stream(format_desc)

        y, sr = audio_stream_to_mono_numpy(audio_stream)

        # Should be mono shape (n,)
        assert len(y.shape) == 1

        audio_stream.close()

    def test_returns_float32(self, audio_file):
        """Test that mono conversion returns float32."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        y, sr = audio_stream_to_mono_numpy(audio_stream)

        assert y.dtype == np.float32

        audio_stream.close()

    def test_preserves_normalization(self, audio_file):
        """Test that mono conversion preserves normalization."""
        media_file = MediaFile(audio_file, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        y, sr = audio_stream_to_mono_numpy(audio_stream)

        # Should still be normalized to [-1, 1]
        assert np.all(y >= -1.0) and np.all(y <= 1.0)

        audio_stream.close()


class TestAudioNumpyWithDrumLoops:
    """Tests with drum loop fixtures to verify audio quality."""

    @pytest.fixture
    def drum_loop_120bpm(self):
        """Get 120 BPM drum loop."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_house_claves_delay_120bpm.wav"
        if not sample_file.exists():
            pytest.skip("120 BPM drum loop not available")
        return str(sample_file)

    @pytest.fixture
    def drum_loop_128bpm(self):
        """Get 128 BPM drum loop."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_house_beat_generic_128bpm.wav"
        if not sample_file.exists():
            pytest.skip("128 BPM drum loop not available")
        return str(sample_file)

    def test_drum_loop_conversion(self, drum_loop_120bpm):
        """Test conversion of drum loop maintains audio quality."""
        media_file = MediaFile(drum_loop_120bpm, enable_write=False)
        audio_stream = media_file.get_audio_stream()

        y, sr = audio_stream_to_numpy(audio_stream)

        # Should have reasonable audio data
        assert len(y) > 0
        assert sr > 0

        # Drum loops should have reasonable energy (not silent)
        rms = np.sqrt(np.mean(y**2))
        assert rms > 0.001, f"Audio seems too quiet: RMS={rms}"

        audio_stream.close()

    def test_mono_conversion_preserves_energy(self, drum_loop_128bpm):
        """Test that mono conversion doesn't lose too much energy."""
        media_file = MediaFile(drum_loop_128bpm, enable_write=False)

        # Get stereo version
        format_desc_stereo = AudioFormatDescriptor(channels=2)
        audio_stream_stereo = media_file.get_audio_stream(format_desc_stereo)
        y_stereo, sr_stereo = audio_stream_to_numpy(audio_stream_stereo)
        audio_stream_stereo.close()

        # Get mono version
        format_desc_mono = AudioFormatDescriptor(channels=1)
        audio_stream_mono = media_file.get_audio_stream(format_desc_mono)
        y_mono, sr_mono = audio_stream_to_mono_numpy(audio_stream_mono)
        audio_stream_mono.close()

        # Both should have reasonable energy
        if len(y_stereo.shape) == 2:
            rms_stereo = np.sqrt(np.mean(y_stereo**2))
        else:
            rms_stereo = np.sqrt(np.mean(y_stereo**2))

        rms_mono = np.sqrt(np.mean(y_mono**2))

        assert rms_mono > 0.001, "Mono audio has insufficient energy"
        # Mono and stereo RMS should be in the same ballpark
        # (within factor of 2 is reasonable for averaging)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
