"""
RapidEvolution3 BPM analyzer - Python port of the RE3 beat detection algorithm.

This analyzer implements the multi-band spectral analysis algorithm from
RapidEvolution3, using 6 frequency bands, elliptical IIR filters, and
FFT-based periodicity detection.

Reference: https://github.com/djqualia/RapidEvolution3
"""

from typing import Optional, Callable, List
import numpy as np

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QSpinBox,
                                QDoubleSpinBox, QFormLayout, QGroupBox)

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption, build_widget_from_option
from util.logging import log


class EllipticalFilter:
    """
    IIR elliptical filter implementation - matches RapidEvolution3 exactly.

    NOTE: This implementation uses non-standard variable naming to match
    the Java RE3 code. In RE3, 'a' contains numerator coefficients and 'b'
    contains denominator coefficients (opposite of standard DSP notation).
    """

    def __init__(self, in_a: np.ndarray, in_b: np.ndarray):
        """
        Initialize elliptical filter with coefficients.

        Args:
            in_a: Numerator coefficients (feedforward) - called 'a' in RE3 Java code
            in_b: Denominator coefficients (feedback) - called 'b' in RE3 Java code
        """
        # Match Java naming (backwards from standard DSP notation!)
        self.a = np.array(in_a, dtype=np.float64)
        self.b = np.array(in_b, dtype=np.float64)
        self.past_a = np.zeros(len(in_a), dtype=np.float64)
        self.past_b = np.zeros(len(in_b), dtype=np.float64)

    def process(self, val: float) -> float:
        """
        Process a single sample through the filter - matches RE3 exactly.

        Args:
            val: Input sample value

        Returns:
            Filtered output value
        """
        # Shift input history (Java: for i=1 to length-1: past_b[i] = past_b[i-1])
        # In Java this appears to copy forward, but actually shifts right
        for i in range(len(self.past_b) - 1, 0, -1):
            self.past_b[i] = self.past_b[i - 1]
        self.past_b[0] = val

        # Calculate output (Java adds both terms)
        newval = 0.0
        for k in range(len(self.b)):
            newval += self.b[k] * self.past_b[k]
        for k in range(len(self.a)):
            newval += self.a[k] * self.past_a[k]

        # Shift output history
        for i in range(len(self.past_a) - 1, 0, -1):
            self.past_a[i] = self.past_a[i - 1]
        self.past_a[0] = newval

        return newval


class Hanning:
    """Hanning window generator (unused in current implementation but kept for completeness)."""

    def __init__(self, sample_rate: float):
        self.sample_rate = sample_rate


class BPMRecord:
    """Record of BPM candidate and its score."""

    def __init__(self):
        self.bpm: float = 0.0
        self.score: float = 0.0


class DetectedBpm:
    """Result of BPM detection with accuracy and intensity metrics."""

    def __init__(self, bpm: float, accuracy: float, intensity: int):
        """
        Initialize detected BPM result.

        Args:
            bpm: Detected BPM value
            accuracy: Confidence/accuracy score (0.0 to 1.0)
            intensity: Beat intensity score (0 to 100)
        """
        self.bpm = bpm
        self.accuracy = accuracy
        self.intensity = intensity

    def __repr__(self) -> str:
        return f"DetectedBpm(bpm={self.bpm:.2f}, accuracy={self.accuracy:.2f}, intensity={self.intensity})"


