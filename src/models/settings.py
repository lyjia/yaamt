from dataclasses import dataclass, field
from typing import List

from PySide6.QtCore import QSettings, Qt


@dataclass
class ColumnSettings:
    """Stores the state of an individual column in the file list view."""
    id: str
    label: str
    width: int
    is_visible: bool


def _create_default_columns() -> List[ColumnSettings]:
    """Creates a default set of columns for the file list view."""
    return [
        ColumnSettings(id="name", label="Name", width=250, is_visible=True),
        ColumnSettings(id="size", label="Size", width=100, is_visible=True),
        ColumnSettings(id="type", label="Type", width=100, is_visible=True),
        ColumnSettings(id="date_modified", label="Date Modified", width=150, is_visible=True),
        ColumnSettings(id="title", label="Title", width=200, is_visible=True),
        ColumnSettings(id="artist", label="Artist", width=150, is_visible=True),
        ColumnSettings(id="album", label="Album", width=150, is_visible=True),
        ColumnSettings(id="genre", label="Genre", width=100, is_visible=True),
        ColumnSettings(id="bpm", label="BPM", width=75, is_visible=True),
        ColumnSettings(id="key", label="Key", width=75, is_visible=True),
    ]


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