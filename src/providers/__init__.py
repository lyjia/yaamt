import importlib
import pkgutil
from enum import Enum
from typing import Callable, Dict, List, Type
from providers.analysis import AnalyzerBase, AnalyzerCategory
from util.debug import is_debug_mode
from util.logging import log

"""
Provider Registry

Providers relying on this discovery system should register themselves here using the register_* functions. (See `discover_providers()`)

"""

class ProviderType(Enum):
    ANALYZER = "ANALYZER"

PROVIDER_REGISTRY: Dict[ ProviderType, Dict[ AnalyzerCategory, List[Type[AnalyzerBase]]]] = {}
for cat in ProviderType:
    PROVIDER_REGISTRY[cat] = {}

def get_analyzers_by_category(category: AnalyzerCategory) -> List[Type[AnalyzerBase]]:
    """
    Get all analyzers for a given category.

    Args:
        category: The analyzer category (e.g., 'bpm', 'key', 'gain')

    Returns:
        List of analyzer classes for that category, or empty list if none found
        (Filters out debug_only analyzers when debug mode is OFF)
    """
    analyzers = PROVIDER_REGISTRY[ProviderType.ANALYZER].get(category, [])

    # Filter out debug_only analyzers when debug mode is disabled
    if not is_debug_mode():
        analyzers = [a for a in analyzers if not getattr(a, 'debug_only', False)]

    return analyzers


def get_all_categories(provider_type: ProviderType) -> List[AnalyzerCategory]:
    """
    Get list of all analyzer categories.

    Returns:
        Sorted list of category names
    """
    return list(PROVIDER_REGISTRY[provider_type].keys())


def get_analyzer_by_name(name: str) -> Type[AnalyzerBase] | None:
    """
    Get an analyzer class by its name.

    Args:
        name: The analyzer class name (e.g., 'LibrosaBPMAnalyzer')

    Returns:
        The analyzer class if found, None otherwise
    """
    for typ in ProviderType:
        for analyzers in PROVIDER_REGISTRY[typ].values():
            for analyzer in analyzers:
                if analyzer.__name__ == name:
                    return analyzer
    return None

def register_provider(provider_type: ProviderType, provider_category: AnalyzerCategory, klass: Type[AnalyzerBase] ):
    """
    Registers a provider class to the provider registry under a specified type
    and category. If the class is already registered, a warning is logged and registration is skipped.

    :param provider_type: The type of the provider to register.
    :param provider_category: The category of the provider to register.
    :param klass: The class to be registered. Must be a subclass of
        `AnalyzerBase`.
    :return: None
    """
    gotten = PROVIDER_REGISTRY[provider_type].get(provider_category, [])
    if klass not in gotten:
        PROVIDER_REGISTRY[provider_type][provider_category] = gotten + [klass]
        log.debug(f"Registered {provider_type} {provider_category} {klass}")
    else:
        log.warn(f"{klass} Already registered, skipping!")

def register_analyzer(category: AnalyzerCategory, klass: Type[AnalyzerBase]):
    """
    Registers an Analyzer module to the Providers registry, under the given AnalyzerCategory.

    Also registers any resources required by the analyzer with the global ResourceManager.

    :param category: The category under which the analyzer should be registered.
    :param klass: The class of the analyzer to be registered.
    :return: None
    """
    register_provider(ProviderType.ANALYZER, category, klass)

    # Register required resources with global ResourceManager
    try:
        resources = klass.get_required_resources()
        if resources:
            from util.resource_manager import get_resource_manager
            resource_manager = get_resource_manager()
            for resource in resources:
                resource_manager.register_resource(resource)
            log.debug(f"Registered {len(resources)} resources for {klass.__name__}")
    except Exception as e:
        log.warning(f"Error registering resources for {klass.__name__}: {e}")


def analyzer(category: AnalyzerCategory, debug_only: bool = False) -> Callable[[Type[AnalyzerBase]], Type[AnalyzerBase]]:
    """
    Class decorator that registers an analyzer with the provider registry.

    Usage:
        @analyzer(AnalyzerCategory.BPM)
        class MyBPMAnalyzer(AnalyzerBase):
            ...

        @analyzer(AnalyzerCategory.BPM, debug_only=True)
        class ExperimentalAnalyzer(AnalyzerBase):
            ...

    :param category: The category under which the analyzer should be registered.
    :param debug_only: If True, analyzer is only available in debug builds (default: False).
    :return: A decorator function that registers the class and returns it unchanged.
    """
    def decorator(klass: Type[AnalyzerBase]) -> Type[AnalyzerBase]:
        if debug_only:
            klass.debug_only = True
        register_analyzer(category, klass)
        return klass
    return decorator

def discover_providers():
    """
    Loads provider modules from the static manifest.

    The imported modules will self-register with the provider registry.

    :return: None
    """
    # Import the static manifest (works in both compiled executables and development)
    from providers.analysis import _manifest
    log.debug("Loaded providers from static manifest")


# def _discover_providers_dynamic():
#     """
#     Dynamically discovers providers using pkgutil (development mode only).
#
#     This method does NOT work in compiled executables (Nuitka, PyInstaller, etc.)
#     as it relies on filesystem access to discover modules.
#
#     NOTE: This function is no longer used. All provider modules must be explicitly
#     listed in the static manifest at providers/analysis/_manifest.py
#
#     :return: None
#     """
#     scan_package = importlib.import_module(__package__)
#     scan_path = scan_package.__path__
#
#     for typ in pkgutil.iter_modules(scan_path): # providers.<provider type>
#         provider_type_module = importlib.import_module(scan_package.__name__ + "." + typ.name)
#
#         if typ.name == "analysis":
#             for cat in pkgutil.iter_modules(provider_type_module.__path__): # providers.analysis.<analysis category>
#                 # discover analysis providers
#                 provider_category_module = importlib.import_module(provider_type_module.__name__ + "." + cat.name)
#
#                 if "base" not in provider_category_module.__name__:
#                     for mod in pkgutil.iter_modules(provider_category_module.__path__):
#                         importlib.import_module(provider_category_module.__name__ + "." + mod.name)

discover_providers()