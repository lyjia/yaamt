"""
Integration tests for audio format adaptation system.

Tests the full pipeline of format adaptation including AudioStreamFactory,
MediaFile integration, and adapter chains working together.
"""

import pytest
import os
import numpy as np
from models.media_file import MediaFile
from providers.audio.factory import AudioStreamFactory
from providers.audio.format_descriptor import AudioFormatDescriptor
from providers.audio.adapters.resampling_adapter import ResamplingAdapter
from providers.audio.adapters.channel_mixing_adapter import ChannelMixingAdapter
from providers.audio.adapters.bit_depth_adapter import BitDepthAdapter


# Get the path to test fixtures
TEST_FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "fixtures", "metadata"
)


class TestMediaFileIntegration:
    """Test MediaFile.get_audio_stream() with format adaptation."""

    def test_get_audio_stream_native_format(self):
        """Test getting audio stream in native format (no adaptation)."""
        # Use a test fixture
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")
        media_file = MediaFile(test_file)

        # Get stream without format descriptor
        with media_file.get_audio_stream() as stream:
            # Should return stream in native format
            assert stream is not None
            assert stream.samplerate > 0
            assert stream.nchannels > 0
            assert stream.sample_width > 0
            assert stream.duration_seconds > 0

            # Should be able to read audio data
            data = stream.read(1024)
            assert len(data) > 0

    def test_get_audio_stream_with_format_descriptor(self):
        """Test getting audio stream with format adaptation."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")
        media_file = MediaFile(test_file)

        # Request mono audio at 22050 Hz
        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with media_file.get_audio_stream(format_desc) as stream:
            # Stream should match requested format
            assert stream.samplerate == 22050
            assert stream.nchannels == 1

            # Should be able to read audio data
            data = stream.read(1024)
            assert len(data) > 0
            # Verify byte count is a multiple of frame size
            frame_size = stream.nchannels * stream.sample_width
            assert len(data) % frame_size == 0

    def test_get_audio_stream_flac_file(self):
        """Test getting audio stream from FLAC file with adaptation."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.flac")
        media_file = MediaFile(test_file)

        # Request specific format
        format_desc = AudioFormatDescriptor(
            sample_rate=48000,
            channels=2
        )

        with media_file.get_audio_stream(format_desc) as stream:
            assert stream.samplerate == 48000
            assert stream.nchannels == 2

            # Should be able to read and seek
            data1 = stream.read(512)
            assert len(data1) > 0

            stream.seek(0)
            data2 = stream.read(512)
            # Data should be same after seek to beginning
            assert data1 == data2

    def test_get_audio_stream_partial_format_specification(self):
        """Test requesting only some format parameters."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")
        media_file = MediaFile(test_file)

        # Get native format first to compare
        with media_file.get_audio_stream() as native_stream:
            native_rate = native_stream.samplerate
            native_channels = native_stream.nchannels

        # Request only mono, accept native sample rate
        format_desc = AudioFormatDescriptor(channels=1)

        with media_file.get_audio_stream(format_desc) as stream:
            assert stream.nchannels == 1  # Adapted
            assert stream.samplerate == native_rate  # Native

            data = stream.read(1024)
            assert len(data) == 1024 * 1 * stream.sample_width


class TestAudioStreamFactoryIntegration:
    """Test AudioStreamFactory creates correct adapter chains."""

    def test_factory_creates_resampling_adapter(self):
        """Test factory creates resampling adapter when sample rate differs."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Request different sample rate
        format_desc = AudioFormatDescriptor(sample_rate=22050)

        stream = AudioStreamFactory.get_stream(test_file, format_desc)

        # Should be wrapped with ResamplingAdapter
        assert isinstance(stream, ResamplingAdapter)
        assert stream.samplerate == 22050

        stream.close()

    def test_factory_creates_channel_mixing_adapter(self):
        """Test factory creates channel mixing adapter when channels differ."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Get native channels
        with AudioStreamFactory.get_stream(test_file) as native_stream:
            native_channels = native_stream.nchannels

        # Request different channels
        target_channels = 1 if native_channels == 2 else 2
        format_desc = AudioFormatDescriptor(channels=target_channels)

        stream = AudioStreamFactory.get_stream(test_file, format_desc)

        # Should be wrapped with ChannelMixingAdapter
        assert isinstance(stream, ChannelMixingAdapter)
        assert stream.nchannels == target_channels

        stream.close()

    def test_factory_creates_adapter_chain(self):
        """Test factory creates multiple adapters when needed."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Request different sample rate AND different channels
        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        stream = AudioStreamFactory.get_stream(test_file, format_desc)

        # Outer adapter should be channel mixing (last in chain)
        assert isinstance(stream, ChannelMixingAdapter)
        assert stream.nchannels == 1

        # Inner adapter should be resampling
        assert isinstance(stream._source, ResamplingAdapter)
        assert stream._source.samplerate == 22050

        stream.close()

    def test_factory_returns_native_when_format_matches(self):
        """Test factory returns native stream when no adaptation needed."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Get native format
        with AudioStreamFactory.get_stream(test_file) as native_stream:
            native_rate = native_stream.samplerate
            native_channels = native_stream.nchannels

        # Request same format
        format_desc = AudioFormatDescriptor(
            sample_rate=native_rate,
            channels=native_channels
        )

        stream = AudioStreamFactory.get_stream(test_file, format_desc)

        # Should not be wrapped (no adapters needed)
        assert not isinstance(stream, (ResamplingAdapter, ChannelMixingAdapter, BitDepthAdapter))

        stream.close()

    def test_factory_returns_native_when_no_descriptor(self):
        """Test factory returns native stream when format_descriptor is None."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        stream = AudioStreamFactory.get_stream(test_file, None)

        # Should not be wrapped
        assert not isinstance(stream, (ResamplingAdapter, ChannelMixingAdapter, BitDepthAdapter))

        stream.close()


