"""Metadata preferences pane."""
from typing import Tuple, Dict
from PySide6.QtWidgets import (
    QVBoxLayout, QGroupBox, QLabel, QComboBox, QSpinBox,
    QHBoxLayout, QLineEdit, QFormLayout
)
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtCore import Signal

from models.settings import get_qsettings
from windows.preferences.base import PreferencePaneBase
from providers import get_analyzers_by_category, get_all_categories, ProviderType
from providers.analysis import AnalyzerCategory
from util.diatonic_key import get_notation_format_display_list


class ValidatedLineEdit(QLineEdit):
    """
    QLineEdit subclass with validation error display.

    Provides visual feedback for invalid input with red background
    and error message display.
    """

    def __init__(self, parent=None):
        """Initialize the ValidatedLineEdit."""
        super().__init__(parent)
        self._is_valid = True
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 10px;")
        self.error_label.hide()
        self._default_palette = self.palette()

    def set_error(self, msg: str) -> None:
        """
        Set invalid state with error message.

        Args:
            msg: Error message to display
        """
        self._is_valid = False
        # Set red background
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 200, 200))
        self.setPalette(palette)
        # Show error message
        self.error_label.setText(msg)
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear error state and restore normal appearance."""
        self._is_valid = True
        self.setPalette(self._default_palette)
        self.error_label.hide()

    def is_valid(self) -> bool:
        """
        Check if the current value is valid.

        Returns:
            True if valid, False otherwise
        """
        return self._is_valid


class MetadataPane(PreferencePaneBase):
    """Preference pane for metadata and analyzer settings."""

    # BPM range presets: (display_name, (min, max))
    BPM_PRESETS = [
        ("Hip Hop / Trap (55-118)", (55, 118)),
        ("House / Techno (98-138)", (98, 138)),
        ("Trance / Dance (117-151)", (117, 151)),
        ("Drum & Bass (149-181)", (149, 181)),
        ("Hardstyle / Hardcore (95-198)", (95, 198)),
        ("Custom", (None, None)),
    ]

    # Key notation formats are now retrieved from util.diatonic_key to maintain consistency

    def __init__(self, parent=None):
        """Initialize the MetadataPane."""
        super().__init__(parent)
        self.settings = get_qsettings()
        self.analyzer_combos: Dict[AnalyzerCategory, QComboBox] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the UI layout and widgets."""
        layout = QVBoxLayout(self)

        # Preferred Analyzers group
        analyzers_group = QGroupBox("Preferred Analyzers")
        analyzers_layout = QFormLayout()

        categories = get_all_categories(ProviderType.ANALYZER)
        for category in categories:
            combo = QComboBox()
            analyzers = get_analyzers_by_category(category)
            for analyzer in analyzers:
                combo.addItem(analyzer.name, analyzer.__name__)
            self.analyzer_combos[category] = combo
            analyzers_layout.addRow(f"{category.value}:", combo)

        analyzers_group.setLayout(analyzers_layout)

        # BPM Detection group
        bpm_group = QGroupBox("BPM Detection")
        bpm_layout = QVBoxLayout()

        # Detection range preset
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Detection range:"))
        self.bpm_preset_combo = QComboBox()
        for preset_name, _ in self.BPM_PRESETS:
            self.bpm_preset_combo.addItem(preset_name)
        preset_row.addWidget(self.bpm_preset_combo)
        preset_row.addStretch()
        bpm_layout.addLayout(preset_row)

        # Custom range inputs
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Custom range:"))
        self.bpm_min_edit = ValidatedLineEdit()
        self.bpm_min_edit.setFixedWidth(60)
        self.bpm_min_edit.setPlaceholderText("Min")
        range_row.addWidget(self.bpm_min_edit)
        range_row.addWidget(QLabel("to"))
        self.bpm_max_edit = ValidatedLineEdit()
        self.bpm_max_edit.setFixedWidth(60)
        self.bpm_max_edit.setPlaceholderText("Max")
        range_row.addWidget(self.bpm_max_edit)
        range_row.addWidget(QLabel("BPM"))
        range_row.addStretch()
        bpm_layout.addLayout(range_row)

        # Error labels for range inputs
        error_row = QHBoxLayout()
        error_row.addSpacing(120)  # Left spacing to align with inputs
        error_row.addWidget(self.bpm_min_edit.error_label)
        error_row.addWidget(self.bpm_max_edit.error_label)
        error_row.addStretch()
        bpm_layout.addLayout(error_row)

        # Decimal places
        decimal_row = QHBoxLayout()
        decimal_row.addWidget(QLabel("Decimal places:"))
        self.bpm_decimal_spin = QSpinBox()
        self.bpm_decimal_spin.setRange(0, 3)
        self.bpm_decimal_spin.setValue(0)
        self.bpm_decimal_spin.setFixedWidth(60)
        decimal_row.addWidget(self.bpm_decimal_spin)
        decimal_row.addStretch()
        bpm_layout.addLayout(decimal_row)

        bpm_group.setLayout(bpm_layout)

        # Musical Key group
        key_group = QGroupBox("Musical Key")
        key_layout = QVBoxLayout()
        key_layout.addWidget(QLabel("Notation format:"))
        self.key_format_combo = QComboBox()
        for format_name, format_id in get_notation_format_display_list():
            self.key_format_combo.addItem(format_name, format_id)
        key_layout.addWidget(self.key_format_combo)
        key_group.setLayout(key_layout)

        # Add all groups to main layout
        layout.addWidget(analyzers_group)
        layout.addWidget(bpm_group)
        layout.addWidget(key_group)
        layout.addStretch()

        # Connect signals
        self.bpm_preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.bpm_min_edit.textChanged.connect(self._on_range_changed)
        self.bpm_max_edit.textChanged.connect(self._on_range_changed)

    def _on_preset_changed(self, index: int) -> None:
        """Handle BPM preset selection change."""
        if index < 0:
            return

        preset_name, preset_range = self.BPM_PRESETS[index]
        if preset_range[0] is not None:
            # Block signals to avoid recursion
            self.bpm_min_edit.blockSignals(True)
            self.bpm_max_edit.blockSignals(True)
            self.bpm_min_edit.setText(str(preset_range[0]))
            self.bpm_max_edit.setText(str(preset_range[1]))
            self.bpm_min_edit.blockSignals(False)
            self.bpm_max_edit.blockSignals(False)

    def _on_range_changed(self) -> None:
        """Handle manual BPM range input changes."""
        # Validate the inputs
        self._validate_bpm_range()

        # Check if the current values match any preset
        try:
            min_val = int(self.bpm_min_edit.text())
            max_val = int(self.bpm_max_edit.text())

            # Find matching preset
            matching_index = -1
            for i, (_, preset_range) in enumerate(self.BPM_PRESETS):
                if preset_range[0] == min_val and preset_range[1] == max_val:
                    matching_index = i
                    break

            # Block signals and update combo
            self.bpm_preset_combo.blockSignals(True)
            if matching_index >= 0:
                self.bpm_preset_combo.setCurrentIndex(matching_index)
            else:
                # Set to "Custom"
                self.bpm_preset_combo.setCurrentIndex(len(self.BPM_PRESETS) - 1)
            self.bpm_preset_combo.blockSignals(False)
        except (ValueError, AttributeError):
            # Invalid input - set to Custom
            self.bpm_preset_combo.blockSignals(True)
            self.bpm_preset_combo.setCurrentIndex(len(self.BPM_PRESETS) - 1)
            self.bpm_preset_combo.blockSignals(False)

    def _validate_bpm_range(self) -> None:
        """Validate BPM range inputs and show visual feedback."""
        # Clear previous errors
        self.bpm_min_edit.clear_error()
        self.bpm_max_edit.clear_error()

        min_text = self.bpm_min_edit.text()
        max_text = self.bpm_max_edit.text()

        # Validate min
        try:
            min_val = int(min_text)
            if min_val < 1 or min_val > 999:
                self.bpm_min_edit.set_error("Must be 1-999")
        except ValueError:
            if min_text:  # Only show error if not empty
                self.bpm_min_edit.set_error("Must be a number")

        # Validate max
        try:
            max_val = int(max_text)
            if max_val < 1 or max_val > 999:
                self.bpm_max_edit.set_error("Must be 1-999")
        except ValueError:
            if max_text:  # Only show error if not empty
                self.bpm_max_edit.set_error("Must be a number")

        # Validate relationship
        try:
            min_val = int(min_text)
            max_val = int(max_text)
            if min_val >= max_val:
                self.bpm_min_edit.set_error("Min must be < Max")
                self.bpm_max_edit.set_error("Max must be > Min")
        except ValueError:
            pass  # Already handled above

    def get_name(self) -> str:
        """Return the display name for this preference category."""
        return "Metadata"

    def get_icon(self) -> QIcon:
        """Return the icon for the sidebar."""
        from PySide6.QtWidgets import QApplication, QStyle
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)

    def load_from_settings(self) -> None:
        """Read from QSettings and populate all widgets."""
        # Load preferred analyzers
        for category, combo in self.analyzer_combos.items():
            analyzer_name = self.settings.value(f"Analyzers/Preferred/{category.value.lower()}", "")
            if analyzer_name:
                index = combo.findData(analyzer_name)
                if index >= 0:
                    combo.setCurrentIndex(index)

        # Load BPM options
        bpm_min = self.settings.value("Analyzers/CategoryOptions/bpm/range_min", 80, type=int)
        bpm_max = self.settings.value("Analyzers/CategoryOptions/bpm/range_max", 200, type=int)
        bpm_decimals = self.settings.value("Analyzers/CategoryOptions/bpm/decimal_places", 0, type=int)

        self.bpm_min_edit.setText(str(bpm_min))
        self.bpm_max_edit.setText(str(bpm_max))
        self.bpm_decimal_spin.setValue(bpm_decimals)

        # Load key notation format
        key_format = self.settings.value("Analyzers/CategoryOptions/key/notation_format", "standard_abbrev")
        index = self.key_format_combo.findData(key_format)
        if index >= 0:
            self.key_format_combo.setCurrentIndex(index)

    def save_to_settings(self) -> None:
        """Write widget values to QSettings."""
        # Save preferred analyzers
        for category, combo in self.analyzer_combos.items():
            analyzer_name = combo.currentData()
            self.settings.setValue(f"Analyzers/Preferred/{category.value.lower()}", analyzer_name)

        # Save BPM options
        self.settings.setValue("Analyzers/CategoryOptions/bpm/range_min", int(self.bpm_min_edit.text()))
        self.settings.setValue("Analyzers/CategoryOptions/bpm/range_max", int(self.bpm_max_edit.text()))
        self.settings.setValue("Analyzers/CategoryOptions/bpm/decimal_places", self.bpm_decimal_spin.value())

        # Save key notation format
        self.settings.setValue("Analyzers/CategoryOptions/key/notation_format", self.key_format_combo.currentData())

    def validate(self) -> Tuple[bool, str]:
        """Validate all settings in this pane."""
        # Validate BPM range
        self._validate_bpm_range()

        if not self.bpm_min_edit.is_valid() or not self.bpm_max_edit.is_valid():
            return False, "BPM detection range is invalid. Please correct the highlighted errors."

        return True, ""

    def load_defaults(self) -> None:
        """Set all widgets to their default values."""
        # Set first analyzer for each category
        for combo in self.analyzer_combos.values():
            if combo.count() > 0:
                combo.setCurrentIndex(0)

        # Set default BPM values
        self.bpm_min_edit.setText("80")
        self.bpm_max_edit.setText("200")
        self.bpm_decimal_spin.setValue(0)

        # Set default key format
        self.key_format_combo.setCurrentIndex(0)
