"""
BPM Analysis Utilities.

This module provides utility functions and data structures for BPM analysis,
including the BpmCandidate dataclass for representing BPM detection results
and functions to select the best BPM from candidates.
"""

from dataclasses import dataclass

from util.logging import log


@dataclass
class BpmCandidate:
    """
    Represents a BPM detection candidate with certainty weighting.

    Attributes:
        bpm: The detected BPM value
        certainty: Confidence/certainty score for this detection.
                   Higher values indicate more confidence.
                   Scale is analyzer-dependent but should be consistent
                   within each analyzer. Use 0.0 if analyzer doesn't
                   provide confidence scores.
    """
    bpm: float
    certainty: float = 0.0

    def __repr__(self) -> str:
        return f"BpmCandidate(bpm={self.bpm:.2f}, certainty={self.certainty:.4f})"


def adjust_bpm_to_range(
    bpm: float,
    min_bpm: int | None,
    max_bpm: int | None
) -> float:
    """
    Adjust BPM value to fall within the specified range by doubling or halving.

    Many BPM analyzers detect a beat period but may return a BPM that is half
    or double the actual perceived tempo. This function adjusts the value to
    fit within the user's expected range by applying simple 2x or 0.5x
    multipliers.

    The adjustment logic:
    - If BPM < min_bpm: double it (if the result fits within max_bpm)
    - If BPM > max_bpm: halve it (if the result fits within min_bpm)
    - If no valid adjustment is possible, return the original value

    Args:
        bpm: The raw BPM value from the analyzer
        min_bpm: Minimum acceptable BPM (None = no minimum constraint)
        max_bpm: Maximum acceptable BPM (None = no maximum constraint)

    Returns:
        Adjusted BPM value, or original if no valid adjustment is possible
        or if both constraints are None.

    Examples:
        >>> adjust_bpm_to_range(65.0, 80, 200)
        130.0  # Doubled because 65 < 80, and 130 <= 200

        >>> adjust_bpm_to_range(240.0, 80, 200)
        120.0  # Halved because 240 > 200, and 120 >= 80

        >>> adjust_bpm_to_range(120.0, 80, 200)
        120.0  # No adjustment needed

        >>> adjust_bpm_to_range(120.0, None, None)
        120.0  # No constraints, no adjustment
    """
    # No constraints means no adjustment needed
    if min_bpm is None and max_bpm is None:
        return bpm

    original_bpm = bpm

    # Try doubling if below minimum
    if min_bpm is not None and bpm < min_bpm:
        doubled = bpm * 2
        # Check if doubled value fits within max constraint (or no max constraint)
        if max_bpm is None or doubled <= max_bpm:
            log.debug(
                f"BPM {bpm:.2f} below minimum {min_bpm}, "
                f"doubled to {doubled:.2f}"
            )
            return doubled
        # Doubled value exceeds max, can't adjust
        log.debug(
            f"BPM {bpm:.2f} below minimum {min_bpm}, "
            f"but doubled value {doubled:.2f} exceeds maximum {max_bpm}"
        )

    # Try halving if above maximum
    if max_bpm is not None and bpm > max_bpm:
        halved = bpm / 2
        # Check if halved value fits within min constraint (or no min constraint)
        if min_bpm is None or halved >= min_bpm:
            log.debug(
                f"BPM {bpm:.2f} above maximum {max_bpm}, "
                f"halved to {halved:.2f}"
            )
            return halved
        # Halved value is below min, can't adjust
        log.debug(
            f"BPM {bpm:.2f} above maximum {max_bpm}, "
            f"but halved value {halved:.2f} is below minimum {min_bpm}"
        )

    # BPM is already within range, or no valid adjustment found
    return original_bpm


def select_best_bpm(
    candidates: list[BpmCandidate],
    min_bpm: int | None = None,
    max_bpm: int | None = None
) -> float | None:
    """
    Select the best BPM from a list of candidates, applying range adjustment.

    This function selects the highest-certainty candidate and then applies
    range adjustment (doubling/halving) if the value falls outside the
    specified range.

    The candidate list and selection process are logged to DEBUG for
    debugging purposes.

    Args:
        candidates: List of BpmCandidate objects from analyzer.
                    Must not be empty.
        min_bpm: Minimum acceptable BPM (None = no minimum constraint)
        max_bpm: Maximum acceptable BPM (None = no maximum constraint)

    Returns:
        The selected BPM value (possibly adjusted to fit range),
        or None if candidates list is empty.

    Example:
        >>> candidates = [
        ...     BpmCandidate(bpm=65.0, certainty=0.9),
        ...     BpmCandidate(bpm=130.0, certainty=0.7),
        ... ]
        >>> select_best_bpm(candidates, min_bpm=80, max_bpm=200)
        130.0  # 65.0 has highest certainty, doubled to fit range
    """
    if not candidates:
        log.warning("select_best_bpm called with empty candidates list")
        return None

    # Log all candidates for debugging
    log.debug(f"BPM candidates ({len(candidates)} total):")
    for i, candidate in enumerate(candidates):
        log.debug(f"  [{i+1}] {candidate}")

    # Sort by certainty (descending) and select highest
    sorted_candidates = sorted(candidates, key=lambda c: c.certainty, reverse=True)
    best_candidate = sorted_candidates[0]

    log.debug(
        f"Selected highest-certainty candidate: "
        f"BPM={best_candidate.bpm:.2f}, certainty={best_candidate.certainty:.4f}"
    )

    # Apply range adjustment
    final_bpm = adjust_bpm_to_range(best_candidate.bpm, min_bpm, max_bpm)

    if final_bpm != best_candidate.bpm:
        log.debug(
            f"Adjusted BPM from {best_candidate.bpm:.2f} to {final_bpm:.2f} "
            f"(range: {min_bpm}-{max_bpm})"
        )

    return final_bpm