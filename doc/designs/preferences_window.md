# User Preferences Window Design Specification

## Overview

The User Preferences Window provides a centralized interface for users to configure application-wide settings. It features a two-level category structure with a sidebar navigation and preference panes containing widgets for each setting. All preferences are persisted using Qt's QSettings system.

## Design Decisions Summary

1. **Window Type**: Modal dialog that blocks interaction with main window
2. **Category Levels**: Two-level structure (sidebar categories + optional tabs within panes)
3. **Validation**: Real-time validation on field change with visual feedback (red background + error message)
4. **Save Strategy**: "Save", "Cancel", and "Reset to Default..." buttons; validation errors prevent saving
5. **Reset Behavior**: "Reset to Default..." button shows confirmation dialog before clearing all settings
6. **Dirty State**: No confirmation on Cancel with unsaved changes
7. **Settings Storage**: Uses existing QSettings via new `GeneralSettings` dataclass and existing `AnalyzerSettings.category_options`
8. **Category Architecture**: Plugin-style pane registration for extensibility
9. **Icons**: Qt built-in icons with support for custom icons
10. **Window Geometry**: Default 800x600, minimum 600x400, centered on screen (not persisted)
11. **Keyboard Shortcuts**: Esc for Cancel, Ctrl+S (Cmd+S on Mac) for Save
12. **Mac Menu**: macOS automatically handles Preferences menu placement

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Preferences Window                        │
│  ┌──────────────┬──────────────────────────────────────┐    │
│  │  Category    │                                       │    │
│  │  Sidebar     │      Preference Pane Area             │    │
│  │              │                                       │    │
│  │  [General]   │  ┌─────────────────────────────────┐ │    │
│  │   Metadata   │  │  Active Pane (e.g., General)    │ │    │
│  │              │  │  - Widgets for each preference  │ │    │
│  │              │  │  - Optional tabs for subcats    │ │    │
│  │              │  │  - Validation feedback          │ │    │
│  │              │  └─────────────────────────────────┘ │    │
│  │              │                                       │    │
│  └──────────────┴──────────────────────────────────────┘    │
│                                                              │
│  [Reset to Default...]          [Cancel]  [Save]            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Opens Preferences
       ↓
PreferencesWindow loads
       ↓
For each registered pane:
   pane.load_from_settings()
       ↓
User edits widgets
       ↓
Widget validates on change
   → Shows error if invalid
       ↓
User clicks "Save"
       ↓
Validate all panes
   → If any invalid, prevent save
   → Show error message
       ↓
If all valid:
   For each pane:
      pane.save_to_settings()
       ↓
   Close window
