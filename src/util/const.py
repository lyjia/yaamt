import os
from pathlib import Path
from enum import Enum

KEY_STREAM_INFO = "stream_info"
KEY_TAGS = "tags"
KEY_INTERNAL = "internal"

### Metadata Model keys ####
# INTERNAL keys
KEY_IS_MEDIA = "ismedia"  # is this file a media file we care about or something else?
KEY_IS_WRITABLE = "iswritable"
KEY_FILE_ID = "file_id"

# FILESYSTEM keys
KEY_FILE_PATH = "fpath"
KEY_FILE_SIZE = "fsize"
KEY_FILE_SIZE_HUMAN = "fsizeHR"
KEY_FILE_MTIME = "fmtime"
KEY_FILE_MTIME_HUMAN = "fmtimeHR"
KEY_FILE_CTIME = "fctime"
KEY_FILE_CTIME_HUMAN = "fctimeHR"
KEY_FILE_ATIME = "fatime"  # do not use! TODO: remove me
KEY_FILE_ATIME_HUMAN = "fatimeHR"  # do not use! TODO: remove me
KEY_FILE_TYPE = "ftype"
KEY_FILE_TYPE_HUMAN = "ftypeHR"

# STREAM INFO keys
KEY_BITRATE = "bitrate"
KEY_BITRATE_MODE = 'bitrate_mode'
KEY_SAMPLE_RATE = "sample_rate"
KEY_BITS_PER_SAMPLE = "bits_per_sample"
KEY_TOTAL_SAMPLES = "total_samples"
KEY_LENGTH = "length"
KEY_CHANNELS = "channels"
KEY_FORMAT = "format"
KEY_ENCODER_INFO = 'encoder_info'
KEY_STEREO_MODE = 'stereo_mode'
KEY_REPLAYGAIN_TRACK_GAIN = 'replaygain_track_gain'
KEY_REPLAYGAIN_ALBUM_GAIN = 'replaygain_album_gain'
KEY_REPLAYGAIN_TRACK_PEAK = 'replaygain_track_peak'

# TAG KEYS
KEY_ALBUM = 'album'
KEY_ALBUM_ARTIST = 'albumartist'
KEY_ALBUM_ARTIST_SORT = 'albumartistsort'
KEY_ALBUM_SORT = 'albumsort'
KEY_ARRANGER = 'arranger'
KEY_ARTIST = 'artist'
KEY_ARTIST_SORT = 'artistsort'
KEY_AUTHOR = 'author'
KEY_BPM = 'bpm'
KEY_COMMENT = 'comment'
KEY_COMPOSER = 'composer'
KEY_COMPOSER_SORT = 'composersort'
KEY_CONDUCTOR = 'conductor'
KEY_COPYRIGHT = 'copyright'
KEY_DATE = 'date'
KEY_DIATONIC_MODE = 'diatonic_mode'
KEY_DISC_NUMBER = 'discnumber'
KEY_DISC_SUBTITLE = 'discsubtitle'
KEY_DISC_TOTAL = 'disctotal'
KEY_ENCODED_BY = 'encodedby'
KEY_GENRE = 'genre'
KEY_GROUPING = 'grouping'
KEY_INITIAL_KEY = 'initialkey'
KEY_ISRC = 'isrc'
KEY_LABEL = 'label'
KEY_LANGUAGE = 'language'
KEY_LYRICIST = 'lyricist'
KEY_MEDIA = 'media'
KEY_MOOD = 'mood'
KEY_ORGANIZATION = 'organization'
KEY_PUBLISHER = 'publisher'
KEY_REMIXER = 'remixer'
KEY_TITLE = 'title'
KEY_TITLE_SORT = 'titlesort'
KEY_TRACK_NUMBER = 'tracknumber'
KEY_TRACK_TOTAL = 'tracktotal'
KEY_VERSION = 'version'
KEY_YEAR = 'year'

# Tags that are end-user-editable text fields. Used by tag transformers to
# decide which tags should be whitespace-trimmed, empty-string-normalized, etc.
COMMON_WRITABLE_TAGS = [
    KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_ALBUM_ARTIST, KEY_COMPOSER,
    KEY_GENRE, KEY_COMMENT, KEY_COPYRIGHT, KEY_DATE, KEY_YEAR,
    KEY_TRACK_NUMBER, KEY_TRACK_TOTAL, KEY_DISC_NUMBER, KEY_DISC_TOTAL,
    KEY_ISRC, KEY_LABEL, KEY_REMIXER, KEY_LYRICIST, KEY_CONDUCTOR,
    KEY_PUBLISHER, KEY_GROUPING, KEY_BPM, KEY_INITIAL_KEY,
]

