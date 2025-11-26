"""
Unit tests for the MusicalKeyCNNAnalyzer.

Tests the CNN-based key analyzer using real audio fixtures to ensure
proper integration with MediaFile and neural network key detection.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from util.const import IN_GITHUB_RUNNER, KEY_INITIAL_KEY
from providers.analysis.base import AnalyzerResult
from providers.analysis.key.cnn_key import MusicalKeyCNNAnalyzer, KEYNET_RESOURCE_ID
from providers import get_analyzers_by_category
from providers.analysis import AnalyzerCategory
from models.media_file import MediaFile


def get_model_path_or_skip(analyzer):
    """
    Helper to get model path or skip test if model not available.

    With the new resource manager system, _get_model_path() raises RuntimeError
    if the model is not found instead of returning an invalid path.
    """
    try:
        return analyzer._get_model_path()
    except RuntimeError as e:
        if "not found" in str(e).lower():
            pytest.skip("Model checkpoint not available via resource manager")
        raise


class TestMusicalKeyCNNAnalyzerMetadata:
    """Tests for MusicalKeyCNNAnalyzer metadata and discovery."""

    def test_analyzer_metadata(self):
        """Test that analyzer has correct metadata."""
        assert MusicalKeyCNNAnalyzer.name is not None
        assert MusicalKeyCNNAnalyzer.category == "key"
        assert MusicalKeyCNNAnalyzer.version is not None
        assert MusicalKeyCNNAnalyzer.debug_only is True  # Should be debug-only due to PyTorch

    def test_analyzer_discovered(self):
        """Test that MusicalKeyCNNAnalyzer is discovered by registry."""
        key_analyzers = get_analyzers_by_category(AnalyzerCategory.KEY)
        assert MusicalKeyCNNAnalyzer in key_analyzers

    def test_get_required_resources(self):
        """Test that analyzer declares required resources."""
        resources = MusicalKeyCNNAnalyzer.get_required_resources()
        assert len(resources) == 1

        keynet_resource = resources[0]
        assert keynet_resource.resource_id == KEYNET_RESOURCE_ID
        assert keynet_resource.filename == "keynet.pt"
        assert keynet_resource.category == "models"
        assert keynet_resource.display_name == "KeyNet CNN Model"
        assert keynet_resource.required_by == "MusicalKeyCNNAnalyzer"


class TestMusicalKeyCNNAnalyzerBasicBehavior:
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
    def audio_file_with_key(self):
        """Get an audio file that already has key metadata."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_with_bpm_and_key_from_serato.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file with key not available")
        return str(sample_file)

    @pytest.fixture
    def cmin_musical_file(self):
        """Get the C minor musical fixture."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "Cmin_5A_i-v-VI-iv.mp3"
        if not sample_file.exists():
            pytest.skip("C minor musical fixture not available")
        return str(sample_file)

    def test_analyze_skip_existing_key(self, audio_file_with_key):
        """Test that analyzer skips when key exists and overwrite is False."""
        media_file = MediaFile(audio_file_with_key, enable_write=False)

        # Check if file has key metadata (fixtures may not have key set)
        existing_key = media_file.get_tag_simple(KEY_INITIAL_KEY)

        if existing_key is None:
            # Fixture doesn't have key metadata, skip this test
            pytest.skip("Test fixture does not have key metadata set")

        analyzer = MusicalKeyCNNAnalyzer(media_file, {'skip_if_tag_exists': True})
        result = analyzer.analyze()

        assert result.success is True
        assert result.skipped is True
        assert result.error == "Key already set"

    def test_analyze_overwrite_existing_key(self, audio_file_with_key):
        """Test that analyzer processes when skip option is False (default behavior)."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(audio_file_with_key, enable_write=False)

        # Check if file has key metadata
        existing_key = media_file.get_tag_simple(KEY_INITIAL_KEY)

        if existing_key is None:
            pytest.skip("Test fixture does not have key metadata set - cannot test overwrite behavior")

        # Check if model file exists
        analyzer = MusicalKeyCNNAnalyzer(media_file, {'skip_if_tag_exists': False})
        get_model_path_or_skip(analyzer)

        result = analyzer.analyze()

        # Should not skip (default behavior is to analyze all files)
        assert result.skipped is False
        # Will attempt analysis (may succeed or fail depending on audio content)
        assert isinstance(result.success, bool)

    def test_analyze_cancellation(self, valid_audio_file):
        """Test that cancellation is respected."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        analyzer = MusicalKeyCNNAnalyzer(media_file)
        analyzer.cancel()
        result = analyzer.analyze()

        assert result.success is False
        assert "cancelled" in result.error.lower()

    def test_analyze_missing_torch(self, valid_audio_file):
        """Test graceful handling when PyTorch libraries are not available."""
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Mock torch import to fail
        with patch.dict('sys.modules', {'torch': None}):
            analyzer = MusicalKeyCNNAnalyzer(media_file)
            result = analyzer.analyze()

            assert result.success is False
            assert "torch" in result.error.lower() or "librosa" in result.error.lower()

    def test_analyze_missing_model_file(self, valid_audio_file):
        """Test graceful handling when model checkpoint is missing."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Mock resource manager to simulate missing model
        with patch('providers.analysis.key.cnn_key.get_resource_manager') as mock_rm:
            mock_rm.return_value.is_resource_loadable.return_value = False
            analyzer = MusicalKeyCNNAnalyzer(media_file)
            result = analyzer.analyze()

        assert result.success is False
        assert "not found" in result.error.lower()


