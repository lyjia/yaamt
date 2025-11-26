"""General preferences pane."""
from typing import Tuple
from PySide6.QtWidgets import (
    QVBoxLayout, QGroupBox, QRadioButton, QLineEdit, QPushButton,
    QLabel, QComboBox, QHBoxLayout, QFileDialog, QStyleFactory
)
from PySide6.QtGui import QIcon

from models.settings import get_qsettings
from windows.preferences.base import PreferencePaneBase


class GeneralPane(PreferencePaneBase):
    """Preference pane for general application settings."""

    def __init__(self, parent=None):
        """Initialize the GeneralPane."""
        super().__init__(parent)
        self.settings = get_qsettings()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the UI layout and widgets."""
        layout = QVBoxLayout(self)

        # Startup Directory group
        startup_group = QGroupBox("Startup Directory")
        startup_layout = QVBoxLayout()

        self.last_dir_radio = QRadioButton("Remember last directory")
        self.preferred_dir_radio = QRadioButton("Always use this directory:")

        # Directory path row
        dir_row = QHBoxLayout()
        self.dir_path_edit = QLineEdit()
        self.dir_path_edit.setEnabled(False)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setEnabled(False)
        dir_row.addWidget(self.dir_path_edit)
        dir_row.addWidget(self.browse_button)

        startup_layout.addWidget(self.last_dir_radio)
        startup_layout.addWidget(self.preferred_dir_radio)
        startup_layout.addLayout(dir_row)
        startup_group.setLayout(startup_layout)

        # Playback group
        playback_group = QGroupBox("Playback")
        playback_layout = QVBoxLayout()
        playback_layout.addWidget(QLabel("Preferred audio device:"))
        self.audio_device_combo = QComboBox()
        playback_layout.addWidget(self.audio_device_combo)
        playback_group.setLayout(playback_layout)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout()
        appearance_layout.addWidget(QLabel("UI Skin:"))
        self.ui_skin_combo = QComboBox()
        appearance_layout.addWidget(self.ui_skin_combo)
        appearance_group.setLayout(appearance_layout)

        # Add all groups to main layout
        layout.addWidget(startup_group)
        layout.addWidget(playback_group)
        layout.addWidget(appearance_group)
        layout.addStretch()

        # Connect signals
        self.preferred_dir_radio.toggled.connect(self._on_preferred_dir_toggled)
        self.browse_button.clicked.connect(self._on_browse_clicked)

        # Populate combos
        self._populate_audio_devices()
        self._populate_ui_skins()

    def _on_preferred_dir_toggled(self, checked: bool) -> None:
        """Enable/disable the directory path controls based on radio selection."""
        self.dir_path_edit.setEnabled(checked)
        self.browse_button.setEnabled(checked)

    def _on_browse_clicked(self) -> None:
        """Open directory browser dialog."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Preferred Directory",
            self.dir_path_edit.text() or ""
        )
        if directory:
            self.dir_path_edit.setText(directory)

    def _populate_audio_devices(self) -> None:
        """Populate the audio device combo box."""
        self.audio_device_combo.addItem("System Default", "")
        # Add actual audio devices from audio subsystem
        from providers.audio import get_available_audio_devices
        for name, device_id in get_available_audio_devices():
            self.audio_device_combo.addItem(name, device_id)

    def _populate_ui_skins(self) -> None:
        """Populate the UI skin combo box."""
        self.ui_skin_combo.addItem("System Default", "")
        for style in QStyleFactory.keys():
            self.ui_skin_combo.addItem(style, style)

    def get_name(self) -> str:
        """Return the display name for this preference category."""
        return "General"

    def get_icon(self) -> QIcon:
        """Return the icon for the sidebar."""
        # Use Qt standard icon for computer
        from PySide6.QtWidgets import QApplication, QStyle
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def load_from_settings(self) -> None:
        """Read from QSettings and populate all widgets."""
        # Load startup directory mode
        mode = self.settings.value("General/StartupDirectoryMode", "last")
        if mode == "preferred":
            self.preferred_dir_radio.setChecked(True)
        else:
            self.last_dir_radio.setChecked(True)

        # Load preferred directory
        preferred_dir = self.settings.value("General/PreferredDirectory", "")
        self.dir_path_edit.setText(preferred_dir)

        # Load preferred audio device
        device_id = self.settings.value("General/PreferredAudioDevice", "")
        index = self.audio_device_combo.findData(device_id)
        if index >= 0:
            self.audio_device_combo.setCurrentIndex(index)
        else:
            self.audio_device_combo.setCurrentIndex(0)  # Default to system default

        # Load UI skin
        skin = self.settings.value("General/UiSkin", "")
        index = self.ui_skin_combo.findData(skin)
        if index >= 0:
            self.ui_skin_combo.setCurrentIndex(index)
        else:
            self.ui_skin_combo.setCurrentIndex(0)  # Default to system default

    def save_to_settings(self) -> None:
        """Write widget values to QSettings."""
        # Save startup directory mode
        mode = "preferred" if self.preferred_dir_radio.isChecked() else "last"
        self.settings.setValue("General/StartupDirectoryMode", mode)

        # Save preferred directory
        self.settings.setValue("General/PreferredDirectory", self.dir_path_edit.text())

        # Save preferred audio device
        device_id = self.audio_device_combo.currentData()
        self.settings.setValue("General/PreferredAudioDevice", device_id)

        # Save UI skin
        skin = self.ui_skin_combo.currentData()
        self.settings.setValue("General/UiSkin", skin)

    def validate(self) -> Tuple[bool, str]:
        """Validate all settings in this pane."""
        # If "Always use this directory" is selected, path must not be empty
        if self.preferred_dir_radio.isChecked():
            if not self.dir_path_edit.text().strip():
                return False, "Please select a preferred directory or choose 'Remember last directory'"
        return True, ""

    def load_defaults(self) -> None:
        """Set all widgets to their default values."""
        self.last_dir_radio.setChecked(True)
        self.dir_path_edit.setText("")
        self.audio_device_combo.setCurrentIndex(0)
        self.ui_skin_combo.setCurrentIndex(0)
