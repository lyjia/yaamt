"""
Analyzer auto-discovery and registry system.

This module automatically discovers all analyzer classes in submodules and
builds a registry categorized by analyzer type (e.g., bpm, key, gain).
"""

import importlib
import pkgutil
from typing import Dict, List, Type

from providers.analysis.base import AnalyzerBase
from util.logging import log

# Registry: {category_name: [AnalyzerClass, ...]}
ANALYZER_REGISTRY: Dict[str, List[Type[AnalyzerBase]]] = {}


def discover_analyzers() -> None:
    """
    Auto-discover all analyzer classes in submodules.

    Walks through all submodules of providers.analysis, imports them, and
    registers any AnalyzerBase subclasses found. Analyzers are organized
    by their 'category' attribute.
    """
    package = __package__
    package_path = __path__

    for importer, modname, ispkg in pkgutil.walk_packages(package_path, prefix=f"{package}."):
        # Skip the base module itself
        if modname == f"{package}.base":
            continue

        if not ispkg:
            try:
                module = importlib.import_module(modname)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Check if this is an analyzer class (but not the base class itself)
                    if (isinstance(attr, type) and
                        issubclass(attr, AnalyzerBase) and
                        attr is not AnalyzerBase):

                        category = attr.category
                        if category not in ANALYZER_REGISTRY:
                            ANALYZER_REGISTRY[category] = []

                        # Avoid duplicate registration
                        if attr not in ANALYZER_REGISTRY[category]:
                            ANALYZER_REGISTRY[category].append(attr)
                            log.debug(f"Registered analyzer: {attr.name} (category: {category})")

            except Exception as e:
                log.warning(f"Failed to load analyzer module {modname}: {e}")


def get_analyzers_by_category(category: str) -> List[Type[AnalyzerBase]]:
    """
    Get all analyzers for a given category.

    Args:
        category: The analyzer category (e.g., 'bpm', 'key', 'gain')

    Returns:
        List of analyzer classes for that category, or empty list if none found
    """
    return ANALYZER_REGISTRY.get(category, [])


def get_all_categories() -> List[str]:
    """
    Get list of all analyzer categories.

    Returns:
        Sorted list of category names
    """
    return sorted(ANALYZER_REGISTRY.keys())


def get_analyzer_by_name(name: str) -> Type[AnalyzerBase] | None:
    """
    Get an analyzer class by its name.

    Args:
        name: The analyzer class name (e.g., 'LibrosaBPMAnalyzer')

    Returns:
        The analyzer class if found, None otherwise
    """
    for analyzers in ANALYZER_REGISTRY.values():
        for analyzer in analyzers:
            if analyzer.__name__ == name:
                return analyzer
    return None


# Run discovery on import
discover_analyzers()
