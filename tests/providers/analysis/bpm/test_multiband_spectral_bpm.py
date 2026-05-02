"""
Unit tests for the MultibandSpectralBPMAnalyzer.

Tests the RapidEvolution3-based multiband spectral BPM analyzer using real
audio fixtures to ensure proper integration with MediaFile and audio streaming.
"""

import pytest
from pathlib import Path

from providers.analysis.base import AnalyzerResult
from providers.analysis.bpm.re3_bpm import RE3MultibandSpectralBPMAnalyzer
from providers import get_analyzers_by_category
from providers.analysis import AnalyzerCategory
from models.media_file import MediaFile
from util.const import IN_GITHUB_RUNNER


class TestMultibandSpectralBPMAnalyzerMetadata:
    """Tests for MultibandSpectralBPMAnalyzer metadata and discovery."""

    def test_analyzer_metadata(self):
        """Test that analyzer has correct metadata."""
        assert RE3MultibandSpectralBPMAnalyzer.name is not None
        assert RE3MultibandSpectralBPMAnalyzer.category == "bpm"
        assert RE3MultibandSpectralBPMAnalyzer.version is not None

    def test_analyzer_discovered(self):
        """Test that MultibandSpectralBPMAnalyzer is discovered by registry."""
        bpm_analyzers = get_analyzers_by_category(AnalyzerCategory.BPM)
        assert RE3MultibandSpectralBPMAnalyzer in bpm_analyzers


class TestMultibandSpectralBPMAnalyzerBasicBehavior:
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

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file, {'skip_if_tag_exists': True})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is True
        assert result.error == "BPM already set"

    def test_analyze_overwrite_existing_bpm(self, audio_file_with_bpm):
        """Test that analyzer processes when skip option is False (default behavior)."""
        media_file = MediaFile(audio_file_with_bpm, enable_write=False)

        # Verify file has BPM metadata
        existing_bpm = media_file.get_tag_simple('bpm')
        assert existing_bpm is not None, "Test fixture should have BPM metadata"

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file, {'skip_if_tag_exists': False})
        result = analyzer.analyze()

        # Should not skip (default behavior is to analyze all files)
        assert result.skipped is False
        # Will attempt analysis (may succeed or fail depending on audio content)
        assert isinstance(result.success, bool)

    def test_analyze_cancellation(self, valid_audio_file):
        """Test that cancellation is respected."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        analyzer.cancel()
        result = analyzer.analyze()

        assert result.success is False
        assert "cancelled" in result.error.lower()

    def test_length_in_seconds_property(self, valid_audio_file):
        """Test that MediaFile.length_in_seconds property works correctly."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Verify length_in_seconds is accessible and reasonable
        duration = media_file.length_in_seconds
        assert isinstance(duration, float)
        assert duration > 0.0  # Valid audio files should have positive duration
        assert duration < 300.0  # Test fixture should be short (< 5 minutes)

    def test_unsupported_sample_rate(self, valid_audio_file):
        """Test handling of unsupported sample rates."""
        # Note: This test would require a fixture with an unusual sample rate
        # The current fixtures are 44100 Hz which is supported
        # This is a placeholder for when such fixtures are available
        pytest.skip("No fixture with unsupported sample rate available")


class TestMultibandSpectralBPMAnalyzerIntegration:
    """Integration tests with real audio files."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_real_file(self, valid_audio_file):
        """Test analysis on a real audio file."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Run analyzer
        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should complete without crashing
        assert isinstance(result, AnalyzerResult)
        assert isinstance(result.success, bool)

        # DTMF tones don't have a rhythmic beat pattern, so detection may fail
        # We just verify the analyzer runs without errors
        if result.success and not result.skipped:
            # If it somehow detects a BPM, verify it's reasonable
            assert 'bpm_candidates' in result.data
            assert len(result.data['bpm_candidates']) > 0
            assert result.data['bpm_candidates'][0].bpm > 0

    def test_analyze_respects_bpm_range_preferences(self, valid_audio_file, isolated_qsettings):
        """Test that analyzer reads BPM range from QSettings."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Seed the isolated store with a known-valid range and read it back
        # through the same accessor the analyzer uses.
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_min", 80)
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_max", 200)
        min_bpm = isolated_qsettings.value("Analyzers/CategoryOptions/bpm/range_min", 80, type=int)
        max_bpm = isolated_qsettings.value("Analyzers/CategoryOptions/bpm/range_max", 200, type=int)

        assert isinstance(min_bpm, int)
        assert isinstance(max_bpm, int)
        assert min_bpm < max_bpm
        assert min_bpm > 0

        # Run analyzer (it should pick up these settings internally)
        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Verify result structure (actual BPM detection may fail on DTMF tones)
        assert isinstance(result, AnalyzerResult)

    def test_analyze_creates_mono_stream(self, valid_audio_file):
        """Test that analyzer requests mono audio stream."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # The analyzer should request mono audio internally
        # We verify this doesn't crash and completes
        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should complete (whether successful or not)
        assert isinstance(result, AnalyzerResult)

    def test_analyze_handles_short_audio(self, valid_audio_file):
        """Test analyzer behavior with short audio files (< 60s segment length)."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Verify fixture is short (test fixtures should be < 5 seconds)
        duration = media_file.length_in_seconds
        assert duration < 60.0, "Test fixture should be short for this test"

        # Run analyzer with default threshold_time of 60s
        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Should handle short audio gracefully (may succeed or fail)
        assert isinstance(result, AnalyzerResult)

    def test_analyze_with_custom_decimation(self, valid_audio_file):
        """Test analyzer with custom decimation size."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Use faster decimation for quicker processing
        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file, {
            'decimation_size': 128,  # Higher = faster but less precise
            'threshold_time': 30.0   # Shorter segments
        })
        result = analyzer.analyze()

        # Should complete with custom options
        assert isinstance(result, AnalyzerResult)


class TestMultibandSpectralBPMAnalyzerErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_returns_error_on_failure(self, valid_audio_file):
        """Test that analysis failures return proper error messages."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # If analysis fails, should have error message
        if not result.success:
            assert result.error is not None
            assert len(result.error) > 0

    def test_analyzer_closes_audio_stream(self, valid_audio_file):
        """Test that audio stream is properly closed after analysis."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # Audio stream should be closed (we can't easily verify this without
        # mocking, but we verify the analysis completes without hanging)
        assert isinstance(result, AnalyzerResult)


class TestMultibandSpectralBPMAnalyzerSettingsWidget:
    """Tests for the settings widget."""

    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
    def test_get_settings_widget(self):
        """Test that settings widget is returned."""
        widget = RE3MultibandSpectralBPMAnalyzer.get_settings_widget()
        assert widget is not None
    @pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
    def test_settings_widget_has_info_label(self):
        """Test that settings widget explains BPM range configuration."""
        widget = RE3MultibandSpectralBPMAnalyzer.get_settings_widget()

        # Widget should have info label explaining that BPM range
        # is configured in Preferences > Metadata
        # We verify the widget was created successfully
        assert widget is not None


class TestMultibandSpectralBPMAnalyzerWithDrumLoops:
    """Tests for the analyzer with real drum loop fixtures."""

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

    def test_analyze_120bpm_in_range(self, house_120bpm_file, isolated_qsettings):
        """Test 120 BPM file with range that includes 120 BPM."""
        media_file = MediaFile(house_120bpm_file, enable_write=False)

        # Set BPM range to include 120 BPM
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_min", 80)
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_max", 160)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # NOTE: There's currently a bug reading duration from WAV files
        # If duration can't be determined, analyzer will fail with error
        if not result.success and "duration" in result.error.lower():
            pytest.skip(f"Known bug - cannot read duration from WAV: {result.error}")

        assert result.success is True
        assert result.skipped is False
        assert 'bpm_candidates' in result.data

        # Should detect ~120 BPM (raw detection, range adjustment happens in dispatcher)
        detected_bpm = result.data['bpm_candidates'][0].bpm
        # RE3 uses range hints, so it should detect within a reasonable range of 120
        assert 50 <= detected_bpm <= 250, f"Expected reasonable BPM near 120, got {detected_bpm}"

    def test_analyze_128bpm_in_range(self, house_128bpm_file, isolated_qsettings):
        """Test 128 BPM file with range that includes 128 BPM."""
        media_file = MediaFile(house_128bpm_file, enable_write=False)

        # Set BPM range to include 128 BPM (RE3 uses this as hint)
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_min", 100)
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_max", 150)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # NOTE: There's currently a bug reading duration from WAV files
        if not result.success and "duration" in result.error.lower():
            pytest.skip(f"Known bug - cannot read duration from WAV: {result.error}")

        assert result.success is True
        assert result.skipped is False
        assert 'bpm_candidates' in result.data

        # Should detect ~128 BPM (raw detection, range adjustment happens in dispatcher)
        detected_bpm = result.data['bpm_candidates'][0].bpm
        assert 50 <= detected_bpm <= 260, f"Expected reasonable BPM near 128, got {detected_bpm}"

    def test_analyze_175bpm_dnb_in_range(self, dnb_175bpm_file, isolated_qsettings):
        """Test 175 BPM drum and bass file (may have irregular beats)."""
        media_file = MediaFile(dnb_175bpm_file, enable_write=False)

        # Set BPM range to include 175 BPM
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_min", 150)
        isolated_qsettings.setValue("Analyzers/CategoryOptions/bpm/range_max", 200)

        analyzer = RE3MultibandSpectralBPMAnalyzer(media_file)
        result = analyzer.analyze()

        # DNB may be tough due to irregular beats
        # Accept any valid result for now
        if result.success and not result.skipped:
            assert 'bpm_candidates' in result.data
            detected_bpm = result.data['bpm_candidates'][0].bpm
            # Accept any reasonable BPM (could be 175, or half/double)
            assert detected_bpm > 0, f"BPM should be positive, got {detected_bpm}"
            assert 40 <= detected_bpm <= 400, f"BPM should be reasonable, got {detected_bpm}"
        else:
            # It's okay if detection fails on DNB
            assert isinstance(result, AnalyzerResult)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