```

## Core Components

### 1. PreferencesWindow

**Location**: `src/windows/preferences_window.py`

**Purpose**: Main container window that manages category navigation and preference panes.

**Responsibilities**:
- Create modal dialog with 800x600 default size, 600x400 minimum
- Center window on screen (do not persist geometry)
- Maintain list of registered preference panes
- Display QListWidget sidebar (200px wide, 24x24 icons) for category navigation
- Display QStackedWidget for pane area
- Populate sidebar with pane names and icons
- Switch displayed pane when sidebar selection changes
- Implement "Reset to Default...", "Cancel", and "Save" buttons
- On initialization: load all panes from settings
- On Save: validate all panes, show error dialog if any invalid, save all if valid, then close
- On Cancel: close without saving
- On Reset: show confirmation dialog, if confirmed clear all settings and reload panes with defaults
- Setup keyboard shortcuts: Esc for Cancel, QKeySequence.Save for Save

**Pane Registration**:
- Import GeneralPane and MetadataPane
- Create instances in `_register_panes()`
- Future: could use dynamic discovery pattern

**Key Design Points**:
- Modal dialog prevents interaction with main window
- Two-column layout: category list + pane stack
- Validates all panes before saving
- Centered on screen using QScreen.availableGeometry()

### 2. PreferencePaneBase (Abstract Base Class)

**Location**: `src/windows/preferences/base.py`

**Purpose**: Defines the interface all preference panes must implement.

**Required Methods**:
- `get_name() -> str`: Return display name for category (e.g., "General", "Metadata")
- `get_icon() -> QIcon`: Return icon for sidebar (use Qt standard icons or custom)
- `load_from_settings() -> None`: Read from QSettings and populate all widgets
- `save_to_settings() -> None`: Write widget values to QSettings
- `validate() -> Tuple[bool, str]`: Return (is_valid, error_message). Empty string if valid.
- `load_defaults() -> None`: Set all widgets to their default values (without writing to QSettings)

**Optional Methods**:
- `has_changes() -> bool`: Return True if settings differ from saved values (future enhancement)

**Inheritance**:
- Inherits from QWidget (for use in QStackedWidget)
- Uses ABC for abstract methods

**Key Design Points**:
- Abstract base class enforces consistent interface
- Validation returns tuple for detailed error reporting
- Each pane is responsible for its own QSettings keys

### 3. GeneralPane

**Location**: `src/windows/preferences/general_pane.py`

**Purpose**: Preference pane for general application settings.

**Settings Structure**:
Add to `src/models/settings.py`:
```
GeneralSettings dataclass:
  - startup_directory_mode: str = "last"  # "last" or "preferred"
  - preferred_directory: str = ""
  - preferred_audio_device: str = ""  # empty = system default
  - ui_skin: str = ""  # empty = system default
```

**UI Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  General Preferences                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Startup Directory                                      │
│  ○ Remember last directory                              │
│  ○ Always use this directory:                           │
│     [/path/to/preferred/dir        ] [Browse...]        │
│                                                         │
│  Playback                                               │
│  Preferred audio device:                                │
│  [System Default                   ▼]                   │
│                                                         │
│  Appearance                                             │
│  UI Skin:                                               │
│  [Windows                          ▼]                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Widgets**:
- **Startup Directory** (QGroupBox):
  - Two QRadioButtons: "Remember last directory" / "Always use this directory"
  - QLineEdit for directory path (disabled unless second radio selected)
  - QPushButton "Browse..." (disabled unless second radio selected, opens QFileDialog.getExistingDirectory)
  - Radio button toggled signal enables/disables path field and browse button

- **Playback** (QGroupBox):
  - QLabel "Preferred audio device:"
  - QComboBox with "System Default" (data="") as first item, then dynamic devices from audio subsystem

- **Appearance** (QGroupBox):
  - QLabel "UI Skin:"
  - QComboBox with "System Default" (data="") as first item, then QStyleFactory.keys()

**Icon**: Qt standard icon SP_ComputerIcon

**QSettings Keys**:
- `General/StartupDirectoryMode`: "last" | "preferred"
- `General/PreferredDirectory`: path string
- `General/PreferredAudioDevice`: device ID or empty
- `General/UiSkin`: style name or empty

**Validation**:
- If "Always use this directory" is selected, preferred_directory must not be empty
- Return error: "Please select a preferred directory or choose 'Remember last directory'"

**Audio Device Population**:
- Add "System Default" with empty data
- Call audio subsystem's `get_available_audio_devices()` (returns list of (name, id) tuples)
- If saved device not found on load, reset to index 0 (system default)

**UI Skin Population**:
- Add "System Default" with empty data
- Iterate QStyleFactory.keys() and add each
- If saved skin not found on load, reset to index 0 (system default)

**Key Design Points**:
- Uses QGroupBox for logical grouping
- Radio buttons control enable/disable state via toggled signal
- Falls back to system defaults if saved values unavailable
- Browse button uses QFileDialog.getExistingDirectory

### 4. MetadataPane

**Location**: `src/windows/preferences/metadata_pane.py`

**Purpose**: Preference pane for metadata and analyzer settings.

**Settings Structure**:
No new dataclass needed - uses existing `AnalyzerSettings`:
- `AnalyzerSettings.preferred_analyzers`: Dict[category, analyzer_class_name]
- `AnalyzerSettings.category_options[category]`: Dict of category-specific options

**UI Layout**:
```
┌────────────────────────────────────────────────────────────────┐
│  Metadata Preferences                                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Preferred Analyzers                                           │
│  BPM:          [LibRosa BPM Analyzer              ▼]           │
│  Key:          [KeyFinder Analyzer                ▼]           │
│  Loudness:     [ReplayGain Analyzer               ▼]           │
│  MusicBrainz:  [AcoustID Analyzer                 ▼]           │
│                                                                │
│  BPM Detection                                                 │
│  Detection range:  [Hip Hop / Trap (55-118)      ▼]            │
│  Custom range:     [80] to [200] BPM                           │
│  Decimal places:   [⯅0⯆]                                       │
│                                                                │
│  Musical Key                                                   │
│  Notation format:                                              │
│  [Standard with abbreviations (Cmin, Amaj)       ▼]            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Widgets**:

