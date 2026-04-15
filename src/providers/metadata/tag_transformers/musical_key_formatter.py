"""
Musical key formatter transformer.

This transformer converts musical key notation according to user preference.
Supports multiple notation formats including standard, Camelot, and Open Key.
"""

from typing import Any, Optional, Tuple
from PySide6.QtCore import QSettings

from util.const import (
    KEY_INITIAL_KEY, KEY_NOTATION_FORMAT_DEFAULT, SETTINGS_KEY_NOTATION_FORMAT,
)
from util.logging import log
from util.diatonic_key import CAMELOT_MAP, OPEN_KEY_MAP, NOTE_TO_PITCH, parse_key, format_key, NotationFormat
from .base import TransformerBase

class MusicalKeyFormatter(TransformerBase):
    """
    Transformer that formats musical key notation according to user preference.

    Supported formats:
    - "standard_abbrev": Cmin, Amaj, Dbmin, F#maj
    - "standard_single": Cm, A, Dbm, F#
    - "camelot": 6A, 8B, 2A, 7B
    - "open_key": 6m, 8d, 2m, 7d

    Reads preference from the ``SETTINGS_KEY_NOTATION_FORMAT`` QSettings key.
    Default: "standard_abbrev"
    """

    name = "Musical Key Formatter"
    description = "Convert musical key notation according to user preference"
    version = "1.0.0"
    applicable_tags = [KEY_INITIAL_KEY]
    priority = 50  # Default priority

    def __init__(self, settings: QSettings):
        """Initialize the musical key formatter."""
        super().__init__(settings)
        self.notation_format = self._read_notation_preference()

    def _read_notation_preference(self) -> NotationFormat:
        """
        Read the notation_format preference from QSettings.

        Returns:
            Notation format enum (default: NotationFormat.StandardAbbrev)
        """
        value_str = self.settings.value(
            SETTINGS_KEY_NOTATION_FORMAT, KEY_NOTATION_FORMAT_DEFAULT
        )

        # Convert string to enum by matching against enum values
        for fmt in NotationFormat:
            if fmt.value == value_str:
                return fmt

        # Default to standard_abbrev if invalid format
        return NotationFormat.StandardAbbrev

    def transform(self, value: Any, tag_name: str) -> str:
        """
        Transform a musical key value to the target notation format.

        Args:
            value: The key value to transform (may be string)
            tag_name: The generic tag name (should be 'key' or 'musical_key')

        Returns:
            Formatted key string

        Raises:
            ValueError: If the key notation cannot be parsed
        """
        # Handle empty string
        if value == "" or value is None:
            return ""

        # Convert to string
        key_str = str(value)

        # Parse the key
        parsed = parse_key(key_str)
        if parsed is None:
            # raise ValueError(f"Invalid musical key notation: {key_str}")
            log.warning(f"Invalid musical key notation: '{key_str}'. Ignoring...")
            return value

        pitch_class, is_minor = parsed

        # Format according to preference
        return format_key(pitch_class, is_minor, self.notation_format)
