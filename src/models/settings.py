from dataclasses import dataclass, field
from typing import List

from PySide6.QtCore import QSettings, Qt
from util.const import (
    COL_MAIN_NAME, COL_MAIN_SIZE, COL_MAIN_TYPE, COL_MAIN_DATE_MODIFIED,
    COL_MAIN_TITLE, COL_MAIN_ARTIST, COL_MAIN_ALBUM, COL_MAIN_GENRE,
    COL_MAIN_BPM, COL_MAIN_KEY
)

AVAILABLE_COLUMNS = {
    COL_MAIN_NAME: {"id": COL_MAIN_NAME, "label": "Filename", "width": 250, "is_visible": True},
    COL_MAIN_SIZE: {"id": COL_MAIN_SIZE, "label": "Size", "width": 100, "is_visible": True},
    COL_MAIN_TYPE: {"id": COL_MAIN_TYPE, "label": "Type", "width": 100, "is_visible": True},
    COL_MAIN_DATE_MODIFIED: {"id": COL_MAIN_DATE_MODIFIED, "label": "Date Modified", "width": 150, "is_visible": True},
    COL_MAIN_TITLE: {"id": COL_MAIN_TITLE, "label": "Title", "width": 200, "is_visible": True},
    COL_MAIN_ARTIST: {"id": COL_MAIN_ARTIST, "label": "Artist", "width": 150, "is_visible": True},
    COL_MAIN_ALBUM: {"id": COL_MAIN_ALBUM, "label": "Album", "width": 150, "is_visible": True},
    COL_MAIN_GENRE: {"id": COL_MAIN_GENRE, "label": "Genre", "width": 100, "is_visible": True},
    COL_MAIN_BPM: {"id": COL_MAIN_BPM, "label": "BPM", "width": 50, "is_visible": True},
    COL_MAIN_KEY: {"id": COL_MAIN_KEY, "label": "Key", "width": 50, "is_visible": True}
}

@dataclass
class ColumnSettings:
    """Stores the state of an individual column in the file list view."""
    id: str
    label: str
    width: int
    is_visible: bool


def _create_default_columns() -> List[ColumnSettings]:
    """Creates a default set of columns for the file list view."""
    return [ColumnSettings(**settings) for settings in AVAILABLE_COLUMNS.values()]


@dataclass
class FileListSettings:
    """Stores the settings for the file list view."""
    columns: List[ColumnSettings] = field(default_factory=_create_default_columns)
    sort_column: int = 0
    sort_order: int = Qt.SortOrder.AscendingOrder


@dataclass
class Settings:
    """Stores the main application settings."""
    file_list: FileListSettings = field(default_factory=FileListSettings)


settings = QSettings("Lyjia", "Audio Metadata Tool")