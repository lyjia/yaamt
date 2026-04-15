"""
BPM formatter transformer.

This transformer formats BPM values according to the user's decimal places preference.
"""

from typing import Any
from PySide6.QtCore import QSettings

from util.const import KEY_BPM, SETTINGS_BPM_DECIMAL_PLACES
from .base import TransformerBase


class BPMFormatter(TransformerBase):
    """
    Transformer that formats BPM values according to user preferences.

    Reads the user's preferred number of decimal places from the
    ``SETTINGS_BPM_DECIMAL_PLACES`` QSettings key (default: 0, range: 0-3).

    Examples:
    - 173.94 with 0 decimals → "174"
    - 173.94 with 1 decimal → "173.9"
    - 173.94 with 2 decimals → "173.94"
    """

    name = "BPM Formatter"
    description = "Format BPM values according to decimal places preference"
    version = "1.0.0"
    applicable_tags = [KEY_BPM]
    priority = 50  # Default priority

    def __init__(self, settings: QSettings):
        """Initialize the BPM formatter."""
        super().__init__(settings)
        # Read user preference for decimal places (default: 0)
        self.decimal_places = self._read_decimal_places_preference()

    def _read_decimal_places_preference(self) -> int:
        """
        Read the decimal_places preference from QSettings.

        Returns:
            Number of decimal places (0-3, clamped to valid range)
        """
        # Read from settings with default of 0
        value = self.settings.value(SETTINGS_BPM_DECIMAL_PLACES, 0)

        # Convert to int and clamp to valid range
        try:
            decimal_places = int(value)
            # Clamp to valid range 0-3
            return max(0, min(3, decimal_places))
        except (ValueError, TypeError):
            # If conversion fails, use default
            return 0

    def transform(self, value: Any, tag_name: str) -> str:
        """
        Format BPM value according to decimal places preference.

        Args:
            value: The BPM value to format (may be int, float, or string)
            tag_name: The generic tag name (should be 'bpm')

        Returns:
            Formatted BPM string

        Raises:
            ValueError: If the value cannot be parsed as a number
        """
        # Handle empty string (already processed by EmptyStringHandler)
        if value == "":
            return ""

        # Parse as float
        try:
            bpm_float = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid BPM value: {value} (must be numeric)")

        # Round to specified decimal places
        rounded_bpm = round(bpm_float, self.decimal_places)

        # Format as string
        if self.decimal_places == 0:
            # Integer format
            return str(int(rounded_bpm))
        else:
            # Float format with specified decimal places
            format_str = f"{{:.{self.decimal_places}f}}"
            return format_str.format(rounded_bpm)
