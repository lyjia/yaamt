from enum import Enum
from typing import Dict, List, Type
from providers.analysis import AnalyzerBase, AnalyzerCategory

"""
Provider Registry

Providers relying on a discovery system should register themselves here using the register_* functions.

This was previously a fancy ai-generated auto-discovery system that used reflection to discover analyzers,
but this approach was not compatible with Nuitka's compilation process, so I've replaced it with something simpler.
"""

ANALYZER_REGISTRY: Dict[ AnalyzerCategory, List[Type[AnalyzerBase]] ] = {}

def get_analyzers_by_category(category: AnalyzerCategory) -> List[Type[AnalyzerBase]]:
    """
    Get all analyzers for a given category.

    Args:
        category: The analyzer category (e.g., 'bpm', 'key', 'gain')

    Returns:
        List of analyzer classes for that category, or empty list if none found
    """
    return ANALYZER_REGISTRY.get(category, [])


def get_all_categories() -> List[AnalyzerCategory]:
    """
    Get list of all analyzer categories.

    Returns:
        Sorted list of category names
    """
    return list(ANALYZER_REGISTRY.keys())


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

def register_analyzer(category: AnalyzerCategory, analyzer_class: Type[AnalyzerBase]):
    gotten = ANALYZER_REGISTRY.get(category, [])
    if analyzer_class not in gotten:
        ANALYZER_REGISTRY[category] = gotten + [analyzer_class]