- **Preferred Analyzers** (QGroupBox):
  - Get categories from `get_all_categories()`
  - For each category: create row with QLabel (category name uppercase + ":") and QComboBox
  - Populate each combo from `get_analyzers_by_category(category)` with analyzer.name (data=analyzer.__name__)
  - Store combos in dict: `self.analyzer_combos[category] = combo`

- **BPM Detection** (QGroupBox):
  - **Detection range**: QComboBox with presets (see below)
  - **Custom range**: Two ValidatedLineEdit (60px wide, placeholders "Min"/"Max"), QLabel "to" between, QLabel "BPM" after
  - Error labels positioned below range inputs (120px left spacing)
  - **Decimal places**: QSpinBox (range 0-3, default 0, 60px wide)

- **Musical Key** (QGroupBox):
  - **Notation format**: QComboBox with key formats (see below)

**BPM Range Presets**:
Combo items with (display_name, (min, max)) as data:
- "Hip Hop / Trap (55-118)" → (55, 118)
- "House / Techno (65-138)" → (65, 138)
- "Trance / Dance (75-158)" → (75, 158)
- "Drum & Bass (85-178)" → (85, 178)
- "Hardstyle / Hardcore (95-198)" → (95, 198)
- "Custom" → (None, None)

**Key Notation Formats**:
Combo items with (display_name, format_id) as data:
- "Standard with abbreviations (Cmin, Amaj)" → "standard_abbrev"
- "Standard with single letter (Cm, A)" → "standard_single"
- "Camelot (6A, 8B)" → "camelot"
- "Open Key (1m, 12d)" → "open_key"

**Icon**: Qt standard icon SP_FileDialogDetailedView

**QSettings Keys**:
- `Analyzers/Preferred/{category}`: analyzer class name
- `Analyzers/CategoryOptions/bpm/range_min`: integer (1-999)
- `Analyzers/CategoryOptions/bpm/range_max`: integer (1-999)
- `Analyzers/CategoryOptions/bpm/decimal_places`: integer (0-3)
- `Analyzers/CategoryOptions/key/notation_format`: format ID string

**Default Values**:
- BPM range: 80-200
- BPM decimal places: 0
- Key notation: "standard_abbrev"

**BPM Preset Behavior**:
- When preset selected: populate min/max fields with preset values
- When min/max edited manually: validate, then check if matches any preset
  - If matches: select that preset (block signals to avoid recursion)
  - If no match: select "Custom" (block signals)

**Validation**:
- BPM min and max must be valid integers
- Both must be in range 1-999
- Min must be < Max
- Show red background + error message on invalid fields
- Error messages:
  - "Must be a number" (non-numeric)
  - "Must be 1-999" (out of range)
  - "Min must be < Max" / "Max must be > Min" (invalid relationship)
- Return validation error: "BPM detection range is invalid. Please correct the highlighted errors."

**Key Design Points**:
- Dynamically populates analyzer dropdowns from ANALYZER_REGISTRY
- BPM preset dropdown auto-populates range fields
- Editing range fields switches preset to "Custom" if no match
- Real-time validation on BPM range with visual feedback
- Uses existing AnalyzerSettings structure in QSettings

