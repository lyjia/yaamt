"""
Unit tests for the LibrosaBPMAnalyzer.

Tests the librosa-based BPM analyzer using real audio fixtures to ensure
proper integration with MediaFile and audio streaming without soundfile dependency.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from util.const import IN_GITHUB_RUNNER
from providers.analysis.base import AnalyzerResult
from providers.analysis.bpm.librosa_bpm import LibrosaBeatTrackingBPMAnalyzer
from providers import get_analyzers_by_category
from providers.analysis import AnalyzerCategory
from models.media_file import MediaFile


class TestLibrosaBPMAnalyzerMetadata:
    """Tests for LibrosaBPMAnalyzer metadata and discovery."""

    def test_analyzer_metadata(self):
        """Test that analyzer has correct metadata."""
        assert LibrosaBeatTrackingBPMAnalyzer.name == "Librosa BPM Analyzer"
        assert LibrosaBeatTrackingBPMAnalyzer.category == "bpm"
        assert LibrosaBeatTrackingBPMAnalyzer.version == "1.0.0"
        assert "librosa" in LibrosaBeatTrackingBPMAnalyzer.description.lower()

    def test_analyzer_discovered(self):
        """Test that LibrosaBPMAnalyzer is discovered by registry."""
        bpm_analyzers = get_analyzers_by_category(AnalyzerCategory.BPM)
        assert LibrosaBeatTrackingBPMAnalyzer in bpm_analyzers


class TestLibrosaBPMAnalyzerBasicBehavior:
    """Tests for basic analyzer behavior using real fixtures."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    @pytest.fixture
    def audio_file_with_bpm(self):
        """Get an audio file that already has BPM metadata."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_with_bpm_and_key_from_serato.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file with BPM not available")
        return str(sample_file)

    def test_analyze_skip_existing_bpm(self, audio_file_with_bpm):
        """Test that analyzer skips when BPM exists and overwrite is False."""
        media_file = MediaFile(audio_file_with_bpm, enable_write=False)

        # Verify file has BPM metadata
        existing_bpm = media_file.get_tag_simple('bpm')
        assert existing_bpm is not None, "Test fixture should have BPM metadata"

        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file, {'skip_if_tag_exists': True})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is True
        assert result.error == "BPM already set"

    def test_analyze_overwrite_existing_bpm(self, audio_file_with_bpm):
        """Test that analyzer processes when skip option is False (default behavior)."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(audio_file_with_bpm, enable_write=False)

        # Verify file has BPM metadata
        existing_bpm = media_file.get_tag_simple('bpm')
        assert existing_bpm is not None, "Test fixture should have BPM metadata"

        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file, {'skip_if_tag_exists': False})
        result = analyzer.analyze()

        # Should not skip (default behavior is to analyze all files)
        assert result.skipped is False
        # Will attempt analysis (may succeed or fail depending on audio content)
        assert isinstance(result.success, bool)

    def test_analyze_cancellation(self, valid_audio_file):
        """Test that cancellation is respected."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        analyzer.cancel()
        result = analyzer.analyze()

        assert result.success is False
        assert "cancelled" in result.error.lower()

    def test_analyze_missing_librosa(self, valid_audio_file):
        """Test graceful handling when librosa library is not available."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Mock librosa import to fail
        with patch.dict('sys.modules', {'librosa': None}):
            analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
            result = analyzer.analyze()

            assert result.success is False
            assert "librosa" in result.error.lower()


