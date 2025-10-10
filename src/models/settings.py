from dataclasses import dataclass, field
from typing import List, Dict, Any

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
    is_writable: bool = False


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
class GeneralSettings:
    """
    Stores general application settings.

    Attributes:
        startup_directory_mode: How to determine startup directory ("last" or "preferred")
        preferred_directory: Directory path when using "preferred" mode
        preferred_audio_device: Audio device ID (empty string = system default)
        ui_skin: UI style name (empty string = system default)
    """
    startup_directory_mode: str = "last"
    preferred_directory: str = ""
    preferred_audio_device: str = ""
    ui_skin: str = ""


@dataclass
class AnalyzerSettings:
    """
    Stores analyzer preferences.

    Attributes:
        preferred_analyzers: Map of category -> preferred analyzer class name
                           Example: {'bpm': 'LibrosaBPMAnalyzer', 'key': 'KeyFinderAnalyzer'}
        thread_pool_size: Thread pool size for parallel execution (default: 1 for sequential)
        category_options: Category-specific settings (e.g., key notation preference)
                         Example: {'key': {'notation': 'camelot'}}
    """
    preferred_analyzers: Dict[str, str] = field(default_factory=dict)
    thread_pool_size: int = 1
    category_options: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class Settings:
    """Stores the main application settings."""
    file_list: FileListSettings = field(default_factory=FileListSettings)
    general: GeneralSettings = field(default_factory=GeneralSettings)
    analyzers: AnalyzerSettings = field(default_factory=AnalyzerSettings)


settings = QSettings("Lyjia", "Audio Metadata Tool")