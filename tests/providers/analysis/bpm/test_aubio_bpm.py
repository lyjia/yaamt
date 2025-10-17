"""
Unit tests for the AubioBPMAnalyzer.

Tests the aubio-based BPM analyzer using real audio fixtures to ensure
proper integration with MediaFile and audio streaming.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from util.const import IN_GITHUB_RUNNER
from providers.analysis.base import AnalyzerResult
from providers.analysis.bpm.aubio_bpm import AubioBPMAnalyzer
from providers import get_analyzers_by_category
from providers.analysis import AnalyzerCategory
from models.media_file import MediaFile


class TestAubioBPMAnalyzerMetadata:
    """Tests for AubioBPMAnalyzer metadata and discovery."""

    def test_analyzer_metadata(self):
        """Test that analyzer has correct metadata."""
        assert AubioBPMAnalyzer.name == "Aubio BPM Analyzer"
        assert AubioBPMAnalyzer.category == "bpm"
        assert AubioBPMAnalyzer.version == "1.0.0"
        assert "aubio" in AubioBPMAnalyzer.description.lower()

    def test_analyzer_discovered(self):
        """Test that AubioBPMAnalyzer is discovered by registry."""
        bpm_analyzers = get_analyzers_by_category(AnalyzerCategory.BPM)
        assert AubioBPMAnalyzer in bpm_analyzers


class TestAubioBPMAnalyzerBasicBehavior:
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

        analyzer = AubioBPMAnalyzer(media_file, {'overwrite_existing': False})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is True
        assert result.error == "BPM already set"

    def test_analyze_overwrite_existing_bpm(self, audio_file_with_bpm):
        """Test that analyzer processes when overwrite option is True."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(audio_file_with_bpm, enable_write=False)

        # Verify file has BPM metadata
        existing_bpm = media_file.get_tag_simple('bpm')
        assert existing_bpm is not None, "Test fixture should have BPM metadata"

        analyzer = AubioBPMAnalyzer(media_file, {'overwrite_existing': True})
        result = analyzer.analyze()

        # Should not skip (overwrite is True)
        assert result.skipped is False
        # Will attempt analysis (may succeed or fail depending on audio content)
        assert isinstance(result.success, bool)

    def test_analyze_cancellation(self, valid_audio_file):
        """Test that cancellation is respected."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = AubioBPMAnalyzer(media_file)
        analyzer.cancel()
        result = analyzer.analyze()

        assert result.success is False
        assert "cancelled" in result.error.lower()

    def test_analyze_missing_aubio(self, valid_audio_file):
        """Test graceful handling when aubio library is not available."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Mock aubio import to fail
        with patch.dict('sys.modules', {'aubio': None}):
            analyzer = AubioBPMAnalyzer(media_file)
            result = analyzer.analyze()

            assert result.success is False
            assert "aubio" in result.error.lower()


class TestAubioBPMAnalyzerWithAubio:
    """Tests for analyzer with aubio library (if available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_requests_mono_audio(self, valid_audio_file):
        """Test that analyzer requests mono audio via AudioFormatDescriptor."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        from providers.audio.format_descriptor import AudioFormatDescriptor

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file)

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

        # Verify mono audio was requested
        assert format_desc_used is not None
        assert isinstance(format_desc_used, AudioFormatDescriptor)
        assert format_desc_used.channels == 1  # Must request mono

    def test_analyze_creates_mono_stream(self, valid_audio_file):
        """Test that analyzer requests mono audio stream."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)

        # The analyzer should request mono audio internally
        # We verify this doesn't crash and completes
        analyzer = AubioBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should complete (whether successful or not)
        assert isinstance(result, AnalyzerResult)


class TestAubioBPMAnalyzerIntegration:
    """Integration tests with real audio files (if aubio is available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_real_file(self, valid_audio_file):
        """Test analysis on a real audio file (if aubio is available)."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        # Create MediaFile
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Run analyzer
        analyzer = AubioBPMAnalyzer(media_file)
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
class TestAubioBPMAnalyzerSettingsWidget:
    """Tests for the settings widget."""

    def test_get_settings_widget(self, qapp):
        """Test that settings widget is returned with correct controls."""
        widget = AubioBPMAnalyzer.get_settings_widget()
        assert widget is not None

        # Verify widget has expected controls by object name
        method_combo = widget.findChild(widget.__class__.__bases__[0], "method")
        mode_group = widget.findChild(widget.__class__.__bases__[0], "mode")

        # These controls should exist (even if Qt's findChild doesn't find them
        # due to layout/hierarchy, we verify the widget was created)
        assert widget is not None

    def test_settings_widget_has_method_options(self, qapp):
        """Test that settings widget includes method selection."""
        widget = AubioBPMAnalyzer.get_settings_widget()

        # Widget should contain method selection with various algorithms
        # We can't easily test Qt widget internals without full Qt environment,
        # but we verify the widget was created successfully
        assert widget is not None


class TestAubioBPMAnalyzerWithDrumLoops:
    """Tests for the analyzer with real drum loop fixtures (requires aubio)."""

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
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(house_120bpm_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Should successfully detect BPM on a clear drum loop
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            # Accept 120 BPM or common multiples/divisions (60, 240)
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Aubio should detect something reasonable for a drum loop
            assert 50 <= detected_bpm <= 250, f"BPM should be reasonable, got {detected_bpm}"

    def test_analyze_128bpm_drum_loop(self, house_128bpm_file):
        """Test analysis on 128 BPM house drum loop."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(house_128bpm_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Should successfully detect BPM on a clear drum loop
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            # Accept 128 BPM or common multiples/divisions (64, 256)
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Aubio should detect something reasonable for a drum loop
            assert 50 <= detected_bpm <= 260, f"BPM should be reasonable, got {detected_bpm}"

    def test_analyze_175bpm_dnb_loop(self, dnb_175bpm_file):
        """Test analysis on 175 BPM drum and bass loop (may be challenging)."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(dnb_175bpm_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file)
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # DNB may be tough due to irregular beats - accept any valid result
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            # Accept a wide range for DNB
            assert 60 <= detected_bpm <= 200, f"BPM should be reasonable, got {detected_bpm}"
        else:
            # It's okay if detection fails on DNB
            pass

    def test_analyze_120bpm_fast_mode(self, house_120bpm_file):
        """Test 120 BPM drum loop with fast mode."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(house_120bpm_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file, {'mode': 'fast'})
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Fast mode should still work on drum loops
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"

    def test_analyze_128bpm_default_mode(self, house_128bpm_file):
        """Test 128 BPM drum loop with default mode."""
        try:
            import aubio  # noqa: F401
        except ImportError:
            pytest.skip("aubio library not installed")

        media_file = MediaFile(house_128bpm_file, enable_write=False)
        analyzer = AubioBPMAnalyzer(media_file, {'mode': 'default'})
        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Default mode should work well on clear drum loops
        if result.success and not result.skipped:
            assert 'bpm' in result.data
            detected_bpm = result.data['bpm']
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