ALL_TAGS = { #display names for each tag
    KEY_ALBUM: "Album",
    KEY_ALBUM_ARTIST: "Album Artist",
    KEY_ARTIST: "Artist",
    KEY_BPM: "BPM",
    KEY_COMMENT: "Comment",
    KEY_COMPOSER: "Composer",
    KEY_DATE: "Date",
    KEY_DISC_NUMBER: "Disc",
    KEY_DISC_TOTAL: "Discs",
    KEY_ENCODED_BY: "Encoded By",
    KEY_GENRE: "Genre",
    KEY_GROUPING: "Grouping",
    KEY_INITIAL_KEY: "Key",
    KEY_ISRC: "ISRC",
    KEY_LANGUAGE: "Language",
    KEY_MOOD: "Mood",
    KEY_TITLE: "Title",
    KEY_TRACK_NUMBER: "Track",
    KEY_TRACK_TOTAL: "Tracks",
    KEY_YEAR: "Year"
}


#### END metadata model keys ####

# UI constants
LOADING_PLACEHOLDER = "⧖"  # Hourglass symbol for loading state

#### COLUMN names for file list ####
COL_MAIN_FILENAME = "filename"
COL_MAIN_SIZE = "size"
COL_MAIN_TYPE = "type"
COL_MAIN_DATE_MODIFIED = "date_modified"
COL_MAIN_DATE_CREATED = "date_created"
COL_MAIN_TITLE = KEY_TITLE
COL_MAIN_ARTIST = KEY_ARTIST
COL_MAIN_ALBUM = KEY_ALBUM
COL_MAIN_GENRE = KEY_GENRE
COL_MAIN_BPM = KEY_BPM
COL_MAIN_KEY = KEY_INITIAL_KEY

GROUP_FILE = "file"
GROUP_META = "metadata"

AVAILABLE_COLUMNS = { # for right-side file pane
    COL_MAIN_FILENAME: {"id": COL_MAIN_FILENAME, "group": GROUP_FILE, "label": "Filename", "width": 250, "is_visible": True, "is_writable": False},
    COL_MAIN_SIZE: {"id": COL_MAIN_SIZE, "group": GROUP_FILE, "label": "Size", "width": 100, "is_visible": True, "is_writable": False},
    COL_MAIN_TYPE: {"id": COL_MAIN_TYPE, "group": GROUP_FILE, "label": "Type", "width": 100, "is_visible": True, "is_writable": False},
    COL_MAIN_DATE_MODIFIED: {"id": COL_MAIN_DATE_MODIFIED, "group": GROUP_FILE, "label": "Date Modified", "width": 150, "is_visible": True, "is_writable": False},

    COL_MAIN_TITLE: {"id": COL_MAIN_TITLE, "group": GROUP_META, "label": ALL_TAGS[KEY_TITLE], "width": 200, "is_visible": True, "is_writable": True},
    COL_MAIN_ARTIST: {"id": COL_MAIN_ARTIST, "group": GROUP_META, "label": ALL_TAGS[KEY_ARTIST], "width": 150, "is_visible": True, "is_writable": True},
    COL_MAIN_ALBUM: {"id": COL_MAIN_ALBUM, "group": GROUP_META, "label": ALL_TAGS[KEY_ALBUM], "width": 150, "is_visible": True, "is_writable": True},
    COL_MAIN_GENRE: {"id": COL_MAIN_GENRE, "group": GROUP_META, "label": ALL_TAGS[KEY_GENRE], "width": 100, "is_visible": True, "is_writable": True},
    COL_MAIN_BPM: {"id": COL_MAIN_BPM, "group": GROUP_META, "label": ALL_TAGS[KEY_BPM], "width": 50, "is_visible": True, "is_writable": True},
    COL_MAIN_KEY: {"id": COL_MAIN_KEY, "group": GROUP_META, "label": ALL_TAGS[KEY_INITIAL_KEY], "width": 50, "is_visible": True, "is_writable": True}
}
#### END column names for file list ####

KEY_PROVIDER = 'provider'
KEY_ALL_PROVIDERS = 'all_providers'
KEY_AVAIL_KEYS = 'available_keys'
KEY_TAG_INTERNAL = 'internal_tags'
KEY_TAG_GENERIC = 'generic_tags'
KEY_VALUE = 'value'
KEY_ALL_VALUES = 'all_values'

PROJECT_ROOT = Path(__file__).parent.parent.parent

MAP_INTERNAL_TO_GENERIC = 'i2g'
MAP_GENERIC_TO_INTERNAL = 'g2i'

