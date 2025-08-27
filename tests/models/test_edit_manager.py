import pytest
from unittest.mock import Mock, patch
from PySide6.QtTest import QSignalSpy
from models.edit_manager import EditManager
from models.media_file import MediaFile


@pytest.fixture(autouse=True)
def mock_media_file(monkeypatch):
    """Fixture to mock MediaFile and prevent file system access."""
    def mock_init(self, file_path, enable_write=False):
        self._file_path = file_path
        self._file_id = hash(file_path)
        self.enable_write = enable_write

    def mock_get_tag_simple(self, tag_name, is_internal_tag_key=False):
        return f"mock_value_{tag_name}"

    def mock_save(self, changes):
        pass

    monkeypatch.setattr('models.media_file.MediaFile.__init__', mock_init)
    monkeypatch.setattr('models.media_file.MediaFile.get_tag_simple', mock_get_tag_simple)
    monkeypatch.setattr('models.media_file.MediaFile.save', mock_save)


class TestEditManager:
    """Comprehensive test suite for the EditManager class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Reset the singleton instance for each test
        EditManager._instance = None
        self.edit_manager = EditManager()
        # Register a dummy media file for tests that require it
        self.dummy_media_file = MediaFile('dummy.mp3')
        self.edit_manager.register_media_files([self.dummy_media_file])

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
        assert self.edit_manager.get_staged_changes_for_file(MediaFile('nonexistent.mp3')) == {'generic_tags': {}, 'internal_tags': {}}

    def test_autosave_property_getter(self):
        """Test the autosave property getter."""
        assert self.edit_manager.autosave is False

    def test_autosave_property_setter_changes_value(self):
        """Test that setting autosave property changes the internal value."""
        # Spy on the autosave_changed signal
        spy = QSignalSpy(self.edit_manager.autosave_changed)

        # Set autosave to True
        self.edit_manager.autosave = True
        assert self.edit_manager.autosave is True

        # Verify signal was emitted
        assert spy.count() == 1
        assert spy.at(0)[0] is True

    def test_autosave_property_setter_no_signal_when_unchanged(self):
        """Test that setting autosave to the same value doesn't emit signal."""
        # Set initial value
        self.edit_manager._autosave = True

        # Spy on the autosave_changed signal
        spy = QSignalSpy(self.edit_manager.autosave_changed)

        # Set the same value again
        self.edit_manager.autosave = True

        # Verify no signal was emitted
        assert spy.count() == 0

    def test_autosave_property_setter_signal_emission(self):
        """Test that autosave_changed signal is emitted when value changes."""
        spy = QSignalSpy(self.edit_manager.autosave_changed)

        # Test True -> False -> True transitions
        self.edit_manager.autosave = True
        assert spy.count() == 1
        assert spy.at(0)[0] is True

        self.edit_manager.autosave = False
        assert spy.count() == 2
        assert spy.at(1)[0] is False

        self.edit_manager.autosave = True
        assert spy.count() == 3
        assert spy.at(2)[0] is True

    def test_stage_change_single_file_single_tag(self):
        """Test staging a change for a single file and single tag."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')

        # Verify the change was staged
        assert self.dummy_media_file.file_id in self.edit_manager._staged_changes
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags']['title'] == 'New Title'
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['internal_tags'] == {}

        # Verify helper methods work correctly
        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'title') == 'New Title'
        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'title', is_internal_tag=False) == 'New Title'

        # Verify has_staged_changes returns True
        assert self.edit_manager.has_staged_changes() is True

        # Verify signal was emitted
        assert spy.count() == 1
        assert spy.at(0)[0] is True

    def test_stage_change_multiple_files_same_tag(self):
        """Test staging a change for multiple files with the same tag."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        media_file1 = MediaFile('file1.mp3')
        media_file2 = MediaFile('file2.mp3')
        media_file3 = MediaFile('file3.mp3')
        media_files = [media_file1, media_file2, media_file3]
        self.edit_manager.register_media_files(media_files)
        self.edit_manager.stage_change(media_files, 'artist', 'New Artist')

        # Verify changes were staged for all files
        for media_file in media_files:
            assert media_file.file_id in self.edit_manager._staged_changes
            assert self.edit_manager._staged_changes[media_file.file_id]['generic_tags']['artist'] == 'New Artist'
            assert self.edit_manager._staged_changes[media_file.file_id]['internal_tags'] == {}

        # Verify signal was emitted
        assert spy.count() == 1
        assert spy.at(0)[0] is True

    def test_stage_change_single_file_multiple_tags(self):
        """Test staging multiple changes for a single file."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        # Stage first change
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')

        # Stage second change
        self.edit_manager.stage_change([self.dummy_media_file], 'artist', 'New Artist')

        # Verify both changes were staged
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags']['title'] == 'New Title'
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags']['artist'] == 'New Artist'
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['internal_tags'] == {}

        # Verify signal was emitted for each stage_change call
        assert spy.count() == 2
        assert spy.at(0)[0] is True
        assert spy.at(1)[0] is True

    def test_stage_change_overwrites_existing_value(self):
        """Test that staging a change overwrites existing staged value."""
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'Old Title')
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags']['title'] == 'Old Title'

        # Stage new value for same file and tag
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags']['title'] == 'New Title'

    def test_stage_change_different_files_different_tags(self):
        """Test staging changes for different files and different tags."""
        media_file1 = MediaFile('file1.mp3')
        media_file2 = MediaFile('file2.mp3')
        self.edit_manager.register_media_files([media_file1, media_file2])

        self.edit_manager.stage_change([media_file1], 'title', 'Title 1')
        self.edit_manager.stage_change([media_file2], 'artist', 'Artist 2')
        self.edit_manager.stage_change([media_file1], 'album', 'Album 1')

        expected = {
            media_file1.file_id: {
                'generic_tags': {'title': 'Title 1', 'album': 'Album 1'},
                'internal_tags': {}
            },
            media_file2.file_id: {
                'generic_tags': {'artist': 'Artist 2'},
                'internal_tags': {}
            }
        }
        assert self.edit_manager._staged_changes == expected

    def test_stage_change_empty_file_paths(self):
        """Test staging changes with empty file paths list."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        self.edit_manager.stage_change([], 'title', 'New Title')

        # Verify no changes were staged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (signal is emitted regardless of file paths)
        assert spy.count() == 1
        assert spy.at(0)[0] is False

    def test_commit_changes_clears_staged_changes(self):
        """Test that commit_changes clears all staged changes."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        media_file1 = MediaFile('file1.mp3')
        media_file2 = MediaFile('file2.mp3')
        self.edit_manager.register_media_files([media_file1, media_file2])

        # Stage some changes
        self.edit_manager.stage_change([media_file1], 'title', 'New Title')
        self.edit_manager.stage_change([media_file2], 'artist', 'New Artist')
        assert self.edit_manager.has_staged_changes() is True

        # Commit changes
        self.edit_manager.commit_changes()

        # Verify staged changes were cleared
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (2 staging calls + 1 reset call)
        assert spy.count() == 3
        assert spy.at(0)[0] is True
        assert spy.at(1)[0] is True
        assert spy.at(2)[0] is False

    def test_commit_changes_no_changes_staged(self):
        """Test commit_changes when no changes are staged."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        # Commit without any staged changes
        self.edit_manager.commit_changes()

        # Verify state remains unchanged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (reset_changes always emits signal)
        assert spy.count() == 1
        assert spy.at(0)[0] is False

    def test_reset_changes_clears_staged_changes(self):
        """Test that reset_changes clears all staged changes."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        media_file1 = MediaFile('file1.mp3')
        media_file2 = MediaFile('file2.mp3')
        self.edit_manager.register_media_files([media_file1, media_file2])

        # Stage some changes
        self.edit_manager.stage_change([media_file1], 'title', 'New Title')
        self.edit_manager.stage_change([media_file2], 'artist', 'New Artist')
        assert self.edit_manager.has_staged_changes() is True

        # Reset changes
        self.edit_manager.reset_changes()

        # Verify staged changes were cleared
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (2 staging calls + 1 reset call)
        assert spy.count() == 3
        assert spy.at(0)[0] is True
        assert spy.at(1)[0] is True
        assert spy.at(2)[0] is False

    def test_reset_changes_no_changes_staged(self):
        """Test reset_changes when no changes are staged."""
        spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        # Reset without any staged changes
        self.edit_manager.reset_changes()

        # Verify state remains unchanged
        assert self.edit_manager._staged_changes == {}
        assert self.edit_manager.has_staged_changes() is False

        # Verify signal was emitted (reset_changes always emits signal)
        assert spy.count() == 1
        assert spy.at(0)[0] is False

    def test_has_staged_changes_empty_dict(self):
        """Test has_staged_changes returns False for empty staged changes."""
        assert self.edit_manager.has_staged_changes() is False

    def test_has_staged_changes_with_changes(self):
        """Test has_staged_changes returns True when changes are staged."""
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')
        assert self.edit_manager.has_staged_changes() is True

    def test_has_staged_changes_empty_file_dict(self):
        """Test has_staged_changes with file entry but no tags."""
        # Manually create empty dict for a file (edge case)
        self.edit_manager._staged_changes[self.dummy_media_file.file_id] = {'generic_tags': {}, 'internal_tags': {}}
        assert self.edit_manager.has_staged_changes() is False

    def test_has_staged_changes_empty_tags_dicts(self):
        """Test has_staged_changes with empty tag dictionaries."""
        # Manually create file entry with empty tag dicts
        self.edit_manager._staged_changes[self.dummy_media_file.file_id] = {'generic_tags': {}, 'internal_tags': {}}
        assert self.edit_manager.has_staged_changes() is False

    def test_signal_emissions_independence(self):
        """Test that different signals are emitted independently."""
        autosave_spy = QSignalSpy(self.edit_manager.autosave_changed)
        changes_spy = QSignalSpy(self.edit_manager.staged_changes_exist)

        # Change autosave - should only emit autosave_changed
        self.edit_manager.autosave = True
        assert autosave_spy.count() == 1
        assert changes_spy.count() == 0

        # Stage changes - should only emit staged_changes_exist
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')
        assert autosave_spy.count() == 1
        assert changes_spy.count() == 1

        # Change autosave again - should only emit autosave_changed
        self.edit_manager.autosave = False
        assert autosave_spy.count() == 2
        assert changes_spy.count() == 1

    def test_multiple_instances_share_state(self):
        """Test that multiple EditManager instances share the same state."""
        # Create second instance
        edit_manager2 = EditManager()

        # Verify they are the same object
        assert self.edit_manager is edit_manager2

        # Make changes through first instance
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'New Title')
        self.edit_manager.autosave = True

        # Verify changes are reflected in second instance
        assert edit_manager2.has_staged_changes() is True
        assert edit_manager2.autosave is True
        assert edit_manager2._staged_changes[self.dummy_media_file.file_id]['generic_tags']['title'] == 'New Title'

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
            media_file = MediaFile(f'file{i}.mp3')
            self.edit_manager.register_media_files([media_file])
            tag = f'tag{i}'
            self.edit_manager.stage_change([media_file], tag, value)

            assert self.edit_manager._staged_changes[media_file.file_id]['generic_tags'][tag] == value

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
            media_file = MediaFile(f'file{i}.mp3')
            self.edit_manager.register_media_files([media_file])
            self.edit_manager.stage_change([media_file], 'title', value)

            assert self.edit_manager._staged_changes[media_file.file_id]['generic_tags']['title'] == value

    def test_stage_change_preserves_other_files_changes(self):
        """Test that staging changes for one file doesn't affect other files."""
        media_file1 = MediaFile('file1.mp3')
        media_file2 = MediaFile('file2.mp3')
        self.edit_manager.register_media_files([media_file1, media_file2])

        # Stage changes for file1
        self.edit_manager.stage_change([media_file1], 'title', 'Title 1')
        self.edit_manager.stage_change([media_file1], 'artist', 'Artist 1')

        # Stage changes for file2
        self.edit_manager.stage_change([media_file2], 'title', 'Title 2')

        # Verify file1 changes are preserved
        assert self.edit_manager._staged_changes[media_file1.file_id]['generic_tags']['title'] == 'Title 1'
        assert self.edit_manager._staged_changes[media_file1.file_id]['generic_tags']['artist'] == 'Artist 1'

        # Verify file2 changes are correct
        assert self.edit_manager._staged_changes[media_file2.file_id]['generic_tags']['title'] == 'Title 2'
        assert 'artist' not in self.edit_manager._staged_changes[media_file2.file_id]['generic_tags']

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
        media_file = MediaFile('test.mp3')
        self.edit_manager.register_media_files([media_file])
        self.edit_manager.stage_change([media_file], tag, value)

        assert self.edit_manager._staged_changes[media_file.file_id]['generic_tags'][tag] == value

    def test_stage_change_internal_tag_without_provider_raises_error(self):
        """Test that staging an internal tag without provider raises ValueError."""
        with pytest.raises(ValueError, match="Provider must be specified for internal tag"):
            self.edit_manager.stage_change([self.dummy_media_file], 'TIT2', 'Title', is_internal_tag=True)

    def test_stage_change_internal_tag_with_provider(self):
        """Test staging changes for internal tags with provider context."""
        # Create a mock provider
        mock_provider = Mock()

        self.edit_manager.stage_change([self.dummy_media_file], 'TIT2', 'New Title', is_internal_tag=True, provider=mock_provider)

        # Verify the change was staged correctly
        assert self.dummy_media_file.file_id in self.edit_manager._staged_changes
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['generic_tags'] == {}
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['internal_tags']['TIT2']['value'] == 'New Title'
        assert self.edit_manager._staged_changes[self.dummy_media_file.file_id]['internal_tags']['TIT2']['provider'] is mock_provider

    def test_get_staged_value_for_generic_tag(self):
        """Test getting staged value for generic tags."""
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'Test Title')

        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'title') == 'Test Title'
        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'title', is_internal_tag=False) == 'Test Title'
        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'title', is_internal_tag=True) is None

    def test_get_staged_value_for_internal_tag(self):
        """Test getting staged value for internal tags."""
        mock_provider = Mock()
        self.edit_manager.stage_change([self.dummy_media_file], 'TIT2', 'Test Title', is_internal_tag=True, provider=mock_provider)

        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'TIT2', is_internal_tag=True) == 'Test Title'
        assert self.edit_manager.get_staged_value(self.dummy_media_file, 'TIT2', is_internal_tag=False) is None

    def test_get_staged_value_nonexistent_file(self):
        """Test getting staged value for nonexistent file returns None."""
        assert self.edit_manager.get_staged_value(MediaFile('nonexistent.mp3'), 'title') is None

    def test_get_staged_changes_for_file(self):
        """Test getting all staged changes for a specific file."""
        # Stage some changes
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'Test Title')
        mock_provider = Mock()
        self.edit_manager.stage_change([self.dummy_media_file], 'TIT2', 'Internal Title', is_internal_tag=True, provider=mock_provider)

        changes = self.edit_manager.get_staged_changes_for_file(self.dummy_media_file)
        expected = {
            'generic_tags': {'title': 'Test Title'},
            'internal_tags': {'TIT2': {'value': 'Internal Title', 'provider': mock_provider}}
        }
        assert changes == expected

    def test_commit_changes_emits_signal_with_provider_context(self):
        """Test that commit_changes emits signal with provider context."""
        # Stage some changes
        self.edit_manager.stage_change([self.dummy_media_file], 'title', 'Test Title')
        mock_provider = Mock()
        self.edit_manager.stage_change([self.dummy_media_file], 'TIT2', 'Internal Title', is_internal_tag=True, provider=mock_provider)

        # Spy on the commit_requested signal
        spy = QSignalSpy(self.edit_manager.commit_requested)

        # Commit changes
        self.edit_manager.commit_changes()

        # Verify signal was emitted with correct data
        assert spy.count() == 1
        commit_data = spy.at(0)[0]

        assert self.dummy_media_file.file_id in commit_data
        assert commit_data[self.dummy_media_file.file_id]['generic_tags']['title'] == 'Test Title'
        assert commit_data[self.dummy_media_file.file_id]['internal_tags']['TIT2']['value'] == 'Internal Title'
        assert commit_data[self.dummy_media_file.file_id]['internal_tags']['TIT2']['provider'] is mock_provider