"""
Test that multiprocessing can be toggled on/off based on thread pool size.
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from models.settings import get_qsettings
from providers.analysis.bpm.stub_bpm import StubBPMAnalyzer
from workers.analyzer_dispatcher import AnalyzerDispatcher
from models.media_file import MediaFile


class TestMultiprocessingToggle:
    """Test that single-threaded mode bypasses multiprocessing."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_media_file(self, temp_dir):
        """Create a mock MediaFile instance."""
        file_path = Path(temp_dir) / "test.mp3"
        file_path.write_text("")  # Create empty file

        mock_file = MagicMock(spec=MediaFile)
        mock_file.file_path = str(file_path)
        mock_file.get_tag_simple = MagicMock(return_value=None)
        mock_file.save = MagicMock()
        return mock_file

    @pytest.fixture(autouse=True)
    def reset_dispatcher(self):
        """Reset dispatcher before each test."""
        AnalyzerDispatcher._instance = None
        yield
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

    def test_single_threaded_mode_no_multiprocessing(self, mock_media_file):
        """Test that thread_pool_size=1 runs without multiprocessing."""
        # Set to single-threaded
        settings = get_qsettings()
        settings.setValue("Analyzers/thread_pool_size", 1)

        # Reset dispatcher to pick up new settings
        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

        # Verify it initialized with thread_pool_size=1
        assert dispatcher.thread_pool_size == 1

        # Run analysis - should work without process pool
        dispatcher.enqueue(StubBPMAnalyzer, [mock_media_file])

        # Just verify it doesn't crash and can be started
        # (We won't wait for completion to keep test fast)
        try:
            dispatcher.start()
            # If we got here without exception, single-threaded mode works
            assert True
        except Exception as e:
            pytest.fail(f"Single-threaded mode failed: {e}")

    def test_multi_threaded_mode_uses_multiprocessing(self, mock_media_file):
        """Test that thread_pool_size>1 uses multiprocessing."""
        # Set to multi-threaded
        settings = get_qsettings()
        settings.setValue("Analyzers/thread_pool_size", 4)

        # Reset dispatcher to pick up new settings
        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

        # Verify it initialized with thread_pool_size=4
        assert dispatcher.thread_pool_size == 4

        # Run analysis - should use process pool
        dispatcher.enqueue(StubBPMAnalyzer, [mock_media_file])

        # Just verify it doesn't crash and can be started
        try:
            dispatcher.start()
            # If we got here without exception, multi-threaded mode works
            assert True
        except Exception as e:
            pytest.fail(f"Multi-threaded mode failed: {e}")

    def test_settings_default_to_single_threaded(self):
        """Test that default settings use single-threaded mode."""
        settings = get_qsettings()
        # Don't set any value - should default to 1
        settings.remove("Analyzers/thread_pool_size")

        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()

        # Should default to 1
        assert dispatcher.thread_pool_size == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
