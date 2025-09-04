import logging
import os

log = logging.getLogger(__name__)
import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QStyleOptionViewItem
from PySide6.QtCore import QModelIndex, QRect, Qt
from unittest.mock import MagicMock, PropertyMock

from delegates.editable_metadata_delegate import EditableMetadataDelegate

IN_GITHUB_RUNNER = (os.getenv("GITHUB_ACTIONS") == "true")


@pytest.fixture
def qapp():
    """Create an application instance for the tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def delegate():
    return EditableMetadataDelegate()


@pytest.fixture
def parent_widget(qapp):
    from PySide6.QtWidgets import QWidget 
    return QWidget()


@pytest.fixture
def model():
    model = MagicMock()
    model.data.return_value = "test_value"
    return model


@pytest.fixture
def index(model):
    index = QModelIndex()
    index.model = lambda: model
    return index


@pytest.mark.skipif(IN_GITHUB_RUNNER,
                    reason="Crashes in github runner with: Fatal Python error: Aborted, test_editable_metadata_delegate.py, line 16 in qapp")
def test_create_editor(delegate, parent_widget, index, qapp):
    """Test that createEditor returns a QLineEdit."""
    log.info("Running test_create_editor")
    editor = delegate.createEditor(parent_widget, QStyleOptionViewItem(), index)
    assert isinstance(editor, QLineEdit)


@pytest.mark.skipif(IN_GITHUB_RUNNER,
                    reason="Crashes in github runner with: Fatal Python error: Aborted, test_editable_metadata_delegate.py, line 16 in qapp")
def test_set_editor_data(delegate, model, index, qapp):
    """Test that setEditorData sets the editor's text and selects it."""
    log.info("Running test_set_editor_data")
    editor = QLineEdit()
    delegate.setEditorData(editor, index)
    assert editor.text() == "test_value"
    assert editor.selectedText() == "test_value"


@pytest.mark.skipif(IN_GITHUB_RUNNER,
                    reason="Crashes in github runner with: Fatal Python error: Aborted, test_editable_metadata_delegate.py, line 16 in qapp")
def test_set_model_data(delegate, model, index, qapp):
    """Test that setModelData updates the model's data."""
    log.info("Running test_set_model_data")
    editor = QLineEdit()
    editor.setText("new_value")
    delegate.setModelData(editor, model, index)
    model.setData.assert_called_once_with(index, "new_value", role=Qt.ItemDataRole.EditRole)


@pytest.mark.skipif(IN_GITHUB_RUNNER,
                    reason="Crashes in github runner with: Fatal Python error: Aborted, test_editable_metadata_delegate.py, line 16 in qapp")
def test_set_model_data_no_change(delegate, model, index, qapp):
    """Test that setModelData does not update the model if the value is unchanged."""
    log.info("Running test_set_model_data_no_change")
    model.data.return_value = "new_value"
    editor = QLineEdit()
    editor.setText("  new_value  ")  # Test stripping whitespace
    delegate.setModelData(editor, model, index)
    model.setData.assert_not_called()


@pytest.mark.skipif(IN_GITHUB_RUNNER,
                    reason="Crashes in github runner with: Fatal Python error: Aborted, test_editable_metadata_delegate.py, line 16 in qapp")
def test_update_editor_geometry(delegate, qapp):
    """Test that updateEditorGeometry sets the editor's geometry."""
    log.info("Running test_update_editor_geometry")
    editor = QLineEdit()
    option = QStyleOptionViewItem()
    option.rect = QRect(10, 20, 30, 40)
    delegate.updateEditorGeometry(editor, option, QModelIndex())
    assert editor.geometry() == QRect(10, 20, 30, 40)