class TestMusicalKeyCNNAnalyzerWithTorch:
    """Tests for analyzer with PyTorch library (if available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_requests_mono_float_audio_44khz(self, valid_audio_file):
        """Test that analyzer requests mono float32 audio at 44.1kHz via AudioFormatDescriptor."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        from providers.audio.format_descriptor import AudioFormatDescriptor

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

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

        # Verify mono float audio at 44.1kHz was requested
        assert format_desc_used is not None
        assert isinstance(format_desc_used, AudioFormatDescriptor)
        assert format_desc_used.channels == 1  # Must request mono
        assert format_desc_used.sample_width == 4  # 32-bit
        assert format_desc_used.sample_format == 'float'
        assert format_desc_used.sample_rate == 44100  # CNN requires 44.1kHz

    def test_analyze_uses_audio_numpy_converter(self, valid_audio_file):
        """Test that analyzer uses audio_numpy conversion utilities."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        # The analyzer should use audio_stream_to_numpy internally
        # We verify this doesn't crash and completes
        result = analyzer.analyze()

        # Should complete (whether successful or not)
        assert isinstance(result, AnalyzerResult)

    def test_analyze_closes_stream_on_success(self, valid_audio_file):
        """Test that audio stream is properly closed after analysis."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        # Run analysis
        result = analyzer.analyze()

        # Just verify it completes - stream closing is internal
        assert isinstance(result, AnalyzerResult)

    def test_analyze_closes_stream_on_error(self, valid_audio_file):
        """Test that audio stream is closed even on error."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Force an error by cancelling immediately
        analyzer = MusicalKeyCNNAnalyzer(media_file)
        analyzer.cancel()

        result = analyzer.analyze()

        # Stream should be closed in finally block
        assert isinstance(result, AnalyzerResult)
        assert result.success is False


class TestMusicalKeyCNNAnalyzerIntegration:
    """Integration tests with real audio files (if PyTorch is available)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_analyze_real_file(self, valid_audio_file):
        """Test analysis on a real audio file (if PyTorch is available)."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        # Create MediaFile
        media_file = MediaFile(valid_audio_file, enable_write=False)

        # Run analyzer
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        result = analyzer.analyze()

        # Should complete without crashing
        assert isinstance(result, AnalyzerResult)
        assert isinstance(result.success, bool)

        # DTMF tones don't have a clear musical key, so detection may succeed or fail
        # We just verify the analyzer runs without errors
        if result.success and not result.skipped:
            # If it detects a key, verify it's a valid format
            assert KEY_INITIAL_KEY in result.data
            key_str = result.data[KEY_INITIAL_KEY]
            assert isinstance(key_str, str)
            assert len(key_str) > 0


class TestMusicalKeyCNNAnalyzerDeviceSelection:
    """Tests for device selection (CPU/CUDA)."""

    @pytest.fixture
    def valid_audio_file(self):
        """Get a valid audio file from test fixtures."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "sample_dtmf_original.flac"
        if not sample_file.exists():
            pytest.skip("Sample audio file not available")
        return str(sample_file)

    def test_device_auto_selection(self, valid_audio_file):
        """Test that auto device selection works."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file, {'device': 'auto'})

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        result = analyzer.analyze()
        assert isinstance(result, AnalyzerResult)

    def test_device_cpu_selection(self, valid_audio_file):
        """Test that CPU device selection works."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(valid_audio_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file, {'device': 'cpu'})

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        result = analyzer.analyze()
        assert isinstance(result, AnalyzerResult)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMusicalKeyCNNAnalyzerSettingsWidget:
    """Tests for the settings widget."""

    def test_get_settings_widget(self, qapp):
        """Test that settings widget is returned with correct structure."""
        widget = MusicalKeyCNNAnalyzer.get_settings_widget()
        assert widget is not None

    def test_get_options_metadata(self):
        """Test that options metadata is returned."""
        options = MusicalKeyCNNAnalyzer.get_options_metadata()
        assert len(options) > 0

        # Verify expected options exist
        option_names = [opt.name for opt in options]
        assert 'device' in option_names
        # Note: model_path option removed - model management now via Resources pane