### 5. ValidatedLineEdit Widget

**Location**: `src/windows/preferences/metadata_pane.py` (can be extracted to separate file if reused)

**Purpose**: QLineEdit subclass with validation error display.

**Components**:
- QLineEdit as base
- QLabel for error message (red color, small font, initially hidden)
- Internal `_is_valid` boolean flag

**Methods**:
- `set_error(msg)`: Set invalid state, change background to light red (QPalette.Base + red.lighter(180)), show error label with message
- `clear_error()`: Reset to valid state, restore default palette, hide error label
- `is_valid()`: Return current validity state

**Usage Pattern**:
- Create ValidatedLineEdit instance
- Place error_label in layout below/beside the edit widget
- Call `set_error()` or `clear_error()` during validation
- Check `is_valid()` before saving

**Design Rationale**: Encapsulates validation UI logic for reusability and consistency.

## Settings Storage Structure

### QSettings Keys

All settings use `QSettings("Lyjia", "Audio Metadata Tool")`.

**General Settings**:
```
General/StartupDirectoryMode = "last" | "preferred"
General/PreferredDirectory = "/path/to/directory"
General/PreferredAudioDevice = "" (system default) | "device_id"
General/UiSkin = "" (system default) | "Fusion" | "Windows" | etc.
```

**Metadata/Analyzer Settings** (existing structure):
```
Analyzers/Preferred/bpm = "LibrosaBPMAnalyzer"
Analyzers/Preferred/key = "KeyFinderAnalyzer"
Analyzers/Preferred/loudness = "ReplayGainAnalyzer"
Analyzers/Preferred/musicbrainz = "AcoustIDAnalyzer"

Analyzers/CategoryOptions/bpm/range_min = 80
Analyzers/CategoryOptions/bpm/range_max = 200
Analyzers/CategoryOptions/bpm/decimal_places = 0

Analyzers/CategoryOptions/key/notation_format = "standard_abbrev"
```

### Default Values

**General**:
- StartupDirectoryMode: "last"
- PreferredDirectory: ""
- PreferredAudioDevice: "" (system default)
- UiSkin: "" (system default)

**Metadata**:
- BPM range: 80-200
- BPM decimal places: 0
- Key notation: "standard_abbrev"
- Preferred analyzers: First available analyzer for each category

## Integration Points

### 1. MainWindow Integration

**Location**: `src/windows/main_window.py`

**Menu Integration**:
- Add "Preferences" action to File menu
- Set shortcut: Ctrl+, (automatically becomes Cmd+, on macOS)
- Connect to `_show_preferences()` method
- macOS automatically moves "Preferences" to app menu (Qt handles this)

**Show Preferences Method**:
- Create PreferencesWindow(self)
- Call dialog.exec() (modal)
- After dialog closes, call `_apply_preference_changes()`

**Apply Preference Changes**:
- Read `General/UiSkin` from QSettings
- If non-empty, apply via `QApplication.setStyle(QStyleFactory.create(ui_skin))`
- Apply other immediate-effect changes (if any)

### 2. Audio Subsystem Integration

**Required Functions** (in `src/providers/audio/`):

**get_available_audio_devices()**:
- Return list of (device_name, device_id) tuples
- Called by GeneralPane to populate dropdown

**set_preferred_audio_device(device_id)**:
- Set active audio device
- If device_id is empty string, use system default
- Return boolean success

**Startup Behavior**:
- On app startup, read `General/PreferredAudioDevice`
- Call `set_preferred_audio_device(device_id)`
- If device unavailable, fall back to system default

### 3. Analyzer Integration

**No changes needed** - MetadataPane reads/writes existing `AnalyzerSettings` structure.

**Analyzer Usage**:
Analyzers read from QSettings:
- BPM range: `Analyzers/CategoryOptions/bpm/range_min` and `range_max`
- BPM decimals: `Analyzers/CategoryOptions/bpm/decimal_places`
- Key format: `Analyzers/CategoryOptions/key/notation_format`

