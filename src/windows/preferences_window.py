"""Main preferences window."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QStackedWidget, QMessageBox, QSplitter, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize

from models.settings import get_qsettings
from PySide6.QtGui import QKeySequence, QShortcut

from util.const import (
    SETTINGS_GROUP_GENERAL, SETTINGS_GROUP_ANALYZERS_PREFERRED,
    SETTINGS_GROUP_ANALYZERS_CATEGORY_OPTIONS, SETTINGS_GROUP_RESOURCES,
    SETTINGS_GROUP_INTEGRATIONS, SETTINGS_GROUP_RENAME,
)
from windows.preferences.base import PreferencePaneBase
from windows.preferences.general_pane import GeneralPane
from windows.preferences.integrations_pane import IntegrationsPane
from windows.preferences.metadata_pane import MetadataPane
from windows.preferences.rename_presets_pane import RenamePresetsPane
from windows.preferences.resources_pane import ResourcesPane


class PreferencesWindow(QDialog):
    """
    Main preferences window with category sidebar and preference panes.

    This window provides a centralized interface for configuring application
    settings. It features:
    - Category sidebar for navigation
    - Stacked widget area for preference panes
    - Save, Cancel, and Reset to Default buttons
    - Real-time validation with visual feedback
    """

    def __init__(self, parent=None):
        """Initialize the PreferencesWindow."""
        super().__init__(parent)
        self.settings = get_qsettings()
        self.panes: list[PreferencePaneBase] = []

        self._setup_window()
        self._setup_ui()
        self._register_panes()
        self._setup_shortcuts()
        self._load_all_panes()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(800, 600)
        self.setMinimumSize(600, 400)

        # Center on screen
        if self.parent():
            parent_geo = self.parent().geometry()
            self.move(
                parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                parent_geo.y() + (parent_geo.height() - self.height()) // 2
            )
        else:
            # Center on primary screen
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                self.move(
                    screen_geo.x() + (screen_geo.width() - self.width()) // 2,
                    screen_geo.y() + (screen_geo.height() - self.height()) // 2
                )

    def _setup_ui(self) -> None:
        """Create the UI layout and widgets."""
        layout = QVBoxLayout(self)

        # Create splitter for sidebar and pane area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Category sidebar
        self.category_list = QListWidget()
        self.category_list.setFixedWidth(200)
        self.category_list.setIconSize(QSize(24, 24))
        splitter.addWidget(self.category_list)

        # Preference pane area
        self.pane_stack = QStackedWidget()
        splitter.addWidget(self.pane_stack)

        layout.addWidget(splitter)

        # Button row
        button_layout = QHBoxLayout()

        self.reset_button = QPushButton("Reset to Default...")
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)

        # Connect signals
        self.category_list.currentRowChanged.connect(self.pane_stack.setCurrentIndex)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._on_save_clicked)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        # Escape for Cancel
        esc_shortcut = QShortcut(Qt.Key.Key_Escape, self)
        esc_shortcut.activated.connect(self.reject)

        # Ctrl+S / Cmd+S for Save
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._on_save_clicked)

    def _register_panes(self) -> None:
        """Register all preference panes."""
        # Create and register panes
        general_pane = GeneralPane()
        metadata_pane = MetadataPane()
        resources_pane = ResourcesPane()
        rename_presets_pane = RenamePresetsPane()
        integrations_pane = IntegrationsPane()

        self.panes = [
            general_pane,
            metadata_pane,
            resources_pane,
            rename_presets_pane,
            integrations_pane,
        ]

        # Add to UI
        for pane in self.panes:
            item = QListWidgetItem(pane.get_icon(), pane.get_name())
            self.category_list.addItem(item)
            self.pane_stack.addWidget(pane)
            # Recompute Save's enabled state whenever any pane reports a
            # validity change (e.g. an API key field finishes verifying).
            pane.validity_changed.connect(self._refresh_save_enabled)

        # Select first category
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

        self._refresh_save_enabled()

    def _refresh_save_enabled(self) -> None:
        """Disable Save when any pane reports it isn't ready to save."""
        ready = all(pane.is_ready_to_save() for pane in self.panes)
        self.save_button.setEnabled(ready)

    def _load_all_panes(self) -> None:
        """Load settings for all panes."""
        for pane in self.panes:
            pane.load_from_settings()

    def select_pane(self, name: str) -> bool:
        """
        Select the preference pane whose ``get_name()`` matches ``name``.

        Used by other windows (e.g. the analyzer setup dialog) that want to
        deep-link into a specific preference pane.

        Args:
            name: The pane's display name (case-sensitive).

        Returns:
            True if a pane with that name was found and selected, False otherwise.
        """
        for i, pane in enumerate(self.panes):
            if pane.get_name() == name:
                self.category_list.setCurrentRow(i)
                return True
        return False

    def _on_save_clicked(self) -> None:
        """Handle Save button click."""
        # Validate all panes
        for pane in self.panes:
            is_valid, error_msg = pane.validate()
            if not is_valid:
                QMessageBox.warning(
                    self,
                    "Cannot Save Preferences",
                    f"Cannot save preferences:\n\n{error_msg}"
                )
                return

        # All valid - save all panes
        for pane in self.panes:
            pane.save_to_settings()

        # Close dialog
        self.accept()

    def _on_reset_clicked(self) -> None:
        """Handle Reset to Default button click."""
        result = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Reset all preferences to default values? This cannot be undone.",
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Reset:
            # Clear all preference settings
            self._clear_all_settings()

            # Load defaults into all panes
            for pane in self.panes:
                pane.load_defaults()

    def _clear_all_settings(self) -> None:
        """Clear all preference-related settings from QSettings."""
        # Clear General settings
        self.settings.remove(SETTINGS_GROUP_GENERAL)

        # Clear Analyzer settings
        self.settings.remove(SETTINGS_GROUP_ANALYZERS_PREFERRED)
        self.settings.remove(SETTINGS_GROUP_ANALYZERS_CATEGORY_OPTIONS)

        # Clear Resources settings
        self.settings.remove(SETTINGS_GROUP_RESOURCES)

        # Clear Rename presets
        self.settings.remove(SETTINGS_GROUP_RENAME)

        # Clear Integrations settings
        self.settings.remove(SETTINGS_GROUP_INTEGRATIONS)