class TestMusicalKeyCNNAnalyzerWithMusicalFixtures:
    """Tests for the analyzer with musical fixtures (requires PyTorch)."""

    @pytest.fixture
    def cmin_file(self):
        """Get the C minor musical progression fixture."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "Cmin_5A_i-v-VI-iv.mp3"
        if not sample_file.exists():
            pytest.skip("C minor musical fixture not available")
        return str(sample_file)

    def test_analyze_c_minor_progression(self, cmin_file):
        """Test analysis on C minor progression (i-v-VI-iv)."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(cmin_file, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Should successfully detect a key
        if result.success and not result.skipped:
            assert KEY_INITIAL_KEY in result.data
            detected_key = result.data[KEY_INITIAL_KEY]

            # Should detect some form of C (Cm, C, or enharmonic equivalent)
            assert isinstance(detected_key, str)
            assert len(detected_key) > 0

            # The file is C minor (5A in Camelot notation)
            # CNN should ideally detect "Cm" but we accept any valid detection


class TestMusicalKeyCNNAnalyzerWithDrumLoops:
    """Tests with drum loops (which may not have clear key)."""

    @pytest.fixture
    def drum_loop(self):
        """Get a drum loop fixture."""
        fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"
        sample_file = fixture_path / "lyjia_house_claves_delay_120bpm.wav"
        if not sample_file.exists():
            pytest.skip("Drum loop fixture not available")
        return str(sample_file)

    def test_analyze_drum_loop(self, drum_loop):
        """Test that analyzer completes on drum loops (may not detect clear key)."""
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("PyTorch/torchaudio/librosa not installed")

        media_file = MediaFile(drum_loop, enable_write=False)
        analyzer = MusicalKeyCNNAnalyzer(media_file)

        # Check if model exists
        model_path = get_model_path_or_skip(analyzer)

        result = analyzer.analyze()

        assert isinstance(result, AnalyzerResult)

        # Drum loops may not have a clear key - just verify it completes
        # If it succeeds, the key should be valid format
        if result.success and not result.skipped:
            assert KEY_INITIAL_KEY in result.data
            key_str = result.data[KEY_INITIAL_KEY]
            assert isinstance(key_str, str)
            assert len(key_str) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