### 4. Startup Directory Integration

**Location**: `src/windows/main_window.py` or `src/yaamt-gui.py`

**On Application Startup**:
- Read `General/StartupDirectoryMode` from QSettings
- If "preferred":
  - Read `General/PreferredDirectory`
  - If valid directory exists, call `set_current_directory(path)`
  - Else fallback to home directory
- If "last":
  - Read `MainWindow/LastDirectory`
  - If valid directory exists, call `set_current_directory(path)`
  - Else fallback to home directory

**On Directory Change**:
- Save current path to `MainWindow/LastDirectory` in QSettings
- This ensures "last" mode always has an up-to-date value

## User Workflow

### Opening Preferences

1. User clicks **File > Preferences** (or Ctrl+,)
2. PreferencesWindow opens as modal dialog, centered on screen
3. Window loads current settings from QSettings into all panes
4. First category (General) is selected by default

### Editing Preferences

1. User clicks a category in sidebar (e.g., "Metadata")
2. Corresponding pane displays in pane area
3. User modifies widgets
4. Real-time validation occurs:
   - BPM range validates on text change
   - Invalid fields show red background + error message
   - BPM preset auto-updates to "Custom" if values don't match a preset

### Saving Preferences

1. User clicks **Save** button (or Ctrl+S)
2. Window calls `validate()` on all panes
3. If any pane returns (False, error_msg):
   - Show QMessageBox.warning: "Cannot save preferences:\n\n{error_msg}"
   - Keep window open
   - User must fix errors before retrying
4. If all panes return (True, ""):
   - Call `save_to_settings()` on all panes
   - Close window with accept()
   - MainWindow applies immediate changes (UI skin, etc.)

### Cancelling

1. User clicks **Cancel** button (or Esc)
2. Window closes immediately without saving
3. No confirmation dialog (per requirements)

### Resetting to Defaults

