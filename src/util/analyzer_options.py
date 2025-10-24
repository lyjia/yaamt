"""
Analyzer Option System

This module provides a declarative system for defining analyzer options that can be
used by both the CLI (argparse) and GUI (Qt widgets). This eliminates code duplication
and ensures consistency between the two interfaces.

Key components:
- AnalyzerOption: Dataclass defining a single option's metadata
- build_widget_from_option(): Auto-generate Qt widget from option metadata
- add_option_to_argparse(): Add option to argparse parser
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union
from argparse import ArgumentParser

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QSlider
)
from PySide6.QtCore import Qt, QSettings


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
    choices: Optional[List[Union[Any, Tuple[Any, str]]]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    interval: Optional[float] = None
    suffix: Optional[str] = None

    def __post_init__(self):
        """Validate option configuration."""
        valid_types = {'int', 'float', 'bool', 'choice', 'slider'}
        if self.type not in valid_types:
            raise ValueError(f"Invalid option type '{self.type}'. Must be one of {valid_types}")

        if self.type == 'choice' and not self.choices:
            raise ValueError(f"Option '{self.name}' of type 'choice' must have choices defined")

        if self.type in ('int', 'float', 'slider'):
            if self.min is not None and self.max is not None and self.min > self.max:
                raise ValueError(f"Option '{self.name}': min ({self.min}) cannot be greater than max ({self.max})")


def build_widget_from_option(option: AnalyzerOption,
                            settings_group: Optional[str] = None) -> QWidget:
    """
    Auto-generate appropriate Qt widget from option metadata.

    Widget Selection Logic:
    - type='slider' → Always use QSlider + QSpinBox/QDoubleSpinBox
    - type='int'/'float' with min/max/interval → QSlider + SpinBox
    - type='int'/'float' without interval → SpinBox only
    - type='bool' → QCheckBox
    - type='choice' → QComboBox

    The generated widget will have its objectName set to option.name,
    which is used by AnalyzerSetupDialog._extract_settings_from_widget()
    to retrieve values.

    QSettings Integration:
    If settings_group is provided, the widget will load its initial value
    from QSettings and save changes back automatically.

    Args:
        option: The AnalyzerOption to create a widget for
        settings_group: Optional QSettings group path (e.g., "analyzers/AubioBPMAnalyzer")

    Returns:
        QWidget configured based on option metadata
    """
    # Load saved value from QSettings if available
    saved_value = option.default
    if settings_group:
        settings = QSettings("Lyjia", "Audio Metadata Tool")
        settings.beginGroup(settings_group)

        # Type-appropriate retrieval
        if option.type == 'bool':
            saved_value = settings.value(option.name, option.default, type=bool)
        elif option.type in ('int', 'slider'):
            saved_value = settings.value(option.name, option.default, type=int)
        elif option.type == 'float':
            saved_value = settings.value(option.name, option.default, type=float)
        else:  # choice
            saved_value = settings.value(option.name, option.default)

        settings.endGroup()

    # Create widget based on type
    if option.type == 'bool':
        return _build_checkbox(option, saved_value, settings_group)

    elif option.type == 'choice':
        return _build_combobox(option, saved_value, settings_group)

    elif option.type == 'slider' or (option.type in ('int', 'float') and
                                     option.min is not None and
                                     option.max is not None and
                                     option.interval is not None):
        return _build_slider_spinbox(option, saved_value, settings_group)

    elif option.type == 'int':
        return _build_spinbox(option, saved_value, settings_group, is_float=False)

    elif option.type == 'float':
        return _build_spinbox(option, saved_value, settings_group, is_float=True)

    else:
        raise ValueError(f"Cannot build widget for option type: {option.type}")


def _build_checkbox(option: AnalyzerOption,
                   value: bool,
                   settings_group: Optional[str]) -> QCheckBox:
    """Build a QCheckBox widget."""
    checkbox = QCheckBox(option.help)
    checkbox.setObjectName(option.name)
    checkbox.setChecked(value)

    # Save to QSettings on change
    if settings_group:
        def save_value(checked: bool):
            settings = QSettings("Lyjia", "Audio Metadata Tool")
            settings.beginGroup(settings_group)
            settings.setValue(option.name, checked)
            settings.endGroup()

        checkbox.stateChanged.connect(lambda state: save_value(state == Qt.CheckState.Checked))

    return checkbox


def _build_combobox(option: AnalyzerOption,
                   value: Any,
                   settings_group: Optional[str]) -> QWidget:
    """Build a QComboBox widget with optional label."""
    container = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    # Add label
    label = QLabel(option.help + ":")
    layout.addWidget(label)

    # Create combo box
    combo = QComboBox()
    combo.setObjectName(option.name)

    # Add items (handle both simple values and (value, label) tuples)
    for choice in option.choices:
        if isinstance(choice, tuple):
            # (value, label) tuple
            combo.addItem(choice[1], choice[0])
        else:
            # Simple value
            combo.addItem(str(choice), choice)

    # Set current value
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            break

    layout.addWidget(combo)

    # Save to QSettings on change
    if settings_group:
        def save_value(index: int):
            settings = QSettings("Lyjia", "Audio Metadata Tool")
            settings.beginGroup(settings_group)
            settings.setValue(option.name, combo.itemData(index))
            settings.endGroup()

        combo.currentIndexChanged.connect(save_value)

    container.setLayout(layout)
    return container


def _build_spinbox(option: AnalyzerOption,
                  value: Union[int, float],
                  settings_group: Optional[str],
                  is_float: bool) -> QWidget:
    """Build a QSpinBox or QDoubleSpinBox widget."""
    container = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    # Add label
    label = QLabel(option.help + ":")
    layout.addWidget(label)

    # Create spin box
    if is_float:
        spinbox = QDoubleSpinBox()
        spinbox.setDecimals(2)
    else:
        spinbox = QSpinBox()

    spinbox.setObjectName(option.name)

    # Set range
    if option.min is not None:
        spinbox.setMinimum(option.min)
    if option.max is not None:
        spinbox.setMaximum(option.max)

    # Set step
    if option.interval is not None:
        spinbox.setSingleStep(option.interval)

    # Set suffix
    if option.suffix:
        spinbox.setSuffix(option.suffix)

    # Set value
    spinbox.setValue(value)

    layout.addWidget(spinbox)

    # Save to QSettings on change
    if settings_group:
        def save_value(new_value: Union[int, float]):
            settings = QSettings("Lyjia", "Audio Metadata Tool")
            settings.beginGroup(settings_group)
            settings.setValue(option.name, new_value)
            settings.endGroup()

        spinbox.valueChanged.connect(save_value)

    container.setLayout(layout)
    return container


def _build_slider_spinbox(option: AnalyzerOption,
                         value: Union[int, float],
                         settings_group: Optional[str]) -> QWidget:
    """Build a QSlider + QSpinBox/QDoubleSpinBox combo widget."""
    container = QWidget()
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)

    # Add label
    label = QLabel(option.help + ":")
    main_layout.addWidget(label)

    # Horizontal layout for slider and spinbox
    h_layout = QHBoxLayout()

    # Create slider
    slider = QSlider(Qt.Orientation.Horizontal)
    # Slider works with integers, so scale if needed
    is_float = option.type == 'float'
    scale_factor = 100 if is_float else 1

    slider_min = int(option.min * scale_factor) if option.min is not None else 0
    slider_max = int(option.max * scale_factor) if option.max is not None else 100
    slider_step = int(option.interval * scale_factor) if option.interval is not None else 1

    slider.setMinimum(slider_min)
    slider.setMaximum(slider_max)
    slider.setSingleStep(slider_step)
    slider.setTickInterval(slider_step)
    slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    slider.setValue(int(value * scale_factor))

    # Note: We don't set objectName on slider, only on spinbox
    # This is because _extract_settings_from_widget() only reads from spinbox

    h_layout.addWidget(slider)

    # Create spinbox
    if is_float:
        spinbox = QDoubleSpinBox()
        spinbox.setDecimals(2)
    else:
        spinbox = QSpinBox()

    spinbox.setObjectName(option.name)

    if option.min is not None:
        spinbox.setMinimum(option.min)
    if option.max is not None:
        spinbox.setMaximum(option.max)
    if option.interval is not None:
        spinbox.setSingleStep(option.interval)
    if option.suffix:
        spinbox.setSuffix(option.suffix)

    spinbox.setValue(value)
    spinbox.setMaximumWidth(80)

    h_layout.addWidget(spinbox)

    # Connect slider and spinbox
    def slider_to_spinbox(slider_value: int):
        actual_value = slider_value / scale_factor if is_float else slider_value
        spinbox.setValue(actual_value)

    def spinbox_to_slider(spinbox_value: Union[int, float]):
        slider_value = int(spinbox_value * scale_factor) if is_float else int(spinbox_value)
        slider.setValue(slider_value)

    slider.valueChanged.connect(slider_to_spinbox)
    spinbox.valueChanged.connect(spinbox_to_slider)

    # Save to QSettings on change
    if settings_group:
        def save_value(new_value: Union[int, float]):
            settings = QSettings("Lyjia", "Audio Metadata Tool")
            settings.beginGroup(settings_group)
            settings.setValue(option.name, new_value)
            settings.endGroup()

        spinbox.valueChanged.connect(save_value)

    main_layout.addLayout(h_layout)

    container.setLayout(main_layout)
    return container


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

    parser.add_argument(arg_name, **kwargs)


def get_common_analyzer_options() -> List[AnalyzerOption]:
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
