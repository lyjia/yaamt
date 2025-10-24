# CLI Refactor Design

**Epic:** Major CLI refactor to support verb-based commands and dynamic analyzer options
## Overview

This design document outlines a major refactor of the command-line interface (`src/yaamt.py`) to:
1. Implement a verb-based command structure (similar to git, chmod)
2. Create a declarative option system that works for both CLI and GUI
3. Enable dynamic discovery of analyzer options without code duplication

## Problem Statement

The current CLI has several limitations:
- Simple flat argument structure doesn't scale well
- Analyzer options are hard-coded in GUI widgets with no CLI access
- No way to list available analyzers or get help on specific analyzers
- No support for analyzer-specific command-line arguments
- Code duplication between GUI and CLI for similar functionality

## Goals

1. Create a unified option metadata system used by both CLI and GUI
2. Implement hierarchical verb-based commands (help, list, read, write, analyze)
3. Support dynamic analyzer option discovery and help generation
4. Maintain backward compatibility with QSettings for GUI preferences
5. Follow Unix command-line conventions

## Architecture

### 1. Declarative Option System

**New File:** `src/util/analyzer_options.py`

Create an `AnalyzerOption` dataclass that serves as the single source of truth for all analyzer options:

```python
@dataclass
class AnalyzerOption:
    """Metadata describing a single analyzer option."""
    name: str              # Option key (e.g., 'buf_size', 'method')
    type: str              # 'int', 'float', 'bool', 'choice', 'slider'
    default: Any           # Default value
    help: str              # Description for CLI help and GUI tooltips
    choices: List[Any] = None      # Valid values for 'choice' type
    min: Optional[float] = None    # Minimum value for numeric types
    max: Optional[float] = None    # Maximum value for numeric types
    interval: Optional[float] = None  # Step size for sliders/spinboxes
    suffix: Optional[str] = None   # Display suffix (e.g., '%', 'ms', 'Hz')
```

**Option Types:**
- `'int'` / `'float'`: Numeric values
- `'bool'`: Boolean checkboxes
- `'choice'`: Dropdown selection from predefined values
- `'slider'`: Numeric slider (forces QSlider + QSpinBox in GUI)

**Helper Functions:**

```python
def build_widget_from_option(option: AnalyzerOption,
                            settings_group: str = None) -> QWidget:
    """
    Auto-generate appropriate Qt widget from option metadata.

    Widget Selection Logic:
    - type='slider' → QSlider + QSpinBox (horizontal layout)
    - type='int'/'float' with min/max/interval → QSlider + QSpinBox
    - type='int'/'float' without interval → QSpinBox only
    - type='bool' → QCheckBox
    - type='choice' → QComboBox

    Args:
        option: The AnalyzerOption to create a widget for
        settings_group: Optional QSettings group for loading saved values

    Returns:
        QWidget configured based on option metadata
    """

def add_option_to_argparse(parser: ArgumentParser,
                          option: AnalyzerOption) -> None:
    """
    Add option to argparse parser with appropriate type and validation.

    Argparse Argument Mapping:
    - type='int' → type=int, metavar='N'
    - type='float' → type=float, metavar='F'
    - type='bool' → action='store_true'/'store_false'
    - type='choice' → choices=[...], type inferred from choices
    - type='slider' → same as 'int'/'float'

    Args:
        parser: ArgumentParser or subparser to add option to
        option: The AnalyzerOption to add
    """
```

### 2. Update Analyzer Base Class

**File:** `src/providers/analysis/base.py`

Add new class method to `AnalyzerBase`:

```python
@classmethod
def get_options_metadata(cls) -> List[AnalyzerOption]:
    """
    Return metadata about this analyzer's configurable options.

    Subclasses should override this to define their specific options.
    This metadata is used by both CLI (argparse) and GUI (widget generation).

    Returns:
        List of AnalyzerOption instances defining this analyzer's options
    """
    return []
```

Modify existing `get_settings_widget()` method:

```python
@classmethod
def get_settings_widget(cls) -> Optional[QWidget]:
    """
    Return a QWidget for analyzer-specific settings.

    Default implementation: auto-generate widget from get_options_metadata().

    Subclasses can:
    1. Use default auto-generation (don't override)
    2. Override for custom layout but use build_widget_from_option() helper
       to maintain consistency with option metadata

    Returns:
        QWidget instance or None if no options
    """
    options = cls.get_options_metadata()
    if not options:
        return None

    widget = QWidget()
    layout = QVBoxLayout()

    settings_group = f"analyzers/{cls.__name__}"
    for option in options:
        option_widget = build_widget_from_option(option, settings_group)
        layout.addWidget(option_widget)

    widget.setLayout(layout)
    return widget
```

