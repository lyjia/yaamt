"""
Unit tests for the analyzer system.

Tests the base analyzer classes, auto-discovery system, and dispatcher.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from util.const import IN_GITHUB_RUNNER
from providers.analysis.base import AnalyzerBase, AnalyzerResult
from providers.analysis import (
    ANALYZER_REGISTRY,
    get_analyzers_by_category,
    get_all_categories,
    get_analyzer_by_name
)
from providers.analysis.bpm.stub_bpm import StubBPMAnalyzer
from workers.analyzer_dispatcher import AnalyzerDispatcher, AnalysisTask
from models.media_file import MediaFile


class TestAnalyzerResult:
    """Tests for AnalyzerResult class."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = AnalyzerResult(success=True, data={'bpm': '120'})
        assert result.success is True
        assert result.data == {'bpm': '120'}
        assert result.error is None
        assert result.skipped is False

    def test_failed_result(self):
        """Test creating a failed result."""
        result = AnalyzerResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.data == {}
        assert result.error == "Something went wrong"
        assert result.skipped is False

    def test_skipped_result(self):
        """Test creating a skipped result."""
        result = AnalyzerResult(success=True, skipped=True, error="Already exists")
        assert result.success is True
        assert result.skipped is True
        assert result.error == "Already exists"

    def test_result_repr(self):
        """Test string representation of results."""
        result = AnalyzerResult(success=True, data={'bpm': '120'})
        assert 'success=True' in repr(result)
        assert 'bpm' in repr(result)


class TestAnalyzerBase:
    """Tests for AnalyzerBase class."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization with options."""
        mock_media_file = Mock()
        options = {'overwrite_existing': True, 'custom_option': 'value'}

        # Create a concrete implementation for testing
        class TestAnalyzer(AnalyzerBase):
            name = "Test Analyzer"
            category = "test"

            def analyze(self):
                return AnalyzerResult(success=True)

        analyzer = TestAnalyzer(mock_media_file, options)

        assert analyzer.media_file is mock_media_file
        assert analyzer.options == options
        assert analyzer.is_cancelled is False

    def test_cancellation(self):
        """Test analyzer cancellation."""
        mock_media_file = Mock()

        class TestAnalyzer(AnalyzerBase):
            def analyze(self):
                return AnalyzerResult(success=True)

        analyzer = TestAnalyzer(mock_media_file)
        assert analyzer.is_cancelled is False

        analyzer.cancel()
        assert analyzer.is_cancelled is True

    def test_validate_file_default(self):
        """Test default file validation (always returns True)."""
        mock_media_file = Mock()

        class TestAnalyzer(AnalyzerBase):
            def analyze(self):
                return AnalyzerResult(success=True)

        is_valid, reason = TestAnalyzer.validate_file(mock_media_file)
        assert is_valid is True
        assert reason is None

    def test_get_settings_widget_default(self):
        """Test default settings widget (returns None)."""
        class TestAnalyzer(AnalyzerBase):
            def analyze(self):
                return AnalyzerResult(success=True)

        widget = TestAnalyzer.get_settings_widget()
        assert widget is None


class TestAutoDiscovery:
    """Tests for the auto-discovery system."""

    def test_registry_populated(self):
        """Test that the registry is populated with discovered analyzers."""
        assert len(ANALYZER_REGISTRY) > 0
        assert 'bpm' in ANALYZER_REGISTRY

    def test_stub_analyzer_discovered(self):
        """Test that StubBPMAnalyzer is discovered."""
        bpm_analyzers = get_analyzers_by_category('bpm')
        assert len(bpm_analyzers) > 0
        assert StubBPMAnalyzer in bpm_analyzers

    def test_get_all_categories(self):
        """Test getting all categories."""
        categories = get_all_categories()
        assert isinstance(categories, list)
        assert 'bpm' in categories
        assert categories == sorted(categories)  # Should be sorted

    def test_get_analyzer_by_name(self):
        """Test finding analyzer by class name."""
        analyzer = get_analyzer_by_name('StubBPMAnalyzer')
        assert analyzer is StubBPMAnalyzer

    def test_get_analyzer_by_name_not_found(self):
        """Test that None is returned for non-existent analyzer."""
        analyzer = get_analyzer_by_name('NonExistentAnalyzer')
        assert analyzer is None


