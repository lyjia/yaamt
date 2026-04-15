"""
Musical Key Analyzer using RapidEvolution3 algorithm.

This analyzer implements the wavelet-based key detection from RapidEvolution3,
using Continuous Wavelet Transform and modal template matching.

Reference:
    https://github.com/djqualia/RapidEvolution3
    references/RapidEvolution3/src/com/mixshare/rapid_evolution/audio/detection/key/KeyDetector.java
"""

from typing import Optional, List
import time
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import analyzer
from util.const import KEY_INITIAL_KEY, KEY_DIATONIC_MODE
from util.analyzer_options import AnalyzerOption
from util.logging import log

# Import the wavelet key detection components
from providers.analysis.key.support.wavelet import (
    KeyProbability,
    count_key_probabilities,
    KEY_DETECTOR_ANALYZE_CHUNK_SIZE
)


@analyzer(AnalyzerCategory.KEY, debug_only=True)
class RE3WaveletKeyAnalyzer(AnalyzerBase):
    """
    Musical key analyzer adapted from the RapidEvolution3 CWT algorithm.

    This analyzer implements chromatic pitch class detection using
    Continuous Wavelet Transform, followed by modal template matching
    to determine the musical key.

    The analyzer processes audio in 8192-sample chunks, extracting
    chromatic energy via wavelets and scoring against 6 modal templates
    (Ionian, Lydian, Mixolydian, Aeolian, Dorian, Phrygian). Locrian
    mode is intentionally excluded due to its harmonic instability and
    rarity in tonal music.

    Configuration: No user-configurable options at this time.
    """

    name = "RE3 Wavelet Key Analyzer"
    description = "Continuous Wavelet Transform-based key detection algorithm adapted from RapidEvolution3 by DJ Qualia."
    category = "key"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform musical key analysis using RE3 CWT algorithm.

        Returns:
            AnalyzerResult with string key value or error/skip status
        """
        audio_stream = None

        try:
            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled

            skipped = self._check_skip_if_exists(KEY_INITIAL_KEY, "Key already set")
            if skipped is not None:
                return skipped

            # Get accuracy setting (percentage of audio to analyze)
            # Default to 100% for maximum accuracy, matching RE3's default
            percent_to_analyze = self.options.get('percent_audio_samples_to_process', 100)
            if percent_to_analyze < 10:
                percent_to_analyze = 10  # Minimum 10%
            elif percent_to_analyze > 100:
                percent_to_analyze = 100  # Maximum 100%

            # Start timing
            start_time = time.perf_counter()

            # Open audio stream in native format (do NOT normalize)
            # Java implementation uses RAW integer values, same as BPM analyzer
            audio_stream = self.media_file.get_audio_stream(None)

            # Get stream properties
            sample_rate = audio_stream.sample_rate
            duration = self.media_file.length_in_seconds

            if duration <= 0:
                return AnalyzerResult(
                    success=False,
                    error="Could not determine track duration"
                )

            log.info(f"RE3 key analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {sample_rate}Hz, duration: {duration:.2f}s")
            log.debug(f"  Accuracy setting: {percent_to_analyze}% of audio will be analyzed")

            # Calculate maximum frequency (Nyquist)
            # Java: int maxfrequency = (int) decoder.getMaxFrequency();
            max_frequency = int(sample_rate / 2)

            # Calculate time per chunk
            # Java: double timeinterval = (double) KEY_DETECTOR_ANALYZE_CHUNK_SIZE / decoder.getSampleRate();
            time_interval = float(KEY_DETECTOR_ANALYZE_CHUNK_SIZE) / sample_rate

            # Initialize KeyProbability accumulator
            # Java: KeyProbability segment_probabilities = null;
            #       double segmentTime = KEY_DETECTOR_ANALYZE_CHUNK_SIZE / decoder.getAudioFormat().getSampleRate() * 1000;
            #       segment_probabilities = new KeyProbability(segmentTime);
            segment_time_ms = KEY_DETECTOR_ANALYZE_CHUNK_SIZE / sample_rate * 1000
            segment_probabilities = KeyProbability(segment_time_ms)

            # Working arrays for CWT calculation
            # Java: double[] norm_keycount = new double[12];
            #       double[] cwt = new double[12];
            norm_keycount = np.zeros(12, dtype=np.float64)
            cwt = np.zeros(12, dtype=np.float64)

            # Stream audio and process
            total_samples = int(sample_rate * duration)
            samples_read = 0
            chunks_processed = 0
            chunks_skipped = 0

            # Calculate chunk selection strategy
            chunk_count = 0
            total_chunks = total_samples // KEY_DETECTOR_ANALYZE_CHUNK_SIZE

            # Check if sectional sampling is enabled (default: False for uniform sampling)
            use_sectional_sampling = self.options.get('intelligent_sampling', False)

            # For sectional sampling, divide song into sections and sample from each
            # This ensures we get samples from intro, middle, and outro
            if use_sectional_sampling and percent_to_analyze < 100 and total_chunks > 10:
                # Calculate how many chunks to process
                target_chunks = max(1, int(total_chunks * percent_to_analyze / 100))

                # Divide song into sections
                if target_chunks >= 3:
                    # Sample from beginning (30%), middle (40%), end (30%)
                    sections = [
                        (0, int(total_chunks * 0.3)),  # Intro
                        (int(total_chunks * 0.3), int(total_chunks * 0.7)),  # Middle
                        (int(total_chunks * 0.7), total_chunks)  # Outro
                    ]
                    chunks_per_section = [
                        int(target_chunks * 0.3),  # 30% from intro
                        int(target_chunks * 0.4),  # 40% from middle
                        target_chunks - int(target_chunks * 0.3) - int(target_chunks * 0.4)  # Rest from outro
                    ]
                else:
                    # For very low sampling, just take from middle
                    sections = [(int(total_chunks * 0.4), int(total_chunks * 0.6))]
                    chunks_per_section = [target_chunks]

                # Build set of chunks to process
                chunks_to_process = set()
                for (start, end), num_chunks in zip(sections, chunks_per_section):
                    if num_chunks > 0 and end > start:
                        section_size = end - start
                        step = max(1, section_size // num_chunks)
                        for i in range(num_chunks):
                            chunk_idx = start + (i * step)
                            if chunk_idx < end:
                                chunks_to_process.add(chunk_idx)

                log.debug(f"Sectional sampling: processing {len(chunks_to_process)} of {total_chunks} chunks")
            else:
                # Process all chunks or use simple interval sampling for short files
                chunks_to_process = None
                process_every_n_chunks = int(100.0 / percent_to_analyze) if percent_to_analyze < 100 else 1

            log.debug(f"Processing {total_samples} samples in {KEY_DETECTOR_ANALYZE_CHUNK_SIZE}-sample chunks")
            if percent_to_analyze < 100:
                if chunks_to_process is not None:
                    log.debug(f"  Using sectional sampling for {percent_to_analyze}% accuracy")
                else:
                    log.debug(f"  Processing every {process_every_n_chunks} chunks for {percent_to_analyze}% accuracy")

            while True:
                # Check for cancellation
                if self.is_cancelled:
                    return AnalyzerResult(
                        success=False,
                        error="Analysis cancelled by user"
                    )

                # Read chunk (size must match KEY_DETECTOR_ANALYZE_CHUNK_SIZE)
                # Java: long frames_read = decoder.readFrames(KEY_DETECTOR_ANALYZE_CHUNK_SIZE);
                audio_bytes = audio_stream.read(KEY_DETECTOR_ANALYZE_CHUNK_SIZE)
                if not audio_bytes:
                    break

                # Convert to float samples (UN normalized - matches Java implementation)
                # Java uses raw integer values, not normalized to [-1.0, 1.0]
                if audio_stream.sample_width == 2:  # 16-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
                elif audio_stream.sample_width == 4:  # 32-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float64)
                else:
                    # For float32 input, scale to match 16-bit range
                    samples = np.frombuffer(audio_bytes, dtype=np.float32).astype(np.float64)
                    samples = samples * 32768.0

                # Sum multi-channel audio to mono (matches Java behavior)
                # Java: for (int c = 0; c < buffer.getNumChannels(); ++c)
                #           val += data[c][f];
                num_channels = audio_stream.channels_qty
                if num_channels > 1:
                    samples = samples.reshape(-1, num_channels).sum(axis=1)

                # Check if we have enough samples for a full chunk
                frames_read = len(samples)

                # Handle incomplete final chunk (RE3 loops the data to fill)
                # Java: if ((frames_read < KEY_DETECTOR_ANALYZE_CHUNK_SIZE) && (frames_read > 0)) {
                #           ...loop audio to fill...
                #       }
                if 0 < frames_read < KEY_DETECTOR_ANALYZE_CHUNK_SIZE:
                    log.debug(f"Incomplete chunk ({frames_read} samples), looping to fill {KEY_DETECTOR_ANALYZE_CHUNK_SIZE}")
                    # OPTIMIZATION: Pad by repeating using numpy.tile
                    # Calculate how many repeats we need
                    repeats = (KEY_DETECTOR_ANALYZE_CHUNK_SIZE + frames_read - 1) // frames_read
                    samples = np.tile(samples, repeats)[:KEY_DETECTOR_ANALYZE_CHUNK_SIZE]
                    frames_read = KEY_DETECTOR_ANALYZE_CHUNK_SIZE

                # Process full chunks only
                if frames_read == KEY_DETECTOR_ANALYZE_CHUNK_SIZE:
                    chunk_count += 1

                    # Decide whether to process or skip this chunk based on accuracy setting
                    if chunks_to_process is not None:
                        # Using intelligent sampling - check if this chunk is in our set
                        should_process = (chunk_count - 1) in chunks_to_process
                    else:
                        # Using simple interval sampling (RE3 approach)
                        should_process = (percent_to_analyze == 100) or (chunk_count % process_every_n_chunks == 1)

                    if should_process:
                        # Perform CWT analysis
                        # Java: analyzeSegment(decoder.getAudioBuffer(), decoder, norm_keycount, segment_probabilities, cwt);
                        count_key_probabilities(
                            wavedata=samples,
                            icount=0,
                            amt=KEY_DETECTOR_ANALYZE_CHUNK_SIZE,
                            time=time_interval,
                            maxfreq=max_frequency,
                            segment_probabilities=segment_probabilities,
                            norm_keycount=norm_keycount,
                            cwt=cwt
                        )
                        chunks_processed += 1
                    else:
                        chunks_skipped += 1

                    samples_read += frames_read

                    # Log progress periodically
                    if chunk_count % 100 == 0:
                        progress_pct = (samples_read / total_samples) * 100
                        if chunks_skipped > 0:
                            log.debug(f"  Processed {chunks_processed} chunks, skipped {chunks_skipped} ({progress_pct:.1f}% of file read)")
                        else:
                            log.debug(f"  Processed {chunks_processed} chunks ({progress_pct:.1f}%)")

                elif frames_read == 0:
                    # End of stream
                    break

            # Finalize analysis
            # Java: segment_probabilities.finish();
            segment_probabilities.finish()

            # Check if we got any data
            # Java: if (!segment_probabilities.hasNoData()) {
            if segment_probabilities.has_no_data():
                return AnalyzerResult(
                    success=False,
                    error="No chromatic data detected - file may be silent or corrupted"
                )

            # Get detected key (with optional mode detection)
            # Java: DetectedKey end_key = segment_probabilities.getDetectedKey();
            #       Key key = segment_probabilities.getDetectedKey(true).getStartKey();
            detect_mode = self.options.get('detect_mode', False)
            detected_key = segment_probabilities.get_detected_key(log_details=False, detect_mode=detect_mode)

            if not detected_key.is_valid() or not detected_key.start_key:
                return AnalyzerResult(
                    success=False,
                    error="Could not detect key - no clear tonality found"
                )

            # Calculate and log elapsed time
            elapsed_time = time.perf_counter() - start_time

            # Log result with mode if detected
            analysis_info = f"[analysis took {elapsed_time:.2f}s"
            if chunks_skipped > 0:
                speedup = (chunks_processed + chunks_skipped) / chunks_processed if chunks_processed > 0 else 1.0
                analysis_info += f", {speedup:.1f}x speedup from {percent_to_analyze}% sampling"
            analysis_info += "]"

            if detected_key.mode:
                log.info(f"RE3 detected key: {detected_key.start_key} {detected_key.mode} (accuracy: {detected_key.accuracy:.2f}) for {self.media_file.file_path} {analysis_info}")
            else:
                log.info(f"RE3 detected key: {detected_key.start_key} (accuracy: {detected_key.accuracy:.2f}) for {self.media_file.file_path} {analysis_info}")

            # Prepare result data
            # Return key string (Tag Transformation system handles notation conversion)
            # The detected key is in RE3 format (e.g., "Am", "C", "F#m")
            # YAAMT's MusicalKeyFormatter will convert to user's preferred notation
            result_data = {KEY_INITIAL_KEY: detected_key.start_key}

            # Include mode if detected (consumer will handle appending to comments)
            if detected_key.mode:
                result_data[KEY_DIATONIC_MODE] = detected_key.mode

            return AnalyzerResult(
                success=True,
                data=result_data
            )

        except InterruptedError:
            return AnalyzerResult(
                success=False,
                error="Analysis cancelled by user"
            )
        except Exception as e:
            log.error(f"RE3 key analysis failed for {self.media_file.file_path}: {e}", exc_info=True)
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
            List of AnalyzerOption instances for wavelet key analyzer options
        """
        return [
            AnalyzerOption(
                name='percent_audio_samples_to_process',
                type='slider',
                default=100,
                min=10,
                max=100,
                interval=10,
                suffix='%',
                help='Percentage of audio to analyze (lower = faster but may be less accurate)'
            ),
            AnalyzerOption(
                name='intelligent_sampling',
                type='bool',
                default=False,
                help='Use sectional sampling (intro/middle/outro) vs uniform interval sampling'
            ),
            AnalyzerOption(
                name='detect_mode',
                type='bool',
                default=False,
                help='Detect and report musical mode (ionian, dorian, phrygian, etc.)'
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring key analyzer parameters.

        Returns:
            QWidget with accuracy slider and mode detection checkbox
        """
        from PySide6.QtWidgets import QCheckBox, QSlider, QHBoxLayout, QSpinBox, QGroupBox
        from PySide6.QtCore import Qt
        from models.settings import settings

        widget = QWidget()
        layout = QVBoxLayout()

        # Info label
        info_label = QLabel(
            "This analyzer uses the RapidEvolution3 wavelet-based key detection algorithm."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Accuracy/Speed slider group
        accuracy_group = QGroupBox("Analysis Speed vs Accuracy")
        accuracy_layout = QVBoxLayout()

        # Description
        accuracy_desc = QLabel(
            "Adjust the percentage of audio to analyze. Lower values are faster but may be less accurate."
        )
        accuracy_desc.setWordWrap(True)
        accuracy_desc.setStyleSheet("font-size: 10px;")
        accuracy_layout.addWidget(accuracy_desc)

        # Slider with labels
        slider_layout = QHBoxLayout()

        # Labels
        fast_label = QLabel("Faster")
        fast_label.setStyleSheet("font-size: 10px;")
        accurate_label = QLabel("More Accurate")
        accurate_label.setStyleSheet("font-size: 10px;")

        # Slider
        accuracy_slider = QSlider(Qt.Horizontal)
        accuracy_slider.setObjectName("percent_audio_samples_to_process")
        accuracy_slider.setMinimum(10)
        accuracy_slider.setMaximum(100)
        accuracy_slider.setSingleStep(10)
        accuracy_slider.setTickInterval(10)
        accuracy_slider.setTickPosition(QSlider.TicksBelow)

        # SpinBox to show percentage
        percent_spinbox = QSpinBox()
        percent_spinbox.setObjectName("percent_audio_samples_to_process_spinbox")
        percent_spinbox.setMinimum(10)
        percent_spinbox.setMaximum(100)
        percent_spinbox.setSingleStep(10)
        percent_spinbox.setSuffix("%")
        percent_spinbox.setMaximumWidth(60)

        # Load saved value or use default
        settings.beginGroup("analyzers/WaveletKeyAnalyzer")
        saved_accuracy = settings.value("percent_audio_samples_to_process", 100, type=int)
        settings.endGroup()

        accuracy_slider.setValue(saved_accuracy)
        percent_spinbox.setValue(saved_accuracy)

        # Connect slider and spinbox
        accuracy_slider.valueChanged.connect(lambda v: percent_spinbox.setValue(v))
        percent_spinbox.valueChanged.connect(lambda v: accuracy_slider.setValue(v))

        # Save preference on change
        def save_accuracy_pref(value):
            settings.beginGroup("analyzers/WaveletKeyAnalyzer")
            settings.setValue("percent_audio_samples_to_process", value)
            settings.endGroup()

        accuracy_slider.valueChanged.connect(save_accuracy_pref)

        slider_layout.addWidget(fast_label)
        slider_layout.addWidget(accuracy_slider)
        slider_layout.addWidget(accurate_label)
        slider_layout.addWidget(percent_spinbox)

        accuracy_layout.addLayout(slider_layout)

        # Sampling strategy checkbox
        sectional_checkbox = QCheckBox("Use sectional sampling (intro/middle/outro)")
        sectional_checkbox.setObjectName("intelligent_sampling")  # Keep name for compatibility
        sectional_checkbox.setToolTip(
            "When enabled with reduced accuracy, samples chunks from the beginning, middle, and end of the song. "
            "When disabled, uses uniform interval sampling throughout the entire track."
        )
        sectional_checkbox.setStyleSheet("font-size: 10px;")

        # Load saved sampling preference
        settings.beginGroup("analyzers/WaveletKeyAnalyzer")
        saved_sectional = settings.value("intelligent_sampling", False, type=bool)  # Default to False (uniform)
        settings.endGroup()

        sectional_checkbox.setChecked(saved_sectional)

        # Save preference on change
        def save_sectional_pref(checked):
            settings.beginGroup("analyzers/WaveletKeyAnalyzer")
            settings.setValue("intelligent_sampling", checked)
            settings.endGroup()

        sectional_checkbox.stateChanged.connect(save_sectional_pref)
        accuracy_layout.addWidget(sectional_checkbox)

        accuracy_group.setLayout(accuracy_layout)
        layout.addWidget(accuracy_group)

        # Mode detection checkbox
        mode_checkbox = QCheckBox("Detect and report musical mode")
        mode_checkbox.setObjectName("detect_mode")

        # Load saved mode detection preference
        settings.beginGroup("analyzers/WaveletKeyAnalyzer")
        saved_mode = settings.value("detect_mode", False, type=bool)
        settings.endGroup()

        mode_checkbox.setChecked(saved_mode)
        mode_checkbox.setToolTip(
            "When enabled, the analyzer will identify the musical mode (ionian, dorian, phrygian, etc.) "
            "and append it to the track's comments field."
        )

        # Save preference on change
        def save_mode_pref(checked):
            settings.beginGroup("analyzers/WaveletKeyAnalyzer")
            settings.setValue("detect_mode", checked)
            settings.endGroup()

        mode_checkbox.stateChanged.connect(save_mode_pref)
        layout.addWidget(mode_checkbox)

        layout.addStretch()
        widget.setLayout(layout)
        return widget