### 3. Update All Analyzers

Each analyzer must implement `get_options_metadata()` to define its options.

**Example: AubioBPMAnalyzer**

```python
@classmethod
def get_options_metadata(cls) -> List[AnalyzerOption]:
    return [
        AnalyzerOption(
            name='method',
            type='choice',
            default='default',
            help='Beat detection algorithm used for onset detection',
            choices=['default', 'specdiff', 'energy', 'hfc', 'complex',
                    'phase', 'wphase', 'kl', 'mkl', 'specflux']
        ),
        AnalyzerOption(
            name='mode',
            type='choice',
            default='default',
            help='Processing preset for speed vs quality tradeoff',
            choices=[
                ('default', 'Default (balanced speed/quality)'),
                ('fast', 'Fast (lower quality, faster processing)')
            ]
        ),
        AnalyzerOption(
            name='buf_size',
            type='int',
            default=1024,
            min=128,
            max=8192,
            interval=128,
            help='Size of analysis window in samples (larger = more accurate but slower)'
        ),
        AnalyzerOption(
            name='hop_size',
            type='int',
            default=512,
            min=64,
            max=4096,
            interval=64,
            help='Number of samples between analysis windows (smaller = more precise but slower)'
        ),
        AnalyzerOption(
            name='samplerate',
            type='int',
            default=0,
            min=0,
            max=192000,
            interval=1000,
            help='Target sample rate for analysis (0 = use file\'s native rate)'
        )
    ]
```

**Example: WaveletKeyAnalyzer (with custom widget)**

```python
@classmethod
def get_options_metadata(cls) -> List[AnalyzerOption]:
    return [
        AnalyzerOption(
            name='percent_audio_samples_to_process',
            type='slider',
            default=100,
            min=10,
            max=100,
            interval=10,
            suffix='%',
            help='Percentage of audio to analyze (lower = faster but less accurate)'
        ),
        AnalyzerOption(
            name='intelligent_sampling',
            type='bool',
            default=True,
            help='Use sectional sampling (intro/middle/outro) vs uniform interval sampling'
        )
    ]

@classmethod
def get_settings_widget(cls) -> Optional[QWidget]:
    """Custom widget with additional styling and info labels."""
    widget = QWidget()
    layout = QVBoxLayout()

    # Add custom info label
    info_label = QLabel(
        "This analyzer uses the RapidEvolution3 wavelet-based key detection algorithm."
    )
    info_label.setWordWrap(True)
    info_label.setStyleSheet("color: gray; font-size: 10px;")
    layout.addWidget(info_label)

    # Use helper for controls (maintains consistency with metadata)
    settings_group = f"analyzers/{cls.__name__}"
    for option in cls.get_options_metadata():
        # Can wrap in QGroupBox or add labels as needed
        if option.name == 'percent_audio_samples_to_process':
            group = QGroupBox("Analysis Speed vs Accuracy")
            group_layout = QVBoxLayout()

            desc = QLabel("Adjust the percentage of audio to analyze...")
            desc.setWordWrap(True)
            group_layout.addWidget(desc)

            option_widget = build_widget_from_option(option, settings_group)
            group_layout.addWidget(option_widget)

            group.setLayout(group_layout)
            layout.addWidget(group)
        else:
            option_widget = build_widget_from_option(option, settings_group)
            layout.addWidget(option_widget)

    widget.setLayout(layout)
    return widget
```

### 4. Command-Line Structure

**New Structure:**

```bash
yaamt.py [global_options] <verb> [subverb] [options] <paths...>

Global Options (before verb):
  --verbose, -v         Enable verbose output
  --version            Show version and exit

Verbs:
  help [verb] [subverb]              Show help for commands/analyzers
  list <type> [filter]               List available modules
  read [options] <paths...>          Read and display metadata
  write [options] <paths...>         Write metadata to files
  analyze <analyzer> [options] <paths...>  Analyze audio files
```

**File Arguments:**
- Always come after all options
- Supports multiple paths
- Paths can be files or directories
- `-R/--recursive` flag controls directory scanning

### 5. Command Details

#### 5.1 `help` Command

```bash
# Main help
yaamt.py help

# Command-specific help
yaamt.py help read
yaamt.py help write
yaamt.py help analyze

# Analyzer list with descriptions
yaamt.py help analyze

# Analyzer-specific help with options
yaamt.py help analyze AubioBPMAnalyzer
yaamt.py help analyze WaveletKeyAnalyzer
```

**Implementation:**
- Dynamically generate analyzer help from `get_options_metadata()`
- Show option name, type, default, valid range/choices, help text
- Group common options vs analyzer-specific options

