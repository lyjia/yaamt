"""
Test parallel analyzer execution functionality.

This module tests the multi-threading capabilities of the analyzer dispatcher.
"""

import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings, QCoreApplication
from PySide6.QtWidgets import QApplication

from providers.analysis.base import AnalyzerBase, AnalyzerResult
from providers.analysis import AnalyzerCategory
from providers import register_analyzer
from workers.analyzer_dispatcher import AnalyzerDispatcher
from models.media_file import MediaFile


class SlowTestAnalyzer(AnalyzerBase):
    """Test analyzer that simulates slow processing."""

    name = "Slow Test Analyzer"
    description = "Analyzer for testing parallel execution"
    category = "test"
    version = "1.0.0"

    processing_time = 0.1  # seconds

    def analyze(self) -> AnalyzerResult:
        """Simulate slow analysis."""
        # Simulate processing time
        time.sleep(self.processing_time)

        return AnalyzerResult(
            success=True,
            data={'test_value': 42}
        )

    @classmethod
    def get_thread_count(cls, options=None) -> int:
        """Return thread count from options or default to 1."""
        if options and 'thread_count' in options:
            return options['thread_count']
        return 1


class TestParallelAnalyzerExecution:
    """Test parallel execution of analyzers."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_media_files(self, temp_dir):
        """Create mock MediaFile instances."""
        files = []
        for i in range(10):
            file_path = Path(temp_dir) / f"test_{i}.mp3"
            file_path.write_text("")  # Create empty file

            mock_file = MagicMock(spec=MediaFile)
            mock_file.file_path = str(file_path)
            mock_file.get_tag_simple.return_value = None
            mock_file.save = MagicMock()
            mock_file.get_tag_simple = MagicMock(return_value=None)
            files.append(mock_file)

        return files

    @pytest.fixture(autouse=True)
    def reset_dispatcher(self):
        """Reset dispatcher before each test."""
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()
        yield
        dispatcher.reset()

    def test_analyzer_thread_count_default(self):
        """Test that analyzer returns default thread count."""
        assert SlowTestAnalyzer.get_thread_count() == 1

    def test_analyzer_thread_count_with_options(self):
        """Test that analyzer returns thread count from options."""
        assert SlowTestAnalyzer.get_thread_count({'thread_count': 4}) == 4

    def test_dispatcher_loads_thread_pool_size(self):
        """Test that dispatcher loads thread pool size from settings."""
        # Set a specific value in settings
        settings = QSettings("Lyjia", "Audio Metadata Tool")
        settings.setValue("Analyzers/thread_pool_size", 4)

        # Create new dispatcher instance (reset singleton)
        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()

        assert dispatcher.thread_pool_size == 4

    # def test_parallel_execution_faster_than_sequential(self, mock_media_files):
    #     """Test that parallel execution is faster than sequential."""
    #     # Configure for sequential execution (1 thread)
    #     settings = QSettings("Lyjia", "Audio Metadata Tool")
    #     settings.setValue("Analyzers/thread_pool_size", 1)

    #     AnalyzerDispatcher._instance = None
    #     dispatcher_seq = AnalyzerDispatcher()
    #     dispatcher_seq.reset()

    #     # Track completion for sequential
    #     seq_completed = False

    #     def seq_complete():
    #         nonlocal seq_completed
    #         seq_completed = True

    #     dispatcher_seq.analysis_completed.connect(seq_complete)

    #     # Time sequential execution
    #     dispatcher_seq.enqueue(SlowTestAnalyzer, mock_media_files[:4])

    #     start_time = time.time()
    #     dispatcher_seq.start()

    #     # Wait for completion (with timeout)
    #     timeout = 2.0
    #     while not seq_completed and (time.time() - start_time) < timeout:
    #         QCoreApplication.processEvents()
    #         time.sleep(0.01)

    #     sequential_time = time.time() - start_time
    #     seq_completed_count = len(dispatcher_seq.completed_tasks)

    #     # Debug output
    #     print(f"Sequential: completed={seq_completed}, count={seq_completed_count}, time={sequential_time:.2f}s")

    #     # Configure for parallel execution (4 threads)
    #     settings.setValue("Analyzers/thread_pool_size", 4)

    #     AnalyzerDispatcher._instance = None
    #     dispatcher_par = AnalyzerDispatcher()
    #     dispatcher_par.reset()

    #     # Track completion for parallel
    #     par_completed = False

    #     def par_complete():
    #         nonlocal par_completed
    #         par_completed = True

    #     dispatcher_par.analysis_completed.connect(par_complete)

    #     # Time parallel execution
    #     dispatcher_par.enqueue(SlowTestAnalyzer, mock_media_files[:4])

    #     start_time = time.time()
    #     dispatcher_par.start()

    #     # Wait for completion
    #     while not par_completed and (time.time() - start_time) < timeout:
    #         QCoreApplication.processEvents()
    #         time.sleep(0.01)

    #     parallel_time = time.time() - start_time
    #     par_completed_count = len(dispatcher_par.completed_tasks)

    #     # Debug output
    #     print(f"Parallel: completed={par_completed}, count={par_completed_count}, time={parallel_time:.2f}s")

    #     # Both should complete all tasks
    #     assert seq_completed_count == 4, f"Sequential only completed {seq_completed_count}/4"
    #     assert par_completed_count == 4, f"Parallel only completed {par_completed_count}/4"

    #     # Parallel should be significantly faster (at least 2x for 4 tasks with 4 threads)
    #     # Sequential: 4 tasks * 0.1s = 0.4s minimum
    #     # Parallel: 1 batch * 0.1s = 0.1s minimum (all 4 run at once)
    #     assert parallel_time < sequential_time * 0.5, \
    #         f"Parallel ({parallel_time:.2f}s) not faster than sequential ({sequential_time:.2f}s)"

    def test_active_tasks_tracking(self, mock_media_files):
        """Test that active tasks are correctly tracked."""
        settings = QSettings("Lyjia", "Audio Metadata Tool")
        settings.setValue("Analyzers/thread_pool_size", 3)

        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

        active_tasks_emitted = []

        def capture_active_tasks(tasks):
            active_tasks_emitted.append(len(tasks))

        dispatcher.active_tasks_updated.connect(capture_active_tasks)

        # Enqueue tasks
        dispatcher.enqueue(SlowTestAnalyzer, mock_media_files[:5])
        dispatcher.start()

        # Let it run for a bit
        timeout = 5.0
        start_time = time.time()
        while dispatcher._is_running and (time.time() - start_time) < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # Should have emitted active task updates
        assert len(active_tasks_emitted) > 0, "No active tasks updates emitted"

        # Should have had multiple tasks active at once (up to 3)
        max_concurrent = max(active_tasks_emitted)
        assert max_concurrent <= 3, f"Too many concurrent tasks: {max_concurrent}"
        assert max_concurrent > 1, f"Not enough concurrent tasks: {max_concurrent}"

    def test_thread_allocation_with_multi_thread_analyzer(self, mock_media_files):
        """Test thread allocation when analyzer needs multiple threads."""

        # Configure analyzer to need 2 threads per instance
        multi_thread_options = {'thread_count': 2}

        settings = QSettings("Lyjia", "Audio Metadata Tool")
        settings.setValue("Analyzers/thread_pool_size", 4)

        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

        max_concurrent = 0

        def track_concurrent(tasks):
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, len(tasks))

        dispatcher.active_tasks_updated.connect(track_concurrent)

        # Enqueue with multi-thread options
        dispatcher.enqueue(SlowTestAnalyzer, mock_media_files[:6], multi_thread_options)
        dispatcher.start()

        # Let it run
        timeout = 5.0
        start_time = time.time()
        while dispatcher._is_running and (time.time() - start_time) < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # With 4 threads and 2 threads per analyzer, should run max 2 concurrent
        assert max_concurrent <= 2, f"Too many concurrent with 2-thread analyzers: {max_concurrent}"

    def test_dispatcher_respects_thread_limit(self, mock_media_files):
        """Test that dispatcher never exceeds configured thread limit."""
        settings = QSettings("Lyjia", "Audio Metadata Tool")
        settings.setValue("Analyzers/thread_pool_size", 2)

        AnalyzerDispatcher._instance = None
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()

        # Track threads in use
        max_threads_used = 0

        def check_thread_usage(tasks):
            nonlocal max_threads_used
            # Each task uses 1 thread (default)
            threads_in_use = len(tasks)
            max_threads_used = max(max_threads_used, threads_in_use)

        dispatcher.active_tasks_updated.connect(check_thread_usage)

        # Enqueue many tasks
        dispatcher.enqueue(SlowTestAnalyzer, mock_media_files)
        dispatcher.start()

        # Let it run
        timeout = 5.0
        start_time = time.time()
        while dispatcher._is_running and (time.time() - start_time) < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # Should never exceed the limit
        assert max_threads_used <= 2, f"Exceeded thread limit: {max_threads_used} > 2"


if __name__ == "__main__":
    # Ensure QApplication exists for tests
    if not QApplication.instance():
        app = QApplication([])

    pytest.main([__file__, "-v"])