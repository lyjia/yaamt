import pytest
from unittest.mock import Mock, patch
from PySide6.QtTest import QSignalSpy
from models.edit_manager import EditManager


class TestEditManager:
    """Comprehensive test suite for the EditManager class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Reset the singleton instance for each test
        EditManager._instance = None
        self.edit_manager = EditManager()

    def teardown_method(self):
        """Clean up after each test method."""
        # Reset the singleton instance
        EditManager._instance = None

    def test_singleton_behavior(self):
        """Test that EditManager is a proper singleton."""
        # Create another instance
        edit_manager2 = EditManager()

        # Verify they are the same instance
        assert self.edit_manager is edit_manager2

        # Verify initialization only happens once
        assert self.edit_manager._initialized is True

    def test_initial_state(self):
        """Test the initial state of the EditManager."""
        # Verify initial autosave state
        assert self.edit_manager.autosave is False

        # Verify no staged changes initially
        assert self.edit_manager.has_staged_changes() is False
        assert self.edit_manager._staged_changes == {}

    def test_autosave_property_getter(self):
        """Test the autosave property getter."""
        assert self.edit_manager.autosave is False

    def test_autosave_property_setter_changes_value(self):
        """Test that setting autosave property changes the internal value."""
        # Spy on the autosave_changed signal
        spy = SignalSpy(self.edit_manager.autosave_changed)

        # Set autosave to True
        self.edit_manager.autosave = True
        assert self.edit_manager.autosave is True

        # Verify signal was emitted
        assert len(spy) == 1
        assert spy[0][0] is True

    def test_autosave_property_setter_no_signal_when_unchanged(self):
        """Test that setting autosave to the same value doesn't emit signal."""
        # Set initial value
        self.edit_manager._autosave = True

        # Spy on the autosave_changed signal
        spy = SignalSpy(self.edit_manager.autosave_changed)

        # Set the same value again
        self.edit_manager.autosave = True

        # Verify no signal was emitted
        assert len(spy) == 0

    def test_autosave_property_setter_signal_emission(self):
        """Test that autosave_changed signal is emitted when value changes."""
        spy = SignalSpy(self.edit_manager.autosave_changed)

        # Test True -> False -> True transitions
        self.edit_manager.autosave = True
        assert len(spy) == 1
        assert spy[0][0] is True

        self.edit_manager.autosave = False
        assert len(spy) == 2
        assert spy[1][0] is False

        self.edit_manager.autosave = True
        assert len(spy) == 3
        assert spy[2][0] is True

    def test_stage_change_single_file_single_tag(self):
        """Test staging a change for a single file and single tag."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')

        # Verify the change was staged
        assert 'file1.mp3' in self.edit_manager._staged_changes
        assert self.edit_manager._staged_changes['file1.mp3']['title'] == 'New Title'

        # Verify has_staged_changes returns True
        assert self.edit_manager.has_staged_changes() is True

        # Verify signal was emitted
        assert len(spy) == 1
        assert spy[0][0] is True

    def test_stage_change_multiple_files_same_tag(self):
        """Test staging a change for multiple files with the same tag."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        file_paths = ['file1.mp3', 'file2.mp3', 'file3.mp3']
        self.edit_manager.stage_change(file_paths, 'artist', 'New Artist')

        # Verify changes were staged for all files
        for file_path in file_paths:
            assert file_path in self.edit_manager._staged_changes
            assert self.edit_manager._staged_changes[file_path]['artist'] == 'New Artist'

        # Verify signal was emitted
        assert len(spy) == 1
        assert spy[0][0] is True

    def test_stage_change_single_file_multiple_tags(self):
        """Test staging multiple changes for a single file."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Stage first change
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')

        # Stage second change
        self.edit_manager.stage_change(['file1.mp3'], 'artist', 'New Artist')

        # Verify both changes were staged
        assert self.edit_manager._staged_changes['file1.mp3']['title'] == 'New Title'
        assert self.edit_manager._staged_changes['file1.mp3']['artist'] == 'New Artist'

        # Verify signal was emitted for each stage_change call
        assert len(spy) == 2
        assert spy[0][0] is True
        assert spy[1][0] is True

    def test_stage_change_overwrites_existing_value(self):
        """Test that staging a change overwrites existing staged value."""
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'Old Title')
        assert self.edit_manager._staged_changes['file1.mp3']['title'] == 'Old Title'

        # Stage new value for same file and tag
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        assert self.edit_manager._staged_changes['file1.mp3']['title'] == 'New Title'

    def test_stage_change_different_files_different_tags(self):
        """Test staging changes for different files and different tags."""
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'Title 1')
        self.edit_manager.stage_change(['file2.mp3'], 'artist', 'Artist 2')
        self.edit_manager.stage_change(['file1.mp3'], 'album', 'Album 1')

        expected = {
            'file1.mp3': {'title': 'Title 1', 'album': 'Album 1'},
            'file2.mp3': {'artist': 'Artist 2'}
        }
        assert self.edit_manager._staged_changes == expected

    def test_stage_change_empty_file_paths(self):
        """Test staging changes with empty file paths list."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        self.edit_manager.stage_change([], 'title', 'New Title')

        # Verify no changes were staged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (signal is emitted regardless of file paths)
        assert len(spy) == 1
        assert spy[0][0] is False

    def test_commit_changes_clears_staged_changes(self):
        """Test that commit_changes clears all staged changes."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Stage some changes
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        self.edit_manager.stage_change(['file2.mp3'], 'artist', 'New Artist')
        assert self.edit_manager.has_staged_changes() is True

        # Commit changes
        self.edit_manager.commit_changes()

        # Verify staged changes were cleared
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (2 staging calls + 1 reset call)
        assert len(spy) == 3
        assert spy[0][0] is True
        assert spy[1][0] is True
        assert spy[2][0] is False

    def test_commit_changes_no_changes_staged(self):
        """Test commit_changes when no changes are staged."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Commit without any staged changes
        self.edit_manager.commit_changes()

        # Verify state remains unchanged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (reset_changes always emits signal)
        assert len(spy) == 1
        assert spy[0][0] is False

    def test_reset_changes_clears_staged_changes(self):
        """Test that reset_changes clears all staged changes."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Stage some changes
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        self.edit_manager.stage_change(['file2.mp3'], 'artist', 'New Artist')
        assert self.edit_manager.has_staged_changes() is True

        # Reset changes
        self.edit_manager.reset_changes()

        # Verify staged changes were cleared
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (2 staging calls + 1 reset call)
        assert len(spy) == 3
        assert spy[0][0] is True
        assert spy[1][0] is True
        assert spy[2][0] is False

    def test_reset_changes_no_changes_staged(self):
        """Test reset_changes when no changes are staged."""
        spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Reset without any staged changes
        self.edit_manager.reset_changes()

        # Verify state remains unchanged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (reset_changes always emits signal)
        assert len(spy) == 1
        assert spy[0][0] is False

    def test_has_staged_changes_empty_dict(self):
        """Test has_staged_changes returns False for empty staged changes."""
        assert self.edit_manager.has_staged_changes() is False

    def test_has_staged_changes_with_changes(self):
        """Test has_staged_changes returns True when changes are staged."""
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        assert self.edit_manager.has_staged_changes() is True

    def test_has_staged_changes_empty_file_dict(self):
        """Test has_staged_changes with file entry but no tags."""
        # Manually create empty dict for a file (edge case)
        self.edit_manager._staged_changes['file1.mp3'] = {}
        assert self.edit_manager.has_staged_changes() is True

    def test_signal_emissions_independence(self):
        """Test that different signals are emitted independently."""
        autosave_spy = SignalSpy(self.edit_manager.autosave_changed)
        changes_spy = SignalSpy(self.edit_manager.staged_changes_exist)

        # Change autosave - should only emit autosave_changed
        self.edit_manager.autosave = True
        assert len(autosave_spy) == 1
        assert len(changes_spy) == 0

        # Stage changes - should only emit staged_changes_exist
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        assert len(autosave_spy) == 1
        assert len(changes_spy) == 1

        # Change autosave again - should only emit autosave_changed
        self.edit_manager.autosave = False
        assert len(autosave_spy) == 2
        assert len(changes_spy) == 1

    def test_multiple_instances_share_state(self):
        """Test that multiple EditManager instances share the same state."""
        # Create second instance
        edit_manager2 = EditManager()

        # Verify they are the same object
        assert self.edit_manager is edit_manager2

        # Make changes through first instance
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'New Title')
        self.edit_manager.autosave = True

        # Verify changes are reflected in second instance
        assert edit_manager2.has_staged_changes() is True
        assert edit_manager2.autosave is True
        assert edit_manager2._staged_changes['file1.mp3']['title'] == 'New Title'

    def test_stage_change_with_various_value_types(self):
        """Test staging changes with various value types."""
        test_values = [
            'string_value',
            42,
            3.14,
            ['list', 'of', 'values'],
            {'key': 'value'},
            None,
            True,
            False
        ]

        for i, value in enumerate(test_values):
            file_path = f'file{i}.mp3'
            tag = f'tag{i}'
            self.edit_manager.stage_change([file_path], tag, value)

            assert self.edit_manager._staged_changes[file_path][tag] == value

    def test_stage_change_with_special_characters(self):
        """Test staging changes with special characters in values."""
        special_values = [
            'Title with ümlauts',
            '艺术家',  # Chinese characters
            '🎵 Musical Notes 🎵',
            'Title\nWith\nNewlines',
            'Title\tWith\tTabs',
            'Title with "quotes"',
            "Title with 'quotes'",
            'Title with /\\*?<>|',
        ]

        for i, value in enumerate(special_values):
            file_path = f'file{i}.mp3'
            self.edit_manager.stage_change([file_path], 'title', value)

            assert self.edit_manager._staged_changes[file_path]['title'] == value

    def test_stage_change_preserves_other_files_changes(self):
        """Test that staging changes for one file doesn't affect other files."""
        # Stage changes for file1
        self.edit_manager.stage_change(['file1.mp3'], 'title', 'Title 1')
        self.edit_manager.stage_change(['file1.mp3'], 'artist', 'Artist 1')

        # Stage changes for file2
        self.edit_manager.stage_change(['file2.mp3'], 'title', 'Title 2')

        # Verify file1 changes are preserved
        assert self.edit_manager._staged_changes['file1.mp3']['title'] == 'Title 1'
        assert self.edit_manager._staged_changes['file1.mp3']['artist'] == 'Artist 1'

        # Verify file2 changes are correct
        assert self.edit_manager._staged_changes['file2.mp3']['title'] == 'Title 2'
        assert 'artist' not in self.edit_manager._staged_changes['file2.mp3']

    @pytest.mark.parametrize("tag,value", [
        ('title', 'Test Title'),
        ('artist', 'Test Artist'),
        ('album', 'Test Album'),
        ('bpm', '128'),
        ('key', 'C#'),
        ('genre', 'Electronic'),
    ])
    def test_stage_change_common_metadata_tags(self, tag, value):
        """Test staging changes for common metadata tags."""
        file_path = 'test.mp3'
        self.edit_manager.stage_change([file_path], tag, value)

        assert self.edit_manager._staged_changes[file_path][tag] == value