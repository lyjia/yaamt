"""
Aubio BPM analyzer using aubio's tempo detection algorithm.

This analyzer detects BPM using the aubio library's beat tracking system.
It streams audio data and returns raw float BPM values.
"""

from typing import Optional, List
import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox,
                                QSpinBox, QGroupBox, QLabel)

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption
from util.bpm import BpmCandidate
from util.logging import log


@analyzer(AnalyzerCategory.BPM)
class AubioBPMAnalyzer(AnalyzerBase):
    """
    BPM analyzer using aubio's tempo detection algorithm.

    This analyzer uses aubio.tempo to detect beats in audio streams and
    calculates BPM from beat intervals. It requests mono audio via the
    Audio Format Adaptation system and returns raw float BPM values.

    Analyzer-specific options:
        - 'method' (str): Beat detection algorithm (default: "default")
        - 'buf_size' (int): Window size in samples (default: 1024)
        - 'hop_size' (int): Hop size in samples (default: 512)
        - 'samplerate' (int): Sample rate for analysis (default: 0 = native)
        - 'mode' (str): Processing preset ("default" or "fast")
    """

    name = "Aubio BPM Analyzer"
    description = "Detects tempo using aubio's beat tracking algorithm"
    category = "bpm"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform BPM analysis using aubio.

        Returns:
            AnalyzerResult with raw float BPM value or error/skip status
        """
        audio_stream = None

        try:
            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled

            skipped = self._check_skip_if_exists('bpm', "BPM already set")
            if skipped is not None:
                return skipped

            # Import aubio (fail gracefully if not available)
            try:
                import aubio
            except ImportError:
                return AnalyzerResult(
                    success=False,
                    error="aubio library not available - please install with: pip install aubio"
                )

            # Get analyzer options
            mode = self.options.get('mode', 'default')

            # Apply mode presets
            if mode == 'fast':
                buf_size = self.options.get('buf_size', 512)
                hop_size = self.options.get('hop_size', 128)
                target_samplerate = self.options.get('samplerate', 8000)
            else:  # default mode
                buf_size = self.options.get('buf_size', 1024)
                hop_size = self.options.get('hop_size', 512)
                target_samplerate = self.options.get('samplerate', 0)  # 0 = use native

            method = self.options.get('method', 'default')

            # Create format descriptor requesting mono audio
            format_descriptor = AudioFormatDescriptor(
                channels=1,
                sample_rate=target_samplerate if target_samplerate > 0 else None
            )

            # Open audio stream (Audio Format Adaptation system handles conversion)
            audio_stream = self.media_file.get_audio_stream(format_descriptor)

            # Get actual sample rate from stream
            samplerate = audio_stream.sample_rate

            log.debug(f"Aubio analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {samplerate}Hz, buf_size: {buf_size}, hop_size: {hop_size}, method: {method}")

            # Initialize aubio tempo detector
            tempo = aubio.tempo(method, buf_size, hop_size, samplerate)

            # Process audio stream and collect beat timestamps
            beats = []
            samples_read = 0

            while True:
                # Check for cancellation periodically
                if self.is_cancelled:
                    return AnalyzerResult(
                        success=False,
                        error="Analysis cancelled by user"
                    )

                # Read audio chunk (read hop_size FRAMES, not bytes)
                audio_bytes = audio_stream.read(hop_size)
                if not audio_bytes:
                    break

                # Convert bytes to numpy array
                # Audio stream should be mono (from Audio Format Adaptation system)
                if audio_stream.sample_width == 2:  # 16-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                    samples = samples / 32768.0  # Normalize to [-1.0, 1.0]
                elif audio_stream.sample_width == 4:  # 32-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32)
                    samples = samples / 2147483648.0  # Normalize to [-1.0, 1.0]
                else:
                    log.warning(f"Unsupported sample width: {audio_stream.sample_width} bytes")
                    samples = np.frombuffer(audio_bytes, dtype=np.float32)

                # Pad if needed (last chunk might be smaller)
                if len(samples) < hop_size:
                    samples = np.pad(samples, (0, hop_size - len(samples)))

                # Feed to tempo detector
                is_beat = tempo(samples)

                # If beat detected, store timestamp
                if is_beat:
                    beat_time = tempo.get_last_s()
                    beats.append(beat_time)

                samples_read += len(samples)

            log.debug(f"  Detected {len(beats)} beats in {samples_read / samplerate:.2f}s")

            # Calculate BPM from beat intervals
            # This matches the aubio command-line tool's calculation method
            if len(beats) < 2:
                return AnalyzerResult(
                    success=False,
                    error=f"Insufficient beats detected ({len(beats)} beats) - track may be too short or have unclear rhythm"
                )

            # Calculate intervals between consecutive beats
            intervals = np.diff(beats)

            # Filter out zero or very small intervals (avoid division by zero)
            # Minimum interval of 0.1s = maximum 600 BPM (unrealistic for most music)
            valid_intervals = intervals[intervals > 0.1]

            if len(valid_intervals) == 0:
                return AnalyzerResult(
                    success=False,
                    error="Could not determine tempo - beat intervals too irregular"
                )

            # Calculate BPM for each interval, then take the mean
            # This matches aubio's reference implementation in cmd.py:
            #   bpms = 60. / np.diff(self.beat_locations)
            #   median_bpm = np.mean(bpms)
            bpms = 60.0 / valid_intervals
            bpm = np.mean(bpms)

            log.info(f"Aubio analyzer detected raw BPM: {bpm:.2f} for {self.media_file.file_path}")

            # Return BPM candidate (aubio doesn't provide confidence scores)
            # Range adjustment is handled by the dispatcher
            return AnalyzerResult(
                success=True,
                data={'bpm_candidates': [BpmCandidate(bpm=float(bpm), certainty=0.0)]}
            )

        except ImportError as e:
            log.error(f"Aubio library import failed: {e}")
            return AnalyzerResult(
                success=False,
                error=f"aubio library not available: {e}"
            )
        except Exception as e:
            log.error(f"Aubio analysis failed for {self.media_file.file_path}: {e}")
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
            List of AnalyzerOption instances for aubio-specific options
        """
        return [
            AnalyzerOption(
                name='method',
                type='choice',
                default='default',
                help='Beat detection algorithm used for onset detection',
                choices=[
                    'default',
                    'specdiff',
                    'energy',
                    'hfc',
                    'complex',
                    'phase',
                    'wphase',
                    'kl',
                    'mkl',
                    'specflux'
                ]
            ),
            AnalyzerOption(
                name='mode',
                type='choice',
                default='default',
                help='Processing preset for speed vs quality tradeoff',
                choices=[
                    ('default', 'Default (balanced speed/quality)'),
                    ('fast', 'Fast (lower quality, faster processing)')
                ]
            ),
            AnalyzerOption(
                name='buf_size',
                type='int',
                default=1024,
                min=128,
                max=8192,
                interval=128,
                help='Size of analysis window in samples (larger = more accurate but slower)'
            ),
            AnalyzerOption(
                name='hop_size',
                type='int',
                default=512,
                min=64,
                max=4096,
                interval=64,
                help='Number of samples between analysis windows (smaller = more precise but slower)'
            ),
            AnalyzerOption(
                name='samplerate',
                type='int',
                default=0,
                min=0,
                max=192000,
                interval=1000,
                help='Target sample rate for analysis (0 = use file\'s native rate)'
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring aubio analyzer parameters.

        Uses option metadata with custom grouping for advanced settings.

        Returns:
            QWidget with controls for method, mode, and advanced parameters
        """
        # Imported lazily so this provider module can be loaded in CLI /
        # headless contexts without dragging in the GUI widget layer.
        from windows.analyzer.option_widgets import build_widget_from_option

        widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        options = cls.get_options_metadata()
        settings_group = f"analyzers/{cls.__name__}"

        # Add basic options (method and mode) directly
        for option in options:
            if option.name in ('method', 'mode'):
                option_widget = build_widget_from_option(option, settings_group)
                main_layout.addWidget(option_widget)

        # Group advanced settings in collapsible group
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)  # Collapsed by default
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(4)

        for option in options:
            if option.name in ('buf_size', 'hop_size', 'samplerate'):
                option_widget = build_widget_from_option(option, settings_group)
                advanced_layout.addWidget(option_widget)

        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)

        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget
