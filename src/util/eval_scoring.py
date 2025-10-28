"""
Scoring logic for analyzer evaluation.

Provides functions for calculating MIREX scores for key detection
and custom scores for BPM detection.
"""

from typing import Tuple
import mingus.core.intervals as intervals


# Note names mapped to pitch classes (0-11)
NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']


def calculate_key_relationship(
    ref_pitch_class: int,
    ref_is_minor: bool,
    analyzed_pitch_class: int,
    analyzed_is_minor: bool
) -> Tuple[float, str]:
    """
    Calculate MIREX relationship score between reference and analyzed keys.

    Args:
        ref_pitch_class: Reference key pitch class (0-11)
        ref_is_minor: True if reference key is minor
        analyzed_pitch_class: Analyzed key pitch class (0-11)
        analyzed_is_minor: True if analyzed key is minor

    Returns:
        Tuple of (score, category_name)
        - score: MIREX score (1.0, 0.5, 0.3, 0.2, or 0.0)
        - category_name: One of 'same key', 'perfect fifth', 'relative major/minor',
                        'parallel major/minor', 'other'
    """
    # Convert pitch classes to mingus note format
    ref_note = NOTE_NAMES[ref_pitch_class]
    analyzed_note = NOTE_NAMES[analyzed_pitch_class]

    # Check for same key (exact match)
    if ref_pitch_class == analyzed_pitch_class and ref_is_minor == analyzed_is_minor:
        return (1.0, 'same key')

    # Calculate semitone distances (both directions since mingus.measure is directional)
    distance_forward = intervals.measure(ref_note, analyzed_note)
    distance_backward = intervals.measure(analyzed_note, ref_note)

    # Check for parallel major/minor (same tonic, different mode)
    if ref_pitch_class == analyzed_pitch_class and ref_is_minor != analyzed_is_minor:
        return (0.2, 'parallel major/minor')

    # Check for relative major/minor (mode differs, distance is 3 semitones in either direction)
    if ref_is_minor != analyzed_is_minor and (distance_forward == 3 or distance_backward == 3):
        return (0.3, 'relative major/minor')

    # Check for perfect fifth (same mode, distance is 7 semitones in either direction)
    if ref_is_minor == analyzed_is_minor and (distance_forward == 7 or distance_backward == 7):
        return (0.5, 'perfect fifth')

    # No meaningful relationship
    return (0.0, 'other')


def calculate_key_score(
    ref_pitch_class: int,
    ref_is_minor: bool,
    analyzed_pitch_class: int,
    analyzed_is_minor: bool
) -> float:
    """
    Calculate MIREX score for key detection.

    Wrapper around calculate_key_relationship that returns only the score.

    Args:
        ref_pitch_class: Reference key pitch class (0-11)
        ref_is_minor: True if reference key is minor
        analyzed_pitch_class: Analyzed key pitch class (0-11)
        analyzed_is_minor: True if analyzed key is minor

    Returns:
        MIREX score (1.0, 0.5, 0.3, 0.2, or 0.0)
    """
    score, _ = calculate_key_relationship(
        ref_pitch_class, ref_is_minor, analyzed_pitch_class, analyzed_is_minor
    )
    return score


def calculate_bpm_score(reference_bpm: float, analyzed_bpm: float) -> Tuple[float, str]:
    """
    Calculate custom score for BPM detection.

    Args:
        reference_bpm: Reference BPM value
        analyzed_bpm: Analyzed BPM value

    Returns:
        Tuple of (score, category)
        - score: 1.0 (exact), 0.5 (±10%), 0.25 (±20%), or 0.0 (other)
        - category: Description of the match quality
    """
    # Round values to 2 decimal places for comparison
    ref_rounded = round(reference_bpm, 2)
    analyzed_rounded = round(analyzed_bpm, 2)

    # Calculate absolute difference
    diff = abs(ref_rounded - analyzed_rounded)

    # Small epsilon for floating point comparison tolerance
    epsilon = 1e-9

    # Exact match (< 0.01 BPM difference)
    if diff < 0.01:
        return (1.0, 'exact')

    # Within ±10%
    threshold_10pct = ref_rounded * 0.1
    if diff <= threshold_10pct + epsilon:
        return (0.5, 'within_10pct')

    # Within ±20%
    threshold_20pct = ref_rounded * 0.2
    if diff <= threshold_20pct + epsilon:
        return (0.25, 'within_20pct')

    # Outside acceptable range
    return (0.0, 'other')
