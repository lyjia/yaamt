"""
Unit tests for CLI formatting utilities.

Tests CSV output formatting, including:
- Newline handling across platforms
- BpmCandidate postprocessing for reports
"""

import pytest
import tempfile
import os
from pathlib import Path

from util.cli_formatters import (
    _format_as_csv,
    format_analysis_results,
    write_output,
)


class TestFormatAsCsv:
    """Tests for CSV formatting function."""

    def test_basic_csv_output(self):
        """Test basic CSV formatting with simple data."""
        rows = [
            {'filepath': '/path/to/file1.mp3', 'bpm': 120.0, 'status': 'success'},
            {'filepath': '/path/to/file2.mp3', 'bpm': 128.0, 'status': 'success'},
        ]
        columns = ['bpm', 'status']

        result = _format_as_csv(rows, columns, 'filepath')

        # Should have header + 2 data rows
        lines = result.strip().split('\n')
        assert len(lines) == 3

        # Check header
        assert 'directory' in lines[0]
        assert 'filename' in lines[0]
        assert 'bpm' in lines[0]
        assert 'status' in lines[0]

    def test_csv_newlines_format(self):
        """Test that CSV uses proper line endings (no double newlines)."""
        rows = [
            {'filepath': '/path/to/file.mp3', 'value': 'test'},
        ]
        columns = ['value']

        result = _format_as_csv(rows, columns, 'filepath')

        # Should not contain \r\r or double \n\n (except trailing)
        assert '\r\r' not in result
        # Count actual lines - should be exactly 2 (header + 1 data)
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) == 2

    def test_csv_empty_rows(self):
        """Test CSV formatting with empty rows list."""
        result = _format_as_csv([], ['col1', 'col2'], 'filepath')
        assert result == ""

    def test_csv_special_characters_in_values(self):
        """Test CSV properly escapes special characters."""
        rows = [
            {'filepath': '/path/to/file.mp3', 'title': 'Song, "With Quotes"'},
        ]
        columns = ['title']

        result = _format_as_csv(rows, columns, 'filepath')

        # CSV should properly quote the value
        assert '"Song, ""With Quotes"""' in result or 'Song, "With Quotes"' in result


class TestWriteOutputNewlines:
    """Tests for write_output newline handling."""

    def test_write_output_no_double_newlines(self):
        """Test that written files don't have double newlines from CSV."""
        # Create CSV-like content with \r\n endings (what csv module produces)
        content = "header1,header2\r\nvalue1,value2\r\n"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            write_output(content, temp_path)

            # Read back the file in binary mode to see actual bytes
            with open(temp_path, 'rb') as f:
                raw_content = f.read()

            # Should not have \r\r\n (which would be double newline on Windows)
            assert b'\r\r\n' not in raw_content
            # Should not have \n\n in the middle of the content
            # (one \n at the end is OK from write_output)
            lines = raw_content.strip().split(b'\n')
            assert len(lines) == 2  # header + 1 data row

        finally:
            os.unlink(temp_path)

    def test_write_output_creates_file(self):
        """Test that write_output creates the file."""
        content = "test content"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name

        try:
            # Delete the file first to ensure write_output creates it
            os.unlink(temp_path)
            assert not os.path.exists(temp_path)

            write_output(content, temp_path)

            assert os.path.exists(temp_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                read_content = f.read()
            assert 'test content' in read_content

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestFormatAnalysisResults:
    """Tests for analysis results formatting."""

    def test_format_results_csv_basic(self):
        """Test basic CSV formatting of analysis results."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {'bpm': 128.0},
                'status': 'success',
                'error': None
            }
        ]

        output = format_analysis_results(results, 'TestAnalyzer', 'csv')

        assert 'TestAnalyzer_bpm' in output
        assert '128.0' in output
        assert 'success' in output

    def test_format_results_csv_with_float_bpm(self):
        """Test that float BPM values are properly formatted in CSV."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {'bpm': 135.9},
                'status': 'success',
                'error': None
            }
        ]

        output = format_analysis_results(results, 'BPMAnalyzer', 'csv')

        # BPM should be a plain number, not a stringified object
        assert '135.9' in output
        assert 'BpmCandidate' not in output

    def test_format_results_table_format(self):
        """Test table formatting of analysis results."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {'bpm': 120.0},
                'status': 'success',
                'error': None
            }
        ]

        output = format_analysis_results(results, 'TestAnalyzer', 'table')

        # Table should have headers and separators
        assert '|' in output
        assert '-' in output

    def test_format_results_json_format(self):
        """Test JSON formatting of analysis results."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {'bpm': 120.0},
                'status': 'success',
                'error': None
            }
        ]

        output = format_analysis_results(results, 'TestAnalyzer', 'json')

        # Should be valid JSON-like structure
        assert '"filepath"' in output
        assert '"results"' in output

    def test_format_results_with_error(self):
        """Test formatting of failed analysis results."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {},
                'status': 'error',
                'error': 'Analysis failed'
            }
        ]

        output = format_analysis_results(results, 'TestAnalyzer', 'csv')

        assert 'error' in output.lower()
        assert 'Analysis failed' in output

    def test_format_results_with_skipped(self):
        """Test formatting of skipped analysis results."""
        results = [
            {
                'filepath': '/path/to/song.mp3',
                'results': {},
                'status': 'skipped',
                'error': 'BPM already set'
            }
        ]

        output = format_analysis_results(results, 'TestAnalyzer', 'csv')

        assert 'skipped' in output.lower() or 'Skipped' in output