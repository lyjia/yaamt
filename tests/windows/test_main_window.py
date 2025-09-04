import pytest
from PySide6.QtWidgets import QTreeView
from unittest.mock import patch

from windows.main_window import MainWindow
from delegates.editable_metadata_delegate import EditableMetadataDelegate

@pytest.fixture
def app(qtbot):
    with patch('windows.main_window.settings') as mock_settings:
        mock_settings.value.return_value = None
        window = MainWindow()
        qtbot.addWidget(window)
        yield window

def test_main_window_sets_editable_delegate(app):
    """
    Integration test to ensure the MainWindow correctly instantiates and sets
    the EditableMetadataDelegate on the QTreeView.
    """
    assert isinstance(app.files_view, QTreeView)
    delegate = app.files_view.itemDelegate()
    assert isinstance(delegate, EditableMetadataDelegate)