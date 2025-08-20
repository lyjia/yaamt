from dataclasses import dataclass, field
from typing import List

from PySide6.QtCore import QSettings, Qt
from util.const import AVAILABLE_COLUMNS



@dataclass
class ColumnSettings:
    """Stores the state of an individual column in the file list view."""
    id: str
    group: str
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