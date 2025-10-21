"""
RapidEvolution3 Key Detector - Python port of the RE3 musical key detection algorithm.

This analyzer implements the Continuous Wavelet Transform (CWT) approach from
RapidEvolution3, using Gaussian-modulated cosine wavelets and modal template matching.

Reference: https://github.com/djqualia/RapidEvolution3
"""

from typing import Optional, Callable, Tuple, List
import numpy as np

from util.logging import log


class DetectedKey:
    """
    Result of musical key detection with accuracy metrics.

    This is a simple data class that holds the detected key information,
    matching the DetectedKey.java class from RE3.

    Attributes:
        start_key: The primary detected key (string format like "Am", "C", "8A")
        end_key: Optional ending key for tracks with key changes (rarely used)
        accuracy: Confidence score from 0.0 to 1.0
    """

    def __init__(self, start_key: str = "", end_key: str = "", accuracy: float = 0.0):
        """
        Initialize detected key result.

        Args:
            start_key: Primary detected key notation
            end_key: Ending key (for key changes), empty string if same as start
            accuracy: Detection confidence (0.0 to 1.0)
        """
        self.start_key = start_key
        self.end_key = end_key
        self.accuracy = accuracy

    def is_valid(self) -> bool:
        """
        Check if this is a valid key detection result.

        Returns:
            True if start_key is not empty or accuracy > 0
        """
        return bool(self.start_key) or self.accuracy > 0.0

    def __repr__(self) -> str:
        if self.end_key and self.end_key != self.start_key:
            return f"DetectedKey(start={self.start_key}, end={self.end_key}, accuracy={self.accuracy:.2f})"
        return f"DetectedKey(key={self.start_key}, accuracy={self.accuracy:.2f})"


# Configuration constants (from re3.properties)
KEY_DETECTOR_ANALYZE_CHUNK_SIZE = 8192
KEY_DETECTOR_MATRIX_START_SCALE = 0.25
KEY_DETECTOR_MATRIX_MAX_OCTAVES = 8
KEY_DETECTOR_MATRIX_SHIFTS = 1
KEY_DETECTOR_MATRIX_WAVELET_WIDTH = 1.0


