"""
GUI widget builders for analyzer options.

This module owns the Qt-specific side of the analyzer option system:
given an :class:`~util.analyzer_options.AnalyzerOption` it produces the
appropriate QWidget (checkbox, combobox, spinbox, slider+spinbox, or
file/directory picker) and wires it up to QSettings for persistence.

The non-GUI half of the system -- the ``AnalyzerOption`` dataclass,
``add_option_to_argparse``, and category-option helpers -- lives in
``util.analyzer_options`` so providers and the CLI can depend on it
without pulling in PySide6.
"""

from typing import Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QSlider,
    QPushButton, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt

from models.settings import get_qsettings
from util.analyzer_options import AnalyzerOption


# File-dialog "all files" filter, kept as a constant to avoid repetition.
_ALL_FILES_FILTER = "All Files (*.*)"

# Scaling factor used when mapping float option ranges onto QSlider's
# integer domain: multiply/divide by this to convert between the user's
# float value and the slider's int position.
_FLOAT_SLIDER_SCALE_FACTOR = 100

# Visual width cap (pixels) for the QSpinBox paired with a QSlider.
_SLIDER_SPINBOX_MAX_WIDTH = 80

# Visual width cap (pixels) for file / directory "Browse..." buttons.
_BROWSE_BUTTON_MAX_WIDTH = 100


def build_widget_from_option(option: AnalyzerOption,
                             settings_group: str | None = None) -> QWidget:
    """
    Auto-generate an appropriate Qt widget from option metadata.

    Widget Selection Logic:
    - type='slider' → QSlider + QSpinBox/QDoubleSpinBox
    - type='int'/'float' with min/max/interval → QSlider + SpinBox
    - type='int'/'float' without interval → SpinBox only
    - type='bool' → QCheckBox
    - type='choice' → QComboBox
    - type='file' / 'directory' → QLineEdit + Browse button

    The generated widget has its objectName set to ``option.name`` so
    ``AnalyzerSetupDialog._extract_settings_from_widget()`` can find it.

    QSettings Integration:
    If ``settings_group`` is provided, the widget loads its initial value
    from QSettings and saves changes back automatically.

    Args:
        option: The AnalyzerOption to create a widget for.
        settings_group: Optional QSettings group path
            (e.g. ``"analyzers/AubioBPMAnalyzer"``).

    Returns:
        QWidget configured from the option metadata.
    """
    saved_value = _load_saved_value(option, settings_group)

    if option.type == 'bool':
        return _build_checkbox(option, saved_value, settings_group)

    if option.type == 'choice':
        return _build_combobox(option, saved_value, settings_group)

    if option.type == 'slider' or (
        option.type in ('int', 'float')
        and option.min is not None
        and option.max is not None
        and option.interval is not None
    ):
        return _build_slider_spinbox(option, saved_value, settings_group)

    if option.type == 'int':
        return _build_spinbox(option, saved_value, settings_group, is_float=False)

    if option.type == 'float':
        return _build_spinbox(option, saved_value, settings_group, is_float=True)

    if option.type == 'file':
        return _build_file_input(option, saved_value, settings_group)

    if option.type == 'directory':
        return _build_directory_input(option, saved_value, settings_group)

    raise ValueError(f"Cannot build widget for option type: {option.type}")


# -----------------------------------------------------------------------------
# Shared QSettings helpers
# -----------------------------------------------------------------------------

def _load_saved_value(option: AnalyzerOption,
                      settings_group: str | None) -> Any:
    """Read this option's saved value from QSettings, or return its default."""
    if not settings_group:
        return option.default

    settings = get_qsettings()
    settings.beginGroup(settings_group)
    try:
        if option.type == 'bool':
            return settings.value(option.name, option.default, type=bool)
        if option.type in ('int', 'slider'):
            return settings.value(option.name, option.default, type=int)
        if option.type == 'float':
            return settings.value(option.name, option.default, type=float)
        # choice / file / directory fall through here
        return settings.value(option.name, option.default)
    finally:
        settings.endGroup()


def _make_settings_saver(option: AnalyzerOption, settings_group: str):
    """
    Return a function that writes ``option.name`` to QSettings under
    ``settings_group``. Used as a slot for widget "value changed" signals.
    """
    def save_value(new_value: Any) -> None:
        settings = get_qsettings()
        settings.beginGroup(settings_group)
        try:
            settings.setValue(option.name, new_value)
        finally:
            settings.endGroup()
    return save_value


