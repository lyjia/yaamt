"""
Empty string handler transformer.

This transformer normalizes None and empty values to empty strings.
It runs early in the transformation pipeline (priority 5) to ensure
consistent handling of empty values by subsequent transformers.
"""

from typing import Any
from PySide6.QtCore import QSettings

from util.const import COMMON_WRITABLE_TAGS
from .base import TransformerBase


class EmptyStringHandler(TransformerBase):
    """
    Transformer that normalizes None and empty values to empty strings.

    This transformer converts:
    - None → ""
    - Empty string → ""
    - Whitespace-only string → ""

    It applies to all tags that support empty values.
    """

    name = "Empty String Handler"
    description = "Normalize None and empty values to empty string"
    version = "1.0.0"
    applicable_tags = list(COMMON_WRITABLE_TAGS)
    priority = 5  # Run first

    def __init__(self, settings: QSettings):
        """Initialize the empty string handler."""
        super().__init__(settings)

    def transform(self, value: Any, tag_name: str) -> str:
        """
        Transform None, empty, or whitespace-only values to empty string.

        Args:
            value: The value to transform
            tag_name: The generic tag name (for context)

        Returns:
            Empty string if value is None, empty, or whitespace-only;
            otherwise the value converted to string
        """
        if value is None:
            return ""

        # Convert to string
        str_value = str(value)

        # If whitespace-only, return empty string
        if str_value.strip() == "":
            return ""

        # Return as-is (will be handled by subsequent transformers)
        return str_value
