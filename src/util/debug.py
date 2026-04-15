"""
Debug Mode State Manager

Manages runtime debug mode state for the application.
Debug mode controls:
- Log verbosity (DEBUG vs INFO)
- Debug menu visibility in GUI
- Debug-only analyzer availability

This module also hosts the shared entrypoint-bootstrap helpers
(`parse_bool_arg`, `initialize_debug_and_logging`) so CLI and GUI
entrypoints can configure debug/logging identically in one call.
"""

import argparse
from typing import Optional

from util.const import IS_DEBUG_BUILD

# Global debug mode state - initialized from build constant
_debug_mode_enabled = IS_DEBUG_BUILD

# Values accepted by the --debug style CLI arguments.
_TRUE_STRINGS = frozenset({'true', 'yes', '1', 'on'})
_FALSE_STRINGS = frozenset({'false', 'no', '0', 'off'})


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


def parse_bool_arg(value: str) -> bool:
    """
    Parse a neutrally-worded boolean CLI value.

    Accepts (case-insensitive) ``true|false|yes|no|1|0|on|off`` per the
    project's CLI argument conventions, so flags like ``--debug`` can be
    written as ``--debug true``, ``--debug no``, etc.

    Args:
        value: The raw string from argparse.

    Returns:
        The parsed boolean.

    Raises:
        argparse.ArgumentTypeError: If the value is not a recognized boolean.
    """
    lowered = value.strip().lower()
    if lowered in _TRUE_STRINGS:
        return True
    if lowered in _FALSE_STRINGS:
        return False
    raise argparse.ArgumentTypeError(
        f"Expected one of true|false|yes|no|1|0|on|off, got {value!r}"
    )


def add_debug_argument(parser: argparse.ArgumentParser) -> None:
    """
    Add a neutrally-worded ``--debug`` argument to ``parser``.

    The argument accepts an optional ``true|false|yes|no`` value; when
    omitted, it defaults to ``None`` so :func:`initialize_debug_and_logging`
    can fall back to the build-time ``IS_DEBUG_BUILD`` constant.
    """
    parser.add_argument(
        '--debug',
        nargs='?',
        const=True,
        default=None,
        type=parse_bool_arg,
        metavar='true|false',
        help='Enable or disable debug mode (default: build-time setting).',
    )


def initialize_debug_and_logging(args: argparse.Namespace) -> None:
    """
    Apply the common debug-and-logging bootstrap used by every entrypoint.

    Inspects ``args.debug`` (as produced by :func:`add_debug_argument`),
    updates the global debug-mode state, and configures the application
    logger at ``debug`` or ``info`` level accordingly.

    Extracting this out of the CLI/GUI entrypoints keeps their
    initialization logic identical and avoids the dead-code trap where
    previously both branches of an ``if args.verbose`` configured logging
    the same way.
    """
    # Import lazily so the debug module stays cheap to import from tests.
    from util.logging import configure_logger

    debug_mode: Optional[bool] = getattr(args, 'debug', None)
    if debug_mode is None:
        debug_mode = IS_DEBUG_BUILD
    set_debug_mode(bool(debug_mode))

    log_level = 'debug' if is_debug_mode() else 'info'
    configure_logger(use_formatter=True, log_level=log_level)
