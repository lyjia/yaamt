"""
Scoring logic for analyzer evaluation.

Provides functions for calculating MIREX scores for key detection
and custom scores for BPM detection.
"""

from typing import Tuple
import mingus.core.intervals as intervals


# Note names mapped to pitch classes (0-11)
NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']


# MIREX Key Scoring Configuration
# Each relationship type maps to its score value
KEY_SCORES = {
    'same key': 1.0,
    'perfect fifth': 0.5,
    'relative major/minor': 0.3,
    'parallel major/minor': 0.2,
    'other': 0.0,
}


# BPM Scoring Configuration
# List of (threshold, score, category) tuples, evaluated in order
# Threshold is the maximum absolute BPM difference for this score tier
BPM_SCORE_TIERS = [
    (0.01, 1.0, 'exact'),          # < 0.01 BPM difference
    (0.02, 0.75, 'nearly_exact'),  # < 0.02 BPM difference
    (0.05, 0.5, 'very_close'),     # < 0.05 BPM difference
    (0.1, 0.25, 'close'),          # < 0.1 BPM difference
]
# Default score for differences outside all tiers
BPM_DEFAULT_SCORE = 0.0
BPM_DEFAULT_CATEGORY = 'other'


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
    Calculate custom score for BPM detection based on absolute difference.

    Args:
        reference_bpm: Reference BPM value
        analyzed_bpm: Analyzed BPM value

    Returns:
        Tuple of (score, category)
        - score: Based on BPM_SCORE_TIERS configuration
        - category: Description of the match quality
    """
    # Round values to 2 decimal places for comparison
    ref_rounded = round(reference_bpm, 2)
    analyzed_rounded = round(analyzed_bpm, 2)

    # Calculate absolute difference and round to avoid floating point precision issues
    diff = round(abs(ref_rounded - analyzed_rounded), 2)

    # Check tiers in order (should be ordered from smallest to largest threshold)
    for threshold, score, category in BPM_SCORE_TIERS:
        if diff < threshold:
            return (score, category)

    # No tier matched, return default
    return (BPM_DEFAULT_SCORE, BPM_DEFAULT_CATEGORY)
