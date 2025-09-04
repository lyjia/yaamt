import os
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit
from PySide6.QtCore import QModelIndex, Qt

from util.logging import log


class EditableMetadataDelegate(QStyledItemDelegate):
    """
    A custom delegate that provides editable cells for metadata in the file list view.

    This delegate handles double-clicking to activate editing mode, creates QLineEdit
    widgets for text editing, and ensures the text is fully selected for easy replacement.
    """
    def __init__(self,  parent=None):
        super().__init__(parent)

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
        The text will be fully selected for easy replacement.

        Args:
            editor: The QLineEdit editor widget
            index: The model index being edited
        """
        if isinstance(editor, QLineEdit):
            # Get the current value from the model
            value = index.model().data(index, role=0)  # Qt.ItemDataRole.DisplayRole is 0
            if value is not None:
                editor.setText(str(value))
            else:
                editor.setText("")

            # Select all text for easy replacement
            editor.selectAll()
            editor.setFocus()

    def setModelData(self, editor, model, index):
        """
        Set the model data from the editor when editing is finished.
        This is called when the user presses Enter or the editor loses focus.

        Args:
            editor: The QLineEdit editor widget
            model: The model to set data on
            index: The model index being edited
        """
        role = Qt.ItemDataRole.EditRole

        if isinstance(editor, QLineEdit):
            new_value = editor.text().strip()

            # Get the original value for comparison
            original_value = model.data(index, role=role)
            if original_value is not None:
                original_value = str(original_value)
            else:
                original_value = ""

            # Only set data if the value has actually changed
            if new_value != original_value:
                source_model = model.sourceModel()
                source_index = model.mapToSource(index)
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