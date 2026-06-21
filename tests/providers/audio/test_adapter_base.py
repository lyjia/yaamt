"""
Unit tests for AdapterBase.

Tests the base adapter class that implements the decorator pattern for
audio stream adaptation.
"""

import pytest
from providers.audio.adapters.base import AdapterBase
from providers.audio.base import AudioStreamBase


class MockAudioStream(AudioStreamBase):
    """Mock audio stream for testing."""

    def __init__(self, sample_rate=44100, channels=2, width=2, duration=10.0):
        super().__init__()
        self._sample_rate = sample_rate
        self._channels = channels
        self._width = width
        self._duration = duration
        self._closed = False
        self._position = 0

    def read(self, n_frames: int) -> bytes:
        if self._closed:
            raise ValueError("Stream is closed")
        # Return dummy data
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


class SimplePassThroughAdapter(AdapterBase):
    """Simple concrete adapter for testing that just passes through data."""

    def read(self, n_frames: int) -> bytes:
        self._check_closed()
        return self._source.read(n_frames)


class SimpleSeeableAdapter(AdapterBase):
    """Simple concrete adapter that supports seeking."""

    def read(self, n_frames: int) -> bytes:
        self._check_closed()
        return self._source.read(n_frames)

    def seek(self, frame_offset: int) -> None:
        if self._closed:
            raise ValueError("Cannot seek on closed adapter")
        self._source.seek(frame_offset)


class TestAdapterBaseCreation:
    """Test creating AdapterBase instances."""

    def test_create_adapter_with_source(self):
        """Test creating an adapter with a source stream."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        assert adapter._source is source
        assert not adapter._closed

    def test_adapter_wraps_source(self):
        """Test that adapter properly wraps the source stream."""
        source = MockAudioStream(sample_rate=48000, channels=1)
        adapter = SimplePassThroughAdapter(source)

        # Should expose source properties
        assert adapter.sample_rate == 48000
        assert adapter.channels_qty == 1


class TestAdapterBaseProperties:
    """Test adapter properties delegate to source by default."""

    def test_samplerate_property(self):
        """Test that sample_rate delegates to source."""
        source = MockAudioStream(sample_rate=96000)
        adapter = SimplePassThroughAdapter(source)

        assert adapter.sample_rate == 96000

    def test_nchannels_property(self):
        """Test that channels_qty delegates to source."""
        source = MockAudioStream(channels=1)
        adapter = SimplePassThroughAdapter(source)

        assert adapter.channels_qty == 1

    def test_sample_width_property(self):
        """Test that sample_width delegates to source."""
        source = MockAudioStream(width=4)
        adapter = SimplePassThroughAdapter(source)

        assert adapter.sample_width == 4

    def test_duration_seconds_property(self):
        """Test that duration_seconds delegates to source."""
        source = MockAudioStream(duration=123.45)
        adapter = SimplePassThroughAdapter(source)

        assert adapter.duration_seconds == 123.45


class TestAdapterBaseRead:
    """Test the read behavior of adapters."""

    def test_read_delegates_to_source(self):
        """Test that read calls the source stream."""
        source = MockAudioStream(sample_rate=44100, channels=2, width=2)
        adapter = SimplePassThroughAdapter(source)

        # Read 1024 frames
        data = adapter.read(1024)

        # Should return data (even if it's dummy data)
        expected_bytes = 1024 * 2 * 2  # frames * channels * width
        assert len(data) == expected_bytes

    def test_read_after_close_raises_error(self):
        """Test that reading after close raises an error."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        adapter.close()

        with pytest.raises(ValueError, match="closed"):
            adapter.read(1024)