class KeyDetectionMatrix:
    """
    Pre-calculated wavelet matrix for chromatic pitch class detection.

    This class generates a 4D matrix of Gaussian-modulated cosine wavelets
    tuned to 12 chromatic pitch classes across multiple octaves.

    Matrix dimensions: [octaves][shifts][sample_points][12_pitches]

    IMPORTANT: This implementation uses specific numeric values to match
    the Java RE3 code exactly. Variable names and comments reference the
    original Java implementation.

    Reference: KeyDetectionMatrix.java in RE3
    """

    def __init__(self, max_frequency: int,
                 start_scale: float = KEY_DETECTOR_MATRIX_START_SCALE,
                 max_octaves: int = KEY_DETECTOR_MATRIX_MAX_OCTAVES,
                 shifts: int = KEY_DETECTOR_MATRIX_SHIFTS,
                 wavelet_width: float = KEY_DETECTOR_MATRIX_WAVELET_WIDTH):
        """
        Initialize the wavelet matrix.

        Args:
            max_frequency: Maximum frequency (typically sample rate / 2)
            start_scale: Starting scale factor for base frequencies (default: 0.25)
            max_octaves: Number of octaves to analyze (default: 8)
            shifts: Number of time shifts per octave (default: 1)
            wavelet_width: Width parameter for Gaussian envelope (default: 1.0)
        """
        self.max_frequency = max_frequency
        self.start_scale = start_scale
        self.max_octaves = max_octaves
        self.shifts = shifts
        self.wavelet_width = wavelet_width

        # Java: int numpoints = KeyDetector.KEY_DETECTOR_ANALYZE_CHUNK_SIZE;
        numpoints = KEY_DETECTOR_ANALYZE_CHUNK_SIZE

        # Java: double timeinterval = ((double)KeyDetector.KEY_DETECTOR_ANALYZE_CHUNK_SIZE) / maxFrequency;
        timeinterval = float(KEY_DETECTOR_ANALYZE_CHUNK_SIZE) / max_frequency

        # Java: double coeff1 = timeinterval / numpoints;
        coeff1 = timeinterval / numpoints

        # Java: double coeff2 = 1.0 / waveletwidth;
        coeff2 = 1.0 / wavelet_width

        # Base frequencies for 12 chromatic pitch classes starting at A (55 Hz)
        # Java: double[] basefrequency = new double[12];
        # Note: These are the exact values from the Java code
        basefrequency = np.array([
            55.0,         # A
            58.27046875,  # A#
            61.73546875,  # B
            65.40640625,  # C
            69.295625,    # C#
            73.41625,     # D
            77.78125,     # D#
            82.406875,    # E
            87.3071875,   # F
            92.49875,     # F#
            97.99875,     # G
            103.82625     # G#
        ], dtype=np.float64)

        # Apply starting scale and calculate frequency parameters
        # Java: for (int p = 0; p < 12; ++p) {
        #           basefrequency[p] *= startscale;
        #           frequencyparam[p] = basefrequency[p] * waveletwidth;
        #       }
        basefrequency *= start_scale
        frequencyparam = basefrequency * wavelet_width

        # Initialize 4D wavelet matrix: [octaves][shifts][samples][pitches]
        # Java: vmatrix = new double[maxoctaves][1][KeyDetector.KEY_DETECTOR_ANALYZE_CHUNK_SIZE][12];
        # Note: shifts dimension is always 1 in RE3 (the loop `for (double ks = 0.5; ks <= 0.5; ks += 0.3)` runs once)
        self.vmatrix = np.zeros((max_octaves, 1, KEY_DETECTOR_ANALYZE_CHUNK_SIZE, 12), dtype=np.float64)

        # Generate wavelets for each octave
        # Java: for (int s = 0; s < maxoctaves; ++s) {
        for s in range(max_octaves):
            # Calculate scale factor for this octave
            # Java: double st = Math.pow(2, -s);
            st = np.power(2.0, -s)

            # Shift loop - in RE3 this only runs once (ks starts at 0.5, ends at 0.5)
            # Java: int n = 0;
            #       for (double ks = 0.5; ks <= 0.5; ks += 0.3) {
            n = 0
            ks = 0.5
            while ks <= 0.5:
                # Java: double k = ks * numpoints;
                k = ks * numpoints

                # Generate wavelet for each sample point
                # Java: for (int m = 0; m < KeyDetector.KEY_DETECTOR_ANALYZE_CHUNK_SIZE; ++m) {
                for m in range(KEY_DETECTOR_ANALYZE_CHUNK_SIZE):
                    # Calculate position parameter
                    # Java: double x = (((double) m) - k) / st * coeff1;
                    # IMPORTANT: Order of operations is ((m - k) / st) * coeff1
                    x = ((float(m) - k) / st) * coeff1

                    # Normalize by wavelet width
                    # Java: double v1 = x / waveletwidth;
                    v1 = x / wavelet_width

                    # Calculate wavelet value for each pitch class
                    # Java: for (int z = 0; z < 12; ++z)
                    #           vmatrix[s][n][m][z] = coeff2
                    #                   * Math.exp(-Math.PI * v1 * v1)
                    #                   * Math.cos(2.0 * Math.PI * frequencyparam[z] * v1)
                    #                   * coeff1 / Math.sqrt(st);
                    for z in range(12):
                        # Gaussian envelope
                        gaussian = np.exp(-np.pi * v1 * v1)

                        # Cosine oscillation at pitch frequency
                        cosine = np.cos(2.0 * np.pi * frequencyparam[z] * v1)

                        # Combined wavelet with normalization
                        # IMPORTANT: Multiply by coeff1 and divide by sqrt(st)
                        self.vmatrix[s, n, m, z] = coeff2 * gaussian * cosine * coeff1 / np.sqrt(st)

                # Increment shift index and continue loop
                # Java: ++n;
                n += 1
                ks += 0.3  # Loop exits after first iteration since 0.5 + 0.3 > 0.5

        log.debug(f"KeyDetectionMatrix initialized: max_freq={max_frequency}Hz, "
                 f"octaves={max_octaves}, matrix_shape={self.vmatrix.shape}")

    def get_max_octaves(self) -> int:
        """Get the number of octaves in the matrix."""
        return self.max_octaves

    def get_shifts(self) -> int:
        """Get the number of time shifts per octave."""
        return self.shifts

    def get_value(self, p: int, ks: int, m: int, z: int) -> float:
        """
        Get a single wavelet value from the matrix.

        Args:
            p: Octave index (0 to max_octaves-1)
            ks: Shift index (0 to shifts-1, always 0 in RE3)
            m: Sample index (0 to chunk_size-1)
            z: Pitch class index (0-11)

        Returns:
            Wavelet coefficient value
        """
        return self.vmatrix[p, ks, m, z]


