"""Integrations preferences pane for third-party service credentials."""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QLabel
)
from PySide6.QtGui import QIcon

from models.settings import get_qsettings
from providers.analysis.fingerprint.musicbrainz_acoustid import (
    verify_acoustid_api_key,
)
from util.const import SETTINGS_ACOUSTID_API_KEY
from windows.preferences.base import PreferencePaneBase
from windows.widgets.api_key_field import ApiKeyField


ACOUSTID_NEW_APPLICATION_URL = "https://acoustid.org/new-application"


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

        self.acoustid_api_key_field = ApiKeyField(
            verifier=verify_acoustid_api_key,
            placeholder="Application API key (register one at acoustid.org/new-application)",
        )
        self.acoustid_api_key_field.validity_changed.connect(
            self._on_field_validity_changed
        )
        key_row.addWidget(self.acoustid_api_key_field, 1)

        acoustid_layout.addLayout(key_row)

        info_label = QLabel(
            "The MusicBrainz AcoustID analyzer uses an <b>application</b> "
            "API key to query acoustid.org for fingerprint matches. This "
            "is <i>not</i> the personal API key shown on your AcoustID "
            "account page — that one is for submissions only and will be "
            "rejected for lookups. Register an application (free) at "
            f'<a href="{ACOUSTID_NEW_APPLICATION_URL}">'
            f"{ACOUSTID_NEW_APPLICATION_URL}</a> and paste the resulting "
            "application API key here."
        )
        info_label.setOpenExternalLinks(True)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        acoustid_layout.addWidget(info_label)

        acoustid_group.setLayout(acoustid_layout)
        layout.addWidget(acoustid_group)

        layout.addStretch()

    # ----- PreferencePaneBase implementation ----------------------------

    def get_name(self) -> str:
        return "Integrations"

    def get_icon(self) -> QIcon:
        from PySide6.QtWidgets import QApplication, QStyle
        return QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_FileDialogNewFolder
        )

    def load_from_settings(self) -> None:
        saved = self.settings.value(SETTINGS_ACOUSTID_API_KEY, "", type=str)
        self.acoustid_api_key_field.setText(saved)
        # Trust persisted keys without re-hitting the network on every open.
        if saved:
            self.acoustid_api_key_field.mark_verified(saved)

    def save_to_settings(self) -> None:
        self.settings.setValue(
            SETTINGS_ACOUSTID_API_KEY,
            self.acoustid_api_key_field.text(),
        )

    def validate(self) -> tuple[bool, str]:
        if self.is_ready_to_save():
            return True, ""
        return False, (
            "AcoustID API key has not been verified. Tab out of the field "
            "to verify it, or clear the field to skip this integration."
        )

    def is_ready_to_save(self) -> bool:
        return self.acoustid_api_key_field.is_valid()

    def load_defaults(self) -> None:
        self.acoustid_api_key_field.setText("")

    # ----- internal -----------------------------------------------------

    def _on_field_validity_changed(self, _is_valid: bool) -> None:
        # Re-emit so the PreferencesWindow can update its Save button.
        self.validity_changed.emit(self.is_ready_to_save())
