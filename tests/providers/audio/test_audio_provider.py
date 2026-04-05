import pytest
import os
import glob
from providers.audio.factory import AudioStreamFactory
from providers.audio.miniaudio_stream import MiniaudioStream
from util.const import PROJECT_ROOT

# Get the path to the fixture audio file
FIXTURE_DIR = os.path.join(PROJECT_ROOT, 'tests', 'fixtures', 'metadata')
AUDIO_FILE_PATH = os.path.join(FIXTURE_DIR, "sample_dtmf_original.flac")
AUDIO_FILE_24BIT = os.path.join(FIXTURE_DIR, "lyjia_dnb019_175bpm.wav")

# Expected properties for the sample_dtmf_original.flac file
EXPECTED_SAMPLERATE = 44100
EXPECTED_NCHANNELS = 2
EXPECTED_SAMPLE_WIDTH = 16 // 8  # bits_per_sample from JSON is 16


class TestAudioStreamBase:
    def test_get_stream_returns_miniaudio_stream_instance(self):
        """
        Verify that AudioStreamBase.get_stream() returns a valid MiniaudioStream instance.
        """
        stream = AudioStreamFactory.get_stream(AUDIO_FILE_PATH)
        assert isinstance(stream, MiniaudioStream)
        stream.close()

    def test_miniaudio_stream_properties(self):
        """
        Verify that the sample_rate, channels_qty, and sample_width properties
        of the MiniaudioStream object return the correct values for a known audio file.
        """
        with AudioStreamFactory.get_stream(AUDIO_FILE_PATH) as stream:
            assert stream.sample_rate == EXPECTED_SAMPLERATE
            assert stream.channels_qty == EXPECTED_NCHANNELS
            assert stream.sample_width == EXPECTED_SAMPLE_WIDTH

    def test_miniaudio_stream_read(self):
        """
        Verify that the read() method returns a non-empty bytes object.
        """
        with AudioStreamFactory.get_stream(AUDIO_FILE_PATH) as stream:
            data = stream.read(1024)  # n_frames is not used anymore, but kept for compatibility
            assert isinstance(data, bytes)
            assert len(data) > 0

    def test_miniaudio_stream_seek(self):
        """
        Verify that the seek() method correctly moves the stream's position.
        This is tested by seeking to a position, reading some data, and then
        seeking back to the beginning and reading again, comparing the data.
        """
        with AudioStreamFactory.get_stream(AUDIO_FILE_PATH) as stream:
            # Read initial data
            initial_data = stream.read(512)
            assert len(initial_data) > 0

            # Seek forward
            seek_offset_frames = 1000
            stream.seek(seek_offset_frames)

            # Read data after seeking
            data_after_seek = stream.read(512)
            assert len(data_after_seek) > 0
            assert data_after_seek != initial_data

            # Seek back to the beginning
            stream.seek(0)

            # Read data from the beginning again
            data_after_seek_back = stream.read(512)
            assert len(data_after_seek_back) > 0
            assert data_after_seek_back == initial_data

    def test_miniaudio_stream_read_after_seek_to_end(self):
        """
        Verify reading after seeking beyond the end of the file.
        miniaudio's seek should clamp to the end, and subsequent reads should return empty bytes.
        """
        with AudioStreamFactory.get_stream(AUDIO_FILE_PATH) as stream:
            # Seek to a very large frame number (effectively beyond the end)
            stream.seek(10**6)
            data = stream.read(512) # Try to read some data
            assert data == b"" # Expect empty bytes as we are at/past the end

    def test_miniaudio_stream_operations_on_closed_stream_raises_error(self):
        """
        Verify that accessing properties or methods of a closed stream raises ValueError.
        """
        stream = AudioStreamFactory.get_stream(AUDIO_FILE_PATH)
        stream.close()

        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.sample_rate
        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.channels_qty
        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.sample_width
        with pytest.raises(ValueError, match="Stream is closed."):
            stream.read(0)
        with pytest.raises(ValueError, match="Stream is closed."):
            stream.seek(0)
        # Closing again should not raise an error, typically.
        stream.close()


class TestMiniaudioStreamFormatConsistency:
    """Tests that MiniaudioStream reports format properties matching its actual bytes."""

    def test_24bit_source_reports_float32_width(self):
        """
        24-bit sources are promoted to float32 (width=4) since miniaudio cannot
        stream SIGNED24 directly.
        """
        with MiniaudioStream(AUDIO_FILE_24BIT) as stream:
            assert stream.sample_width == 4
            assert stream.channels_qty == 2
            assert stream.sample_rate == 44100

    def test_24bit_source_read_returns_correct_byte_count(self):
        """
        read(n_frames) must return exactly n_frames * channels * sample_width bytes.
        """
        with MiniaudioStream(AUDIO_FILE_24BIT) as stream:
            expected = 1024 * stream.channels_qty * stream.sample_width
            data = stream.read(1024)
            assert len(data) == expected

    def test_16bit_source_reports_int16_width(self):
        """16-bit sources stay as int16 (width=2) — no promotion needed."""
        with MiniaudioStream(AUDIO_FILE_PATH) as stream:
            assert stream.sample_width == 2
            assert stream.channels_qty == 2
            assert stream.sample_rate == 44100

    def test_full_read_byte_alignment_24bit(self):
        """
        Reading a 24-bit file to EOF must never produce a chunk whose length
        is not a multiple of (channels * sample_width). This is the exact
        scenario that triggered the original reshape crash.
        """
        with MiniaudioStream(AUDIO_FILE_24BIT) as stream:
            frame_size = stream.channels_qty * stream.sample_width
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                assert len(chunk) % frame_size == 0, (
                    f"Chunk of {len(chunk)} bytes is not aligned to "
                    f"frame size {frame_size}"
                )

    def test_full_read_byte_alignment_16bit(self):
        """Same alignment check for 16-bit files."""
        with MiniaudioStream(AUDIO_FILE_PATH) as stream:
            frame_size = stream.channels_qty * stream.sample_width
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                assert len(chunk) % frame_size == 0

    def test_no_fixture_reports_width_3(self):
        """
        MiniaudioStream should never report sample_width=3, since SIGNED24 is
        not streamable by miniaudio and is promoted to FLOAT32 (width=4).
        """
        audio_extensions = ('*.wav', '*.flac', '*.mp3', '*.ogg', '*.m4a')
        fixture_files = []
        for ext in audio_extensions:
            fixture_files.extend(
                glob.glob(os.path.join(FIXTURE_DIR, ext))
            )

        assert len(fixture_files) > 0, "No fixture files found"

        for filepath in fixture_files:
            with MiniaudioStream(filepath) as stream:
                assert stream.sample_width in (1, 2, 4), (
                    f"{os.path.basename(filepath)} reports "
                    f"sample_width={stream.sample_width}, expected 1, 2, or 4"
                )
