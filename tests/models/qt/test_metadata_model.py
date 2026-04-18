
import json

import pytest

from models.media_file import MediaFile
from models.qt.metadata_model import (
    MetadataTableModel,
    _format_acoustid_fingerprint_cell,
    _format_mbid_cell,
)
from util.const import (
    PROJECT_ROOT, KEY_FILE_TYPE_HUMAN, KEY_TITLE, KEY_ARTIST,
    KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_INITIAL_KEY, KEY_IS_MEDIA, KEY_TAG_GENERIC, IN_GITHUB_RUNNER
)


class TestFingerprintColumnFormatters:
    """The AcoustID Fingerprint and MBID columns synthesise their cell
    text from multiple underlying tags; pin the composite strings so a
    later refactor doesn't quietly change what the user sees."""

    def test_mbid_cell_empty_when_tag_absent(self):
        assert _format_mbid_cell(None) == ""
        assert _format_mbid_cell("") == ""

    def test_mbid_cell_checkmark_when_tag_present(self):
        assert _format_mbid_cell("abc-uuid") == "\u2713"

    def test_fingerprint_cell_empty_when_tag_absent(self):
        assert _format_acoustid_fingerprint_cell(None, None) == ""
        # Even with a score, the checkmark shouldn't appear without the
        # underlying fingerprint tag.
        assert _format_acoustid_fingerprint_cell(None, "0.9") == ""

    def test_fingerprint_cell_checkmark_without_score(self):
        assert _format_acoustid_fingerprint_cell("AQAD...", None) == "\u2713"
        assert _format_acoustid_fingerprint_cell("AQAD...", "") == "\u2713"

    def test_fingerprint_cell_checkmark_with_score_4dp(self):
        # Formatter rounds to 4 decimal places regardless of how the
        # score got stored (analyzer already truncates, but be tolerant
        # if an external tool wrote a longer value).
        assert _format_acoustid_fingerprint_cell("AQAD...", "0.9523") == "\u2713 (0.9523)"
        assert _format_acoustid_fingerprint_cell("AQAD...", "0.95234567") == "\u2713 (0.9523)"
        assert _format_acoustid_fingerprint_cell("AQAD...", 0.5) == "\u2713 (0.5000)"

    def test_fingerprint_cell_gracefully_ignores_unparseable_score(self):
        # Defensive: a garbage score shouldn't prevent the checkmark.
        assert _format_acoustid_fingerprint_cell("AQAD...", "not-a-number") == "\u2713"

# Define the directory containing the test fixtures.
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "metadata"

# Discover all audio files in the fixture directory.
# This list will be used to parameterize the test function.
test_files = [p for p in FIXTURE_DIR.glob('*') if (p.suffix == '.mp3' or p.suffix == ".flac")]

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@pytest.mark.parametrize("media_path", test_files)
def test_get_metadata_from_media_file(media_path):
    '''
    A parameterized test that verifies the get_metadata_from_media_file() method of the MetadataTableModel class.
    '''
    # Construct the path to the JSON file with the expected results.
    expected_json_path = media_path.with_suffix(media_path.suffix + '.json')

    # Load the expected results from the JSON file.
    with open(expected_json_path, 'r', encoding='utf-8') as f:
        expected_dict_nested = json.load(f)

    # Flatten the expected dictionary
    expected_dict = flatten_dict(expected_dict_nested)

    # Initialize the MediaFile object with the path to the test file.
    media_file = MediaFile(media_path)

    # Get the actual dictionary from the MetadataTableModel.
    actual_dict = MetadataTableModel.get_metadata_from_media_file(media_file)

    # Map the keys from the JSON file to the keys used in the application
    key_mapping = {
        'tags_artist_value': KEY_ARTIST,
        'tags_album_value': KEY_ALBUM,
        'tags_title_value': KEY_TITLE,
        'tags_genre_value': KEY_GENRE,
        'tags_bpm_value': KEY_BPM,
        'tags_key_value': KEY_INITIAL_KEY,
        'streaminfo_format_value': KEY_FILE_TYPE_HUMAN,
        'internal_is_media_value': KEY_IS_MEDIA,
    }

    # Create the expected dictionary with the correct keys
    expected_mapped = {}
    for json_key, app_key in key_mapping.items():
        if json_key in expected_dict:
            expected_mapped[app_key] = expected_dict[json_key]

    # Assert that the values for the mapped keys are equal
    for key, value in expected_mapped.items():
        assert actual_dict.get(key) == value, f"Mismatch for key {key}"


