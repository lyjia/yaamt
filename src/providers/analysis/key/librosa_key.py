"""
Librosa Key analyzer using chromagram and Krumhansl-Schmuckler algorithm.

This analyzer detects musical key using librosa's chromagram features
combined with the Krumhansl-Schmuckler key-finding algorithm. It loads
the entire audio file into memory as a numpy array.
"""

from typing import Optional, List
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption, build_widget_from_option
from util.const import KEY_INITIAL_KEY
from util.logging import log


# Krumhansl-Schmuckler key profiles
# Major and minor key profiles from Krumhansl & Kessler (1982)
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Pitch class names
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


class LibrosaKeyAnalyzer(AnalyzerBase):
    """
    Musical key analyzer using librosa chromagram and Krumhansl-Schmuckler algorithm.

    This analyzer computes a chromagram (pitch class distribution) using librosa,
    then applies the Krumhansl-Schmuckler key-finding algorithm to determine the
    most likely musical key (major or minor).

    The analyzer loads the entire audio file into memory, so it may use significant
    memory for long files.

    Analyzer-specific options:
        - 'chromagram_type' (str): Type of chromagram ("cqt" or "stft")
        - 'hop_length' (int): Number of samples between frames (default: 512)
        - 'n_chroma' (int): Number of chroma bins (default: 12)
    """

    name = "Librosa Key Analyzer"
    description = "Detects musical key using chromagram and Krumhansl-Schmuckler algorithm"
    category = "key"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform musical key analysis using librosa chromagram.

        Returns:
            AnalyzerResult with key string or error/skip status
        """
        audio_stream = None

        try:
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if key already exists (skip if requested)
            skip_if_exists = self.options.get('skip_if_tag_exists', False)
            existing_key = self.media_file.get_tag_simple(KEY_INITIAL_KEY)

            if existing_key and skip_if_exists:
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="Key already set"
                )

            # Import librosa (fail gracefully if not available)
            try:
                import librosa
            except ImportError:
                return AnalyzerResult(
                    success=False,
                    error="librosa library not available - please install with: pip install librosa"
                )

            # Get analyzer options
            chromagram_type = self.options.get('chromagram_type', 'cqt')
            hop_length = self.options.get('hop_length', 512)
            n_chroma = self.options.get('n_chroma', 12)

            # Create format descriptor requesting mono float32 audio
            format_descriptor = AudioFormatDescriptor(
                channels=1,
                sample_width=4,
                sample_format='float'
            )

            # Open audio stream
            audio_stream = self.media_file.get_audio_stream(format_descriptor)
            sample_rate = audio_stream.sample_rate

            log.debug(f"Librosa key analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {sample_rate}Hz, chromagram: {chromagram_type}, "
                     f"hop_length: {hop_length}")

            # Convert audio stream to numpy array
            from util.audio_numpy import audio_stream_to_mono_numpy

            # Check file duration to warn about memory usage
            duration = self.media_file.length_in_seconds
            if duration > 600:  # 10 minutes
                log.warning(f"File is {duration:.1f}s long - librosa key analysis may use significant memory")

            y, sr = audio_stream_to_mono_numpy(audio_stream)

            # Close stream early to free resources
            audio_stream.close()
            audio_stream = None

            if len(y) == 0:
                return AnalyzerResult(
                    success=False,
                    error="No audio data available"
                )

            log.debug(f"  Loaded {len(y)} samples ({len(y)/sr:.2f}s)")

            # Check for cancellation before starting analysis
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Compute chromagram
            if chromagram_type == 'cqt':
                # Constant-Q chromagram (more accurate for key detection)
                chromagram = librosa.feature.chroma_cqt(
                    y=y,
                    sr=sr,
                    hop_length=hop_length,
                    n_chroma=n_chroma
                )
            else:  # stft
                # STFT-based chromagram (faster but less accurate)
                chromagram = librosa.feature.chroma_stft(
                    y=y,
                    sr=sr,
                    hop_length=hop_length,
                    n_chroma=n_chroma
                )

            # Average chromagram over time to get overall pitch class distribution
            # Shape: (12,) representing relative energy for each pitch class
            chroma_mean = np.mean(chromagram, axis=1)

            log.debug(f"  Computed chromagram, shape: {chromagram.shape}")

            # Apply Krumhansl-Schmuckler algorithm
            key, mode, correlation = self._krumhansl_schmuckler(chroma_mean)

            # Format key name (e.g., "C", "Am", "F#m")
            if mode == 'minor':
                key_str = f"{key}m"
            else:
                key_str = key

            log.info(f"Librosa analyzer detected key: {key_str} (correlation: {correlation:.3f}) "
                    f"for {self.media_file.file_path}")

            # Return key string (Tag Transformation system handles notation conversion)
            return AnalyzerResult(
                success=True,
                data={KEY_INITIAL_KEY: key_str}
            )

        except ImportError as e:
            log.error(f"Librosa library import failed: {e}")
            return AnalyzerResult(
                success=False,
                error=f"librosa library not available: {e}"
            )
        except Exception as e:
            log.error(f"Librosa key analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(
                success=False,
                error=str(e)
            )
        finally:
            # Always close audio stream
            if audio_stream:
                try:
                    audio_stream.close()
                except Exception as e:
                    log.warning(f"Error closing audio stream: {e}")

    def _krumhansl_schmuckler(self, chroma_mean: np.ndarray) -> tuple[str, str, float]:
        """
        Apply Krumhansl-Schmuckler key-finding algorithm.

        Args:
            chroma_mean: Average chromagram, shape (12,) with values for each pitch class

        Returns:
            Tuple of (key, mode, correlation) where:
                - key is pitch class name (e.g., 'C', 'F#')
                - mode is 'major' or 'minor'
                - correlation is the correlation coefficient (higher = more confident)
        """
        # Normalize chroma to unit length
        chroma_norm = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-8)

        best_correlation = -1.0
        best_key = 'C'
        best_mode = 'major'

        # Try all 24 possible keys (12 major + 12 minor)
        for i in range(12):
            # Rotate profiles to match each pitch class
            major_profile_rotated = np.roll(MAJOR_PROFILE, i)
            minor_profile_rotated = np.roll(MINOR_PROFILE, i)

            # Normalize profiles
            major_norm = major_profile_rotated / (np.linalg.norm(major_profile_rotated) + 1e-8)
            minor_norm = minor_profile_rotated / (np.linalg.norm(minor_profile_rotated) + 1e-8)

            # Calculate correlation (dot product of normalized vectors)
            major_corr = np.dot(chroma_norm, major_norm)
            minor_corr = np.dot(chroma_norm, minor_norm)

            # Check if this major key is the best so far
            if major_corr > best_correlation:
                best_correlation = major_corr
                best_key = PITCH_CLASSES[i]
                best_mode = 'major'

            # Check if this minor key is the best so far
            if minor_corr > best_correlation:
                best_correlation = minor_corr
                best_key = PITCH_CLASSES[i]
                best_mode = 'minor'

        return best_key, best_mode, best_correlation

    @classmethod
    def get_options_metadata(cls) -> List[AnalyzerOption]:
        """
        Return option metadata for this analyzer.

        Returns:
            List of AnalyzerOption instances for librosa key analyzer options
        """
        return [
            AnalyzerOption(
                name='chromagram_type',
                type='choice',
                default='cqt',
                help='Type of chromagram to compute',
                choices=[
                    ('cqt', 'Constant-Q Transform (more accurate, slower)'),
                    ('stft', 'Short-Time Fourier Transform (faster, less accurate)')
                ]
            ),
            AnalyzerOption(
                name='hop_length',
                type='int',
                default=512,
                min=64,
                max=4096,
                interval=64,
                help='Number of samples between analysis frames (smaller = more precise but slower)'
            ),
            AnalyzerOption(
                name='n_chroma',
                type='int',
                default=12,
                min=12,
                max=36,
                interval=12,
                help='Number of chroma bins (12 = semitones, higher = more resolution)'
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring librosa key analyzer parameters.

        Returns:
            QWidget with controls for chromagram and key detection parameters
        """
        widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        # Info label
        info_label = QLabel(
            "Librosa loads the entire audio file into memory and uses the "
            "Krumhansl-Schmuckler algorithm for key detection. "
            "For very long files (>10 minutes), this may use significant memory."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(info_label)

        options = cls.get_options_metadata()
        settings_group = f"analyzers/{cls.__name__}"

        # Add chromagram_type option directly
        for option in options:
            if option.name == 'chromagram_type':
                option_widget = build_widget_from_option(option, settings_group)
                main_layout.addWidget(option_widget)

        # Group advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)  # Collapsed by default
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(4)

        for option in options:
            if option.name in ('hop_length', 'n_chroma'):
                option_widget = build_widget_from_option(option, settings_group)
                advanced_layout.addWidget(option_widget)

        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)

        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget


# Register this analyzer with the Key category
register_analyzer(AnalyzerCategory.KEY, LibrosaKeyAnalyzer)