# -----------------------------------------------------------------------------
# Widget builders
# -----------------------------------------------------------------------------

def _build_checkbox(option: AnalyzerOption,
                    value: bool,
                    settings_group: str | None) -> QCheckBox:
    """Build a QCheckBox widget."""
    checkbox = QCheckBox(option.help)
    checkbox.setObjectName(option.name)
    checkbox.setChecked(value)
    if option.tooltip:
        checkbox.setToolTip(option.tooltip)

    if settings_group:
        save_value = _make_settings_saver(option, settings_group)
        checkbox.stateChanged.connect(
            lambda state: save_value(state == Qt.CheckState.Checked)
        )

    return checkbox


def _build_combobox(option: AnalyzerOption,
                    value: Any,
                    settings_group: str | None) -> QWidget:
    """Build a QComboBox widget with an associated label."""
    container = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(option.help + ":")
    layout.addWidget(label)

    combo = QComboBox()
    combo.setObjectName(option.name)

    for choice in option.choices:
        if isinstance(choice, tuple):
            combo.addItem(choice[1], choice[0])  # (value, label)
        else:
            combo.addItem(str(choice), choice)

    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            break

    layout.addWidget(combo)

    if settings_group:
        save_value = _make_settings_saver(option, settings_group)
        combo.currentIndexChanged.connect(
            lambda index: save_value(combo.itemData(index))
        )

    container.setLayout(layout)
    return container


def _build_spinbox(option: AnalyzerOption,
                   value: int | float,
                   settings_group: str | None,
                   is_float: bool) -> QWidget:
    """Build a labelled QSpinBox or QDoubleSpinBox."""
    container = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(option.help + ":")
    layout.addWidget(label)

    spinbox = QDoubleSpinBox() if is_float else QSpinBox()
    if is_float:
        spinbox.setDecimals(2)
    spinbox.setObjectName(option.name)
    if option.tooltip:
        spinbox.setToolTip(option.tooltip)

    if option.min is not None:
        spinbox.setMinimum(option.min)
    if option.max is not None:
        spinbox.setMaximum(option.max)
    if option.interval is not None:
        spinbox.setSingleStep(option.interval)
    if option.suffix:
        spinbox.setSuffix(option.suffix)

    spinbox.setValue(value)
    layout.addWidget(spinbox)

    if settings_group:
        spinbox.valueChanged.connect(_make_settings_saver(option, settings_group))

    container.setLayout(layout)
    return container


def _build_slider_spinbox(option: AnalyzerOption,
                          value: int | float,
                          settings_group: str | None) -> QWidget:
    """Build a QSlider + QSpinBox/QDoubleSpinBox combo widget."""
    container = QWidget()
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(option.help + ":")
    main_layout.addWidget(label)

    h_layout = QHBoxLayout()

    # QSlider is integer-only; for float options we scale the range up
    # so the slider sees integers and the spinbox shows the real value.
    is_float = option.type == 'float'
    scale_factor = _FLOAT_SLIDER_SCALE_FACTOR if is_float else 1

    slider = QSlider(Qt.Orientation.Horizontal)
    slider_min = int(option.min * scale_factor) if option.min is not None else 0
    slider_max = int(option.max * scale_factor) if option.max is not None else 100
    slider_step = int(option.interval * scale_factor) if option.interval is not None else 1

    slider.setMinimum(slider_min)
    slider.setMaximum(slider_max)
    slider.setSingleStep(slider_step)
    slider.setTickInterval(slider_step)
    slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    slider.setValue(int(value * scale_factor))
    if option.tooltip:
        slider.setToolTip(option.tooltip)
    # Only the spinbox carries the option objectName: the settings extractor
    # reads values from the spinbox, not the slider.
    h_layout.addWidget(slider)

    spinbox = QDoubleSpinBox() if is_float else QSpinBox()
    if is_float:
        spinbox.setDecimals(2)
    spinbox.setObjectName(option.name)
    if option.tooltip:
        spinbox.setToolTip(option.tooltip)

    if option.min is not None:
        spinbox.setMinimum(option.min)
    if option.max is not None:
        spinbox.setMaximum(option.max)
    if option.interval is not None:
        spinbox.setSingleStep(option.interval)
    if option.suffix:
        spinbox.setSuffix(option.suffix)

    spinbox.setValue(value)
    spinbox.setMaximumWidth(_SLIDER_SPINBOX_MAX_WIDTH)
    h_layout.addWidget(spinbox)

    def slider_to_spinbox(slider_value: int) -> None:
        spinbox.setValue(slider_value / scale_factor if is_float else slider_value)

    def spinbox_to_slider(spinbox_value: int | float) -> None:
        slider.setValue(int(spinbox_value * scale_factor) if is_float else int(spinbox_value))

    slider.valueChanged.connect(slider_to_spinbox)
    spinbox.valueChanged.connect(spinbox_to_slider)

    if settings_group:
        spinbox.valueChanged.connect(_make_settings_saver(option, settings_group))

    main_layout.addLayout(h_layout)
    container.setLayout(main_layout)
    return container


