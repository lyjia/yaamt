"""
Analyzer Setup Dialog.

This dialog allows users to select an analyzer from a category and configure
analyzer-specific options before running the analysis.
"""

from typing import List, Type, Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QCheckBox, QWidget, QSpinBox
)
from PySide6.QtCore import Qt

from providers.analysis.base import AnalyzerBase
from providers import get_analyzers_by_category, AnalyzerCategory
from models.settings import settings
from models.media_file import MediaFile
from util.logging import log


class AnalyzerSetupDialog(QDialog):
    """
    Dialog for selecting and configuring an analyzer before execution.

    The dialog displays:
    - List of available analyzers for the selected category
    - Analyzer-specific settings widget (if provided by analyzer)
    - Common options (e.g., overwrite existing data)
    - File count to be analyzed
    """

    def __init__(self, category: AnalyzerCategory, media_files: List[MediaFile], parent=None):
        """
        Initialize the analyzer setup dialog.

        Args:
            category: The analyzer category (e.g., 'bpm', 'key', 'gain')
            media_files: List of MediaFile instances to analyze
            parent: Parent widget
        """
        super().__init__(parent)
        self.category = category
        self.media_files = media_files
        self.selected_analyzer: Optional[Type[AnalyzerBase]] = None
        self.analyzer_options: Dict[str, Any] = {}

        self.setWindowTitle(f"Configure {category.value} Analysis")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._load_preferences()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()

        # Analyzer selection
        analyzer_group = QGroupBox("Analyzer Selection")
        analyzer_layout = QVBoxLayout()

        # Combo box for analyzer selection
        self.analyzer_combo = QComboBox()
        analyzers = get_analyzers_by_category(self.category)

        if not analyzers:
            log.warning(f"No analyzers found for category: {self.category}")
            # Show error and close
            self.analyzer_combo.addItem("No analyzers available")
            self.analyzer_combo.setEnabled(False)
        else:
            for analyzer_class in analyzers:
                self.analyzer_combo.addItem(
                    analyzer_class.name,
                    analyzer_class  # Store class as user data
                )

        self.analyzer_combo.currentIndexChanged.connect(self._on_analyzer_changed)
        analyzer_layout.addWidget(QLabel("Analyzer:"))
        analyzer_layout.addWidget(self.analyzer_combo)

        # Description label
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        analyzer_layout.addWidget(self.description_label)

        analyzer_group.setLayout(analyzer_layout)
        layout.addWidget(analyzer_group)

        # Common options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        self.overwrite_checkbox = QCheckBox("Overwrite Existing Data")
        self.overwrite_checkbox.setToolTip(
            "If checked, analysis will overwrite existing metadata values. "
            "If unchecked, files with existing values will be skipped."
        )
        options_layout.addWidget(self.overwrite_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Analyzer-specific settings container
        self.settings_group = QGroupBox("Analyzer Settings")
        self.settings_layout = QVBoxLayout()
        self.settings_group.setLayout(self.settings_layout)
        self.settings_group.setVisible(False)  # Hidden until analyzer with settings is selected
        layout.addWidget(self.settings_group)

        # File count
        file_count_label = QLabel(f"Files to analyze: {len(self.media_files)}")
        file_count_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(file_count_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.run_button = QPushButton("Run Analysis")
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.run_button.setEnabled(len(analyzers) > 0)
        button_layout.addWidget(self.run_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Trigger initial analyzer selection
        if len(analyzers) > 0:
            self._on_analyzer_changed(0)

    def _on_analyzer_changed(self, index: int):
        """
        Handle analyzer selection change.

        Args:
            index: Index of selected analyzer in combo box
        """
        analyzer_class = self.analyzer_combo.itemData(index)
        if not analyzer_class:
            return

        self.selected_analyzer = analyzer_class

        # Update description
        self.description_label.setText(analyzer_class.description or "No description available.")

        # Clear previous settings widget
        while self.settings_layout.count():
            child = self.settings_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add analyzer-specific settings widget if available
        settings_widget = analyzer_class.get_settings_widget()
        if settings_widget:
            self.settings_layout.addWidget(settings_widget)
            self.settings_group.setVisible(True)
        else:
            self.settings_group.setVisible(False)

    def _on_run_clicked(self):
        """Handle Run Analysis button click."""
        if not self.selected_analyzer:
            log.error("No analyzer selected")
            return

        # Build options dictionary
        self.analyzer_options = {
            'overwrite_existing': self.overwrite_checkbox.isChecked()
        }

        # Extract analyzer-specific options from settings widget
        if self.settings_group.isVisible():
            settings_widget = self.settings_layout.itemAt(0).widget()
            if settings_widget:
                self._extract_settings_from_widget(settings_widget)

        # Save preferences
        self._save_preferences()

        # Accept dialog
        self.accept()

    def _extract_settings_from_widget(self, widget: QWidget):
        """
        Extract settings from the analyzer's settings widget.

        This method looks for QSpinBox, QCheckBox, and other common widgets
        with objectName set, and adds their values to analyzer_options.

        Args:
            widget: The settings widget to extract from
        """
        # Find all QSpinBox widgets
        for spin_box in widget.findChildren(QSpinBox):
            name = spin_box.objectName()
            if name:
                self.analyzer_options[name] = spin_box.value()

        # Find all QCheckBox widgets
        for checkbox in widget.findChildren(QCheckBox):
            name = checkbox.objectName()
            if name:
                self.analyzer_options[name] = checkbox.isChecked()

        # Can be extended for other widget types as needed

    def _load_preferences(self):
        """Load user preferences from QSettings."""
        settings.beginGroup("analyzers")

        # Load preferred analyzer for this category
        preferred_analyzer = settings.value(f"preferred_{self.category}")
        if preferred_analyzer:
            # Find and select the preferred analyzer
            for i in range(self.analyzer_combo.count()):
                analyzer_class = self.analyzer_combo.itemData(i)
                if analyzer_class and analyzer_class.__name__ == preferred_analyzer:
                    self.analyzer_combo.setCurrentIndex(i)
                    break

        # Load overwrite setting (default: False)
        overwrite = settings.value("overwrite_existing", False, type=bool)
        self.overwrite_checkbox.setChecked(overwrite)

        settings.endGroup()

    def _save_preferences(self):
        """Save user preferences to QSettings."""
        settings.beginGroup("analyzers")

        # Save preferred analyzer for this category
        if self.selected_analyzer:
            settings.setValue(
                f"preferred_{self.category}",
                self.selected_analyzer.__name__
            )

        # Save overwrite setting
        settings.setValue(
            "overwrite_existing",
            self.overwrite_checkbox.isChecked()
        )

        settings.endGroup()

    def get_analyzer_class(self) -> Optional[Type[AnalyzerBase]]:
        """
        Get the selected analyzer class.

        Returns:
            The selected analyzer class, or None if dialog was cancelled
        """
        return self.selected_analyzer

    def get_options(self) -> Dict[str, Any]:
        """
        Get the configured options.

        Returns:
            Dictionary of analyzer options
        """
        return self.analyzer_options
