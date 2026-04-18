"""Integrations preferences pane for third-party service credentials."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit
)
from PySide6.QtGui import QIcon

from models.settings import get_qsettings
from util.const import SETTINGS_ACOUSTID_API_KEY
from windows.preferences.base import PreferencePaneBase


ACOUSTID_API_KEY_SIGNUP_URL = "https://acoustid.org/api-key"


class IntegrationsPane(PreferencePaneBase):
    """
    Preference pane for configuring third-party integrations.

    Currently holds the AcoustID API key used by the MusicBrainz AcoustID
    fingerprint analyzer. Additional service credentials (Discogs, etc.)
    can be added here as future analyzers require them.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_qsettings()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        desc_label = QLabel(
            "API keys and credentials for the third-party services used by "
            "yaamt's analyzers."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # AcoustID group
        acoustid_group = QGroupBox("AcoustID")
        acoustid_layout = QVBoxLayout()

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API key:"))

        self.acoustid_api_key_edit = QLineEdit()
        self.acoustid_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.acoustid_api_key_edit.setPlaceholderText(
            "Required — register a free key at acoustid.org/api-key"
        )
        key_row.addWidget(self.acoustid_api_key_edit, 1)

        acoustid_layout.addLayout(key_row)

        info_label = QLabel(
            "The MusicBrainz AcoustID analyzer uses this key to query "
            "acoustid.org for fingerprint matches. Register a free key at "
            f'<a href="{ACOUSTID_API_KEY_SIGNUP_URL}">'
            f"{ACOUSTID_API_KEY_SIGNUP_URL}</a>."
        )
        info_label.setOpenExternalLinks(True)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        acoustid_layout.addWidget(info_label)

        acoustid_group.setLayout(acoustid_layout)
        layout.addWidget(acoustid_group)

        layout.addStretch()

    # PreferencePaneBase implementation

    def get_name(self) -> str:
        return "Integrations"

    def get_icon(self) -> QIcon:
        from PySide6.QtWidgets import QApplication, QStyle
        return QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_FileDialogNewFolder
        )

    def load_from_settings(self) -> None:
        self.acoustid_api_key_edit.setText(
            self.settings.value(SETTINGS_ACOUSTID_API_KEY, "", type=str)
        )

    def save_to_settings(self) -> None:
        self.settings.setValue(
            SETTINGS_ACOUSTID_API_KEY,
            self.acoustid_api_key_edit.text().strip(),
        )

    def validate(self) -> tuple[bool, str]:
        return True, ""

    def load_defaults(self) -> None:
        self.acoustid_api_key_edit.clear()