class KeyProbabilitySet:
    """
    Container for normalized probability distribution across 12 possible keys.

    This class holds the final scores for each of the 12 chromatic keys
    and provides utility methods to find the best match.

    Reference: KeyProbabilitySet.java in RE3
    """

    # Note names indexed 0-11 (A, A#, B, C, C#, D, D#, E, F, F#, G, G#)
    # This matches RE3's chromatic indexing where A=0
    NOTE_NAMES = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]

    def __init__(self, normalized_probabilities: np.ndarray, is_major: bool, mode_type: str):
        """
        Initialize probability set.

        Args:
            normalized_probabilities: Array of 12 probabilities (should sum to ~1.0)
            is_major: True for major/ionian-type modes, False for minor/aeolian-type
            mode_type: Mode name (e.g., "ionian", "aeolian", "dorian")
        """
        self.normalized_probabilities = np.array(normalized_probabilities, dtype=np.float64)
        self.is_major = is_major
        self.mode_type = mode_type

        # Validation (matching Java debug check)
        total = np.sum(self.normalized_probabilities)
        if abs(total - 1.0) > 0.00001:
            log.debug(f"KeyProbabilitySet: improper probability set, total={total}")

    def get_probability(self, index: int) -> float:
        """Get probability for a specific key index (0-11)."""
        return float(self.normalized_probabilities[index])

    def get_max_probability(self) -> float:
        """Get the highest probability value."""
        # Java: double maximum = Double.MIN_VALUE;
        #       for (int i = 0; i < 12; ++i) {
        #           if (normalizedProbabilities[i] > maximum)
        #               maximum = normalizedProbabilities[i];
        #       }
        return float(np.max(self.normalized_probabilities))

    def get_min_probability(self) -> float:
        """Get the lowest probability value."""
        # Java: double minimum = Double.MAX_VALUE;
        #       for (int i = 0; i < 12; ++i)
        #           if (normalizedProbabilities[i] < minimum)
        #               minimum = normalizedProbabilities[i];
        return float(np.min(self.normalized_probabilities))

    def get_total_probability(self) -> float:
        """Get sum of all probabilities (should be ~1.0)."""
        # Java: double total = 0.0;
        #       for (int i = 0; i < 12; ++i)
        #           total += normalizedProbabilities[i];
        return float(np.sum(self.normalized_probabilities))

    def get_key_string(self, detect_advanced_modes: bool = False) -> str:
        """
        Get the key string with highest probability.

        Args:
            detect_advanced_modes: If True, append mode name (e.g., "A dorian")

        Returns:
            Key string (e.g., "A", "Am", "C#", "F#m")
        """
        # Find index with maximum probability
        # Java: double maximum = Double.MIN_VALUE;
        #       int index = -1;
        #       for (int i = 0; i < 12; ++i) {
        #           if (normalizedProbabilities[i] > maximum) {
        #               maximum = normalizedProbabilities[i];
        #               index = i;
        #           }
        #       }
        index = int(np.argmax(self.normalized_probabilities))

        # Build key string
        # Java: StringBuffer key = new StringBuffer();
        #       if (index == 0) key.append("A");
        #       else if (index == 1) key.append("A#");
        #       ...
        key = self.NOTE_NAMES[index]

        # Add 'm' suffix for minor
        # Java: if (!major) key.append("m");
        if not self.is_major:
            key += "m"

        # Add mode name if advanced detection is enabled
        # Java: if (RE3Properties.getBoolean("detect_advanced_keys")) {
        #           key.append(" ");
        #           key.append(type);
        #       }
        if detect_advanced_modes:
            key += f" {self.mode_type}"

        return key.strip()