1. User clicks **Reset to Default...** button
2. Confirmation dialog appears: "Reset all preferences to default values? This cannot be undone."
3. If user clicks "Cancel": dialog closes, no changes made
4. If user clicks "Reset":
   - Clear all preference-related QSettings keys (both General/* and Analyzers/*)
   - Call `load_defaults()` on all panes to populate widgets with default values
   - Window remains open, allowing user to review defaults before saving
   - User must still click "Save" to persist the defaults (or "Cancel" to revert to previous settings)

## Validation Details

### BPM Range Validation

**Rules**:
- Min must be a valid integer (1-999)
- Max must be a valid integer (1-999)
- Min must be < Max

**Visual Feedback**:
- Invalid field: red background (using QPalette)
- Error message: small red text to right or below widget
- Both min and max show error if min >= max

**Error Messages**:
- "Must be a number" - non-numeric input
- "Must be 1-999" - out of range
- "Min must be < Max" / "Max must be > Min" - invalid relationship

**Validation Trigger**:
- On textChanged signal
- Clear previous errors before re-validating

### Directory Validation

**Rules**:
- If "Always use this directory" radio is selected, path must not be empty

**Visual Feedback**:
- Error dialog on save attempt (no inline validation)

**Error Message**:
- "Please select a preferred directory or choose 'Remember last directory'"

### Future Validation

Additional validations can be added using the ValidatedLineEdit pattern or similar approaches.

## Platform Considerations

### macOS

- **Menu Placement**: Qt automatically moves "Preferences" from File menu to Application menu (no special code needed)
- **Keyboard Shortcut**: Cmd+, automatically used (QKeySequence handles platform detection)
- **Dialog Style**: Modal dialog follows macOS conventions automatically

### Windows/Linux

- **Menu Placement**: Preferences remains in File menu
- **Keyboard Shortcut**: Ctrl+,
- **Dialog Style**: Native platform appearance

**No platform-specific code required** - Qt handles all differences automatically.

## Extensibility

### Adding New Preference Categories

**Steps**:

1. **Create new pane class** in `src/windows/preferences/{name}_pane.py`:
   - Inherit from PreferencePaneBase
   - Implement required abstract methods
   - Define QSettings keys
   - Create UI layout with widgets

2. **Register pane** in `PreferencesWindow._register_panes()`:
   - Import new pane class
   - Add instance to self.panes list

3. **Add settings dataclass** (if needed) to `src/models/settings.py`

### Future: Dynamic Registration

Could implement plugin-style registration using decorator pattern:
- Define PREFERENCE_PANE_REGISTRY dict
- Create `@register_preference_pane` decorator
- Auto-discover panes in `__init__.py`
- Similar to analyzer discovery system

## Testing Considerations

### Unit Testing Preference Panes

**Strategy**:
- Test each pane independently
- Mock QSettings for isolation
- Test load/save round-trip
- Test validation logic

**Example Test Pattern**:
```
test_general_pane_load_save():
  1. Create GeneralPane instance
  2. Set widget values manually
  3. Call save_to_settings()
  4. Create new GeneralPane instance
  5. Call load_from_settings()
  6. Assert widget values match original
  7. Cleanup QSettings
```

**Example Validation Test**:
```
test_bpm_range_validation():
  1. Create MetadataPane instance
  2. Set invalid values (min=150, max=100)
  3. Call validate()
  4. Assert returns (False, error_message)
  5. Assert error message contains "BPM"
  6. Set valid values (min=80, max=200)
  7. Call validate()
  8. Assert returns (True, "")
```

### Integration Testing

**Test Complete Workflow**:
- Open PreferencesWindow
- Modify multiple panes
- Trigger save
- Verify QSettings values
- Verify MainWindow applies changes

**Test Validation Blocking**:
- Set invalid value in one pane
- Attempt save
- Verify error dialog appears
- Verify window remains open
- Fix error, retry save
- Verify success

**Test Reset to Defaults**:
- Open PreferencesWindow
- Modify some settings
- Click "Reset to Default..."
- Verify confirmation dialog appears
- Click "Cancel" on confirmation
- Verify no changes to widgets
- Click "Reset to Default..." again
- Click "Reset" on confirmation
- Verify all widgets show default values
- Verify QSettings still has old values (not saved yet)
- Click "Save"
- Verify QSettings has default values
- Reopen window
- Verify all widgets still show defaults

### Qt Widget Tests

**Important**: All tests requiring QApplication must use skipif decorator:
```
@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions")
```

## File Structure

```
src/
├── windows/
│   ├── preferences_window.py          # Main preferences window
│   └── preferences/
│       ├── __init__.py
│       ├── base.py                    # PreferencePaneBase abstract class
│       ├── general_pane.py            # General preferences pane
│       └── metadata_pane.py           # Metadata preferences pane
└── models/
    └── settings.py                    # Add GeneralSettings dataclass

tests/
├── test_preferences_window.py         # Window tests
└── test_preferences_panes.py          # Individual pane tests
```

## Open Questions / Future Enhancements

1. **Settings Import/Export**: Should users be able to export/import preferences as a file?
2. **Per-Category Reset**: Should there also be a per-category reset button in addition to global reset?
3. **Search/Filter**: For many preferences, should there be a search box to filter settings?
4. **Tabs in Panes**: No current categories use tabs, but architecture supports it - when needed, add QTabWidget to pane layout
5. **Audio Device Hot-Plug**: Should preferences detect when devices are added/removed while window is open?
6. **UI Skin Preview**: Should changing UI skin show a preview before saving?
7. **Analyzer Settings Widget**: Some analyzers may want custom settings widgets in the future (via `get_settings_widget()`)

## References

- Epic: `doc/epics/20251010_User_Preferences_Window.md`
- Main Window: `src/windows/main_window.py`
- Settings Model: `src/models/settings.py`
- Analyzer System: `doc/designs/analyzer_system.md`
- QSettings: Qt documentation on application settings