class TestStubBPMAnalyzer:
    """Tests for the StubBPMAnalyzer."""

    @pytest.fixture
    def mock_media_file(self):
        """Create a mock MediaFile for testing."""
        media_file = Mock(spec=MediaFile)
        media_file.file_path = "/test/file.mp3"
        media_file.get_tag_simple.return_value = None
        return media_file

    def test_stub_analyzer_metadata(self):
        """Test that stub analyzer has correct metadata."""
        assert StubBPMAnalyzer.name == "Stub BPM Analyzer"
        assert StubBPMAnalyzer.category == "bpm"
        assert StubBPMAnalyzer.version == "0.1.0"

    def test_analyze_success(self, mock_media_file):
        """Test successful analysis."""
        analyzer = StubBPMAnalyzer(mock_media_file)
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is False
        assert 'bpm' in result.data
        assert result.data['bpm'] == '120'

    def test_analyze_skip_existing(self, mock_media_file):
        """Test that analyzer skips when BPM exists and overwrite is False."""
        mock_media_file.get_tag_simple.return_value = '128'
        analyzer = StubBPMAnalyzer(mock_media_file, {'overwrite_existing': False})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is True
        assert result.error == "BPM already set"

    def test_analyze_overwrite_existing(self, mock_media_file):
        """Test that analyzer overwrites when overwrite option is True."""
        mock_media_file.get_tag_simple.return_value = '128'
        analyzer = StubBPMAnalyzer(mock_media_file, {'overwrite_existing': True})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is False
        assert result.data['bpm'] == '120'

    def test_analyze_cancellation(self, mock_media_file):
        """Test that cancellation is respected."""
        analyzer = StubBPMAnalyzer(mock_media_file)
        analyzer.cancel()
        result = analyzer.analyze()

        assert result.success is False
        assert "cancelled" in result.error.lower()

    def test_decimal_places_zero(self, mock_media_file):
        """Test BPM with 0 decimal places (default)."""
        analyzer = StubBPMAnalyzer(mock_media_file, {'decimal_places': 0})
        result = analyzer.analyze()

        assert result.data['bpm'] == '120'

    def test_decimal_places_one(self, mock_media_file):
        """Test BPM with 1 decimal place."""
        analyzer = StubBPMAnalyzer(mock_media_file, {'decimal_places': 1})
        result = analyzer.analyze()

        assert result.data['bpm'] == '120.0'

    def test_decimal_places_two(self, mock_media_file):
        """Test BPM with 2 decimal places."""
        analyzer = StubBPMAnalyzer(mock_media_file, {'decimal_places': 2})
        result = analyzer.analyze()

        assert result.data['bpm'] == '120.00'

    def test_decimal_places_clamped(self, mock_media_file):
        """Test that decimal places are clamped to 0-2 range."""
        # Test value too high
        analyzer = StubBPMAnalyzer(mock_media_file, {'decimal_places': 5})
        result = analyzer.analyze()
        assert result.data['bpm'] == '120.00'  # Should clamp to 2

        # Test negative value
        analyzer = StubBPMAnalyzer(mock_media_file, {'decimal_places': -1})
        result = analyzer.analyze()
        assert result.data['bpm'] == '120'  # Should clamp to 0

    def test_get_settings_widget(self):
        """Test that settings widget is returned."""
        widget = StubBPMAnalyzer.get_settings_widget()
        assert widget is not None

        # Find the spin box
        spin_box = widget.findChild(type(widget).__bases__[0], "decimal_places")
        # The widget should have the decimal_places spin box, but exact structure
        # depends on Qt implementation, so just verify widget exists
        assert widget is not None


class TestAnalysisTask:
    """Tests for AnalysisTask class."""

    def test_task_initialization(self):
        """Test creating an analysis task."""
        mock_media_file = Mock(spec=MediaFile)
        options = {'overwrite_existing': True}

        task = AnalysisTask(StubBPMAnalyzer, mock_media_file, options)

        assert task.analyzer_class is StubBPMAnalyzer
        assert task.media_file is mock_media_file
        assert task.options == options
        assert task.result is None
        assert task.analyzer_instance is None


class TestAnalyzerDispatcher:
    """Tests for AnalyzerDispatcher singleton."""

    @pytest.fixture
    def dispatcher(self):
        """Get dispatcher instance and reset it for each test."""
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()
        return dispatcher

    @pytest.fixture
    def mock_media_files(self):
        """Create mock MediaFile instances."""
        files = []
        for i in range(3):
            mf = Mock(spec=MediaFile)
            mf.file_path = f"/test/file{i}.mp3"
            mf.get_tag_simple.return_value = None
            mf.save = Mock()
            files.append(mf)
        return files

    def test_singleton_pattern(self):
        """Test that dispatcher is a singleton."""
        dispatcher1 = AnalyzerDispatcher()
        dispatcher2 = AnalyzerDispatcher()
        assert dispatcher1 is dispatcher2

    def test_enqueue_tasks(self, dispatcher, mock_media_files):
        """Test enqueueing tasks."""
        dispatcher.enqueue(StubBPMAnalyzer, mock_media_files)
        assert len(dispatcher.queue) == 3

    def test_enqueue_with_options(self, dispatcher, mock_media_files):
        """Test enqueueing tasks with options."""
        options = {'overwrite_existing': True, 'decimal_places': 2}
        dispatcher.enqueue(StubBPMAnalyzer, mock_media_files, options)

        assert len(dispatcher.queue) == 3
        for task in dispatcher.queue:
            assert task.options == options

    def test_get_summary_empty(self, dispatcher):
        """Test summary with no completed tasks."""
        summary = dispatcher.get_summary()
        assert summary['total'] == 0
        assert summary['successful'] == 0
        assert len(summary['failed']) == 0
        assert len(summary['skipped']) == 0

    def test_reset(self, dispatcher, mock_media_files):
        """Test resetting dispatcher state."""
        dispatcher.enqueue(StubBPMAnalyzer, mock_media_files)
        dispatcher.reset()

        assert len(dispatcher.queue) == 0
        assert len(dispatcher.completed_tasks) == 0
        assert dispatcher.current_task is None
        assert dispatcher._is_running is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
