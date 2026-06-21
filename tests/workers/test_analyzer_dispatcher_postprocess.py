"""
Unit tests for analyzer dispatcher result postprocessing.

Tests the _postprocess_result_data function which handles:
- BPM candidate selection and range adjustment
- Consistent output between tag writing and report generation
"""

import pytest
from unittest.mock import patch, MagicMock

from util.bpm import BpmCandidate
from workers.analyzer_dispatcher import _postprocess_result_data


class TestPostprocessResultData:
    """Tests for the _postprocess_result_data function."""

    def test_empty_result_data(self):
        """Test with empty result data."""
        result = _postprocess_result_data({}, {})
        assert result == {}

    def test_none_result_data(self):
        """Test with None result data."""
        result = _postprocess_result_data(None, {})
        assert result == {}

    def test_passthrough_non_bpm_data(self):
        """Test that non-BPM data is passed through unchanged."""
        input_data = {'key': 'Am', 'some_value': 42}
        result = _postprocess_result_data(input_data, {})

        assert result['key'] == 'Am'
        assert result['some_value'] == 42

    def test_bpm_candidates_converted_to_bpm(self):
        """Test that bpm_candidates list is converted to single bpm value."""
        candidates = [BpmCandidate(bpm=128.0, certainty=0.9)]
        input_data = {'bpm_candidates': candidates}

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            mock_qsettings.value.side_effect = lambda key, default, type: default
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, {})

        assert 'bpm' in result
        assert result['bpm'] == 128.0
        assert 'bpm_candidates' not in result

    def test_bpm_candidates_selects_highest_certainty(self):
        """Test that the candidate with highest certainty is selected."""
        candidates = [
            BpmCandidate(bpm=64.0, certainty=0.5),
            BpmCandidate(bpm=128.0, certainty=0.9),  # Highest certainty
            BpmCandidate(bpm=256.0, certainty=0.3),
        ]
        input_data = {'bpm_candidates': candidates}

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            mock_qsettings.value.side_effect = lambda key, default, type: default
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, {})

        assert result['bpm'] == 128.0

    def test_bpm_range_from_options(self):
        """Test that BPM range from options is used for adjustment."""
        # BPM of 64 should be doubled to 128 when min_bpm is 80
        candidates = [BpmCandidate(bpm=64.0, certainty=0.9)]
        input_data = {'bpm_candidates': candidates}
        options = {'bpm_min': 80, 'bpm_max': 200}

        result = _postprocess_result_data(input_data, options)

        # 64 * 2 = 128, which fits in range 80-200
        assert result['bpm'] == 128.0

    def test_bpm_range_fallback_to_settings(self):
        """Test that BPM range falls back to QSettings when not in options."""
        candidates = [BpmCandidate(bpm=64.0, certainty=0.9)]
        input_data = {'bpm_candidates': candidates}
        options = {}  # No BPM range in options

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            # Return 80 for min and 200 for max
            mock_qsettings.value.side_effect = lambda key, default, type: 80 if 'min' in key else 200
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, options)

        # 64 * 2 = 128, which fits in range 80-200
        assert result['bpm'] == 128.0

    def test_empty_bpm_candidates_list(self):
        """Test handling of empty bpm_candidates list."""
        input_data = {'bpm_candidates': []}

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            mock_qsettings.value.side_effect = lambda key, default, type: default
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, {})

        # Should not have 'bpm' key since candidates were empty
        assert 'bpm' not in result
        assert 'bpm_candidates' not in result

    def test_preserves_other_data_with_bpm_candidates(self):
        """Test that other data is preserved when processing BPM candidates."""
        candidates = [BpmCandidate(bpm=128.0, certainty=0.9)]
        input_data = {
            'bpm_candidates': candidates,
            'key': 'Am',
            'other_field': 'value'
        }

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            mock_qsettings.value.side_effect = lambda key, default, type: default
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, {})

        assert result['bpm'] == 128.0
        assert result['key'] == 'Am'
        assert result['other_field'] == 'value'
        assert 'bpm_candidates' not in result

    def test_does_not_modify_original_data(self):
        """Test that the original data dictionary is not modified."""
        candidates = [BpmCandidate(bpm=128.0, certainty=0.9)]
        input_data = {'bpm_candidates': candidates, 'key': 'Am'}

        with patch('workers.analyzer_dispatcher.get_qsettings') as mock_settings:
            mock_qsettings = MagicMock()
            mock_qsettings.value.side_effect = lambda key, default, type: default
            mock_settings.return_value = mock_qsettings

            result = _postprocess_result_data(input_data, {})

        # Original should still have bpm_candidates
        assert 'bpm_candidates' in input_data
        assert len(input_data['bpm_candidates']) == 1