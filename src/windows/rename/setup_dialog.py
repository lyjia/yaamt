"""Rename setup dialog - lets the user compose a format string and preview results.

Responsibilities:
- Compose a format string (with preset dropdown, token reference button).
- Show a live single-line example using SAMPLE_RENAME_METADATA (updates on
  every keystroke).
- Show a preview table of the selected files (up to ~12 rows); refreshes
  when the textbox loses focus.
- Let the user choose collision behavior.

The dialog does NOT perform renames - it just returns the configured values
so the MainWindow can drive a RenameDispatcher.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from models.settings import get_qsettings
from util.const import (
    RENAME_COLLISION_MODE_DEFAULT,
    RENAME_COLLISION_MODE_LABELS,
    RENAME_PRESETS_DEFAULTS,
    SAMPLE_RENAME_EXTENSION,
    SAMPLE_RENAME_METADATA,
    SETTINGS_ARRAY_RENAME_PRESETS,
    SETTINGS_GROUP_RENAME,
    SETTINGS_RENAME_COLLISION_MODE,
)
from util.logging import log
from util.rename_formatter import (
    FormatParseError,
    build_token_map_from_dict,
    format_filename,
    sanitize_filename,
    validate_format_string,
)
from windows.rename.token_reference_dialog import TokenReferenceDialog

if TYPE_CHECKING:
    from models.media_file import MediaFile


# Cap for the preview table - renaming 10k+ files shouldn't lock the dialog up.
PREVIEW_ROW_LIMIT = 12


def load_presets_from_settings() -> list[str]:
    """Load the user's format-string presets from QSettings."""
    settings = get_qsettings()
    settings.beginGroup(SETTINGS_GROUP_RENAME)
    size = settings.beginReadArray(SETTINGS_ARRAY_RENAME_PRESETS)
    presets: list[str] = []
    for i in range(size):
        settings.setArrayIndex(i)
        value = settings.value("value", "", type=str)
        if value:
            presets.append(value)
    settings.endArray()
    settings.endGroup()
    if not presets:
        # First run: seed with factory defaults so the dropdown isn't empty.
        return list(RENAME_PRESETS_DEFAULTS)
    return presets


def save_presets_to_settings(presets: list[str]) -> None:
    """Persist the user's format-string presets to QSettings."""
    settings = get_qsettings()
    settings.beginGroup(SETTINGS_GROUP_RENAME)
    # Clear the existing array entirely before writing.
    settings.remove(SETTINGS_ARRAY_RENAME_PRESETS)
    settings.beginWriteArray(SETTINGS_ARRAY_RENAME_PRESETS, len(presets))
    for i, value in enumerate(presets):
        settings.setArrayIndex(i)
        settings.setValue("value", value)
    settings.endArray()
    settings.endGroup()


