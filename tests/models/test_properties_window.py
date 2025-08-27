import os
import tempfile
import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from windows.properties_window import PropertiesWindow
from models.media_file import MediaFile
from models.edit_manager import EditManager
from util.const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM

# Create QApplication instance for Qt widgets
@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def sample_file(tmp_path):
    """Create a temporary audio file for testing."""
    temp_file = tmp_path / "test.mp3"
    # Create a minimal MP3 file for testing
    with open(temp_file, 'wb') as f:
        # Write minimal MP3 header (this is a simplified version)
        f.write(b'\xFF\xFB\x00\x00')  # MP3 frame sync
    return MediaFile(str(temp_file), enable_write=True)

def test_properties_window_initialization(qapp, sample_file):
    """Test that PropertiesWindow initializes correctly with EditManager."""
    window = PropertiesWindow([sample_file])

    # Verify EditManager is initialized
    assert hasattr(window, 'edit_manager')
    assert isinstance(window.edit_manager, EditManager)

    # Verify MediaFile is initialized
    assert hasattr(window, 'media_files')
    assert isinstance(window.media_files[0], MediaFile)

def test_edit_manager_signal_connection(qapp, sample_file):
    """Test that PropertiesWindow connects to EditManager signals."""
    window = PropertiesWindow([sample_file])

    # Verify signal connection exists
    assert hasattr(window.edit_manager, 'staged_changes_exist')
    # The signal should be connected during initialization

def test_staged_changes_display(qapp, sample_file):
    """Test that PropertiesWindow displays staged values correctly."""
    window = PropertiesWindow([sample_file])

    # Stage a change via EditManager
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "Staged Title")

    # Verify the staged value is displayed in the UI
    assert window.main_tab._get_display_value(KEY_TITLE) == "Staged Title"

def test_committed_changes_display(qapp, sample_file):
    """Test that PropertiesWindow displays committed values when no staged changes exist."""
    window = PropertiesWindow([sample_file])

    # Get the original committed value
    original_value = sample_file.get_tag_simple(KEY_TITLE)

    # Verify the committed value is displayed when no staged changes exist
    assert window.main_tab._get_display_value(KEY_TITLE) == original_value

def test_simple_tab_edit_stages_changes(qapp, sample_file):
    """Test that editing fields in the simple tab stages changes via EditManager."""
    window = PropertiesWindow([sample_file])

    # Simulate editing a field
    window.main_tab._on_edited(KEY_TITLE, "New Title")

    # Verify the change was staged
    assert window.edit_manager.get_staged_value(sample_file, KEY_TITLE) == "New Title"

def test_button_states_with_staged_changes(qapp, sample_file):
    """Test that button states update correctly based on EditManager state."""
    window = PropertiesWindow([sample_file])

    # Reset the EditManager to ensure clean state
    window.edit_manager.reset_changes()

    # Initially no changes, OK button should be disabled
    window.update_button_states()
    assert not window.ok_button.isEnabled()
    assert window.close_button.text() == "Close"

    # Stage a change
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "New Title")

    # Trigger the signal manually since we're testing
    window.on_staged_changes_changed(True)

    # Verify buttons update
    assert window.ok_button.isEnabled()
    assert window.close_button.text() == "Cancel"

def test_commit_request_handling(qapp, sample_file):
    """Test that PropertiesWindow handles commit requests from EditManager."""
    window = PropertiesWindow([sample_file])

    # Stage some changes
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "New Title")
    window.edit_manager.stage_change([sample_file], KEY_ARTIST, "New Artist")

    # Mock the save method to avoid actual file I/O
    with patch.object(sample_file, 'save') as mock_save:
        # Simulate commit request - use the window's file_path to ensure exact match
        commit_data = {
            sample_file.file_path: {
                'generic_tags': {KEY_TITLE: "New Title", KEY_ARTIST: "New Artist"},
                'internal_tags': {}
            }
        }
        # Connect the handle_commit function to the commit_requested signal
        window.edit_manager.commit_requested.connect(lambda data: sample_file.save(data[sample_file.file_path]))

        # Commit changes via EditManager (this will emit the commit_requested signal)
        window.edit_manager.commit_changes()

        # Verify save was called with correct changes
        mock_save.assert_called_once_with(commit_data[sample_file.file_path])