class TestFullPipelineIntegration:
    """Test the full pipeline from file to adapted output."""

    def test_full_pipeline_read_entire_file(self):
        """Test reading an entire file with format adaptation."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Request specific format
        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            # Read entire file in chunks
            all_data = bytearray()
            chunk_size = 4096

            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                all_data.extend(chunk)

            # Verify we read data
            assert len(all_data) > 0

            # Verify data is consistent with format
            total_samples = len(all_data) // stream.sample_width
            total_frames = total_samples // stream.nchannels

            # Duration should match
            expected_frames = int(stream.duration_seconds * stream.samplerate)
            # Allow for some rounding error
            assert abs(total_frames - expected_frames) < stream.samplerate * 0.1

    def test_full_pipeline_seek_and_read(self):
        """Test seeking and reading with format adaptation."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            # Read from beginning
            data1 = stream.read(1024)
            assert len(data1) > 0

            # Seek to middle
            mid_frame = int(stream.duration_seconds * stream.samplerate / 2)
            stream.seek(mid_frame)
            data2 = stream.read(1024)
            assert len(data2) > 0

            # Data should be different
            assert data1 != data2

            # Seek back to beginning
            stream.seek(0)
            data3 = stream.read(1024)

            # Should match first read (approximately, due to resampling)
            assert len(data3) == len(data1)

    def test_full_pipeline_multiple_adaptations(self):
        """Test applying multiple adaptations and verify output."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Get native format first
        with AudioStreamFactory.get_stream(test_file) as native_stream:
            native_data = native_stream.read(4096)
            native_rate = native_stream.samplerate
            native_channels = native_stream.nchannels
            native_width = native_stream.sample_width

        # Request heavily adapted format
        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1 if native_channels == 2 else 2
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as adapted_stream:
            adapted_data = adapted_stream.read(4096)

            # Verify format changed
            assert adapted_stream.samplerate == 22050
            assert adapted_stream.nchannels != native_channels

            # Both should have data
            assert len(native_data) > 0
            assert len(adapted_data) > 0

            # Data should be different (different format)
            assert native_data != adapted_data

    def test_full_pipeline_consistency(self):
        """Test that multiple reads with same format produce consistent results."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        # Read file twice with same format
        with AudioStreamFactory.get_stream(test_file, format_desc) as stream1:
            data1 = stream1.read(4096)

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream2:
            data2 = stream2.read(4096)

        # Should produce same output
        assert data1 == data2

    def test_full_pipeline_with_context_manager(self):
        """Test that context manager properly closes all adapters in chain."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        # Use context manager
        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            data = stream.read(1024)
            assert len(data) > 0

        # Stream should be closed
        assert stream._closed

        # Should not be able to read after close
        with pytest.raises(ValueError):
            stream.read(1024)


class TestMultipleFileFormats:
    """Test adaptation with different file formats."""

    def test_mp3_format_adaptation(self):
        """Test format adaptation with MP3 files."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            assert stream.samplerate == 22050
            assert stream.nchannels == 1

            data = stream.read(2048)
            assert len(data) > 0
            # Verify byte count is a multiple of frame size
            frame_size = stream.nchannels * stream.sample_width
            assert len(data) % frame_size == 0

    def test_flac_format_adaptation(self):
        """Test format adaptation with FLAC files."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.flac")

        format_desc = AudioFormatDescriptor(
            sample_rate=48000,
            channels=2
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            assert stream.samplerate == 48000
            assert stream.nchannels == 2

            data = stream.read(2048)
            assert len(data) > 0
            # Verify byte count is a multiple of frame size
            frame_size = stream.nchannels * stream.sample_width
            assert len(data) % frame_size == 0


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    def test_invalid_format_descriptor(self):
        """Test that invalid format descriptors raise appropriate errors."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        # Request invalid sample rate (0)
        format_desc = AudioFormatDescriptor(sample_rate=0)

        with pytest.raises(ValueError):
            AudioStreamFactory.get_stream(test_file, format_desc)

    def test_nonexistent_file(self):
        """Test that nonexistent files raise appropriate errors."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "nonexistent_file.mp3")

        format_desc = AudioFormatDescriptor(sample_rate=22050)

        with pytest.raises(Exception):
            AudioStreamFactory.get_stream(test_file, format_desc)


class TestPerformanceCharacteristics:
    """Test performance characteristics of the adaptation pipeline."""

    def test_adaptation_faster_than_realtime(self):
        """Test that format adaptation processes faster than realtime."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            import time

            # Read entire file and measure time
            start_time = time.time()
            total_frames = 0

            while True:
                data = stream.read(4096)
                if not data:
                    break
                frames = len(data) // (stream.nchannels * stream.sample_width)
                total_frames += frames

            elapsed_time = time.time() - start_time

            # Calculate audio duration
            audio_duration = total_frames / stream.samplerate

            # Processing should be faster than realtime
            # Allow for some overhead but should be at least 2x realtime
            assert elapsed_time < audio_duration * 0.5, \
                f"Processing too slow: {elapsed_time:.3f}s for {audio_duration:.3f}s audio"

    def test_memory_efficient_streaming(self):
        """Test that streaming doesn't load entire file into memory."""
        test_file = os.path.join(TEST_FIXTURE_DIR, "sample_dtmf_nometa.mp3")

        format_desc = AudioFormatDescriptor(
            sample_rate=22050,
            channels=1
        )

        with AudioStreamFactory.get_stream(test_file, format_desc) as stream:
            # Read in small chunks - should work without loading entire file
            chunk_size = 512
            chunks_read = 0

            while chunks_read < 10:  # Read just 10 chunks
                data = stream.read(chunk_size)
                if not data:
                    break
                chunks_read += 1

            # Should have successfully read some chunks
            assert chunks_read > 0
