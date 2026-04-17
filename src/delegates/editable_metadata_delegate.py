import os
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit
from PySide6.QtCore import QModelIndex, Qt

from util.logging import log

PLACEHOLDER_MULTIPLE_VALUES = "<< multiple values >>"


class EditableMetadataDelegate(QStyledItemDelegate):
    """
    A custom delegate that provides editable cells for metadata in the file list view.

    This delegate handles double-clicking to activate editing mode, creates QLineEdit
    widgets for text editing, and ensures the text is fully selected for easy replacement.

    When multiple rows are selected, the delegate applies the edit to all selected rows
    via the source model's setDataForRows() method.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_model = None
        self._proxy_model = None

    def set_selection_model(self, selection_model):
        self._selection_model = selection_model

    def set_proxy_model(self, proxy_model):
        self._proxy_model = proxy_model

    def _get_selected_source_rows(self, column):
        """
        Returns a list of source-model row indices for the current selection at the given column.
        Returns an empty list if selection info is unavailable.
        """
        if not self._selection_model or not self._proxy_model:
            return []

        selected_indexes = self._selection_model.selectedRows(column)
        if len(selected_indexes) <= 1:
            return []

        return [self._proxy_model.mapToSource(idx).row() for idx in selected_indexes]

    def createEditor(self, parent, option, index):
        """
        Create and return a QLineEdit widget for editing the cell content.

        Args:
            parent: The parent widget for the editor
            option: Style options for the widget
            index: The model index being edited

        Returns:
            QLineEdit: The editor widget
        """
        editor = QLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        """
        Set the editor's data to the current value of the cell.
        For multi-select, shows a placeholder if values differ across selected rows.

        Args:
            editor: The QLineEdit editor widget
            index: The model index being edited
        """
        if not isinstance(editor, QLineEdit):
            return

        source_rows = self._get_selected_source_rows(index.column())

        if source_rows:
            # Multi-selection: collect values across all selected rows for this column
            values = set()
            for sel_index in self._selection_model.selectedRows(index.column()):
                val = sel_index.data(Qt.ItemDataRole.EditRole)
                values.add(val if val is not None else "")

            if len(values) == 1:
                editor.setText(str(values.pop()))
            else:
                editor.setText("")
                editor.setPlaceholderText(PLACEHOLDER_MULTIPLE_VALUES)
        else:
            # Single selection: existing behavior
            value = index.model().data(index, role=Qt.ItemDataRole.DisplayRole)
            if value is not None:
                editor.setText(str(value))
            else:
                editor.setText("")

        editor.selectAll()
        editor.setFocus()

    def setModelData(self, editor, model, index):
        """
        Set the model data from the editor when editing is finished.
        For multi-select, applies the change to all selected rows via setDataForRows().

        Args:
            editor: The QLineEdit editor widget
            model: The model to set data on
            index: The model index being edited
        """
        if not isinstance(editor, QLineEdit):
            return

        role = Qt.ItemDataRole.EditRole
        new_value = editor.text().strip()
        source_model = model.sourceModel()
        source_index = model.mapToSource(index)

        source_rows = self._get_selected_source_rows(index.column())

        if source_rows:
            # Multi-row edit
            if new_value == "" and editor.placeholderText() == PLACEHOLDER_MULTIPLE_VALUES:
                return  # User didn't change anything

            log.debug(f"Multi-edit: applying '{new_value}' to {len(source_rows)} rows, column {source_index.column()}")
            if source_model.setDataForRows(source_rows, source_index.column(), new_value, role=role):
                source_model.finished_with_edits()
        else:
            # Single-row edit (existing behavior)
            original_value = model.data(index, role=role)
            if original_value is not None:
                original_value = str(original_value)
            else:
                original_value = ""

            if new_value != original_value:
                log.debug(f"Updating source index {source_index} with new value '{new_value}'")
                source_model.setData(source_index, new_value, role=role)
                source_model.finished_with_edits()

    def updateEditorGeometry(self, editor, option, index):
        """
        Update the editor's geometry to match the cell geometry.

        Args:
            editor: The QLineEdit editor widget
            option: Style options containing the cell rectangle
            index: The model index being edited
        """
        editor.setGeometry(option.rect)
