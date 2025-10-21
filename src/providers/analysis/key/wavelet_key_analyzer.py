"""
Musical Key Analyzer using RapidEvolution3 algorithm.

This analyzer implements the wavelet-based key detection from RapidEvolution3,
using Continuous Wavelet Transform and modal template matching.

Reference: https://github.com/djqualia/RapidEvolution3
"""

from typing import Optional
import time
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from util.logging import log

# Import the wavelet key detection components
from providers.analysis.key.support.wavelet import (
    KeyProbability,
    count_key_probabilities,
    KEY_DETECTOR_ANALYZE_CHUNK_SIZE
)


class WaveletKeyAnalyzer(AnalyzerBase):
    """
    Musical key analyzer using the RapidEvolution3 CWT algorithm.

    This analyzer implements chromatic pitch class detection using
    Continuous Wavelet Transform, followed by modal template matching
    to determine the musical key.

    The analyzer processes audio in 8192-sample chunks, extracting
    chromatic energy via wavelets and scoring against 6 modal templates
    (Ionian, Lydian, Mixolydian, Aeolian, Dorian, Phrygian).

    Configuration: No user-configurable options at this time.
    """

    name = "Wavelet Key Analyzer (RE3)"
    description = "Wavelet-based key detection (ported from RapidEvolution3)"
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
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if key already exists (unless overwrite is enabled)
            overwrite = self.options.get('overwrite_existing', False)
            existing_key = self.media_file.get_tag_simple('key')

            if existing_key and not overwrite:
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="Key already set"
                )

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

            log.debug(f"Processing {total_samples} samples in {KEY_DETECTOR_ANALYZE_CHUNK_SIZE}-sample chunks")

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
                    samples_read += frames_read

                    # Log progress periodically
                    if chunks_processed % 100 == 0:
                        progress_pct = (samples_read / total_samples) * 100
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
            if detected_key.mode:
                log.info(f"RE3 detected key: {detected_key.start_key} {detected_key.mode} (accuracy: {detected_key.accuracy:.2f}) for {self.media_file.file_path} [analysis took {elapsed_time:.2f}s]")
            else:
                log.info(f"RE3 detected key: {detected_key.start_key} (accuracy: {detected_key.accuracy:.2f}) for {self.media_file.file_path} [analysis took {elapsed_time:.2f}s]")

            # Prepare result data
            # Return key string (Tag Transformation system handles notation conversion)
            # The detected key is in RE3 format (e.g., "Am", "C", "F#m")
            # YAAMT's MusicalKeyFormatter will convert to user's preferred notation
            result_data = {'key': detected_key.start_key}

            # Include mode if detected (consumer will handle appending to comments)
            if detected_key.mode:
                result_data['mode'] = detected_key.mode

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
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring key analyzer parameters.

        Returns:
            QWidget with mode detection checkbox
        """
        from PySide6.QtWidgets import QCheckBox

        widget = QWidget()
        layout = QVBoxLayout()

        # Info label
        info_label = QLabel(
            "This analyzer uses the RapidEvolution3 wavelet-based key detection algorithm."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Mode detection checkbox
        mode_checkbox = QCheckBox("Detect and report musical mode")
        mode_checkbox.setObjectName("detect_mode")
        mode_checkbox.setChecked(False)
        mode_checkbox.setToolTip(
            "When enabled, the analyzer will identify the musical mode (ionian, dorian, phrygian, etc.) "
            "and append it to the track's comments field."
        )
        layout.addWidget(mode_checkbox)

        layout.addStretch()
        widget.setLayout(layout)
        return widget


# Register this analyzer with the Key category
register_analyzer(AnalyzerCategory.KEY, WaveletKeyAnalyzer)