class SubBandSeparator:
    """
    Multi-band frequency separator for BPM detection.

    This class implements the core RE3 algorithm: separating audio into 6 frequency
    bands, extracting energy envelopes, and detecting periodicities via FFT.

    IMPORTANT: This implementation expects unnormalized audio samples (raw integer
    values like -32768 to +32767 for 16-bit audio), matching the Java implementation.
    The filter coefficients and energy calculations were designed for this range.
    """

    # Filter coefficients for different sample rates (from MATLAB ellip())
    # Format: sample_rate -> (lowpass, band1, band2, band3, band4, highpass)
    #
    # NOTE: For future optimization, these could be generated dynamically using:
    #   from scipy.signal import ellip
    #   b, a = ellip(6, 3, 40, 200/22050)  # lowpass example
    # This would allow supporting arbitrary sample rates instead of pre-calculated ones.
    FILTER_COEFFICIENTS = {
        44100.0: {
            'lowpass': ([0.0099, -0.0596, 0.1488, -0.1983, 0.1488, -0.0596, 0.0099],
                       [1.0000, -5.9824, 14.9136, -19.8306, 14.8340, -5.9186, 0.9841]),
            'band1': ([0.0008, -0.0031, 0.0039, 0, -0.0039, 0.0031, -0.0008],
                     [1.0000, -5.9777, 14.8941, -19.7994, 14.8107, -5.9109, 0.9833]),
            'band2': ([0.0016, -0.0062, 0.0077, -0.0000, -0.0077, 0.0062, -0.0016],
                     [1.0000, -5.9445, 14.7453, -19.5360, 14.5807, -5.8125, 0.9669]),
            'band3': ([0.0031, -0.0120, 0.0147, 0.0000, -0.0147, 0.0120, -0.0031],
                     [1.0000, -5.8459, 14.3244, -18.8305, 14.0062, -5.5891, 0.9349]),
            'band4': ([0.0062, -0.0222, 0.0257, -0.0000, -0.0257, 0.0222, -0.0062],
                     [1.0000, -5.5249, 13.0378, -16.8004, 12.4644, -5.0499, 0.8740]),
            'highpass': ([0.3918, -2.2137, 5.3423, -7.0405, 5.3423, -2.2137, 0.3918],
                        [1.0000, -4.3595, 8.5011, -9.3963, 6.2685, -2.4280, 0.4444]),
        },
        48000.0: {
            'lowpass': ([0.0099, -0.0596, 0.1489, -0.1985, 0.1489, -0.0596, 0.0099],
                       [1.0000, -5.9839, 14.9211, -19.8450, 14.8478, -5.9253, 0.9853]),
            'band1': ([0.0007, -0.0029, 0.0036, -0.0000, -0.0036, 0.0029, -0.0007],
                     [1.0000, -5.9799, 14.9043, -19.8181, 14.8276, -5.9185, 0.9846]),
            'band2': ([0.0014, -0.0057, 0.0071, 0.0000, -0.0071, 0.0057, -0.0014],
                     [1.0000, -5.9506, 14.7724, -19.5830, 14.6208, -5.8291, 0.9695]),
            'band3': ([0.0028, -0.0111, 0.0136, -0.0000, -0.0136, 0.0111, -0.0028],
                     [1.0000, -5.8648, 14.4036, -18.9606, 14.1094, -5.6277, 0.9400]),
            'band4': ([0.0057, -0.0207, 0.0243, 0.0000, -0.0243, 0.0207, -0.0057],
                     [1.0000, -5.5879, 13.2831, -17.1787, 12.7455, -5.1450, 0.8836]),
            'highpass': ([0.4135, -2.3589, 5.7244, -7.5578, 5.7244, -2.3589, 0.4135],
                        [1.0000, -4.5260, 9.0508, -10.1755, 6.8322, -2.6290, 0.4665]),
        },
        # Additional sample rates can be added as needed
        # RE3 supports: 8k, 11.025k, 16k, 22.05k, 32k, 64k, 88.2k, 96k, 192k
    }

    def __init__(self, sample_rate: float, min_bpm: float, max_bpm: float,
                 seconds: float, decimation_size: int = 64, threshold_time: float = 60.0,
                 progress_callback: Optional[Callable[[float], None]] = None,
                 cancel_check: Optional[Callable[[], bool]] = None):
        """
        Initialize SubBandSeparator.

        Args:
            sample_rate: Audio sample rate in Hz
            min_bpm: Minimum BPM to detect
            max_bpm: Maximum BPM to detect
            seconds: Track length in seconds
            decimation_size: Energy decimation factor
            threshold_time: Segment length for early detection (seconds)
            progress_callback: Optional callback for progress updates (0.0 to 1.0)
            cancel_check: Optional callback to check if cancelled
        """
        self.sample_rate = sample_rate
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self.seconds = seconds
        self.progress_callback = progress_callback
        self.cancel_check = cancel_check

        # Find closest supported sample rate
        supported_rates = list(self.FILTER_COEFFICIENTS.keys())
        closest_rate = min(supported_rates, key=lambda x: abs(x - sample_rate))

        if abs(closest_rate - sample_rate) > 100:
            raise ValueError(f"Unsupported sample rate: {sample_rate}Hz. Closest supported: {closest_rate}Hz")

        # Adjust decimation size and threshold based on track length
        segments = seconds / threshold_time
        actual_segments = np.floor(segments)
        overflow = segments - actual_segments
        overflow /= actual_segments
        overflow += 1.0

        if seconds > threshold_time:
            threshold_time *= overflow
            decimation_size = int(np.floor(decimation_size * overflow * (sample_rate / 44100.0)))
        else:
            decimation_size = int(np.floor(decimation_size * (sample_rate / 44100.0) * (seconds / threshold_time)))

        self.decimation_size = decimation_size
        self.threshold_time = threshold_time
        self.effective_sample_rate = sample_rate / decimation_size

        # Calculate segment size
        self.energy_segment_size = int(self.effective_sample_rate * threshold_time)

        # Initialize energy buffers for each band
        self.lowpass_data = np.zeros(self.energy_segment_size)
        self.band1_data = np.zeros(self.energy_segment_size)
        self.band2_data = np.zeros(self.energy_segment_size)
        self.band3_data = np.zeros(self.energy_segment_size)
        self.band4_data = np.zeros(self.energy_segment_size)
        self.highpass_data = np.zeros(self.energy_segment_size)

        # Envelope extraction buffers
        self.final_lowpass_data = np.zeros(self.energy_segment_size - 1)
        self.final_band1_data = np.zeros(self.energy_segment_size - 1)
        self.final_band2_data = np.zeros(self.energy_segment_size - 1)
        self.final_band3_data = np.zeros(self.energy_segment_size - 1)
        self.final_band4_data = np.zeros(self.energy_segment_size - 1)
        self.final_highpass_data = np.zeros(self.energy_segment_size - 1)

        # Buffer indices
        self.lp_index = 0
        self.b1_index = 0
        self.b2_index = 0
        self.b3_index = 0
        self.b4_index = 0
        self.hp_index = 0

        # Extra samples buffer for decimation
        self.extra = None

        # BPM detection state
        self.results = None
        self.first_block_size = -1
        self.normalized = False
        self.locked_on = False
        self.early_detect_threshold = 4
        self.segment_bpms = []

        # Initialize filters
        coeffs = self.FILTER_COEFFICIENTS[closest_rate]
        self.lowpass_filter = EllipticalFilter(*coeffs['lowpass'])
        self.band1_filter = EllipticalFilter(*coeffs['band1'])
        self.band2_filter = EllipticalFilter(*coeffs['band2'])
        self.band3_filter = EllipticalFilter(*coeffs['band3'])
        self.band4_filter = EllipticalFilter(*coeffs['band4'])
        self.highpass_filter = EllipticalFilter(*coeffs['highpass'])

        self.hwindow = Hanning(sample_rate)

        log.debug(f"SubBandSeparator initialized: decimation={decimation_size}, "
                 f"segment_length={threshold_time:.2f}s, effective_rate={self.effective_sample_rate:.2f}Hz")

    def send(self, data: np.ndarray):
        """
        Send audio data to the separator for processing.

        Args:
            data: Mono audio samples (single channel)
        """
        count = 0

        while count + self.decimation_size <= len(data):
            # Check for cancellation
            if self.cancel_check and self.cancel_check():
                return

            # Initialize energy accumulators
            new_lowpass = 1.0
            new_band1pass = 1.0
            new_band2pass = 1.0
            new_band3pass = 1.0
            new_band4pass = 1.0
            new_highpass = 1.0
            this_decimation_size = self.decimation_size

            # Process extra samples from previous chunk
            if self.extra is not None:
                for i in range(len(self.extra)):
                    if self.cancel_check and self.cancel_check():
                        return

                    val = self.extra[i]
                    lowpass_val = self.lowpass_filter.process(val)
                    band1_val = self.band1_filter.process(val)
                    band2_val = self.band2_filter.process(val)
                    band3_val = self.band3_filter.process(val)
                    band4_val = self.band4_filter.process(val)
                    highpass_val = self.highpass_filter.process(val)

                    # Accumulate energy (rectify and square)
                    new_lowpass += max(0, lowpass_val) ** 2
                    new_band1pass += max(0, band1_val) ** 2
                    new_band2pass += max(0, band2_val) ** 2
                    new_band3pass += max(0, band3_val) ** 2
                    new_band4pass += max(0, band4_val) ** 2
                    new_highpass += max(0, highpass_val) ** 2

                this_decimation_size -= len(self.extra)
                self.extra = None

            # Process current chunk
            for i in range(this_decimation_size):
                if self.cancel_check and self.cancel_check():
                    return

                val = data[i + count]
                lowpass_val = self.lowpass_filter.process(val)
                band1_val = self.band1_filter.process(val)
                band2_val = self.band2_filter.process(val)
                band3_val = self.band3_filter.process(val)
                band4_val = self.band4_filter.process(val)
                highpass_val = self.highpass_filter.process(val)

                # Accumulate energy (rectify and square)
                new_lowpass += max(0, lowpass_val) ** 2
                new_band1pass += max(0, band1_val) ** 2
                new_band2pass += max(0, band2_val) ** 2
                new_band3pass += max(0, band3_val) ** 2
                new_band4pass += max(0, band4_val) ** 2
                new_highpass += max(0, highpass_val) ** 2

            # Store log energy
            self.lowpass_data[self.lp_index] = np.log(new_lowpass)
            self.lp_index += 1
            self.band1_data[self.b1_index] = np.log(new_band1pass)
            self.b1_index += 1
            self.band2_data[self.b2_index] = np.log(new_band2pass)
            self.b2_index += 1
            self.band3_data[self.b3_index] = np.log(new_band3pass)
            self.b3_index += 1
            self.band4_data[self.b4_index] = np.log(new_band4pass)
            self.b4_index += 1
            self.highpass_data[self.hp_index] = np.log(new_highpass)
            self.hp_index += 1

            # Check if segment is full
            if self.lp_index >= len(self.lowpass_data):
                log.debug(f"Processing {self.threshold_time:.2f}s segment")
                self._extract_and_process()

            count += this_decimation_size

        # Store remaining samples
        if count < len(data):
            self.extra = data[count:].copy()

    def _extract_and_process(self):
        """Extract envelopes and process each frequency band."""
        # Process each band
        self._envelope_extract(self.lowpass_data, self.final_lowpass_data)
        self.lp_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_lowpass_data)
        log.debug(f"  Lowpass BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        self._envelope_extract(self.band1_data, self.final_band1_data)
        self.b1_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_band1_data)
        log.debug(f"  Band1 BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        self._envelope_extract(self.band2_data, self.final_band2_data)
        self.b2_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_band2_data)
        log.debug(f"  Band2 BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        self._envelope_extract(self.band3_data, self.final_band3_data)
        self.b3_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_band3_data)
        log.debug(f"  Band3 BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        self._envelope_extract(self.band4_data, self.final_band4_data)
        self.b4_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_band4_data)
        log.debug(f"  Band4 BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        self._envelope_extract(self.highpass_data, self.final_highpass_data)
        self.hp_index = 0
        detected_bpm = self._calculate_spectral_sum(self.min_bpm, self.final_highpass_data)
        log.debug(f"  Highpass BPM: {detected_bpm:.2f}")

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Analysis cancelled")

        # Get overall BPM from combined results
        detected_bpm = self._get_overall_bpm()
        log.debug(f"  Current overall BPM: {detected_bpm:.2f}")

        # Check for early lock-on
        self.segment_bpms.append(detected_bpm)
        if len(self.segment_bpms) >= self.early_detect_threshold:
            # Check if last N segments agree
            recent = self.segment_bpms[-self.early_detect_threshold:]
            if len(set(recent)) == 1 and detected_bpm != 0.0:
                self.locked_on = True
                log.info(f"Locked on to BPM: {detected_bpm:.2f}")

    def _envelope_extract(self, decimated_data: np.ndarray, final_data: np.ndarray):
        """
        Extract onset envelope using first-order difference and thresholding.

        Args:
            decimated_data: Input decimated energy data
            final_data: Output envelope data
        """
        # Calculate first-order differences (onset detection)
        diffs = np.diff(decimated_data)

        # Half-wave rectify (only positive changes = onsets)
        diffs = np.maximum(0, diffs)

        # Calculate threshold using standard deviation
        avg_diff = np.mean(diffs)
        std_dev = np.std(diffs)
        threshold = std_dev * 1.5

        # Apply threshold
        final_data[:] = np.where(np.abs(diffs) >= threshold, diffs, 0)

    def _calculate_spectral_sum(self, min_bpm: float, final_data: np.ndarray) -> float:
        """
        Calculate BPM using FFT-based spectral analysis with harmonic reinforcement.

        Args:
            min_bpm: Minimum BPM to consider
            final_data: Envelope data to analyze

        Returns:
            Detected BPM for this band
        """
        first_time = self.results is None
        if first_time:
            self.results = []

        # Pad to next power of 2 (for efficient FFT)
        power = 1
        size = 2 ** power
        while size <= len(final_data):
            power += 1
            size = 2 ** power
        power += 1
        size = 2 ** power

        # Zero-pad data
        diff = size - len(final_data)
        diff //= 2
        padded_data = np.pad(final_data, (diff, size - len(final_data) - diff), mode='constant')

        # Compute FFT
        fft_data = np.fft.fft(padded_data)
        fft_magnitude = np.abs(fft_data)

        # Search for BPM candidates
        block = 1
        max_value = 0.0
        return_bpm = 0.0

        bpm = (block / len(padded_data)) * self.effective_sample_rate * 60.0

        while bpm <= self.max_bpm:
            if bpm >= min_bpm:
                temp_block = block
                value = 0.0
                count = 0
                norm = 0.0

                # Sum fundamental and first 3 harmonics with interpolation
                while (temp_block < len(padded_data) // 2) and (count < 3):
                    value += fft_magnitude[temp_block]
                    norm += 1

                    if count == 0:
                        # Add sub-harmonics (1/2, 1/4, 1/8) with interpolation
                        for divisor in [2, 4, 8]:
                            sub_block = temp_block / divisor
                            if sub_block >= 1:
                                # Linear interpolation
                                sub_block_int = int(sub_block)
                                alpha = sub_block - sub_block_int

                                if sub_block_int < len(fft_magnitude):
                                    val1 = fft_magnitude[sub_block_int]
                                    val2 = fft_magnitude[min(sub_block_int + 1, len(fft_magnitude) - 1)]
                                    value += val1 * (1 - alpha) + val2 * alpha
                                    norm += 1

                    temp_block *= 2
                    count += 1

                value /= norm if norm > 0 else 1

                if value > max_value:
                    max_value = value
                    return_bpm = bpm

                # Store or update result
                if first_time:
                    record = BPMRecord()
                    record.bpm = bpm
                    record.score = value
                    self.results.append(record)
                    if self.first_block_size == -1:
                        self.first_block_size = block
                else:
                    if block - self.first_block_size < len(self.results):
                        self.results[block - self.first_block_size].score += value

            block += 1
            bpm = (block / len(padded_data)) * self.effective_sample_rate * 60.0

        return return_bpm

    def _get_overall_bpm(self) -> float:
        """Get the highest-scoring BPM from results."""
        if not self.results:
            return 0.0

        max_score = 0.0
        detected_bpm = 0.0

        for record in self.results:
            if record.score > max_score:
                detected_bpm = record.bpm
                max_score = record.score

        return detected_bpm

    def normalize(self):
        """Normalize results by averaging with neighbors."""
        if self.normalized or not self.results:
            return

        if not self.results:
            self._extract_and_process()

        new_results = []
        for i in range(len(self.results)):
            record = self.results[i]

            # Get neighbors (with wraparound)
            if i == 0:
                record2 = self.results[i + 1]
                record3 = self.results[-1]
            elif i == len(self.results) - 1:
                record2 = self.results[i - 1]
                record3 = self.results[0]
            else:
                record2 = self.results[i - 1]
                record3 = self.results[i + 1]

            # Create smoothed record
            new_record = BPMRecord()
            new_record.bpm = record.bpm
            new_record.score = record.score + record2.score * 0.5 + record3.score * 0.5
            new_results.append(new_record)

        self.results = new_results
        self.normalized = True

    def get_bpm(self) -> DetectedBpm:
        """
        Get final BPM detection result.

        Returns:
            DetectedBpm with BPM, accuracy, and intensity
        """
        self.normalize()

        if not self.results:
            return DetectedBpm(0.0, 0.0, 0)

        # Find top 3 BPM candidates
        max_score = 0.0
        min_score = float('inf')
        detected_bpm = 0.0
        min_bpm1 = 0.0
        max_bpm1 = 0.0

        log.debug("Final BPM candidates:")
        for i, record in enumerate(self.results):
            log.debug(f"  BPM: {record.bpm:.2f}, score: {record.score:.4f}")

            if i == 0:
                min_score = record.score
            else:
                if record.score < min_score:
                    min_score = record.score

            if record.score > max_score:
                detected_bpm = self._get_rounded_bpm(i)
                max_score = record.score
                min_bpm1 = record.bpm * 0.975
                max_bpm1 = record.bpm * 1.025

        # Calculate accuracy
        total_score = sum(r.score for r in self.results)
        average = total_score / len(self.results)
        score_range = max_score - min_score

        if score_range > 0:
            accuracy = (max_score - average) / score_range
        else:
            accuracy = 0.01

        # Clamp accuracy
        if np.isnan(accuracy) or accuracy < 0.01:
            accuracy = 0.01

        # Calculate beat intensity (simplified - full implementation would use spectral flux)
        intensity = int(min(100, max(1, accuracy * 100)))

        log.info(f"Detected BPM: {detected_bpm:.2f}, accuracy: {accuracy:.2f}, intensity: {intensity}")

        return DetectedBpm(detected_bpm, accuracy, intensity)

    def _get_rounded_bpm(self, index: int) -> float:
        """Round BPM based on granularity from neighboring values."""
        if not self.results or index >= len(self.results):
            return 0.0

        this_record = self.results[index]
        next_record = self.results[index + 1] if (index + 1) < len(self.results) else None
        last_record = self.results[index - 1] if index > 0 else None

        bpm_diff = 0.0
        if next_record:
            bpm_diff = abs(this_record.bpm - next_record.bpm)
        if last_record:
            this_diff = abs(this_record.bpm - last_record.bpm)
            if this_diff > bpm_diff:
                bpm_diff = this_diff

        # Determine decimal places based on granularity
        decimal_places = self._extract_decimal_places(str(bpm_diff))
        return round(this_record.bpm, decimal_places)

    @staticmethod
    def _extract_decimal_places(input_str: str) -> int:
        """Extract appropriate decimal places from a number string."""
        returnval = 0
        past_comma = False

        for i, char in enumerate(input_str):
            if i >= len(input_str):
                break
            if char == '.':
                past_comma = True
            elif past_comma:
                if char != '0':
                    return returnval + 1
                else:
                    returnval += 1
            else:
                if char != '0':
                    return returnval

        return returnval


class MultibandSpectralBPMAnalyzer(AnalyzerBase):
    """
    BPM analyzer using the RapidEvolution3 algorithm.

    This analyzer implements the multi-band spectral analysis approach from
    RapidEvolution3, providing accurate BPM detection for a wide range of
    electronic and dance music.

    The BPM detection range is read from user preferences:
        - Analyzers/CategoryOptions/bpm/range_min
        - Analyzers/CategoryOptions/bpm/range_max

    Analyzer-specific options:
        - 'decimation_size' (int): Energy decimation factor (default: 64)
        - 'threshold_time' (float): Segment length for early detection (default: 60.0s)
    """

    name = "Multiband Spectral BPM Analyzer (RE3)"
    description = "Multi-band spectral analysis (ported from RapidEvolution3)"
    category = "bpm"
    debug_only = True  # Heavy computation, excluded from release builds
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform BPM analysis using RE3 algorithm.

        Returns:
            AnalyzerResult with float BPM value or error/skip status
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

            # Read BPM range from user preferences
            settings = QSettings("Lyjia", "Audio Metadata Tool")
            min_bpm = settings.value("Analyzers/CategoryOptions/bpm/range_min", 80, type=int)
            max_bpm = settings.value("Analyzers/CategoryOptions/bpm/range_max", 200, type=int)

            # Get analyzer-specific options
            decimation_size = self.options.get('decimation_size', 64)
            threshold_time = self.options.get('threshold_time', 60.0)

            # Open audio stream in native format (do NOT use ChannelMixingAdapter)
            # Java implementation SUMS channels, not averages them
            audio_stream = self.media_file.get_audio_stream(None)

            # Get stream properties
            sample_rate = audio_stream.sample_rate
            duration = self.media_file.length_in_seconds

            if duration <= 0:
                return AnalyzerResult(
                    success=False,
                    error="Could not determine track duration"
                )

            log.info(f"RE3 analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {sample_rate}Hz, duration: {duration:.2f}s")
            log.debug(f"  BPM range: {min_bpm}-{max_bpm}, decimation: {decimation_size}")

            # Progress callback stub (for future implementation)
            # TODO: Wire this up to the analyzer dispatcher's progress reporting system
            def progress_callback(progress: float):
                """Report analysis progress (0.0 to 1.0)."""
                pass  # Stub for future implementation

            # Cancellation check
            def cancel_check() -> bool:
                return self.is_cancelled

            # Initialize SubBandSeparator
            try:
                separator = SubBandSeparator(
                    sample_rate=sample_rate,
                    min_bpm=min_bpm,
                    max_bpm=max_bpm,
                    seconds=duration,
                    decimation_size=decimation_size,
                    threshold_time=threshold_time,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            except ValueError as e:
                return AnalyzerResult(
                    success=False,
                    error=f"Unsupported sample rate: {e}"
                )

            # Stream audio and process
            chunk_size = 8192
            total_samples = int(sample_rate * duration)
            samples_read = 0

            while True:
                # Check for cancellation
                if self.is_cancelled:
                    return AnalyzerResult(
                        success=False,
                        error="Analysis cancelled by user"
                    )

                # Check for early lock-on
                if separator.locked_on:
                    log.info("Early lock-on detected, stopping analysis")
                    break

                # Read chunk
                audio_bytes = audio_stream.read(chunk_size)
                if not audio_bytes:
                    break

                # Convert to float samples (unnormalized - matches Java implementation)
                # Java uses raw integer values, not normalized to [-1.0, 1.0]
                # Java SUMS channels for multi-channel audio, not averages
                if audio_stream.sample_width == 2:  # 16-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
                elif audio_stream.sample_width == 4:  # 32-bit
                    samples = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float64)
                else:
                    # For float32 input, scale to match 16-bit range
                    samples = np.frombuffer(audio_bytes, dtype=np.float32).astype(np.float64)
                    samples = samples * 32768.0

                # If multi-channel, sum channels to mono (matches Java behavior)
                num_channels = audio_stream.channels_qty
                if num_channels > 1:
                    samples = samples.reshape(-1, num_channels).sum(axis=1)

                # Send to separator
                separator.send(samples)

                samples_read += len(samples)

                # Update progress (stub)
                if total_samples > 0:
                    progress = samples_read / total_samples
                    progress_callback(progress)

            # Get final BPM result
            result = separator.get_bpm()

            if result.bpm <= 0:
                return AnalyzerResult(
                    success=False,
                    error="Could not detect BPM - no clear tempo found"
                )

            log.info(f"RE3 detected BPM: {result.bpm:.2f} for {self.media_file.file_path}")

            # Return raw float BPM (Tag Transformation system handles formatting)
            return AnalyzerResult(
                success=True,
                data={'bpm': float(result.bpm)}
            )

        except InterruptedError:
            return AnalyzerResult(
                success=False,
                error="Analysis cancelled by user"
            )
        except Exception as e:
            log.error(f"RE3 analysis failed for {self.media_file.file_path}: {e}", exc_info=True)
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
            List of AnalyzerOption instances for RE3-specific options
        """
        return [
            AnalyzerOption(
                name='decimation_size',
                type='int',
                default=64,
                min=8,
                max=256,
                interval=8,
                help='Energy decimation factor (higher = faster but less precise)'
            ),
            AnalyzerOption(
                name='threshold_time',
                type='float',
                default=60.0,
                min=10.0,
                max=120.0,
                interval=10.0,
                help='Segment length for early detection (seconds)'
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring RE3 analyzer parameters.

        Note: BPM range is configured globally in Preferences > Metadata,
        so it's not included in this analyzer-specific settings widget.

        Returns:
            QWidget with controls for algorithm parameters
        """
        widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        # Info label
        info_label = QLabel(
            "BPM detection range is configured in Preferences > Metadata.\n"
            "Advanced settings below are for fine-tuning the algorithm."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(info_label)

        # Advanced settings (collapsible)
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(4)

        # Use helper for controls (maintains consistency with metadata)
        settings_group = f"analyzers/{cls.__name__}"
        for option in cls.get_options_metadata():
            option_widget = build_widget_from_option(option, settings_group)
            advanced_layout.addWidget(option_widget)

        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)

        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget


# Register this analyzer with the BPM category
register_analyzer(AnalyzerCategory.BPM, MultibandSpectralBPMAnalyzer)