class SingleKeyProbabilityFilter:
    """
    Single modal template filter for key detection.

    This filter scores 12 possible keys by comparing input chromatic pitch
    profiles against a rotated modal template (e.g., ionian/major scale).

    Reference: SingleKeyProbabilityFilter.java in RE3
    """

    def __init__(self, is_major: bool, mode_type: str, probabilities: np.ndarray):
        """
        Initialize filter with modal template.

        Args:
            is_major: True for major-type modes (ionian, lydian, mixolydian)
            mode_type: Mode name (e.g., "ionian", "aeolian")
            probabilities: 12-element template defining expected pitch class weights
        """
        # Validate input
        if probabilities is None or len(probabilities) != 12:
            log.error(f"SingleKeyProbabilityFilter: probabilities array incorrect length for key={mode_type}")

        # Check that probabilities sum to 1.0 (matching Java validation)
        total = np.sum(probabilities)
        if abs(total - 1.0) > 0.0001:
            log.error(f"SingleKeyProbabilityFilter: total probability != 1.0 for key={mode_type}")

        self.is_major = is_major
        self.mode_type = mode_type
        self.probabilities = np.array(probabilities, dtype=np.float64)

        # Initialize probability accumulator for 12 keys
        # Java: private double[] probability = new double[12];
        self.probability = np.zeros(12, dtype=np.float64)

        # Create probability matrix with rotated templates for each key
        # Java: private double[][] pmatrix = new double[12][12];
        #       for (int k = 0; k < 12; ++k) {
        #           for (int n = 0; n < 12; ++n) {
        #               int offset = n + k;
        #               if (offset >= 12) offset -= 12;
        #               pmatrix[k][offset] = probabilities[n];
        #           }
        #       }
        self.pmatrix = np.zeros((12, 12), dtype=np.float64)
        for k in range(12):
            for n in range(12):
                # Java: int offset = n + k;
                #       if (offset >= 12) offset -= 12;
                offset = n + k
                if offset >= 12:
                    offset -= 12
                # Java: pmatrix[k][offset] = probabilities[n];
                self.pmatrix[k, offset] = probabilities[n]

    def add(self, values: np.ndarray) -> None:
        """
        Add chromatic pitch class data and accumulate scores for each key.

        Args:
            values: 12-element array of pitch class energies
        """
        # Java: for (int k = 0; k < 12; ++k) {
        #           double total = 0.0;
        #           for (int n = 0; n < 12; ++n)
        #               total += pmatrix[k][n] * values[n];
        #           probability[k] = total + probability[k];// * decay;
        #       }
        for k in range(12):
            total = 0.0
            for n in range(12):
                # IMPORTANT: Multiply pmatrix[k][n] BY values[n], then accumulate
                total += self.pmatrix[k, n] * values[n]
            # IMPORTANT: Add total TO probability[k], not replace
            self.probability[k] = total + self.probability[k]

    def get_probability(self, index: int) -> float:
        """Get accumulated probability for a specific key index."""
        return float(self.probability[index])

    def clear_probabilities(self) -> None:
        """Reset all accumulated probabilities to zero."""
        # Java: for (int i = 0; i < 12; ++i)
        #           probability[i] = 0.0;
        self.probability.fill(0.0)

    def get_normalized_probabilities(self) -> KeyProbabilitySet:
        """
        Get normalized probabilities as a KeyProbabilitySet.

        Returns:
            KeyProbabilitySet with probabilities normalized to sum to 1.0
        """
        # Java: double[] normalizedProbabilities = new double[12];
        #       double total = 0.0;
        #       for (int i = 0; i < 12; ++i)
        #           total += probability[i];
        #       for (int i = 0; i < 12; ++i)
        #           normalizedProbabilities[i] = probability[i] / total;
        total = np.sum(self.probability)
        if total > 0:
            normalized = self.probability / total
        else:
            normalized = self.probability.copy()

        return KeyProbabilitySet(normalized, self.is_major, self.mode_type)

    def is_all_zeros(self) -> bool:
        """Check if all probabilities are zero."""
        # Java: for (int i = 0; i < 12; ++i)
        #           if (probability[i] > 0.0)
        #               return false;
        #       return true;
        return np.all(self.probability == 0.0)


