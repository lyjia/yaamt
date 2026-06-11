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
def test_open_window_stages_nothing(qapp, sample_file):
    """Regression: opening the Properties window must not stage any changes.

    MainTab used to connect textChanged (which fires on the programmatic
    setText() calls that populate the form), staging a phantom edit for
    every non-empty field the moment the window opened. The visible symptom
    was file-view cells turning bold after opening and closing the window
    without touching anything.
    """
    edit_manager = EditManager()
    edit_manager.reset_changes()

    window = PropertiesWindow([sample_file], edit_manager)
    qapp.processEvents()

    assert not edit_manager.has_staged_changes(), (
        f"opening the window staged: {edit_manager.get_staged_changes_for_file(sample_file)}"
    )


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_refresh_tabs_stages_nothing(qapp, sample_file):
    """Regression: re-populating the tabs (analyzer completion path) must not
    stage changes either — it runs the same setText()/tree-rebuild code as
    the constructor."""
    edit_manager = EditManager()
    edit_manager.reset_changes()

    window = PropertiesWindow([sample_file], edit_manager)
    qapp.processEvents()
    window.refresh_tabs()
    qapp.processEvents()

    assert not edit_manager.has_staged_changes()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_user_keystrokes_still_stage_changes(qapp, sample_file):
    """Typing into a Main tab field (real key events, not setText) must stage."""
    from PySide6.QtTest import QTest

    edit_manager = EditManager()
    edit_manager.reset_changes()

    window = PropertiesWindow([sample_file], edit_manager)
    qapp.processEvents()

    QTest.keyClicks(window.main_tab.title_edit, "X")

    staged = edit_manager.get_staged_value_for_file(sample_file, KEY_TITLE)
    assert staged is not None
    assert staged.endswith("X")


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

    # Verify buttons update. The close button never relabels to "Cancel":
    # closing does not discard edits (it commits them with autosave on, or
    # leaves them queued with autosave off).
    assert window.ok_button.isEnabled()
    assert window.close_button.text() == "Close"

@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_close_with_autosave_on_commits_staged_changes(qapp, sample_file):
    """Autosave on: closing the window persists staged edits to disk."""
    from PySide6.QtCore import QEventLoop

    edit_manager = EditManager()
    edit_manager.reset_changes()
    edit_manager.set_autosave(True)

    window = PropertiesWindow([sample_file], edit_manager)
    qapp.processEvents()

    window.main_tab._on_edited(KEY_TITLE, "Saved By Close")

    loop = QEventLoop()
    edit_manager.commit_finished.connect(loop.quit)
    edit_manager.commit_failed.connect(loop.quit)
    window.close()
    loop.exec()
    assert edit_manager.wait_for_pending_commit()
    qapp.processEvents()

    assert not edit_manager.has_staged_changes()
    reread = MediaFile(sample_file.file_path)
    assert reread.get_tag_simple(KEY_TITLE) == "Saved By Close"


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_close_with_autosave_off_keeps_changes_queued(qapp, sample_file):
    """Autosave off: closing the window leaves edits staged, file untouched."""
    edit_manager = EditManager()
    edit_manager.reset_changes()
    edit_manager.set_autosave(False)
    original_title = sample_file.get_tag_simple(KEY_TITLE)

    try:
        window = PropertiesWindow([sample_file], edit_manager)
        qapp.processEvents()

        window.main_tab._on_edited(KEY_TITLE, "Queued Edit")
        window.close()
        qapp.processEvents()

        assert edit_manager.get_staged_value_for_file(sample_file, KEY_TITLE) == "Queued Edit"
        reread = MediaFile(sample_file.file_path)
        assert reread.get_tag_simple(KEY_TITLE) == original_title
    finally:
        edit_manager.reset_changes()
        edit_manager.set_autosave(True)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_unrelated_commit_does_not_close_window(qapp, sample_file):
    """A commit initiated elsewhere (File > Save Changes) must not close an
    open Properties window that has no commit in flight."""
    edit_manager = EditManager()
    edit_manager.reset_changes()

    window = PropertiesWindow([sample_file], edit_manager)
    window.show()
    qapp.processEvents()

    # Simulate some other component's commit finishing.
    edit_manager.commit_finished.emit([])
    qapp.processEvents()

    assert window.isVisible()
    window.close()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
def test_commit_request_handling(qapp, sample_file):
    """The background commit saves the staged changes through MediaFile.save()."""
    from PySide6.QtCore import QEventLoop

    edit_manager = EditManager()
    edit_manager.reset_changes()
    window = PropertiesWindow([sample_file], edit_manager)

    # Stage some changes
    window.edit_manager.stage_change([sample_file], KEY_TITLE, "New Title")
    window.edit_manager.stage_change([sample_file], KEY_ARTIST, "New Artist")

    # Mock the save method to avoid actual file I/O
    with patch.object(sample_file, 'save') as mock_save:
        loop = QEventLoop()
        window.edit_manager.commit_finished.connect(loop.quit)
        window.edit_manager.commit_failed.connect(loop.quit)
        assert window.edit_manager.commit_changes() is True
        loop.exec()
        assert window.edit_manager.wait_for_pending_commit()
        qapp.processEvents()

        # Verify save was called with the staged changes
        mock_save.assert_called_once_with({
            KEY_TAG_GENERIC: {KEY_TITLE: "New Title", KEY_ARTIST: "New Artist"},
            KEY_TAG_INTERNAL: {}
        })