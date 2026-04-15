"""
Base classes for tag value transformers.

This module defines the abstract interface that all tag transformers must implement.
Transformers are responsible for normalizing and formatting tag values before they are
written to files.
"""

from abc import ABC, abstractmethod
from typing import Any
from PySide6.QtCore import QSettings


class TransformerBase(ABC):
    """
    Abstract base class for tag value transformers.

    Each transformer is responsible for converting raw tag values (which may be
    int, float, or string) into properly formatted string values according to
    user preferences.

    Transformers declare which tags they apply to via the `applicable_tags`
    class attribute, and are applied in priority order (lower priority values
    run first).

    Attributes:
        name: Human-readable name of this transformer
        description: Brief description of what this transformer does
        version: Version string for this transformer
        applicable_tags: List of generic tag names this transformer applies to
        priority: Integer controlling transformation order (lower = earlier, default 50)
    """

    name: str = "Base Transformer"
    description: str = "Base transformer class"
    version: str = "1.0.0"
    applicable_tags: list[str] = []
    priority: int = 50

    def __init__(self, settings: QSettings):
        """
        Initialize the transformer with access to user preferences.

        Args:
            settings: QSettings instance for reading user preferences
        """
        self.settings = settings

    @abstractmethod
    def transform(self, value: Any, tag_name: str) -> str:
        """
        Transform a raw tag value into a formatted string.

        This method accepts any type (int, float, str, None) and must return
        a properly formatted string value. If the transformation cannot be
        performed, raise ValueError with a descriptive error message.

        Args:
            value: The raw value to transform (may be int, float, str, or None)
            tag_name: The generic tag name for context (e.g., 'bpm', 'key', 'title')

        Returns:
            The transformed value as a string

        Raises:
            ValueError: If the transformation fails or the value is invalid
        """
        pass