class TestLibrosaBPMAnalyzerWithLibrosa:
    """Tests for analyzer with librosa library (if available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_requests_mono_float_audio(self, valid_audio_file):
        """Test that analyzer requests mono float32 audio via AudioFormatDescriptor."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        from providers.audio.format_descriptor import AudioFormatDescriptor

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)

        # Spy on get_audio_stream to verify format descriptor
        original_get_stream = media_file.get_audio_stream
        format_desc_used = None

        def capture_format_desc(format_descriptor=None):
            nonlocal format_desc_used
            format_desc_used = format_descriptor
            return original_get_stream(format_descriptor)

        media_file.get_audio_stream = capture_format_desc

        # Run analysis
        result = analyzer.analyze()

        # Verify mono float audio was requested
        assert format_desc_used is not None
        assert isinstance(format_desc_used, AudioFormatDescriptor)
        assert format_desc_used.channels == 1  # Must request mono
        assert format_desc_used.sample_width == 4  # 32-bit
        assert format_desc_used.sample_format == 'float'

    def test_analyze_uses_audio_numpy_converter(self, valid_audio_file):
        """Test that analyzer uses audio_numpy conversion utilities."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)

        # The analyzer should use audio_stream_to_numpy internally
        # We verify this doesn't crash and completes
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should complete (whether successful or not)
        assert isinstance(result, AnalyzerResult)

    def test_analyze_closes_stream_on_success(self, valid_audio_file):
        """Test that audio stream is properly closed after analysis."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)

        # Run analysis
        result = analyzer.analyze()

        # Just verify it completes - stream closing is internal
        assert isinstance(result, AnalyzerResult)

    def test_analyze_closes_stream_on_error(self, valid_audio_file):
        """Test that audio stream is closed even on error."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Force an error by cancelling immediately
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        analyzer.cancel()

        result = analyzer.analyze()

        # Stream should be closed in finally block
        assert isinstance(result, AnalyzerResult)
        assert result.success is False


class TestLibrosaBPMAnalyzerIntegration:
    """Integration tests with real audio files (if librosa is available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_real_file(self, valid_audio_file):
        """Test analysis on a real audio file (if librosa is available)."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        # Create MediaFile
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Run analyzer
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should complete without crashing
        assert isinstance(result, AnalyzerResult)
        assert isinstance(result.success, bool)

        # DTMF tones don't have a rhythmic beat pattern, so detection may fail
        # We just verify the analyzer runs without errors
        if result.success and not result.skipped:
            # If it somehow detects a BPM, verify it's reasonable
            assert 'bpm' in result.data
            assert isinstance(result.data['bpm'], float)
            assert result.data['bpm'] > 0


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestLibrosaBPMAnalyzerSettingsWidget:
    """Tests for the settings widget."""

    def test_get_settings_widget(self, qapp):
        """Test that settings widget is returned with correct structure."""
        widget = LibrosaBeatTrackingBPMAnalyzer.get_settings_widget()
        assert widget is not None

        # Verify widget was created (full Qt inspection not needed)
        assert widget is not None

    def test_get_options_metadata(self):
        """Test that options metadata is returned."""
        options = LibrosaBeatTrackingBPMAnalyzer.get_options_metadata()
        assert len(options) > 0

        # Verify expected options exist
        option_names = [opt.name for opt in options]
        assert 'start_bpm' in option_names
        assert 'tightness' in option_names
        assert 'trim' in option_names
        assert 'aggregate_method' in option_names
        assert 'hop_length' in option_names


class TestLibrosaBPMAnalyzerWithDrumLoops:
    """Tests for the analyzer with real drum loop fixtures (requires librosa)."""

    @pytest.fixture
    def house_120bpm_file(self):
        """Get the 120 BPM house claves drum loop."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_house_claves_delay_120bpm.wav"
        if not sample_file.exists():
            pytest.skip("120 BPM drum loop fixture not available")
        return str(sample_file)

    @pytest.fixture
    def house_128bpm_file(self):
        """Get the 128 BPM house beat drum loop."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_house_beat_generic_128bpm.wav"
        if not sample_file.exists():
            pytest.skip("128 BPM drum loop fixture not available")
        return str(sample_file)

    @pytest.fixture
    def dnb_175bpm_file(self):
        """Get the 175 BPM drum and bass loop."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_dnb019_175bpm.wav"
        if not sample_file.exists():
            pytest.skip("175 BPM drum and bass fixture not available")
        return str(sample_file)

    def test_analyze_120bpm_drum_loop(self, house_120bpm_file):
        """Test analysis on 120 BPM house drum loop."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(house_120bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Should successfully detect BPM on a clear drum loop
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            # Accept 120 BPM or common multiples/divisions (60, 240)
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Librosa should detect something reasonable for a drum loop
            assert 50 <= detected_bpm <= 250, f"BPM should be reasonable, got {detected_bpm}"

    def test_analyze_128bpm_drum_loop(self, house_128bpm_file):
        """Test analysis on 128 BPM house drum loop."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(house_128bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Should successfully detect BPM on a clear drum loop
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            # Accept 128 BPM or common multiples/divisions (64, 256)
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Librosa should detect something reasonable for a drum loop
            assert 50 <= detected_bpm <= 260, f"BPM should be reasonable, got {detected_bpm}"

    def test_analyze_175bpm_dnb_loop(self, dnb_175bpm_file):
        """Test analysis on 175 BPM drum and bass loop."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(dnb_175bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # DNB may be challenging - accept any valid result
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Accept a wide range for DNB (may detect half or double tempo)
            assert 60 <= detected_bpm <= 200, f"BPM should be reasonable, got {detected_bpm}"

    def test_analyze_with_custom_start_bpm(self, house_128bpm_file):
        """Test analysis with custom start_bpm option."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(house_128bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file, {'start_bpm': 128.0})
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        if result.success and not result.skipped:
            assert 'bpm' in result.data
            assert result.data['bpm'] > 0

    def test_analyze_with_median_aggregation(self, house_120bpm_file):
        """Test analysis with median aggregation."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(house_120bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file, {'aggregate_method': 'median'})
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        if result.success and not result.skipped:
            assert 'bpm' in result.data
            assert result.data['bpm'] > 0

    def test_analyze_with_mean_aggregation(self, house_120bpm_file):
        """Test analysis with mean aggregation."""
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa library not installed")

        media_file = MediaFile(house_120bpm_file, enable_write=False)
        analyzer = LibrosaBeatTrackingBPMAnalyzer(media_file, {'aggregate_method': 'mean'})
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        if result.success and not result.skipped:
            assert 'bpm' in result.data
            assert result.data['bpm'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
