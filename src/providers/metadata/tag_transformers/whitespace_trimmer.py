"""
Whitespace trimmer transformer.

This transformer removes leading and trailing whitespace from string values.
It runs early in the transformation pipeline (priority 10) to ensure clean
input for subsequent transformers.
"""

from typing import Any
from PySide6.QtCore import QSettings

from util.const import COMMON_WRITABLE_TAGS
from .base import TransformerBase


class WhitespaceTrimmer(TransformerBase):
    """
    Transformer that removes leading and trailing whitespace.

    This transformer converts string values like:
    - "  Title  " → "Title"
    - "Artist\n" → "Artist"
    - "\tAlbum" → "Album"

    It applies to all string-based tags.
    """

    name = "Whitespace Trimmer"
    description = "Remove leading and trailing whitespace from string values"
    version = "1.0.0"
    applicable_tags = list(COMMON_WRITABLE_TAGS)
    priority = 10  # Run early (after empty string handler)

    def __init__(self, settings: QSettings):
        """Initialize the whitespace trimmer."""
        super().__init__(settings)

    def transform(self, value: Any, tag_name: str) -> str:
        """
        Remove leading and trailing whitespace from the value.

        Args:
            value: The value to transform
            tag_name: The generic tag name (for context)

        Returns:
            The value with leading and trailing whitespace removed
        """
        # Convert to string (might already be a string from EmptyStringHandler)
        str_value = str(value) if value is not None else ""

        # Strip whitespace
        return str_value.strip()