from PySide6.QtCore import Qt
from models.settings import ColumnSettings
from models.edit_manager import EditManager


@pytest.fixture
def columns():
    return [
        ColumnSettings(id="title", label="Title", group="tag", width=200, is_visible=True, is_writable=True),
        ColumnSettings(id="artist", label="Artist", group="tag", width=200, is_visible=True, is_writable=False),
    ]

@pytest.fixture
def edit_manager():
    return EditManager()

@pytest.fixture
def model(columns, edit_manager):
    return MetadataTableModel(columns, edit_manager)

def test_flags_editable(model):
    """Test that flags() returns ItemIsEditable for writable columns."""
    index = model.createIndex(0, 0)
    flags = model.flags(index)
    assert flags & Qt.ItemFlag.ItemIsEditable

def test_flags_not_editable(model):
    """Test that flags() does not return ItemIsEditable for non-writable columns."""
    index = model.createIndex(0, 1)
    flags = model.flags(index)
    assert not (flags & Qt.ItemFlag.ItemIsEditable)

def test_set_data(model, edit_manager):
    """Test that setData() stages a change with the EditManager."""
    media_file = MediaFile(test_files[0])
    model._data = [MetadataTableModel.get_metadata_from_media_file(media_file)]
    edit_manager._media_files = {media_file.file_id: media_file}

    index = model.createIndex(0, 0)
    new_value = "New Title"

    data_changed_emitted = False
    def on_data_changed(*args, **kwargs):
        nonlocal data_changed_emitted
        data_changed_emitted = True

    model.dataChanged.connect(on_data_changed)
    assert model.setData(index, new_value, role=Qt.ItemDataRole.EditRole)
    assert data_changed_emitted

    file_id = media_file.file_id
    assert edit_manager.has_staged_changes()
    staged_change = edit_manager.get_staged_changes(file_id)
    assert staged_change[KEY_TAG_GENERIC][KEY_TITLE] == new_value
    assert model._data[0][KEY_TITLE] == new_value

def test_set_data_not_writable(model):
    """Test that setData() returns False for non-writable columns."""
    index = model.createIndex(0, 1)
    assert not model.setData(index, "New Artist", role=Qt.ItemDataRole.EditRole)


# Tests for seamless file loading feature

def test_add_rows(model):
    """Test that add_rows() appends new rows to the model."""
    initial_count = model.rowCount()
    assert initial_count == 0

    # Add some rows
    rows_data = [
        {KEY_TITLE: "Song 1", KEY_ARTIST: "Artist 1"},
        {KEY_TITLE: "Song 2", KEY_ARTIST: "Artist 2"},
        {KEY_TITLE: "Song 3", KEY_ARTIST: "Artist 3"},
    ]

    rows_inserted_emitted = False
    def on_rows_inserted(*args, **kwargs):
        nonlocal rows_inserted_emitted
        rows_inserted_emitted = True

    model.rowsInserted.connect(on_rows_inserted)
    model.add_rows(rows_data)

    assert rows_inserted_emitted
    assert model.rowCount() == 3
    assert model._data[0][KEY_TITLE] == "Song 1"
    assert model._data[1][KEY_TITLE] == "Song 2"
    assert model._data[2][KEY_TITLE] == "Song 3"


def test_add_rows_empty_list(model):
    """Test that add_rows() handles empty list gracefully."""
    initial_count = model.rowCount()
    model.add_rows([])
    assert model.rowCount() == initial_count  # No change


def test_add_rows_incremental(model):
    """Test that add_rows() can be called multiple times."""
    model.add_rows([{KEY_TITLE: "Song 1"}])
    assert model.rowCount() == 1

    model.add_rows([{KEY_TITLE: "Song 2"}, {KEY_TITLE: "Song 3"}])
    assert model.rowCount() == 3

    model.add_rows([{KEY_TITLE: "Song 4"}])
    assert model.rowCount() == 4


