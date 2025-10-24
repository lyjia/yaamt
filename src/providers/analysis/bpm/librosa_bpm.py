"""
Librosa BPM analyzer using librosa's beat tracking algorithm.

This analyzer detects BPM using the librosa library's beat tracking system.
It loads the entire audio file into memory as a numpy array and returns
raw float BPM values.
"""

from typing import Optional, List
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption, build_widget_from_option
from util.logging import log


class LibrosaBPMAnalyzer(AnalyzerBase):
    """
    BPM analyzer using librosa's beat tracking algorithm.

    This analyzer uses librosa.beat.beat_track() to detect beats in audio
    and calculates BPM. It loads the entire audio file into memory as a
    numpy array, so it may use significant memory for long files.

    Analyzer-specific options:
        - 'start_bpm' (float): Initial tempo estimate (default: 120.0)
        - 'tightness' (float): Tightness of beat tracking (default: 100)
        - 'trim' (bool): Trim leading/trailing silence (default: True)
        - 'aggregate_method' (str): How to combine onsets ("median" or "mean")
        - 'hop_length' (int): Number of samples between frames (default: 512)
    """

    name = "Librosa BPM Analyzer"
    description = "Detects tempo using librosa's beat tracking algorithm"
    category = "bpm"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform BPM analysis using librosa.

        Returns:
            AnalyzerResult with raw float BPM value or error/skip status
        """
        audio_stream = None

        try:
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if BPM already exists (skip if requested)
            skip_if_exists = self.options.get('skip_if_tag_exists', False)
            existing_bpm = self.media_file.get_tag_simple('bpm')

            if existing_bpm and skip_if_exists:
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="BPM already set"
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
            start_bpm = self.options.get('start_bpm', 120.0)
            tightness = self.options.get('tightness', 100)
            trim = self.options.get('trim', True)
            aggregate_method = self.options.get('aggregate_method', 'median')
            hop_length = self.options.get('hop_length', 512)

            # Create format descriptor requesting mono float32 audio
            format_descriptor = AudioFormatDescriptor(
                channels=1,
                sample_width=4,
                sample_format='float'
            )

            # Open audio stream
            audio_stream = self.media_file.get_audio_stream(format_descriptor)
            sample_rate = audio_stream.sample_rate

            log.debug(f"Librosa BPM analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {sample_rate}Hz, start_bpm: {start_bpm}, "
                     f"tightness: {tightness}, aggregate: {aggregate_method}")

            # Convert audio stream to numpy array
            from util.audio_numpy import audio_stream_to_mono_numpy

            # Check file duration to warn about memory usage
            duration = self.media_file.length_in_seconds
            if duration > 600:  # 10 minutes
                log.warning(f"File is {duration:.1f}s long - librosa BPM analysis may use significant memory")

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

            # Compute onset strength envelope with specified aggregation
            aggregate_func = np.median if aggregate_method == 'median' else np.mean
            onset_env = librosa.onset.onset_strength(
                y=y,
                sr=sr,
                hop_length=hop_length,
                aggregate=aggregate_func
            )

            # Perform beat tracking
            tempo, beat_frames = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sr,
                start_bpm=start_bpm,
                tightness=tightness,
                trim=trim,
                hop_length=hop_length
            )

            # tempo is returned as a numpy scalar or array
            # Convert to Python float
            if isinstance(tempo, np.ndarray):
                bpm = float(tempo[0]) if len(tempo) > 0 else float(tempo)
            else:
                bpm = float(tempo)

            log.info(f"Librosa analyzer detected BPM: {bpm:.2f} ({len(beat_frames)} beats) "
                    f"for {self.media_file.file_path}")

            # Return raw float BPM value (Tag Transformations system handles formatting)
            return AnalyzerResult(
                success=True,
                data={'bpm': bpm}
            )

        except ImportError as e:
            log.error(f"Librosa library import failed: {e}")
            return AnalyzerResult(
                success=False,
                error=f"librosa library not available: {e}"
            )
        except Exception as e:
            log.error(f"Librosa BPM analysis failed for {self.media_file.file_path}: {e}")
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

    @classmethod
    def get_options_metadata(cls) -> List[AnalyzerOption]:
        """
        Return option metadata for this analyzer.

        Returns:
            List of AnalyzerOption instances for librosa-specific options
        """
        return [
            AnalyzerOption(
                name='start_bpm',
                type='float',
                default=120.0,
                min=40.0,
                max=240.0,
                interval=1.0,
                help='Initial tempo estimate in BPM'
            ),
            AnalyzerOption(
                name='tightness',
                type='float',
                default=100.0,
                min=0.0,
                max=1000.0,
                interval=10.0,
                help='Tightness of beat tracking (higher = more rigid tempo)'
            ),
            AnalyzerOption(
                name='trim',
                type='bool',
                default=True,
                help='Trim leading and trailing silence before analysis'
            ),
            AnalyzerOption(
                name='aggregate_method',
                type='choice',
                default='median',
                help='Method for combining onset detection functions',
                choices=[
                    ('median', 'Median (robust to outliers)'),
                    ('mean', 'Mean (faster but less robust)')
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
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring librosa BPM analyzer parameters.

        Returns:
            QWidget with controls for tempo estimation and beat tracking parameters
        """
        widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        # Info label
        info_label = QLabel(
            "Librosa loads the entire audio file into memory. "
            "For very long files (>10 minutes), this may use significant memory."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(info_label)

        options = cls.get_options_metadata()
        settings_group = f"analyzers/{cls.__name__}"

        # Add basic options (start_bpm, aggregate_method, trim) directly
        for option in options:
            if option.name in ('start_bpm', 'aggregate_method', 'trim'):
                option_widget = build_widget_from_option(option, settings_group)
                main_layout.addWidget(option_widget)

        # Group advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)  # Collapsed by default
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(4)

        for option in options:
            if option.name in ('tightness', 'hop_length'):
                option_widget = build_widget_from_option(option, settings_group)
                advanced_layout.addWidget(option_widget)

        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)

        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget


# Register this analyzer with the BPM category
register_analyzer(AnalyzerCategory.BPM, LibrosaBPMAnalyzer)