**Example Output:**

```
Usage: yaamt.py analyze AubioBPMAnalyzer [options] <paths...>

Detects tempo using aubio's beat tracking algorithm

Common Options:
  -R, --recursive           Scan subdirectories
  -w, --write-tags          Write results to file metadata
  -f, --output-format       Output format: json, csv, table (default: table)
  -o, --output-file FILE    Write output to file instead of stdout
  --overwrite-existing      Overwrite existing metadata values
  --threads N               Thread pool size (default: 1)
  --use-saved-prefs         Load options from GUI preferences

Analyzer Options:
  --method {default,specdiff,energy,...}
      Beat detection algorithm (default: default)

  --mode {default,fast}
      Processing preset (default: default)

  --buf-size N
      Analysis window size in samples (default: 1024, range: 128-8192)

  --hop-size N
      Samples between windows (default: 512, range: 64-4096)

  --samplerate N
      Target sample rate, 0=native (default: 0, range: 0-192000)
```

#### 5.2 `list` Command

```bash
# List all analyzers
yaamt.py list analyzers

# Filter by category
yaamt.py list analyzers bpm
yaamt.py list analyzers key
yaamt.py list analyzers loudness
```

**Output Format:**

```
BPM Analyzers:
  StubBPMAnalyzer (v0.1.0)
    Test analyzer that returns a fixed BPM value

  AubioBPMAnalyzer (v1.0.0)
    Detects tempo using aubio's beat tracking algorithm

  MultibandSpectralBPMAnalyzer (v1.0.0)
    Multi-band spectral flux BPM detection with onset detection

Key Analyzers:
  WaveletKeyAnalyzer (v1.0.0)
    RapidEvolution3 wavelet-based key detection algorithm

Loudness Analyzers:
  PeakMeterAnalyzer (v1.0.0)
    Peak level and RMS loudness measurement
```

#### 5.3 `read` Command

```bash
yaamt.py read [options] <paths...>

Options:
  -R, --recursive               Scan subdirectories
  -f, --output-format FORMAT    Output format: json, csv, table (default: table)
  -o, --output-file FILE        Write to file instead of stdout
  --tags TAG1,TAG2,...          Show only specified tags
  --all-tags                    Show all tags (default)
  --stream-info                 Include stream information
  --internal                    Include internal file info
```

**Examples:**

```bash
# Read all metadata
yaamt.py read song.mp3

# Read specific tags only
yaamt.py read --tags title,artist,bpm *.mp3

# Export to CSV
yaamt.py read -f csv -o metadata.csv music/

# Recursive scan with JSON output
yaamt.py read -R -f json /music > all_metadata.json
```

#### 5.4 `write` Command

```bash
yaamt.py write [options] <paths...>

Options:
  -R, --recursive          Scan subdirectories
  --tag KEY=VALUE          Set tag (can be used multiple times)

  Tag Shortcuts:
  --title VALUE            Set title
  --artist VALUE           Set artist
  --album VALUE            Set album
  --bpm VALUE              Set BPM
  --initial-key VALUE      Set musical key
  ... (all tags from ALL_TAGS)
```

**Examples:**

```bash
# Set title on single file
yaamt.py write --title "My Song" song.mp3

# Set multiple tags on multiple files
yaamt.py write --artist "DJ Name" --bpm 128 song1.mp3 song2.mp3

# Set tags on all files in directory
yaamt.py write -R --album "My Album" /music/album/
```

**Behavior:**
- All specified tags are written to all specified files
- Uses `EditManager` for safe writes
- Shows success/error for each file

#### 5.5 `analyze` Command

```bash
yaamt.py analyze <AnalyzerClassName> [options] <paths...>

Common Options:
  -R, --recursive              Scan subdirectories
  -w, --write-tags             Write results to file metadata (default: off)
  -f, --output-format FORMAT   Display format: json, csv, table (default: table)
  -o, --output-file FILE       Write output to file instead of stdout
  --overwrite-existing         Overwrite existing metadata values
  --threads N                  Thread pool size (default: 1)
  --use-saved-prefs            Load analyzer options from GUI preferences

Analyzer-Specific Options:
  (Dynamically added based on analyzer's get_options_metadata())
```

**Implementation:**
1. Use `get_analyzer_by_name()` to find analyzer class
2. Use `get_options_metadata()` to dynamically add argparse options
3. If `--use-saved-prefs` is set, load values from QSettings
4. Create `AnalysisTask` objects
5. Use `AnalyzerDispatcher` for execution
6. Format and display results

**Output Format:**

Table format shows filepath, analyzer results, and status:

