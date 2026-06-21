"""
RapidEvolution3 Key Detector - Python port of the RE3 musical key detection algorithm.

This analyzer implements the Continuous Wavelet Transform (CWT) approach from
RapidEvolution3, using Gaussian-modulated cosine wavelets and modal template matching.

Reference: https://github.com/djqualia/RapidEvolution3
"""
from enum import Enum
from typing import Callable
import numpy as np

from util.logging import log

# Configuration constants (from re3.properties)
KEY_DETECTOR_ANALYZE_CHUNK_SIZE = 8192
KEY_DETECTOR_MATRIX_START_SCALE = 0.25
KEY_DETECTOR_MATRIX_MAX_OCTAVES = 8
KEY_DETECTOR_MATRIX_SHIFTS = 1
KEY_DETECTOR_MATRIX_WAVELET_WIDTH = 1.0

class DiatonicMode(Enum):
    dorian = "dorian",
    phrygian = "phrygian",
    lydian = "lydian",
    mixolydian = "mixolydian",
    aeolian = "aeolian",
    locrian = "locrian",
    ionian = "ionian",
    I = "ionian",
    II = "dorian",
    III = "phrygian",
    IV = "lydian",
    V = "mixolydian",
    VI = "aeolian",
    VII = "locrian"

class DetectedKey:
    """
    Result of musical key detection with accuracy metrics.

    This is a simple data class that holds the detected key information,
    matching the DetectedKey.java class from RE3.

    Attributes:
        start_key: The primary detected key (string format like "Am", "C", "8A")
        end_key: Optional ending key for tracks with key changes (rarely used)
        accuracy: Confidence score from 0.0 to 1.0
        mode: Optional musical mode (string representation)
    """

    def __init__(self, start_key: str = "", end_key: str = "", accuracy: float = 0.0, mode: str = ""):
        """
        Initialize detected key result.

        Args:
            start_key: Primary detected key notation
            end_key: Ending key (for key changes), empty string if same as start
            accuracy: Detection confidence (0.0 to 1.0)
            mode: Optional musical mode type (string, corresponds to DiatonicMode enum values)
        """
        self.start_key = start_key
        self.end_key = end_key
        self.accuracy = accuracy
        self.mode = mode

    def is_valid(self) -> bool:
        """
        Check if this is a valid key detection result.

        Returns:
            True if start_key is not empty or accuracy > 0
        """
        return bool(self.start_key) or self.accuracy > 0.0

    def __repr__(self) -> str:
        if self.end_key and self.end_key != self.start_key:
            if self.mode:
                return f"DetectedKey(start={self.start_key}, end={self.end_key}, accuracy={self.accuracy:.2f}, mode={self.mode})"
            return f"DetectedKey(start={self.start_key}, end={self.end_key}, accuracy={self.accuracy:.2f})"
        if self.mode:
            return f"DetectedKey(key={self.start_key}, accuracy={self.accuracy:.2f}, mode={self.mode})"
        return f"DetectedKey(key={self.start_key}, accuracy={self.accuracy:.2f})"

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

    def get_key_string(self, detect_advanced_modes: bool = False, index: int | None = None) -> str:
        """
        Get the key string for a specific index or the highest probability.

        Args:
            detect_advanced_modes: If True, append mode name (e.g., "A dorian")
            index: Specific key index (0-11). If None, uses highest probability

        Returns:
            Key string (e.g., "A", "Am", "C#", "F#m")
        """
        # Use provided index or find the one with maximum probability
        if index is None:
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

        # Validate index
        if index < 0 or index >= 12:
            log.error(f"Invalid key index: {index}")
            return ""

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
        # OPTIMIZATION: Vectorized matrix multiplication
        # Original Java code:
        # for (int k = 0; k < 12; ++k) {
        #     double total = 0.0;
        #     for (int n = 0; n < 12; ++n)
        #         total += pmatrix[k][n] * values[n];
        #     probability[k] = total + probability[k];
        # }

        # Compute all totals at once using matrix multiplication
        # pmatrix shape: [12, 12], values shape: [12]
        # Result shape: [12]
        totals = np.dot(self.pmatrix, values)

        # Accumulate into probability array
        self.probability += totals

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

    def __init__(self, is_major: bool, mode_type: str, probabilities_list: list[np.ndarray]):
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
        self.filters: list[SingleKeyProbabilityFilter] = []
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