def test_update_row(model):
    """Test that update_row() updates an existing row."""
    # Add initial data
    model.add_rows([
        {KEY_TITLE: "Song 1", KEY_ARTIST: "Artist 1"},
        {KEY_TITLE: "Song 2", KEY_ARTIST: "Artist 2"},
    ])

    data_changed_emitted = False
    def on_data_changed(*args, **kwargs):
        nonlocal data_changed_emitted
        data_changed_emitted = True

    model.dataChanged.connect(on_data_changed)

    # Update the second row
    new_metadata = {KEY_TITLE: "Updated Song 2", KEY_ARTIST: "Updated Artist 2", KEY_ALBUM: "Album"}
    model.update_row(1, new_metadata)

    assert data_changed_emitted
    assert model._data[1][KEY_TITLE] == "Updated Song 2"
    assert model._data[1][KEY_ARTIST] == "Updated Artist 2"
    assert model._data[1][KEY_ALBUM] == "Album"


def test_update_row_invalid_index(model, caplog):
    """Test that update_row() handles invalid indices gracefully."""
    import logging

    # The YAAMT logger has propagate=False, so we need to enable it temporarily
    yaamt_logger = logging.getLogger('YAAMT')
    original_propagate = yaamt_logger.propagate
    yaamt_logger.propagate = True

    try:
        caplog.set_level(logging.DEBUG, logger='YAAMT')

        model.add_rows([{KEY_TITLE: "Song 1"}])

        # Try to update a non-existent row
        model.update_row(5, {KEY_TITLE: "Invalid"})

        # Should log an error and not crash
        assert "Invalid row index for update" in caplog.text
        assert model.rowCount() == 1  # No change
    finally:
        # Restore original propagate setting
        yaamt_logger.propagate = original_propagate


def test_sort_with_none_values(model):
    """Test that sort() handles None values correctly."""
    # Add rows with None values
    model.add_rows([
        {KEY_TITLE: "Song C", KEY_ARTIST: "Artist C"},
        {KEY_TITLE: None, KEY_ARTIST: "Artist B"},
        {KEY_TITLE: "Song A", KEY_ARTIST: None},
    ])

    # Sort by title (ascending)
    model.sort(0, Qt.SortOrder.AscendingOrder)

    # None values should be treated as empty strings and sort first
    assert model._data[0][KEY_TITLE] is None  # None sorts before "Song A"
    assert model._data[1][KEY_TITLE] == "Song A"
    assert model._data[2][KEY_TITLE] == "Song C"


def test_sort_descending_with_none(model):
    """Test that sort() handles None values in descending order."""
    model.add_rows([
        {KEY_TITLE: "Song C", KEY_ARTIST: "Artist C"},
        {KEY_TITLE: None, KEY_ARTIST: "Artist B"},
        {KEY_TITLE: "Song A", KEY_ARTIST: None},
    ])

    # Sort by title (descending)
    model.sort(0, Qt.SortOrder.DescendingOrder)

    # In descending order, None should sort last
    assert model._data[0][KEY_TITLE] == "Song C"
    assert model._data[1][KEY_TITLE] == "Song A"
    assert model._data[2][KEY_TITLE] is None


from util.const import LOADING_PLACEHOLDER


def test_loading_placeholder_display_role(model):
    """Test that loading placeholder is returned for DisplayRole."""
    model.add_rows([{KEY_TITLE: LOADING_PLACEHOLDER, KEY_ARTIST: "Real Artist"}])

    index = model.createIndex(0, 0)  # Title column
    display_data = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert display_data == LOADING_PLACEHOLDER


def test_loading_placeholder_foreground_color(model):
    """Test that loading placeholder is displayed in gray color."""
    from PySide6.QtGui import QColor

    model.add_rows([{KEY_TITLE: LOADING_PLACEHOLDER, KEY_ARTIST: "Real Artist"}])

    index = model.createIndex(0, 0)  # Title column with placeholder
    color = model.data(index, Qt.ItemDataRole.ForegroundRole)

    assert isinstance(color, QColor)
    assert color == QColor(Qt.GlobalColor.lightGray)


def test_non_placeholder_no_gray_color(model):
    """Test that non-placeholder values don't get gray color."""
    model.add_rows([{KEY_TITLE: "Real Title", KEY_ARTIST: "Real Artist"}])

    index = model.createIndex(0, 0)  # Title column with real data
    color = model.data(index, Qt.ItemDataRole.ForegroundRole)

    assert color is None  # No special color for real data
