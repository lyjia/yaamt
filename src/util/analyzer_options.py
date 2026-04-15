"""
Analyzer option metadata (GUI-free half of the system).

This module owns the declarative ``AnalyzerOption`` dataclass and the
CLI-side argparse helpers. It is deliberately free of PySide6 so
providers, analyzers, and the CLI entrypoint can import it without
dragging in Qt.

The GUI counterpart -- :func:`build_widget_from_option` and its
supporting ``_build_*`` helpers -- lives in
``windows.analyzer.option_widgets``. Call that module when you need to
render an option as a Qt widget.
"""

from dataclasses import dataclass, field
from typing import Any
from argparse import ArgumentParser


@dataclass
class AnalyzerOption:
    """
    Metadata describing a single analyzer option.

    This serves as the single source of truth for option definitions,
    used by both CLI argument parsing and GUI widget generation.

    Attributes:
        name: Option identifier (e.g., 'buf_size', 'method')
              Used as argparse dest and QWidget objectName
        type: Option type - 'int', 'float', 'bool', 'choice', 'slider'
        default: Default value for this option
        help: Human-readable description (used in CLI help and tooltips)
        choices: List of valid values for 'choice' type
                Can be:
                - List of values: ['a', 'b', 'c']
                - List of (value, label) tuples: [('a', 'Label A'), ('b', 'Label B')]
        min: Minimum value for numeric types
        max: Maximum value for numeric types
        interval: Step size for numeric types (determines if slider is used)
        suffix: Display suffix for GUI (e.g., '%', 'ms', 'Hz')
    """
    name: str
    type: str
    default: Any
    help: str
    choices: list[Any | tuple[Any, str]] | None = None
    min: float | None = None
    max: float | None = None
    interval: float | None = None
    suffix: str | None = None

    def __post_init__(self):
        """Validate option configuration."""
        valid_types = {'int', 'float', 'bool', 'choice', 'slider', 'file', 'directory'}
        if self.type not in valid_types:
            raise ValueError(f"Invalid option type '{self.type}'. Must be one of {valid_types}")

        if self.type == 'choice' and not self.choices:
            raise ValueError(f"Option '{self.name}' of type 'choice' must have choices defined")

        if self.type in ('int', 'float', 'slider'):
            if self.min is not None and self.max is not None and self.min > self.max:
                raise ValueError(f"Option '{self.name}': min ({self.min}) cannot be greater than max ({self.max})")


def add_option_to_argparse(parser: ArgumentParser,
                          option: AnalyzerOption,
                          prefix: str = "--") -> None:
    """
    Add option to argparse parser with appropriate type and validation.

    Argparse Argument Mapping:
    - type='int'/'slider' → type=int, metavar='N'
    - type='float' → type=float, metavar='F'
    - type='bool' → action='store_true' (default False) or store_false (default True)
    - type='choice' → choices=[...], type inferred from first choice

    The option name is converted to a CLI-friendly format:
    - Underscores → hyphens (e.g., 'buf_size' → '--buf-size')
    - Prefixed with '--' (or custom prefix)

    Args:
        parser: ArgumentParser or subparser to add option to
        option: The AnalyzerOption to add
        prefix: Argument prefix (default: '--')
    """
    # Convert option name to CLI format (underscores → hyphens)
    arg_name = prefix + option.name.replace('_', '-')

    # Build argparse kwargs
    kwargs = {
        'dest': option.name,  # Use original name as dest for consistency
        'help': option.help,
        'default': option.default
    }

    if option.type == 'bool':
        # For boolean, use store_true or store_false based on default
        if option.default:
            kwargs['action'] = 'store_false'
            kwargs['help'] += ' (default: enabled)'
        else:
            kwargs['action'] = 'store_true'
            kwargs['help'] += ' (default: disabled)'
        # Remove default from kwargs (not used with store_true/false)
        del kwargs['default']

    elif option.type == 'choice':
        # Extract just the values from choices (ignoring labels)
        choice_values = []
        for choice in option.choices:
            if isinstance(choice, tuple):
                choice_values.append(choice[0])
            else:
                choice_values.append(choice)

        kwargs['choices'] = choice_values
        kwargs['metavar'] = '{' + ','.join(str(c) for c in choice_values) + '}'

        # Infer type from first choice
        if choice_values:
            kwargs['type'] = type(choice_values[0])

    elif option.type in ('int', 'slider'):
        kwargs['type'] = int
        kwargs['metavar'] = 'N'

        # Add range info to help text
        if option.min is not None and option.max is not None:
            kwargs['help'] += f' (range: {option.min}-{option.max})'
        elif option.min is not None:
            kwargs['help'] += f' (min: {option.min})'
        elif option.max is not None:
            kwargs['help'] += f' (max: {option.max})'

    elif option.type == 'float':
        kwargs['type'] = float
        kwargs['metavar'] = 'F'

        # Add range info to help text
        if option.min is not None and option.max is not None:
            kwargs['help'] += f' (range: {option.min}-{option.max})'
        elif option.min is not None:
            kwargs['help'] += f' (min: {option.min})'
        elif option.max is not None:
            kwargs['help'] += f' (max: {option.max})'

    elif option.type == 'file':
        kwargs['type'] = str
        kwargs['metavar'] = 'PATH'
        kwargs['help'] += ' (file path)'

    elif option.type == 'directory':
        kwargs['type'] = str
        kwargs['metavar'] = 'DIR'
        kwargs['help'] += ' (directory path)'

    parser.add_argument(arg_name, **kwargs)


def get_common_analyzer_options() -> list[AnalyzerOption]:
    """
    Return common options available for all analyzers.

    These options are used by the analyze command and AnalyzerSetupDialog.

    Returns:
        List of common AnalyzerOption instances
    """
    return [
        AnalyzerOption(
            name='skip_if_tag_exists',
            type='bool',
            default=False,
            help='Skip analysis if tag already has a value (analyze all files by default)'
        )
    ]


# BPM range preference keys in QSettings (re-exported from util.const so all
# QSettings paths are centralised there). Kept at module level so existing
# ``from util.analyzer_options import BPM_RANGE_*`` imports keep working.
from util.const import (  # noqa: E402 - intentional: re-export
    BPM_RANGE_MIN_KEY,
    BPM_RANGE_MAX_KEY,
    BPM_RANGE_MIN_DEFAULT,
    BPM_RANGE_MAX_DEFAULT,
)


def get_bpm_category_options() -> list[AnalyzerOption]:
    """
    Return BPM-specific category options for CLI.

    These options can be passed via CLI. By default, BPM range is disabled
    (no min/max constraint). Use --use-saved-prefs to load from preferences.

    Options:
        - bpm_min: Minimum BPM for range enforcement (default: None/disabled)
        - bpm_max: Maximum BPM for range enforcement (default: None/disabled)

    The BPM range is used in two ways:
    1. As a hint to analyzers that support it (e.g., RE3 uses it to filter
       candidates during analysis)
    2. As a postprocessing constraint that adjusts the result by doubling
       or halving to fit within the range

    Returns:
        List of AnalyzerOption instances for BPM category options
    """
    return [
        AnalyzerOption(
            name='bpm_min',
            type='int',
            default=0,  # 0 means disabled
            min=0,
            max=999,
            help='Minimum BPM for detection range (0 = disabled)'
        ),
        AnalyzerOption(
            name='bpm_max',
            type='int',
            default=0,  # 0 means disabled
            min=0,
            max=999,
            help='Maximum BPM for detection range (0 = disabled)'
        )
    ]
