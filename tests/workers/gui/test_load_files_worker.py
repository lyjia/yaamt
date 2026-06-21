import os
import tempfile
import pytest
from pathlib import Path
from PySide6.QtCore import QEventLoop, QTimer

from workers.gui.load_files_worker import LoadFilesWorker
from util.const import (
    KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_CTIME,
    KEY_FILE_TYPE, KEY_IS_MEDIA, KEY_FILE_ID, KEY_TITLE, KEY_ARTIST,
    KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_INITIAL_KEY, LOADING_PLACEHOLDER,
    IN_GITHUB_RUNNER
)


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some dummy files
        for i in range(5):
            Path(tmpdir, f"test_file_{i}.txt").write_text(f"content {i}")
        yield tmpdir


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_worker_signals_exist():
    """Test that LoadFilesWorker has the expected signals."""
    worker = LoadFilesWorker("/fake/path")

    assert hasattr(worker.signals, 'finished')
    assert hasattr(worker.signals, 'progress')
    assert hasattr(worker.signals, 'result')
    assert hasattr(worker.signals, 'files_discovered')
    assert hasattr(worker.signals, 'file_updated')
    assert hasattr(worker.signals, 'discovery_finished')
    assert hasattr(worker.signals, 'enrichment_progress')


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_worker_initialization():
    """Test that LoadFilesWorker initializes with correct default values."""
    test_path = "/test/directory"
    worker = LoadFilesWorker(test_path)

    assert worker.directory_path == test_path
    assert worker._is_cancelled is False
    assert worker._priority_range == (0, 100)
    assert worker._discovered_files == []
    assert worker.DISCOVERY_BATCH_SIZE == 100


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_worker_cancellation():
    """Test that worker cancellation flag works."""
    worker = LoadFilesWorker("/fake/path")

    assert worker._is_cancelled is False
    worker.cancel()
    assert worker._is_cancelled is True


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_set_priority_range():
    """Test that set_priority_range updates the priority range."""
    worker = LoadFilesWorker("/fake/path")

    worker.set_priority_range(10, 50)
    assert worker._priority_range == (10, 50)

    worker.set_priority_range(100, 200)
    assert worker._priority_range == (100, 200)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_discovery_emits_signals(temp_test_dir):
    """Test that discovery phase emits files_discovered and discovery_finished signals."""
    worker = LoadFilesWorker(temp_test_dir)

    # Track signals
    discovered_batches = []
    finished_count = []

    def on_files_discovered(files):
        discovered_batches.append(files)

    def on_discovery_finished(count):
        finished_count.append(count)

    worker.signals.files_discovered.connect(on_files_discovered)
    worker.signals.discovery_finished.connect(on_discovery_finished)

    # Run discovery (but not enrichment)
    result = worker._run_discovery()

    assert result is True
    assert len(discovered_batches) > 0  # Should have at least one batch
    assert len(finished_count) == 1  # Should emit finished once
    assert finished_count[0] == 5  # We created 5 files
    assert len(worker._discovered_files) == 5


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_discovery_creates_placeholder_data(temp_test_dir):
    """Test that discovered files have placeholder data for metadata fields."""
    worker = LoadFilesWorker(temp_test_dir)

    discovered_files = []

    def on_files_discovered(files):
        discovered_files.extend(files)

    worker.signals.files_discovered.connect(on_files_discovered)
    worker._run_discovery()

    # Check that discovered files have the expected structure
    assert len(discovered_files) == 5

    for file_data in discovered_files:
        # Check filesystem data is present
        assert KEY_FILE_PATH in file_data
        assert KEY_FILE_SIZE in file_data
        assert KEY_FILE_MTIME in file_data
        assert KEY_FILE_CTIME in file_data
        assert KEY_FILE_TYPE in file_data

        # Check that metadata fields have placeholder
        assert file_data[KEY_TITLE] == LOADING_PLACEHOLDER
        assert file_data[KEY_ARTIST] == LOADING_PLACEHOLDER
        assert file_data[KEY_ALBUM] == LOADING_PLACEHOLDER
        assert file_data[KEY_GENRE] == LOADING_PLACEHOLDER
        assert file_data[KEY_BPM] == LOADING_PLACEHOLDER
        assert file_data[KEY_INITIAL_KEY] == LOADING_PLACEHOLDER

        # Check that some fields are None (unknown until enrichment)
        assert file_data[KEY_IS_MEDIA] is None
        assert file_data[KEY_FILE_ID] is None


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_get_prioritized_indices_with_range():
    """Test that _get_prioritized_indices respects priority range."""
    worker = LoadFilesWorker("/fake/path")
    worker._discovered_files = [f"file_{i}" for i in range(100)]  # 100 files

    # Set priority range to 10-20
    worker.set_priority_range(10, 20)

    indices = worker._get_prioritized_indices()

    # Should have all 100 indices
    assert len(indices) == 100
    # First 10 indices should be from priority range (10-20)
    assert indices[0:10] == list(range(10, 20))
    # Remaining indices should be the rest (0-10, 20-100)
    remaining = indices[10:]
    assert 0 in remaining
    assert 9 in remaining
    assert 20 in remaining
    assert 99 in remaining


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_get_prioritized_indices_clamps_range():
    """Test that _get_prioritized_indices clamps out-of-range priority values."""
    worker = LoadFilesWorker("/fake/path")
    worker._discovered_files = [f"file_{i}" for i in range(10)]  # 10 files

    # Set priority range beyond file count
    worker.set_priority_range(5, 500)

    indices = worker._get_prioritized_indices()

    # Should still work without errors
    assert len(indices) == 10
    # Should include files 5-9 first
    assert 5 in indices[0:5]
    assert 9 in indices[0:5]


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_discovery_batching(temp_test_dir):
    """Test that discovery emits files in batches."""
    worker = LoadFilesWorker(temp_test_dir)
    worker.DISCOVERY_BATCH_SIZE = 2  # Small batch for testing

    batch_sizes = []

    def on_files_discovered(files):
        batch_sizes.append(len(files))

    worker.signals.files_discovered.connect(on_files_discovered)
    worker._run_discovery()

    # With 5 files and batch size 2, we should get: [2, 2, 1]
    assert sum(batch_sizes) == 5  # Total files
    assert batch_sizes[0] == 2  # First batch
    assert batch_sizes[1] == 2  # Second batch
    assert batch_sizes[2] == 1  # Remaining files


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
def test_discovery_cancellation(temp_test_dir):
    """Test that discovery respects cancellation flag."""
    # Create a directory with many files to ensure we can cancel mid-discovery
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(500):
            Path(tmpdir, f"file_{i}.txt").write_text("content")

        worker = LoadFilesWorker(tmpdir)

        # Cancel after first batch
        def on_first_batch(files):
            worker.cancel()

        worker.signals.files_discovered.connect(on_first_batch)

        result = worker._run_discovery()

        # Should return False when cancelled
        assert result is False
        # Should have discovered some but not all files
        assert 0 < len(worker._discovered_files) < 500
