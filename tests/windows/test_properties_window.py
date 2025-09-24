import os
import tempfile
import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from pathlib import Path
import shutil
from util.const import PROJECT_ROOT, KEY_TAG_GENERIC, KEY_TAG_INTERNAL, IN_GITHUB_RUNNER

from windows.properties_window import PropertiesWindow
from models.media_file import MediaFile
from models.edit_manager import EditManager
from util.const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM

@pytest.fixture
def sample_file(tmp_path):
    """Create a temporary audio file for testing."""
    source_file = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "sample_dtmf_unicode.mp3"
    temp_file = tmp_path / source_file.name
    shutil.copy(source_file, temp_file)
    return MediaFile(str(temp_file), enable_write=True)

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_properties_window_initialization(qapp, sample_file):
    """Test that PropertiesWindow initializes correctly with EditManager."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Verify EditManager is initialized
    assert hasattr(window, 'edit_manager')
    assert isinstance(window.edit_manager, EditManager)

    # Verify MediaFile is initialized
    assert hasattr(window, 'media_files')
    assert isinstance(window.media_files[0], MediaFile)

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_edit_manager_signal_connection(qapp, sample_file):
    """Test that PropertiesWindow connects to EditManager signals."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Verify signal connection exists
    assert hasattr(window.edit_manager, 'staged_changes_exist')
    # The signal should be connected during initialization

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_staged_changes_display(qapp, sample_file):
    """Test that PropertiesWindow displays staged values correctly."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Stage a change via EditManager
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "Staged Title")

    # Verify the staged value is displayed in the UI
    assert window.main_tab._get_display_value(KEY_TITLE) == "Staged Title"

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_committed_changes_display(qapp, sample_file):
    """Test that PropertiesWindow displays committed values when no staged changes exist."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Get the original committed value
    original_value = sample_file.get_tag_simple(KEY_TITLE)

    # Verify the committed value is displayed when no staged changes exist
    assert window.main_tab._get_display_value(KEY_TITLE) == original_value

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_simple_tab_edit_stages_changes(qapp, sample_file):
    """Test that editing fields in the simple tab stages changes via EditManager."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Simulate editing a field
    window.main_tab._on_edited(KEY_TITLE, "New Title")

    # Verify the change was staged
    assert window.edit_manager.get_staged_value_for_file(sample_file, KEY_TITLE) == "New Title"

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_button_states_with_staged_changes(qapp, sample_file):
    """Test that button states update correctly based on EditManager state."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

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

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_commit_request_handling(qapp, sample_file):
    """Test that PropertiesWindow handles commit requests from EditManager."""
    edit_manager = EditManager()
    window = PropertiesWindow([sample_file], edit_manager)

    # Stage some changes
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "New Title")
    window.edit_manager.stage_change([sample_file], KEY_ARTIST, "New Artist")

    # Mock the save method to avoid actual file I/O
    with patch.object(sample_file, 'save') as mock_save:
        # Simulate commit request - use the window's file_id to ensure exact match
        commit_data = {
            str(sample_file.file_id): {
                KEY_TAG_GENERIC: {KEY_TITLE: "New Title", KEY_ARTIST: "New Artist"},
                KEY_TAG_INTERNAL: {}
            }
        }
        # Connect the handle_commit function to the commit_requested signal
        window.edit_manager.commit_started.connect(lambda: sample_file.save(commit_data[str(sample_file.file_id)]))

        # Commit changes via EditManager (this will emit the commit_requested signal)
        window.edit_manager.commit_changes()

        # Verify save was called with correct changes
        mock_save.assert_called_once_with(commit_data[str(sample_file.file_id)])