class RenameSetupDialog(QDialog):
    """Configuration dialog for the rename-by-metadata feature."""

    def __init__(
        self,
        media_files: list["MediaFile"],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Files Based on Metadata")
        self.setModal(True)
        self.resize(720, 560)

        self._media_files = list(media_files)
        self._sample_tokens = build_token_map_from_dict(SAMPLE_RENAME_METADATA)
        self._qsettings = get_qsettings()
        self._presets = load_presets_from_settings()

        self._setup_ui()
        self._connect_signals()
        self._refresh_sample_label()
        self._refresh_preview_table()

    # -- public accessors ---------------------------------------------------

    def get_format_string(self) -> str:
        return self.format_edit.text()

    def get_collision_mode(self) -> str:
        return self.collision_combo.currentData()

    # -- UI construction ----------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Description.
        desc = QLabel(
            "Rename selected files using a format string built from their "
            "metadata. Tokens are wrapped in %PERCENT% characters. Enclose a "
            "segment in [brackets]? to mark it optional - it renders only if "
            "every token inside has a value. Use :00 inside a token (e.g. "
            "%TRACKNUMBER:00%) to pad numbers with leading zeros."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Format string row.
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_edit = QLineEdit()
        # Seed with the first preset so the user sees something meaningful.
        if self._presets:
            self.format_edit.setText(self._presets[0])
        fmt_row.addWidget(self.format_edit, stretch=1)

        self.presets_button = QToolButton()
        self.presets_button.setText("Presets \u25be")
        self.presets_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.presets_button.setMenu(self._build_presets_menu())
        fmt_row.addWidget(self.presets_button)

        self.tokens_button = QPushButton("Show token reference...")
        fmt_row.addWidget(self.tokens_button)

        layout.addLayout(fmt_row)

        # Live sample label.
        self.sample_label = QLabel("Example: ")
        self.sample_label.setStyleSheet("color: #555; font-style: italic;")
        self.sample_label.setWordWrap(True)
        self.sample_label.setToolTip(
            "Live preview using sample metadata from track 7, disc 1 of "
            "Dieselboy's 'The Dungeonmaster's Guide' (Raiden - Infection, "
            "E-Sassin Remix). Updates as you type."
        )
        layout.addWidget(self.sample_label)

        # Preview table.
        preview_header = QLabel("Preview (updates when the format field loses focus):")
        layout.addWidget(preview_header)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["Current name", "New name"])
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setAlternatingRowColors(True)
        ph = self.preview_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.preview_table, stretch=1)

        self.preview_hint = QLabel()
        self.preview_hint.setStyleSheet("color: #777; font-size: 10px;")
        layout.addWidget(self.preview_hint)

        # Collision mode row.
        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("If target exists:"))
        self.collision_combo = QComboBox()
        for mode_id, label in RENAME_COLLISION_MODE_LABELS.items():
            self.collision_combo.addItem(label, mode_id)
        saved_mode = self._qsettings.value(
            SETTINGS_RENAME_COLLISION_MODE,
            RENAME_COLLISION_MODE_DEFAULT,
            type=str,
        )
        idx = self.collision_combo.findData(saved_mode)
        if idx >= 0:
            self.collision_combo.setCurrentIndex(idx)
        col_row.addWidget(self.collision_combo, stretch=1)
        layout.addLayout(col_row)

        # OK / Cancel buttons.
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accepted)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _build_presets_menu(self) -> QMenu:
        menu = QMenu(self)
        for preset in self._presets:
            action = QAction(preset, self)
            action.triggered.connect(lambda checked=False, p=preset: self._apply_preset(p))
            menu.addAction(action)
        if not self._presets:
            empty = QAction("(no presets defined)", self)
            empty.setEnabled(False)
            menu.addAction(empty)
        menu.addSeparator()
        manage = QAction("Manage presets in Preferences...", self)
        manage.triggered.connect(self._on_manage_presets)
        menu.addAction(manage)
        return menu

    # -- signal wiring ------------------------------------------------------

    def _connect_signals(self) -> None:
        self.format_edit.textChanged.connect(self._refresh_sample_label)
        self.format_edit.editingFinished.connect(self._refresh_preview_table)
        self.tokens_button.clicked.connect(self._on_show_tokens)

    # -- actions ------------------------------------------------------------

    def _apply_preset(self, preset: str) -> None:
        self.format_edit.setText(preset)
        self._refresh_preview_table()

    def _on_show_tokens(self) -> None:
        dlg = TokenReferenceDialog(self)
        dlg.exec()

    def _on_manage_presets(self) -> None:
        QMessageBox.information(
            self,
            "Manage Presets",
            "Open the Preferences window and select 'Rename Presets' to "
            "add, remove, or reorder your format-string presets.",
        )

    # -- live updates -------------------------------------------------------

    def _render_for_tokens(self, fmt: str, tokens: dict[str, str]) -> tuple[str, str]:
        """
        Render a format string against a token map, returning (preview, error).

        preview is the sanitized filename (extension appended) or an error
        marker in angle brackets. error is an optional human-readable error.
        """
        ok, msg = validate_format_string(fmt)
        if not ok:
            return ("<invalid format>", msg)
        try:
            rendered = format_filename(fmt, tokens)
        except FormatParseError as e:
            return ("<invalid format>", str(e))
        sanitized = sanitize_filename(rendered)
        if not sanitized:
            return ("<empty filename>", "Format string rendered to an empty filename")
        return (sanitized, "")

    def _refresh_sample_label(self) -> None:
        fmt = self.format_edit.text()
        if not fmt:
            self.sample_label.setText("Example: (enter a format string above)")
            self._set_ok_enabled(False)
            return
        preview, error = self._render_for_tokens(fmt, self._sample_tokens)
        if error and preview.startswith("<"):
            self.sample_label.setText(f"Example: {preview} - {error}")
            self._set_ok_enabled(False)
            return
        self.sample_label.setText(f"Example: {preview}{SAMPLE_RENAME_EXTENSION}")
        self._set_ok_enabled(True)

    def _set_ok_enabled(self, enabled: bool) -> None:
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(enabled)

    def _refresh_preview_table(self) -> None:
        fmt = self.format_edit.text()
        files_to_show = self._media_files[:PREVIEW_ROW_LIMIT]
        self.preview_table.setRowCount(len(files_to_show))

        for row, mf in enumerate(files_to_show):
            try:
                from util.rename_formatter import build_token_map
                tokens = build_token_map(mf)
            except Exception as e:
                log.warning(f"Failed to build token map for {mf.file_path}: {e}")
                tokens = {}

            current_name = os.path.basename(mf.file_path)
            ext = os.path.splitext(current_name)[1]

            if not fmt:
                new_name = "(enter a format string)"
            else:
                preview, error = self._render_for_tokens(fmt, tokens)
                if error and preview.startswith("<"):
                    new_name = preview
                else:
                    new_name = f"{preview}{ext}"

            cur_item = QTableWidgetItem(current_name)
            new_item = QTableWidgetItem(new_name)
            self.preview_table.setItem(row, 0, cur_item)
            self.preview_table.setItem(row, 1, new_item)

        total = len(self._media_files)
        if total > PREVIEW_ROW_LIMIT:
            self.preview_hint.setText(
                f"Showing {PREVIEW_ROW_LIMIT} of {total} selected files."
            )
        else:
            self.preview_hint.setText(f"{total} file(s) selected.")

    # -- accept -------------------------------------------------------------

    def _on_accepted(self) -> None:
        fmt = self.format_edit.text().strip()
        if not fmt:
            QMessageBox.warning(
                self, "Invalid Format", "Enter a format string before continuing."
            )
            return
        ok, msg = validate_format_string(fmt)
        if not ok:
            QMessageBox.warning(self, "Invalid Format", msg)
            return

        # Persist the collision-mode choice so the dropdown remembers it next time.
        self._qsettings.setValue(
            SETTINGS_RENAME_COLLISION_MODE, self.get_collision_mode()
        )
        self.accept()