class KeyProbability:
    """
    Main key detection accumulator using 6 modal templates.

    This class manages the complete key detection process, accumulating
    chromatic pitch class data over time and matching against modal
    templates to determine the most likely musical key.

    NOTE: While there are 7 diatonic modes, only 6 are used for detection.
    Locrian mode (VII) is intentionally excluded because:
    - It has a diminished fifth (tritone), making it harmonically unstable
    - Songs in locrian are extremely rare in tonal/popular music
    - Including it would likely produce false positives and reduce accuracy

    This design matches the RapidEvolution3 reference implementation.

    Reference: KeyProbability.java in RE3
    """

    # Segment size for processing (seconds) - data is accumulated then analyzed
    ANALYZE_SEGMENT_SIZE = 0.1  # Process every 0.1 seconds of accumulated data

    def __init__(self, segment_time: float):
        """
        Initialize key probability detector.

        Args:
            segment_time: Not used in current implementation, kept for compatibility
        """
        self.segment_size = 0.0  # Accumulated time
        self.segment_totals = np.zeros(12, dtype=np.float64)  # Accumulated pitch class energies

        # Initialize 6 modal filters (3 major-type, 3 minor-type)
        # NOTE: Locrian (VII) is intentionally excluded - see class docstring for rationale
        # These are the exact templates from KeyProbability.java constructor

        # Java: filters.add(new SingleKeyProbabilityFilter(true, "ionian",
        #           new double[] { 0.2, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.12 }));
        self.filters: list[SingleKeyProbabilityFilter | MultiKeyProbabilityFilter] = []

        # Major-type modes (ionian, lydian, mixolydian)
        self.filters.append(SingleKeyProbabilityFilter(
            is_major=True,
            mode_type="ionian",
            probabilities=np.array([0.2, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.12])
        ))

        # Java: filters.add(new SingleKeyProbabilityFilter(true, "lydian",
        #           new double[] { 0.2, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.12 }));
        self.filters.append(SingleKeyProbabilityFilter(
            is_major=True,
            mode_type="lydian",
            probabilities=np.array([0.2, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.12])
        ))

        # Java: filters.add(new SingleKeyProbabilityFilter(true, "mixolydian",
        #           new double[] { 0.2, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.16, 0.0, 0.12, 0.12, 0.0 }));
        self.filters.append(SingleKeyProbabilityFilter(
            is_major=True,
            mode_type="mixolydian",
            probabilities=np.array([0.2, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.16, 0.0, 0.12, 0.12, 0.0])
        ))

        # Minor-type modes (aeolian, dorian, phrygian)
        # Aeolian has 2 variants (natural and harmonic minor)
        # Java: filters.add(new MultiKeyProbabilityFilter(false, "aeolian", new double[][] {
        #           new double[] { 0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.12, 0.0 },
        #           new double[] { 0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.0, 0.12 } // harmonic
        #       }));
        self.filters.append(MultiKeyProbabilityFilter(
            is_major=False,
            mode_type="aeolian",
            probabilities_list=[
                np.array([0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.12, 0.0]),  # natural
                np.array([0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.0, 0.12])   # harmonic
            ]
        ))

        # Dorian has 2 variants
        # Java: filters.add(new MultiKeyProbabilityFilter(false, "dorian", new double[][] {
        #           new double[] { 0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.12, 0.0 },
        #           new double[] { 0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.12 } // augmented
        #       }));
        self.filters.append(MultiKeyProbabilityFilter(
            is_major=False,
            mode_type="dorian",
            probabilities_list=[
                np.array([0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.12, 0.0]),
                np.array([0.2, 0.0, 0.12, 0.16, 0.0, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.12])  # augmented
            ]
        ))

        # Phrygian (single template)
        # Java: filters.add(new SingleKeyProbabilityFilter(false, "phrygian",
        #           new double[] { 0.2, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.12, 0.0 }));
        self.filters.append(SingleKeyProbabilityFilter(
            is_major=False,
            mode_type="phrygian",
            probabilities=np.array([0.2, 0.12, 0.0, 0.16, 0.0, 0.12, 0.0, 0.16, 0.12, 0.0, 0.12, 0.0])
        ))

    def add(self, totals: np.ndarray, time: float) -> None:
        """
        Add chromatic pitch class energies for a time segment.

        Args:
            totals: 12-element array of pitch class energies
            time: Duration in seconds this data represents
        """
        # Java: segment_size += time;
        #       for (int i = 0; i < totals.length; ++i)
        #           segment_totals[i] += totals[i];
        self.segment_size += time
        for i in range(len(totals)):
            # IMPORTANT: Accumulate (+=), not replace
            self.segment_totals[i] += totals[i]

        # Process when we've accumulated enough data
        # Java: if (segment_size > analyze_segment_size)
        #           processSegment();
        if self.segment_size > self.ANALYZE_SEGMENT_SIZE:
            self._process_segment()

    def finish(self) -> None:
        """Process any remaining accumulated data."""
        # Java: if (segment_size > 0)
        #           processSegment();
        if self.segment_size > 0:
            self._process_segment()

    def _process_segment(self) -> None:
        """
        Process accumulated segment data through modal filters.

        This normalizes the accumulated pitch class totals and sends
        them to each modal filter for scoring.
        """
        # Normalize segment totals to sum to 1.0
        # Java: double total = 0;
        #       for (int i = 0; i < 12; ++i)
        #           total += segment_totals[i];
        #       if (total > 0)
        #           for (int i = 0; i < 12; ++i)
        #               segment_totals[i] /= total;
        # OPTIMIZATION: Use numpy operations instead of Python loops
        total = np.sum(self.segment_totals)
        if total > 0:
            self.segment_totals /= total

        # Send normalized data to each filter
        # Java: for (int f = 0; f < filters.size(); ++f) {
        #           KeyProbabilityFilter filter = (KeyProbabilityFilter)filters.get(f);
        #           filter.add(segment_totals);
        #       }
        for filter_instance in self.filters:
            filter_instance.add(self.segment_totals)

        # Reset for next segment
        # Java: segment_size = 0;
        #       for (int i = 0; i < segment_totals.length; ++i)
        #           segment_totals[i] = 0;
        # OPTIMIZATION: Use numpy fill instead of Python loop
        self.segment_size = 0.0
        self.segment_totals.fill(0.0)

    def get_detected_key(self, log_details: bool = False, detect_mode: bool = False) -> DetectedKey:
        """
        Get the detected key from accumulated filter results.

        Args:
            log_details: If True, log debugging information
            detect_mode: If True, track and return the detected mode

        Returns:
            DetectedKey with best match and accuracy score
        """
        # Collect results from all filters
        results: list[tuple[str, float, str]] = []  # (key_string, probability, mode_type)
        max_probability = 0.0
        min_probability = float('inf')
        total_probability = 0.0

        # Java: for (int f = 0; f < filters.size(); ++f) {
        #           KeyProbabilityFilter filter = (KeyProbabilityFilter)filters.get(f);
        #           KeyProbabilitySet resultSet = filter.getNormalizedProbabilities();
        #           resultSet.addResults(results);
        #           ...
        #       }
        for filter_instance in self.filters:
            result_set = filter_instance.get_normalized_probabilities()

            # Add all 12 keys from this filter to results
            for i in range(12):
                # Get the key string for THIS specific index, not the highest one
                key_str = result_set.get_key_string(detect_advanced_modes=False, index=i)
                prob = result_set.get_probability(i)
                mode_type = result_set.mode_type if detect_mode else ""
                results.append((key_str, prob, mode_type))

            # Track statistics
            filter_max = result_set.get_max_probability()
            if filter_max > max_probability:
                max_probability = filter_max

            filter_min = result_set.get_min_probability()
            if filter_min < min_probability:
                min_probability = filter_min

            total_probability += result_set.get_total_probability()

        # Calculate accuracy based on how much the max stands out
        # Java: double average = total_probability / (filters.size() * 12);
        #       double range = max_probability - min_probability;
        #       double accuracy = (max_probability - average) / range;
        if len(self.filters) > 0:
            average = total_probability / (len(self.filters) * 12)
            range_val = max_probability - min_probability

            if range_val > 0:
                accuracy = (max_probability - average) / range_val
            else:
                accuracy = 0.01

            # Clamp accuracy to [0, 1]
            # Java: if (accuracy < 0.0) accuracy = 0.0;
            #       if (accuracy > 1.0) accuracy = 1.0;
            if accuracy < 0.0:
                accuracy = 0.0
            if accuracy > 1.0:
                accuracy = 1.0
        else:
            accuracy = 0.01

        # Sort results by probability (descending)
        # Java uses SortObjectWrapper which sorts descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Get top result
        if results and len(results) > 0:
            best_key = results[0][0]
            best_mode = results[0][2] if detect_mode else ""
            return DetectedKey(start_key=best_key, end_key="", accuracy=accuracy, mode=best_mode)
        else:
            return DetectedKey(start_key="", end_key="", accuracy=0.01)

    def has_no_data(self) -> bool:
        """Check if all filters have zero data."""
        # Java: boolean all_zeros = true;
        #       for (int f = 0; f < filters.size(); ++f) {
        #           KeyProbabilityFilter filter = (KeyProbabilityFilter)filters.get(f);
        #           if (!filter.isAllZeros())
        #               all_zeros = false;
        #       }
        #       return all_zeros;
        all_zeros = True
        for filter_instance in self.filters:
            if not filter_instance.is_all_zeros():
                all_zeros = False
        return all_zeros


