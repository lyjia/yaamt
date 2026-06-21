"""Preferences pane for managing rename format-string presets."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from util.const import RENAME_PRESETS_DEFAULTS
from windows.preferences.base import PreferencePaneBase
from windows.rename.setup_dialog import (
    load_presets_from_settings,
    save_presets_to_settings,
)


class RenamePresetsPane(PreferencePaneBase):
    """
    Lets the user add, remove, reorder, and reset the rename format-string
    presets that populate the rename setup dialog's preset dropdown.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    # -- PreferencePaneBase API ---------------------------------------------

    def get_name(self) -> str:
        return "Rename Presets"

    def get_icon(self) -> QIcon:
        return QIcon()  # no icon - the preferences window handles missing icons gracefully

    def load_from_settings(self) -> None:
        self._populate_list(load_presets_from_settings())

    def save_to_settings(self) -> None:
        save_presets_to_settings(self._collect_presets())

    def validate(self) -> tuple[bool, str]:
        # Empty list is allowed; the dropdown will just show "(no presets
        # defined)". No other validation required - the format-string syntax
        # is forgiving enough that invalid entries render as text.
        return True, ""

    def load_defaults(self) -> None:
        self._populate_list(list(RENAME_PRESETS_DEFAULTS))

    # -- UI -----------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        desc = QLabel(
            "Manage the list of format-string presets shown in the 'Rename "
            "Files Based on Metadata' dialog's preset dropdown. See the token "
            "reference in that dialog for a list of available placeholders."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        body = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.list_widget.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked
            | QListWidget.EditTrigger.EditKeyPressed
        )
        body.addWidget(self.list_widget, stretch=1)

        button_col = QVBoxLayout()
        self.add_button = QPushButton("Add...")
        self.edit_button = QPushButton("Edit...")
        self.remove_button = QPushButton("Remove")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")
        self.reset_button = QPushButton("Reset to Factory Defaults...")

        for btn in (
            self.add_button,
            self.edit_button,
            self.remove_button,
            self.up_button,
            self.down_button,
        ):
            button_col.addWidget(btn)
        button_col.addStretch()
        button_col.addWidget(self.reset_button)
        body.addLayout(button_col)

        layout.addLayout(body)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.remove_button.clicked.connect(self._on_remove)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(+1))
        self.reset_button.clicked.connect(self._on_reset)

    # -- helpers ------------------------------------------------------------

    def _populate_list(self, presets: list[str]) -> None:
        self.list_widget.clear()
        for preset in presets:
            self._add_item(preset)

    def _add_item(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.list_widget.addItem(item)

    def _collect_presets(self) -> list[str]:
        return [
            self.list_widget.item(i).text().strip()
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).text().strip()
        ]

    # -- button handlers ----------------------------------------------------

    def _on_add(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Add Preset", "Format string:", text="%ARTIST% - %TITLE%"
        )
        if ok and text.strip():
            self._add_item(text.strip())
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _on_edit(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        text, ok = QInputDialog.getText(
            self, "Edit Preset", "Format string:", text=item.text()
        )
        if ok:
            text = text.strip()
            if text:
                item.setText(text)

    def _on_remove(self) -> None:
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _move(self, delta: int) -> None:
        row = self.list_widget.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self.list_widget.count():
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(new_row, item)
        self.list_widget.setCurrentRow(new_row)

    def _on_reset(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Reset Rename Presets",
            "Replace the current preset list with the factory defaults? "
            "Custom presets will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.load_defaults()