class MultiKeyProbabilityFilter:
    """
    Multi-template filter for keys with modal variations.

    This filter combines multiple SingleKeyProbabilityFilter instances
    (e.g., for natural minor and harmonic minor) and takes the maximum
    score across all variations.

    Reference: MultiKeyProbabilityFilter.java in RE3
    """

    def __init__(self, is_major: bool, mode_type: str, probabilities_list: List[np.ndarray]):
        """
        Initialize multi-template filter.

        Args:
            is_major: True for major-type modes
            mode_type: Mode name (e.g., "aeolian", "dorian")
            probabilities_list: List of probability templates (for variations)
        """
        self.is_major = is_major
        self.mode_type = mode_type
        self.probability = np.zeros(12, dtype=np.float64)

        # Create single filter for each template variation
        # Java: private Vector<KeyProbabilityFilter> filters = new Vector<KeyProbabilityFilter>();
        #       for (int p = 0; p < probabilities.length; ++p) {
        #           SingleKeyProbabilityFilter filter = new SingleKeyProbabilityFilter(major, type, probabilities[p]);
        #           filters.add(filter);
        #       }
        self.filters: List[SingleKeyProbabilityFilter] = []
        for template in probabilities_list:
            filter_instance = SingleKeyProbabilityFilter(is_major, mode_type, template)
            self.filters.append(filter_instance)

    def add(self, values: np.ndarray) -> None:
        """
        Add chromatic data and accumulate maximum scores across template variations.

        Args:
            values: 12-element array of pitch class energies
        """
        # Java: double[] add_probabilities = new double[12];
        #       for (int f = 0; f < filters.size(); ++f) {
        #           SingleKeyProbabilityFilter filter = (SingleKeyProbabilityFilter)filters.get(f);
        #           filter.clearProbabilities();
        #           filter.add(values);
        #           for (int p = 0; p < 12; ++p)
        #               if (filter.getProbability(p) > add_probabilities[p])
        #                   add_probabilities[p] = filter.getProbability(p);
        #       }
        #       for (int p = 0; p < 12; ++p)
        #           probability[p] += add_probabilities[p];
        add_probabilities = np.zeros(12, dtype=np.float64)

        for filter_instance in self.filters:
            # Clear and recompute for this template
            filter_instance.clear_probabilities()
            filter_instance.add(values)

            # Take maximum probability for each key
            for p in range(12):
                prob = filter_instance.get_probability(p)
                # IMPORTANT: Take MAX, not sum
                if prob > add_probabilities[p]:
                    add_probabilities[p] = prob

        # Accumulate into our probability array
        # IMPORTANT: Add (+=), don't replace
        for p in range(12):
            self.probability[p] += add_probabilities[p]

    def get_normalized_probabilities(self) -> KeyProbabilitySet:
        """Get normalized probabilities."""
        # Java: same as SingleKeyProbabilityFilter
        total = np.sum(self.probability)
        if total > 0:
            normalized = self.probability / total
        else:
            normalized = self.probability.copy()

        return KeyProbabilitySet(normalized, self.is_major, self.mode_type)

    def is_all_zeros(self) -> bool:
        """Check if all probabilities are zero."""
        return np.all(self.probability == 0.0)