# Global cache for KeyDetectionMatrix instances
_matrix_cache: dict[int, KeyDetectionMatrix] = {}

def count_key_probabilities(
    wavedata: np.ndarray,
    icount: int,
    amt: int,
    time: float,
    maxfreq: int,
    segment_probabilities: KeyProbability,
    norm_keycount: np.ndarray,
    cwt: np.ndarray
) -> None:
    """
    Perform Continuous Wavelet Transform (CWT) on audio data to extract chromatic pitch classes.

    This function convolves audio samples with pre-calculated wavelets to measure
    the energy in each of the 12 chromatic pitch classes.

    Args:
        wavedata: Audio sample data (mono channel)
        icount: Starting index in wavedata
        amt: Number of samples to process (typically KEY_DETECTOR_ANALYZE_CHUNK_SIZE)
        time: Duration in seconds this chunk represents
        maxfreq: Maximum frequency (sample rate / 2)
        segment_probabilities: KeyProbability instance to accumulate results
        norm_keycount: 12-element working array for pitch class energies (will be zeroed)
        cwt: 12-element working array for CWT coefficients (will be zeroed)

    Reference: KeyDetector.java lines 204-223
    """
    # Get wavelet matrix for this sample rate (cached to avoid expensive recreation)
    # Java: KeyDetectionMatrix matrix = getMatrix(maxfreq);
    # OPTIMIZATION: Cache matrix by maxfreq to avoid recreating for every chunk
    if maxfreq not in _matrix_cache:
        _matrix_cache[maxfreq] = KeyDetectionMatrix(maxfreq)
        log.debug(f"Created and cached KeyDetectionMatrix for maxfreq={maxfreq}Hz")
    matrix = _matrix_cache[maxfreq]

    # Java: int icountInt = (int)icount;
    icount_int = int(icount)

    # Zero the norm_keycount accumulator
    # Java: for (int i = 0; i < norm_keycount.length; ++i)
    #           norm_keycount[i] = 0.0;
    # OPTIMIZATION: Use numpy fill instead of Python loop
    norm_keycount.fill(0.0)

    # Loop over all octaves
    # Java: for (int p = 0; p < matrix.getMaxOctaves(); p++) {
    for p in range(matrix.get_max_octaves()):
        # Loop over all shifts (always 1 in RE3)
        # Java: for (int ks = 0; ks < matrix.getShifts(); ks++) {
        for ks in range(matrix.get_shifts()):
            # Zero the CWT coefficients array for this octave/shift
            # Java: for (int z = 0; z < 12; ++z)
            #           cwt[z] = 0.0;
            # OPTIMIZATION: Use numpy fill instead of Python loop
            cwt.fill(0.0)

            # Convolve audio with wavelets for all 12 pitch classes
            # OPTIMIZATION: Vectorized matrix multiplication instead of nested loops
            # Original Java code:
            # for (int m = 0; m < amt; ++m) {
            #     for (int z = 0; z < 12; ++z) {
            #         cwt[z] += wavedata[m + icountInt] * matrix.getValue(p, ks, m, z);
            #     }
            # }

            # Get the wavelet matrix slice for this octave and shift
            # Shape: [amt, 12]
            wavelet_slice = matrix.vmatrix[p, ks, :amt, :]

            # Get the audio data for this chunk
            # Shape: [amt]
            audio_chunk = wavedata[icount_int:icount_int + amt]

            # Perform dot product: audio_chunk @ wavelet_slice
            # This computes the convolution for all 12 pitch classes at once
            # Result shape: [12]
            cwt[:] = np.dot(audio_chunk, wavelet_slice)

            # Accumulate absolute CWT values into pitch class energies
            # Java: for (int z = 0; z< 12; ++z)
            #           norm_keycount[z] += Math.abs(cwt[z]);
            # OPTIMIZATION: Use numpy operations instead of Python loop
            norm_keycount += np.abs(cwt)

    # Send accumulated pitch class energies to KeyProbability
    # Java: segment_probabilities.add(norm_keycount, time);
    segment_probabilities.add(norm_keycount, time)