class TestAdapterBaseSeek:
    """Test the seek behavior of adapters."""

    def test_seek_not_implemented_by_default(self):
        """Test that seek raises NotImplementedError by default."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        with pytest.raises(NotImplementedError):
            adapter.seek(0)

    def test_seek_can_be_implemented(self):
        """Test that subclasses can implement seek."""
        source = MockAudioStream()
        adapter = SimpleSeeableAdapter(source)

        # Should not raise
        adapter.seek(1000)
        assert source._position == 1000

    def test_seek_after_close_raises_error(self):
        """Test that seeking after close raises an error."""
        source = MockAudioStream()
        adapter = SimpleSeeableAdapter(source)

        adapter.close()

        with pytest.raises(ValueError, match="closed"):
            adapter.seek(0)


class TestAdapterBaseClose:
    """Test the close behavior of adapters."""

    def test_close_sets_closed_flag(self):
        """Test that close sets the _closed flag."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        assert not adapter._closed

        adapter.close()

        assert adapter._closed

    def test_close_closes_source(self):
        """Test that close closes the source stream."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        adapter.close()

        assert source._closed

    def test_multiple_close_is_safe(self):
        """Test that calling close multiple times is safe."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        adapter.close()
        adapter.close()  # Should not raise

        assert adapter._closed
        assert source._closed


class TestAdapterBaseContextManager:
    """Test the context manager protocol."""

    def test_context_manager_enter(self):
        """Test that __enter__ returns the adapter."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        with adapter as ctx:
            assert ctx is adapter

    def test_context_manager_exit_closes_adapter(self):
        """Test that __exit__ closes the adapter."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        with adapter:
            assert not adapter._closed

        assert adapter._closed
        assert source._closed

    def test_context_manager_with_exception(self):
        """Test that __exit__ closes even with an exception."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        try:
            with adapter:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still be closed
        assert adapter._closed
        assert source._closed

    def test_context_manager_typical_usage(self):
        """Test typical context manager usage pattern."""
        source = MockAudioStream(sample_rate=44100, channels=2, width=2)

        with SimplePassThroughAdapter(source) as adapter:
            # Read some data
            data = adapter.read(1024)
            assert len(data) > 0
            assert not adapter._closed

        # After exiting, should be closed
        assert adapter._closed


class TestAdapterBaseChaining:
    """Test chaining multiple adapters together."""

    def test_chain_two_adapters(self):
        """Test wrapping an adapter with another adapter."""
        source = MockAudioStream(sample_rate=44100)
        adapter1 = SimplePassThroughAdapter(source)
        adapter2 = SimplePassThroughAdapter(adapter1)

        # Should delegate through the chain
        assert adapter2.sample_rate == 44100

        # Reading should work through the chain
        data = adapter2.read(512)
        assert len(data) == 512 * 2 * 2  # frames * channels * width

    def test_chain_close_closes_all(self):
        """Test that closing outer adapter closes the whole chain."""
        source = MockAudioStream()
        adapter1 = SimplePassThroughAdapter(source)
        adapter2 = SimplePassThroughAdapter(adapter1)

        adapter2.close()

        assert adapter2._closed
        assert adapter1._closed
        assert source._closed

    def test_chain_three_adapters(self):
        """Test chaining three adapters together."""
        source = MockAudioStream(sample_rate=48000, channels=1, width=4)
        adapter1 = SimplePassThroughAdapter(source)
        adapter2 = SimplePassThroughAdapter(adapter1)
        adapter3 = SimplePassThroughAdapter(adapter2)

        # Properties should delegate through entire chain
        assert adapter3.sample_rate == 48000
        assert adapter3.channels_qty == 1
        assert adapter3.sample_width == 4

        # Read should work through entire chain
        data = adapter3.read(256)
        expected_bytes = 256 * 1 * 4  # frames * channels * width
        assert len(data) == expected_bytes


class TestAdapterBaseCheckClosed:
    """Test the _check_closed helper method."""

    def test_check_closed_when_open(self):
        """Test that _check_closed doesn't raise when adapter is open."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        # Should not raise
        adapter._check_closed()

    def test_check_closed_when_closed(self):
        """Test that _check_closed raises when adapter is closed."""
        source = MockAudioStream()
        adapter = SimplePassThroughAdapter(source)

        adapter.close()

        with pytest.raises(ValueError, match="closed"):
            adapter._check_closed()