```
File                          | AubioBPMAnalyzer_bpm | Status
------------------------------|---------------------|------------------
song1.mp3                     | 128.5               | Success
song2.mp3                     | 140.2               | Success
song3.mp3                     | -                   | Error: Insufficient beats detected
```

CSV format:

```csv
filepath,AubioBPMAnalyzer_bpm,status,error
song1.mp3,128.5,success,
song2.mp3,140.2,success,
song3.mp3,,error,Insufficient beats detected
```

JSON format:

```json
[
  {
    "filepath": "song1.mp3",
    "analyzer": "AubioBPMAnalyzer",
    "results": {"bpm": 128.5},
    "status": "success"
  },
  {
    "filepath": "song2.mp3",
    "analyzer": "AubioBPMAnalyzer",
    "results": {"bpm": 140.2},
    "status": "success"
  },
  {
    "filepath": "song3.mp3",
    "analyzer": "AubioBPMAnalyzer",
    "results": {},
    "status": "error",
    "error": "Insufficient beats detected"
  }
]
```

**Examples:**

```bash
# Basic analysis, display results only
yaamt.py analyze AubioBPMAnalyzer song.mp3

# Analyze and write to tags
yaamt.py analyze AubioBPMAnalyzer -w --overwrite-existing *.mp3

# Analyze with custom options
yaamt.py analyze AubioBPMAnalyzer --method specdiff --buf-size 2048 song.mp3

# Batch analyze to CSV
yaamt.py analyze AubioBPMAnalyzer -R -f csv -o results.csv /music/

# Use saved GUI preferences
yaamt.py analyze AubioBPMAnalyzer --use-saved-prefs -w -R /music/

# Multi-threaded analysis
yaamt.py analyze AubioBPMAnalyzer --threads 4 -w /music/*.mp3
```

### 6. New Utility Modules

#### 6.1 `src/util/analyzer_options.py`

Contains:
- `AnalyzerOption` dataclass
- `build_widget_from_option()` - Auto-generate Qt widgets
- `add_option_to_argparse()` - Add options to argparse
- Helper functions for QSettings integration

#### 6.2 `src/util/cli_formatters.py`

Contains:
- `format_analyzer_list()` - Format analyzer list for display
- `format_help_for_analyzer()` - Generate comprehensive help text
- `format_analysis_results()` - Format results in table/csv/json
- `format_metadata_output()` - Format metadata for read command
- `write_output()` - Write to file or stdout based on args

### 7. Implementation Phases

#### Phase 1: Foundation
1. Create `src/util/analyzer_options.py` with option system
2. Update `src/providers/analysis/base.py` with `get_options_metadata()`
3. Test basic option metadata and widget generation

#### Phase 2: Analyzer Updates
4. Update all 5 analyzer files with `get_options_metadata()`
5. Test that auto-generated widgets match existing custom widgets
6. Verify QSettings integration still works

#### Phase 3: CLI Refactor
7. Create `src/util/cli_formatters.py`
8. Refactor `src/yaamt.py` with verb-based structure
9. Implement each command (help, list, read, write, analyze)

#### Phase 4: Integration
10. Update `src/windows/analyzer/setup_dialog.py` for compatibility
11. Run full test suite
12. Fix any issues

## Testing Strategy

### Unit Tests
- Test `AnalyzerOption` dataclass
- Test `build_widget_from_option()` for each option type
- Test `add_option_to_argparse()` for each option type
- Test option metadata for each analyzer

### Integration Tests
- Test each CLI command with various options
- Test analyzer option extraction from widgets
- Test QSettings save/load with new system
- Test `--use-saved-prefs` loads correct values
- Test all output formats (table, csv, json)
- Test file output vs stdout
- Test recursive scanning
- Test multi-threaded analysis

### Regression Tests
- Verify GUI analyzer dialogs still work
- Verify QSettings preferences persist correctly
- Verify existing analyzer functionality unchanged

## Benefits

1. **No Code Duplication:** Options defined once, used by both CLI and GUI
2. **Automatic CLI Support:** New analyzers get CLI support automatically
3. **Consistent UX:** Same options, same behavior in GUI and CLI
4. **Extensible:** Easy to add new option types or commands
5. **Self-Documenting:** Help text generated from option metadata
6. **Unix-Style:** Familiar command structure for CLI users
7. **Flexible Output:** Multiple formats, file or stdout
8. **Safe:** Maintains existing QSettings integration

## Future Enhancements

- Add `verify` command to check file integrity
- Add `batch` command for complex multi-step operations
- Support for configuration files (YAML/JSON)
- Tab completion support for shells
- Progress bars for long-running operations
- Colored output support
- Interactive mode for complex edits