def _build_path_input(option: AnalyzerOption,
                      value: str,
                      settings_group: str | None,
                      placeholder: str,
                      open_dialog) -> QWidget:
    """
    Shared implementation for file and directory picker widgets.

    Args:
        option: The AnalyzerOption being rendered.
        value: Current saved path value.
        settings_group: Optional QSettings group for persistence.
        placeholder: Placeholder text shown when no path is selected.
        open_dialog: Callable ``(parent_widget, current_text) -> str`` that
            opens the appropriate dialog and returns the selected path
            (or an empty string if cancelled).
    """
    container = QWidget()
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)

    label = QLabel(option.help + ":")
    main_layout.addWidget(label)

    h_layout = QHBoxLayout()

    line_edit = QLineEdit()
    line_edit.setObjectName(option.name)
    line_edit.setText(str(value) if value else '')
    line_edit.setPlaceholderText(placeholder if not value else "")
    h_layout.addWidget(line_edit)

    browse_button = QPushButton("Browse...")
    browse_button.setMaximumWidth(_BROWSE_BUTTON_MAX_WIDTH)

    def on_browse() -> None:
        selected = open_dialog(container, line_edit.text())
        if selected:
            line_edit.setText(selected)

    browse_button.clicked.connect(on_browse)
    h_layout.addWidget(browse_button)

    main_layout.addLayout(h_layout)

    if settings_group:
        line_edit.textChanged.connect(_make_settings_saver(option, settings_group))

    container.setLayout(main_layout)
    return container


def _build_file_input(option: AnalyzerOption,
                      value: str,
                      settings_group: str | None) -> QWidget:
    """Build a file-picker widget (line edit + Browse button)."""

    def open_file_dialog(parent: QWidget, current_text: str) -> str:
        filters = _file_filters_from_choices(option.choices)
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            f"Select {option.help}",
            current_text or "",
            filters,
        )
        return file_path

    return _build_path_input(
        option, value, settings_group,
        placeholder="Select a file...",
        open_dialog=open_file_dialog,
    )


def _build_directory_input(option: AnalyzerOption,
                           value: str,
                           settings_group: str | None) -> QWidget:
    """Build a directory-picker widget (line edit + Browse button)."""

    def open_directory_dialog(parent: QWidget, current_text: str) -> str:
        return QFileDialog.getExistingDirectory(
            parent,
            f"Select {option.help}",
            current_text or "",
        )

    return _build_path_input(
        option, value, settings_group,
        placeholder="Select a directory...",
        open_dialog=open_directory_dialog,
    )


def _file_filters_from_choices(choices) -> str:
    """
    Build a QFileDialog filter string from ``option.choices``.

    ``choices`` may be either a list of extensions (``[".pth", ".pt"]``) or
    a list of pre-formatted filter descriptions
    (``["PyTorch Models (*.pth *.pt)", "ONNX Models (*.onnx)"]``).
    Anything else falls back to an "all files" filter.
    """
    if not choices:
        return _ALL_FILES_FILTER

    first = choices[0]
    if isinstance(first, str) and first.startswith('.'):
        extensions = ' '.join(f'*{ext}' for ext in choices)
        return f"Model Files ({extensions});;{_ALL_FILES_FILTER}"
    if isinstance(first, str) and '(' in first:
        return ';;'.join(choices) + f";;{_ALL_FILES_FILTER}"
    return _ALL_FILES_FILTER
