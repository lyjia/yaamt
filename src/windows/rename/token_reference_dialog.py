"""Token reference dialog for the rename feature.

A read-only, sectioned table of every token the format string supports. Rows
are copyable so the user can grab tokens directly with Ctrl+C.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from util.rename_formatter import list_tokens_by_section


class TokenReferenceDialog(QDialog):
    """Simple dialog showing every supported rename token grouped by section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Tokens")
        self.setModal(True)
        self.resize(520, 560)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel(
            "Insert any of these tokens into the format string to substitute "
            "the corresponding metadata value. Rows are selectable and can be "
            "copied with Ctrl+C."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Token", "Field"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._populate_table()
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _populate_table(self) -> None:
        """Populate the table, with bold non-selectable rows as section headers."""
        sections = list_tokens_by_section()

        total_rows = sum(len(rows) + 1 for rows in sections.values())  # +1 header per section
        self.table.setRowCount(total_rows)

        bold = QFont()
        bold.setBold(True)
        header_brush = QBrush(QColor(220, 220, 220))

        row = 0
        for section, entries in sections.items():
            # Section header row spans both columns.
            hdr_item = QTableWidgetItem(section)
            hdr_item.setFont(bold)
            hdr_item.setBackground(header_brush)
            hdr_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # non-selectable
            self.table.setItem(row, 0, hdr_item)
            blank = QTableWidgetItem("")
            blank.setBackground(header_brush)
            blank.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, blank)
            row += 1

            for token, description in entries:
                token_item = QTableWidgetItem(token)
                desc_item = QTableWidgetItem(description)
                self.table.setItem(row, 0, token_item)
                self.table.setItem(row, 1, desc_item)
                row += 1
