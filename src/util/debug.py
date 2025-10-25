"""
Debug Mode State Manager

Manages runtime debug mode state for the application.
Debug mode controls:
- Log verbosity (DEBUG vs INFO)
- Debug menu visibility in GUI
- Debug-only analyzer availability
"""

from util.const import IS_DEBUG_BUILD

# Global debug mode state - initialized from build constant
_debug_mode_enabled = IS_DEBUG_BUILD


def is_debug_mode() -> bool:
    """
    Check if debug mode is currently enabled.

    Returns:
        True if debug mode is enabled, False otherwise
    """
    return _debug_mode_enabled


def set_debug_mode(enabled: bool) -> None:
    """
    Set the debug mode state.

    Args:
        enabled: True to enable debug mode, False to disable
    """
    global _debug_mode_enabled
    _debug_mode_enabled = enabled
