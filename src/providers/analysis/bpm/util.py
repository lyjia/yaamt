"""
BPM Analysis Utilities.

This module provides utility functions for BPM analysis, including
postprocessing functions to adjust BPM values to fit within user-specified ranges.
"""

from typing import Optional

from util.logging import log


def adjust_bpm_to_range(
    bpm: float,
    min_bpm: Optional[int],
    max_bpm: Optional[int]
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