IN_GITHUB_RUNNER = (os.getenv("GITHUB_ACTIONS") == "true")

MOD_TYPE_ANALYZER = "Analyzer"

# Build mode configuration - patched by build system
IS_DEBUG_BUILD = False  # Default to debug mode; build system patches this for release builds
VERSION_STRING = None  # VERSION_STRING is updated dynamically by the build system; leave this set to None

# Application identity for QSettings
APP_ORGANIZATION_NAME = "Lyjia"
APP_APPLICATION_NAME = "YAAMT"

# BPM range presets: (display_name, (min, max))
# Used by both preferences and analyzer setup dialog
BPM_RANGE_PRESETS = [
    ("Hip Hop / Trap (55-118)", (55, 118)),
    ("House / Techno (98-138)", (98, 138)),
    ("Trance / Dance (117-151)", (117, 151)),
    ("Drum & Bass (149-181)", (149, 181)),
    ("Hardstyle / Hardcore (95-198)", (95, 198)),
    ("Custom", (None, None)),
]

#### QSettings paths ####
# Central registry of all QSettings keys and groups used by the application.
# Any new QSettings access should add its key here rather than hard-coding a
# string literal in the GUI/model code.

# Top-level groups (used with settings.beginGroup / settings.remove)
SETTINGS_GROUP_GENERAL = "General"
SETTINGS_GROUP_FAVORITES = "Favorites"
SETTINGS_GROUP_FILE_LIST = "file_list"
SETTINGS_GROUP_ANALYZERS_PREFERRED = "Analyzers/Preferred"
SETTINGS_GROUP_ANALYZERS_CATEGORY_OPTIONS = "Analyzers/CategoryOptions"
SETTINGS_GROUP_RESOURCES = "Resources"

# Sub-array keys within their groups
SETTINGS_ARRAY_FAVORITES_LOCATIONS = "locations"
SETTINGS_ARRAY_FILE_LIST_COLUMNS = "columns"

# General settings
SETTINGS_STARTUP_DIR_MODE = "General/StartupDirectoryMode"
SETTINGS_PREFERRED_DIRECTORY = "General/PreferredDirectory"
SETTINGS_PREFERRED_AUDIO_DEVICE = "General/PreferredAudioDevice"
SETTINGS_UI_SKIN = "General/UiSkin"

# Debug / playback adaptation settings
SETTINGS_DEBUG_PLAYBACK_ADAPTATION = "Debug/PlaybackFormatAdaptationEnabled"
SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE = "Debug/PlaybackSampleRate"
SETTINGS_DEBUG_PLAYBACK_CHANNELS = "Debug/PlaybackChannels"
SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH = "Debug/PlaybackSampleWidth"
SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT = "Debug/PlaybackSampleFormat"

# Analyzer category-option settings (BPM, key)
SETTINGS_BPM_RANGE_MIN = "Analyzers/CategoryOptions/bpm/range_min"
SETTINGS_BPM_RANGE_MAX = "Analyzers/CategoryOptions/bpm/range_max"
SETTINGS_BPM_DECIMAL_PLACES = "Analyzers/CategoryOptions/bpm/decimal_places"
SETTINGS_KEY_NOTATION_FORMAT = "Analyzers/CategoryOptions/key/notation_format"

# Prefix (not a complete key) for per-category preferred analyzer selection.
# Use as f"{SETTINGS_ANALYZERS_PREFERRED_PREFIX}/{category_lower}".
SETTINGS_ANALYZERS_PREFERRED_PREFIX = SETTINGS_GROUP_ANALYZERS_PREFERRED

# Resources settings
SETTINGS_RESOURCES_CACHE_ROOT = "Resources/CacheRoot"
SETTINGS_RESOURCES_CUSTOM_LOCATIONS = "Resources/CustomLocations"

# Analyzer thread pool size (not a category option, shared with thread scheduler)
SETTINGS_ANALYZERS_THREAD_POOL_SIZE = "Analyzers/thread_pool_size"

# Default values for settings
BPM_RANGE_MIN_DEFAULT = 80
BPM_RANGE_MAX_DEFAULT = 200
KEY_NOTATION_FORMAT_DEFAULT = "standard_abbrev"
STARTUP_DIR_MODE_DEFAULT = "last"

# Backwards-compatible aliases (these constants used to live in analyzer_options;
# they are re-exported here so all settings paths are discoverable in one place).
BPM_RANGE_MIN_KEY = SETTINGS_BPM_RANGE_MIN
BPM_RANGE_MAX_KEY = SETTINGS_BPM_RANGE_MAX
