"""
Tag transformer registry and application.

This module provides the central registry for all tag transformers and the
main entry point for applying transformations to tag values.
"""

from typing import Any
from PySide6.QtCore import QSettings

from .base import TransformerBase
from .empty_string_handler import EmptyStringHandler
from .whitespace_trimmer import WhitespaceTrimmer
from .bpm_formatter import BPMFormatter
from .musical_key_formatter import MusicalKeyFormatter

from util.logging import log


# Registry structure: {tag_name: [transformer_class, ...]}
_transformer_registry: dict[str, list[type[TransformerBase]]] = {}


def register_transformer(transformer_class: type[TransformerBase]) -> None:
    """
    Register a transformer class for its applicable tags.

    This function reads the transformer's `applicable_tags` class attribute
    and adds it to the registry for each tag it applies to.

    Args:
        transformer_class: The transformer class to register
    """
    for tag_name in transformer_class.applicable_tags:
        if tag_name not in _transformer_registry:
            _transformer_registry[tag_name] = []
        _transformer_registry[tag_name].append(transformer_class)

    log.debug(f"Registered transformer '{transformer_class.name}' for tags: {transformer_class.applicable_tags}")


def get_transformers_for_tag(tag_name: str) -> list[type[TransformerBase]]:
    """
    Get all transformer classes that apply to a specific tag.

    Returns transformers sorted by priority (lower priority runs first).

    Args:
        tag_name: The generic tag name (e.g., 'bpm', 'key', 'title')

    Returns:
        List of transformer classes sorted by priority
    """
    transformers = _transformer_registry.get(tag_name, [])
    return sorted(transformers, key=lambda t: t.priority)


def apply_transformations(tag_name: str, value: Any, settings: QSettings) -> str:
    """
    Apply all relevant transformers to a tag value.

    This is the main entry point for the transformation pipeline. It:
    1. Gets all transformers for the specified tag
    2. Sorts them by priority
    3. Applies each transformer in order
    4. Returns the final transformed string value

    Args:
        tag_name: The generic tag name (e.g., 'bpm', 'key', 'title')
        value: The raw value to transform (may be int, float, str, or None)
        settings: QSettings instance for reading user preferences

    Returns:
        The transformed value as a string

    Raises:
        ValueError: If any transformer fails to process the value
    """
    # Get transformers for this tag
    transformer_classes = get_transformers_for_tag(tag_name)

    if not transformer_classes:
        # No transformers registered for this tag, just convert to string
        log.debug(f"No transformers registered for tag '{tag_name}', converting to string")
        return str(value) if value is not None else ""

    # Apply each transformer in priority order
    current_value = value
    for transformer_class in transformer_classes:
        transformer = transformer_class(settings)
        try:
            log.debug(f"Applying transformer '{transformer.name}' to tag '{tag_name}': {repr(current_value)}")
            current_value = transformer.transform(current_value, tag_name)
            log.debug(f"Result: {repr(current_value)}")
        except ValueError as e:
            log.error(f"Transformer '{transformer.name}' failed for tag '{tag_name}': {e}")
            raise

    return current_value


# Register all standard transformers at module import time
register_transformer(EmptyStringHandler)
register_transformer(WhitespaceTrimmer)
register_transformer(BPMFormatter)
register_transformer(MusicalKeyFormatter)


__all__ = [
    'TransformerBase',
    'register_transformer',
    'get_transformers_for_tag',
    'apply_transformations',
    'EmptyStringHandler',
    'WhitespaceTrimmer',
    'BPMFormatter',
    'MusicalKeyFormatter',
]
