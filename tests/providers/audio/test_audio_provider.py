import pytest
import os
from providers.audio.provider import AudioStreamProvider
from providers.audio.miniaudio_stream import MiniaudioStream
from util.const import PROJECT_ROOT

# Get the path to the fixture audio file
FIXTURE_DIR = os.path.join(PROJECT_ROOT, 'tests', 'fixtures', 'metadata')
AUDIO_FILE_PATH = os.path.join(FIXTURE_DIR, "sample_dtmf_original.flac")

# Expected properties for the sample_dtmf_original.flac file
EXPECTED_SAMPLERATE = 44100
EXPECTED_NCHANNELS = 2
EXPECTED_SAMPLE_WIDTH = 16 // 8  # bits_per_sample from JSON is 16


class TestAudioStreamProvider:
    def test_get_stream_returns_miniaudio_stream_instance(self):
        """
        Verify that AudioStreamProvider.get_stream() returns a valid MiniaudioStream instance.
        """
        stream = AudioStreamProvider.get_stream(AUDIO_FILE_PATH)
        assert isinstance(stream, MiniaudioStream)
        stream.close()

    def test_miniaudio_stream_properties(self):
        """
        Verify that the samplerate, nchannels, and sample_width properties
        of the MiniaudioStream object return the correct values for a known audio file.
        """
        with AudioStreamProvider.get_stream(AUDIO_FILE_PATH) as stream:
            assert stream.samplerate == EXPECTED_SAMPLERATE
            assert stream.nchannels == EXPECTED_NCHANNELS
            assert stream.sample_width == EXPECTED_SAMPLE_WIDTH

    def test_miniaudio_stream_read(self):
        """
        Verify that the read() method returns a non-empty bytes object
        and that the number of bytes is consistent with the number of frames requested.
        """
        with AudioStreamProvider.get_stream(AUDIO_FILE_PATH) as stream:
            n_frames_to_read = 1024
            data = stream.read(n_frames_to_read)
            assert isinstance(data, bytes)
            # Check if data is not empty, unless the file is shorter than n_frames_to_read
            # For this specific file, it should be long enough.
            if n_frames_to_read * stream.nchannels * stream.sample_width > 0:
                 assert len(data) > 0

            expected_bytes = n_frames_to_read * stream.nchannels * stream.sample_width
            # The actual bytes read might be less if end of stream is reached.
            # For this test, we assume we are not at the end of stream for the first read.
            # A more robust test would read a very small number of frames known to be available.
            # However, for a 1.2s file at 44100Hz, 1024 frames is a small amount.
            assert len(data) == expected_bytes

    def test_miniaudio_stream_seek(self):
        """
        Verify that the seek() method correctly moves the stream's position.
        This is tested by seeking to a position, reading some data, and then
        seeking back to the beginning and reading again, comparing the data.
        """
        with AudioStreamProvider.get_stream(AUDIO_FILE_PATH) as stream:
            n_frames_to_read = 512

            # Read initial data
            initial_data = stream.read(n_frames_to_read)
            assert len(initial_data) == n_frames_to_read * stream.nchannels * stream.sample_width

            # Seek forward
            seek_offset_frames = 1000
            stream.seek(seek_offset_frames)

            # Read data after seeking
            data_after_seek = stream.read(n_frames_to_read)
            assert len(data_after_seek) == n_frames_to_read * stream.nchannels * stream.sample_width
            assert data_after_seek != initial_data

            # Seek back to the beginning
            stream.seek(0)

            # Read data from the beginning again
            data_after_seek_back = stream.read(n_frames_to_read)
            assert len(data_after_seek_back) == n_frames_to_read * stream.nchannels * stream.sample_width
            assert data_after_seek_back == initial_data

    def test_miniaudio_stream_read_after_seek_to_end(self):
        """
        Verify reading after seeking beyond the end of the file.
        miniaudio's seek should clamp to the end, and subsequent reads should return empty bytes.
        """
        with AudioStreamProvider.get_stream(AUDIO_FILE_PATH) as stream:
            # Seek to a very large frame number (effectively beyond the end)
            stream.seek(10**6)
            data = stream.read(1024) # Try to read some data
            assert data == b"" # Expect empty bytes as we are at/past the end

    def test_miniaudio_stream_operations_on_closed_stream_raises_error(self):
        """
        Verify that accessing properties or methods of a closed stream raises ValueError.
        """
        stream = AudioStreamProvider.get_stream(AUDIO_FILE_PATH)
        stream.close()

        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.samplerate
        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.nchannels
        with pytest.raises(ValueError, match="Stream is closed."):
            _ = stream.sample_width
        with pytest.raises(ValueError, match="Stream is closed."):
            stream.read(1024)
        with pytest.raises(ValueError, match="Stream is closed."):
            stream.seek(0)
        # Closing again should not raise an error, typically.
        stream.close()
