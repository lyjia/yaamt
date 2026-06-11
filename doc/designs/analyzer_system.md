# Analyzer System Design Specification

## Overview

The Analyzer System enables automated analysis of audio files to extract metadata such as BPM, musical key, ReplayGain values, and more. Analyzers run asynchronously, present progress to the user, and stage their results to MediaFile objects for saving.

## Design Decisions Summary

1. **Concurrency**: Thread pool-based design, initially configured with pool size of 1 (sequential), expandable later
2. **Save Strategy**: Analyzers stage their results through ``EditManager.stage_change``; the dispatcher commits them synchronously at end-of-batch when ``autosave`` is on, or leaves them as pending edits when it is off
3. **Result Handling**: Analyzers return results as dictionaries; dispatcher merges them into staged changes
4. **Dispatcher**: Singleton service living for application lifetime
5. **Progress Reporting**: Qt signals from dispatcher to UI components
6. **Error States**: Success, Failed, Skipped
7. **Tag Usage**: Analyzers primarily use KEY_TAG_GENERIC fields; KEY_TAG_INTERNAL only for provider-specific edge cases
8. **Analyzer Scope**: Analyzers can set multiple fields when necessary (e.g., ReplayGain sets gain + peak)
9. **Categories**: Module structure is organizational only; categories don't constrain analyzer outputs
10. **Audio Streams**: Analyzers receive AudioStreamBase instances; dispatcher minimizes stream creation to reduce memory usage
11. **Menu Structure**: "Analyze" submenu shows categories only (one level deep); analyzer selection happens in dialog
12. **Menu Sharing**: Same "Analyze" submenu construction used in both File menu and right-click context menu
13. **Batch Analyzers**: Analyzers needing cross-file aggregation (e.g. album ReplayGain) extend ``BatchAnalyzerBase``; the dispatcher defers their tag writes until every per-file task has completed, then calls ``aggregate_results`` to compute and merge cross-file fields before staging

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Main Window                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │         Context Menu → Analyze Submenu             │     │
│  │  (Categories from providers.analysis modules)      │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ├──→ AnalyzerSetupDialog (optional)
                              │
                              ↓
                    ┌─────────────────────┐
                    │ AnalyzerDispatcher  │ (Singleton)
                    │  - Queue management │
                    │  - Thread pool      │
                    │  - Signal emissions │
                    └─────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    ↓                    ↓
          AnalyzerProgressDialog   Worker Threads
                    ↑                    │
                    │                    ↓
                    │           ┌─────────────────┐
                    └───────────│ AnalyzerBase    │
                                │  - analyze()    │
                                │  - Uses:        │
                                │   AudioStreamBase
                                └─────────────────┘
                                        │
                                        ↓
                                  Return results
                                        │
                                        ↓
                    ┌────────────────────────────────────────┐
                    │ Dispatcher merges results              │
                    │ → BatchAnalyzerBase.aggregate_results()│
                    │   for cross-file fields (album gain)   │
                    │ → EditManager.stage_change(...)        │
                    │ → EditManager.commit_changes_sync()    │
                    │   (no-op if autosave is off — stays    │
                    │   as pending edits)                    │
                    └────────────────────────────────────────┘
                                        │
                                        ↓
                              AnalyzerSummaryDialog
```

## Core Components

### 1. AnalyzerBase (Abstract Base Class)

**Location**: `src/providers/analysis/base.py`

**Purpose**: Defines the interface all analyzers must implement.

**Interface**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from models.media_file import MediaFile
from providers.audio.base import AudioStreamBase

class AnalyzerResult:
    """Encapsulates the result of an analysis operation."""
    def __init__(self,
                 success: bool,
                 data: Optional[Dict[str, Any]] = None,
                 error: Optional[str] = None,
                 skipped: bool = False,
                 aggregation_data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.data = data or {}  # Dict of generic_tag_name: value
        self.error = error
        self.skipped = skipped
        # Optional intermediate per-file payload used by BatchAnalyzerBase
        # subclasses to carry state into aggregate_results(). Never written
        # to tags. Must be picklable so it survives the dispatcher's
        # process pool when thread_pool_size > 1.
        self.aggregation_data = aggregation_data

class AnalyzerBase(ABC):
    """Base class for all audio file analyzers."""

    # Class attributes for metadata
    name: str = "Unnamed Analyzer"
    description: str = ""
    category: str = "uncategorized"  # Maps to module name
    version: str = "1.0.0"

    def __init__(self, media_file: MediaFile):
        """
        Initialize analyzer with a MediaFile.

        Args:
            media_file: The MediaFile instance to analyze
        """
        self.media_file = media_file
        self._cancelled = False

    @abstractmethod
    def analyze(self, audio_stream: AudioStreamBase) -> AnalyzerResult:
        """
        Perform analysis on the audio file.

        Args:
            audio_stream: Audio stream provider for reading audio data

        Returns:
            AnalyzerResult containing success status and data/error
        """
        pass

    def cancel(self):
        """Request cancellation of the analysis."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    @classmethod
    def get_settings_widget(cls) -> Optional['QWidget']:
        """
        Return a QWidget for analyzer-specific settings.

        Returns None if no settings are needed.
        Override in subclasses that need configuration UI.
        """
        return None

    @classmethod
    def validate_file(cls, media_file: MediaFile) -> tuple[bool, Optional[str]]:
        """
        Check if this analyzer can process the given file.

        Args:
            media_file: The file to validate

        Returns:
            (is_valid, reason) tuple. reason is None if valid,
            or a string explaining why the file is incompatible.
        """
        return (True, None)
```

**Key Design Points**:
- Analyzers receive a `MediaFile` instance at construction
- The `analyze()` method receives an `AudioStreamBase` instance. Analyzers can also obtain one via `AudioStreamFactory` if not provided, but dispatcher should minimize stream instances to reduce memory usage.
- Analyzers return `AnalyzerResult` objects, not raw dictionaries, for type safety
- Cancellation support via `cancel()` and `is_cancelled` property
- Optional settings UI via `get_settings_widget()`
- File validation via `validate_file()` class method

### 1a. BatchAnalyzerBase (subclass of AnalyzerBase)

For analyzers whose final output depends on data aggregated across multiple files (e.g. ReplayGain album gain needs LUFS measurements from every track in the album).

**Contract**:
- ``analyze()`` populates ``AnalyzerResult.aggregation_data`` with whatever per-file payload the aggregator needs (typically scalars and small arrays — must be picklable).
- ``aggregate_results(completed_tasks, options)`` is a classmethod called once after every per-file task in the batch has completed. It receives the list of successful, non-skipped tasks and returns a ``dict[file_path, dict[generic_tag, value]]`` whose entries are merged into each task's ``result.data`` before staging.

**Dispatcher behavior for BatchAnalyzerBase**:
- Per-file tag writes are *deferred* (no per-task ``_apply_results`` during ``_on_worker_finished``) until ``_finish_processing`` runs aggregation.
- ``task_completed`` signals still fire per task so the progress UI updates incrementally.
- If the user cancels mid-batch, aggregation is skipped and only per-task results from completed tasks are staged.

### 2. AnalyzerDispatcher (Singleton)

**Location**: `src/workers/analyzer_dispatcher.py`

**Purpose**: Manages the queue, threading, and orchestration of analysis tasks.

**Interface**:
```python
from PySide6.QtCore import QObject, Signal, QThreadPool
from typing import List, Type
from models.media_file import MediaFile
from providers.analysis.base import AnalyzerBase, AnalyzerResult

class AnalysisTask:
    """Represents a single file analysis task."""
    def __init__(self, analyzer_class: Type[AnalyzerBase], media_file: MediaFile):
        self.analyzer_class = analyzer_class
        self.media_file = media_file
        self.result: Optional[AnalyzerResult] = None

class AnalyzerDispatcher(QObject):
    """
    Singleton dispatcher for managing analyzer queue and execution.
    """

    # Signals
    analysis_started = Signal()  # Emitted when queue processing begins
    analysis_completed = Signal()  # Emitted when queue is empty
    task_started = Signal(str, str)  # (file_path, analyzer_name)
    task_completed = Signal(str, AnalyzerResult)  # (file_path, result)
    progress_updated = Signal(int, int)  # (completed_count, total_count)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self._initialized = True

        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(1)  # Sequential initially

        self.queue: List[AnalysisTask] = []
        self.completed_tasks: List[AnalysisTask] = []
        self.current_task: Optional[AnalysisTask] = None
        self._is_running = False

    def enqueue(self, analyzer_class: Type[AnalyzerBase],
                media_files: List[MediaFile]):
        """
        Add analysis tasks to the queue.

        Args:
            analyzer_class: The analyzer class to use
            media_files: List of MediaFile instances to analyze
        """
        for mf in media_files:
            task = AnalysisTask(analyzer_class, mf)
            self.queue.append(task)

    def start(self):
        """Begin processing the queue."""
        if self._is_running:
            return

        self._is_running = True
        self.analysis_started.emit()
        self._process_next()

    def cancel_all(self):
        """Cancel all pending and current tasks."""
        self.queue.clear()
        if self.current_task:
            # Signal to cancel current analyzer
            pass
        self._is_running = False

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of completed analysis run.

        Returns dict with:
        - total: total tasks
        - successful: count of successful analyses
        - failed: list of (file_path, error) tuples
        - skipped: list of (file_path, reason) tuples
        """
        pass

    def _process_next(self):
        """Process the next task in the queue."""
        pass

    def _run_analyzer(self, task: AnalysisTask):
        """Execute an analyzer in a worker thread."""
        pass

    def _apply_results(self, task: AnalysisTask):
        """Stage analyzer results via EditManager.stage_change()."""
        pass

    def _run_batch_aggregation(self):
        """For BatchAnalyzerBase runs, call aggregate_results() on the
        successful tasks and merge per-file extras into result.data
        before staging."""
        pass

    def _finalize_writes(self):
        """At end of batch, EditManager.commit_changes_sync() if autosave
        is on; otherwise leave staged changes pending."""
        pass
```

**Key Design Points**:
- Singleton pattern ensures one dispatcher instance
- Uses `QThreadPool` for thread management (initially max=1 thread)
- Emits Qt signals for UI updates (thread-safe)
- Manages task queue and execution lifecycle
- Routes all tag writes through `EditManager.stage_change()` so the autosave preference gates whether they hit disk
- Commits synchronously at end-of-batch — `analysis_completed` does not fire until disk writes are done, avoiding the race where post-analysis UI refresh runs before the save thread completes
- For `BatchAnalyzerBase` analyzers, defers per-file `_apply_results` until after `aggregate_results` runs in `_finish_processing`
- Provides summary data for the summary dialog

### 3. AnalyzerSetupDialog

**Location**: `src/windows/analyzer_setup_dialog.py`

**Purpose**: Dialog for selecting analyzer and configuring settings before execution.

**Features**:
- Opened with a specific category already selected (from menu choice)
- Displays list of available analyzers for that category
- Shows analyzer-specific settings widget (if `get_settings_widget()` returns one)
- Allows user to confirm or cancel analyzer execution
- Reads preferred analyzer from QSettings and pre-selects it

**UI Layout**:
```
┌─────────────────────────────────────────┐
│  Configure BPM Analysis                 │
├─────────────────────────────────────────┤
│  Analyzer: [Essentia BPM Analyzer ▼]    │
│            (LibRosa BPM Analyzer)       │
│            (Essentia BPM Analyzer) ✓    │
│                                         │
│  ┌────────────────────────────────┐    │
│  │  Analyzer-specific settings    │    │
│  │  (from get_settings_widget())  │    │
│  └────────────────────────────────┘    │
│                                         │
│  Files to analyze: 42                   │
│                                         │
│           [Cancel]  [Run Analysis]      │
└─────────────────────────────────────────┘
```

### 4. AnalyzerProgressDialog

**Location**: `src/windows/analyzer_progress_dialog.py`

**Purpose**: Modal dialog showing real-time analysis progress.

**Features**:
- Overall progress bar (files completed / total files)
- Current file path display
- Current analyzer name display
- Cancel button (prompts user about keeping/discarding partial results)
- Connects to AnalyzerDispatcher signals for updates

**UI Layout**:
```
┌─────────────────────────────────────────┐
│  Analyzing Files                        │
├─────────────────────────────────────────┤
│  Analyzer: LibRosa BPM Analyzer         │
│                                         │
│  Current file:                          │
│  C:\Music\track042.mp3                  │
│                                         │
│  Progress: [████████░░░░░░░░] 42/100   │
│                                         │
│                      [Cancel Analysis]  │
└─────────────────────────────────────────┘
```

### 5. AnalyzerSummaryDialog

**Location**: `src/windows/analyzer_summary_dialog.py`

**Purpose**: Display results summary after analysis completes.

**Features**:
- Shows count of successful/failed/skipped files
- Lists failed files with error messages
- Lists skipped files with reasons
- Button to select failed/skipped files in MainWindow for retry

**UI Layout**:
```
┌──────────────────────────────────────────────┐
│  Analysis Complete                           │
├──────────────────────────────────────────────┤
│  Successfully analyzed: 95 / 100 files       │
│                                              │
│  Failed (3):                                 │
│  ├─ track023.mp3: Corrupted audio stream    │
│  ├─ track067.mp3: Insufficient audio data   │
│  └─ track091.mp3: Unsupported sample rate   │
│                                              │
│  Skipped (2):                                │
│  ├─ track014.mp3: BPM already set           │
│  └─ track038.mp3: File too short (< 10s)    │
│                                              │
│  [Select Failed Files]  [Close]             │
└──────────────────────────────────────────────┘
```

## Module Structure

```
src/
└── providers/
    └── analysis/
        ├── __init__.py            # AnalyzerCategory enum
        ├── _manifest.py           # Static analyzer-module manifest (PyInstaller-friendly)
        ├── base.py                # AnalyzerBase, BatchAnalyzerBase, AnalyzerResult
        ├── bpm/
        │   ├── __init__.py
        │   ├── aubio_bpm.py       # AubioBPMAnalyzer
        │   ├── librosa_bpm.py     # LibrosaBeatTrackingBPMAnalyzer
        │   ├── re3_bpm.py         # RE3BPMAnalyzer
        │   └── stub_bpm.py        # StubBPMAnalyzer (debug_only)
        ├── key/
        │   ├── __init__.py
        │   ├── librosa_key.py     # LibrosaChromagramKeyAnalyzer
        │   ├── musical_cnn_key.py # MusicalKeyCNNAnalyzer
        │   └── re3_key.py         # RE3WaveletKeyAnalyzer
        ├── fingerprint/
        │   ├── __init__.py
        │   └── musicbrainz_acoustid.py  # MusicBrainzAcoustIDAnalyzer
        └── loudness/
            ├── __init__.py
            ├── replaygain.py      # ReplayGainAnalyzer (default; BatchAnalyzerBase)
            └── peak_meter.py      # PeakMeterAnalyzer (debug_only)
```

**Auto-Discovery Pattern** (`providers/analysis/__init__.py`):
```python
import importlib
import pkgutil
from typing import Dict, List, Type
from .base import AnalyzerBase

# Registry: {category_name: [AnalyzerClass, ...]}
ANALYZER_REGISTRY: Dict[str, List[Type[AnalyzerBase]]] = {}

def discover_analyzers():
    """Auto-discover all analyzer classes in submodules."""
    package = __package__
    for importer, modname, ispkg in pkgutil.walk_packages(__path__, prefix=f"{package}."):
        if not ispkg:
            try:
                module = importlib.import_module(modname)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, AnalyzerBase) and
                        attr is not AnalyzerBase):

                        category = attr.category
                        if category not in ANALYZER_REGISTRY:
                            ANALYZER_REGISTRY[category] = []
                        ANALYZER_REGISTRY[category].append(attr)
            except Exception as e:
                log.warning(f"Failed to load analyzer module {modname}: {e}")

discover_analyzers()

def get_analyzers_by_category(category: str) -> List[Type[AnalyzerBase]]:
    """Get all analyzers for a given category."""
    return ANALYZER_REGISTRY.get(category, [])

def get_all_categories() -> List[str]:
    """Get list of all analyzer categories."""
    return sorted(ANALYZER_REGISTRY.keys())
```

## User Preferences

**Settings Location**: QSettings (existing `models/settings.py`)

**New Settings Structure**:
```python
# In models/settings.py, add to Settings dataclass:

@dataclass
class AnalyzerSettings:
    """Stores analyzer preferences."""
    # Map of category -> preferred analyzer class name
    preferred_analyzers: Dict[str, str] = field(default_factory=dict)
    # Example: {'bpm': 'LibrosaBPMAnalyzer', 'key': 'KeyFinderAnalyzer'}

    # Thread pool size for parallel execution
    thread_pool_size: int = 1

    # Category-specific settings (e.g., key notation preference)
    category_options: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Example: {'key': {'notation': 'camelot'}}

@dataclass
class Settings:
    """Stores the main application settings."""
    file_list: FileListSettings = field(default_factory=FileListSettings)
    analyzers: AnalyzerSettings = field(default_factory=AnalyzerSettings)
```

**Persistence**:
- Settings are read/written via QSettings
- Preferred analyzers are used to pre-select default in context menu
- Category options (like Camelot notation) are passed to analyzers when instantiated

## Context Menu Integration

**Location**: Should be a shared construct used by both the File menu and right-click context menu

**Structure** (one submenu level deep):
```
File Menu / Right-click Context Menu
├── Open
├── Rename
├── Delete
├── ──────────
├── Analyze ►
│   ├── BPM
│   ├── Key
│   ├── Gain
│   └── MusicBrainz
├── ──────────
└── Properties
```

**Implementation Flow**:
1. Build "Analyze" submenu from `ANALYZER_REGISTRY` categories
2. Create menu item for each category (e.g., "BPM", "Key", "Gain")
3. When category clicked:
   - Show `AnalyzerSetupDialog` with category pre-selected
   - Dialog displays available analyzers for that category
   - Preferred analyzer (from QSettings) is pre-selected in dialog
   - User can change analyzer selection and configure settings
   - User clicks "Run Analysis"
4. Enqueue tasks to `AnalyzerDispatcher`
5. Show `AnalyzerProgressDialog`
6. On completion, show `AnalyzerSummaryDialog`

**Shared Menu Construction**:
- Create a reusable function/method to build the "Analyze" submenu
- This same function is called when building:
  - The File menu's "Analyze" submenu
  - The right-click context menu's "Analyze" submenu
- Ensures consistency between both menu locations

## Data Flow

### Analysis Execution Flow

1. **User initiates analysis**:
   - Right-click files (or File menu) → Analyze → Category (e.g., "BPM")

2. **Setup dialog always shows**:
   - Show `AnalyzerSetupDialog` with selected category
   - Display list of available analyzers for that category
   - Pre-select preferred analyzer from QSettings
   - If analyzer has settings widget, display it
   - User can change analyzer selection
   - User clicks "Run Analysis" or "Cancel"

3. **Dispatcher enqueues tasks**:
   ```python
   dispatcher = AnalyzerDispatcher()
   dispatcher.enqueue(LibrosaBPMAnalyzer, selected_media_files)
   dispatcher.start()
   ```

4. **Progress dialog appears**:
   - Connects to dispatcher signals
   - Shows real-time updates

5. **Worker thread executes analyzer**:
   ```python
   # In worker thread:
   audio_stream = AudioStreamFactory.get_stream(media_file.file_path)
   analyzer = analyzer_class(media_file)
   result = analyzer.analyze(audio_stream)
   audio_stream.close()
   ```

6. **Dispatcher applies results** (on main thread):
   ```python
   if result.success and not result.skipped:
       changes = {
           KEY_TAG_GENERIC: result.data
       }
       media_file.save(changes)
       # Autosave handles actual persistence if enabled
   ```

7. **Summary dialog shows results**:
   - Displays success/failure/skip counts
   - Lists any errors or warnings

### Cancellation Flow

1. **User clicks "Cancel" in progress dialog**:
   - Dialog prompts: "Keep partial results or discard?"

2. **If "Discard"**:
   - `dispatcher.cancel_all()`
   - Clear queue
   - Signal current analyzer to cancel via `analyzer.cancel()`
   - Don't apply any pending results

3. **If "Keep"**:
   - `dispatcher.cancel_all()`
   - Clear remaining queue
   - Apply results from completed tasks
   - Show summary dialog with partial results

## Error Handling

### Error Categories

1. **Validation Errors** (before analysis):
   - File not readable
   - Incompatible format
   - Missing dependencies
   - **Action**: Mark as "Skipped" immediately, don't enqueue

2. **Analysis Errors** (during execution):
   - Corrupted audio data
   - Insufficient audio content
   - Algorithm failure
   - **Action**: Catch exception, create AnalyzerResult with `success=False, error=str(exception)`

3. **I/O Errors** (during save):
   - File locked
   - Insufficient permissions
   - Disk full
   - **Action**: Report as "Failed", show error in summary

### Analyzer Error Handling Pattern

```python
class MyAnalyzer(AnalyzerBase):
    def analyze(self, audio_stream: AudioStreamBase) -> AnalyzerResult:
        try:
            # Validation
            is_valid, reason = self.validate_file(self.media_file)
            if not is_valid:
                return AnalyzerResult(success=True, skipped=True, error=reason)

            # Check for existing data (optional skip logic)
            existing_bpm = self.media_file.get_tag_simple('bpm')
            if existing_bpm:
                return AnalyzerResult(success=True, skipped=True,
                                     error="BPM already set")

            # Perform analysis
            bpm_value = self._calculate_bpm(audio_stream)

            # Check for cancellation periodically
            if self.is_cancelled:
                return AnalyzerResult(success=False, error="Cancelled by user")

            return AnalyzerResult(success=True, data={'bpm': bpm_value})

        except Exception as e:
            log.error(f"Analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(success=False, error=str(e))
```

## Thread Safety

### Qt Signal/Slot Thread Safety

- **AnalyzerDispatcher** runs analyzers in worker threads
- All UI updates MUST use Qt signals (automatically queued across threads)
- **Never** directly call UI methods from worker threads

### MediaFile Thread Safety

- Each `AnalysisTask` has its own `MediaFile` instance
- MediaFile instances are NOT shared between threads
- Dispatcher applies results to MediaFile on main thread only

### Audio Stream Handling

- Each analyzer receives a fresh `AudioStreamBase` instance
- Streams are created in worker thread, used, and closed within same thread
- No stream sharing between analyzers or threads

## Future Enhancements

### Phase 2: Parallelization
- Increase thread pool size via user preference
- Add resource monitoring (CPU/memory limits)
- Implement intelligent scheduling (prioritize short files, spread long files)

### Phase 3: Batch Operations
- Analyze multiple metadata types in one pass (e.g., BPM + Key together)
- Share audio stream between compatible analyzers

### Phase 4: Advanced Features
- Analyzer plugins from external packages
- Cloud-based analyzers (e.g., upload to remote API)
- Machine learning model caching and updates

## Testing Considerations

### Unit Testing Analyzers

```python
# tests/test_analyzers.py
def test_bpm_analyzer():
    # Use test fixture
    media_file = MediaFile('tests/fixtures/120bpm_test.mp3')
    analyzer = LibrosaBPMAnalyzer(media_file)

    audio_stream = AudioStreamFactory.get_stream(media_file.file_path)
    result = analyzer.analyze(audio_stream)
    audio_stream.close()

    assert result.success
    assert result.data['bpm'] == pytest.approx(120, abs=2)
```

### Testing Long Files

- Use test fixtures with varying durations (1s, 10s, 1min, 10min)
- Mock long files by creating minimal test data
- Test cancellation during long-running analysis

### UI Testing

- Mock AnalyzerDispatcher to avoid actual analysis
- Test dialog interactions (setup, progress, summary)
- Verify signal connections and updates

## Open Questions / Future Decisions

1. **Analyzer versioning**: Should we track analyzer versions in metadata? (e.g., "BPM detected by LibRosa v1.2.3")
2. **Result confidence**: Should analyzers return confidence scores? (e.g., "BPM=120, confidence=0.95")
3. **Undo/Redo**: Should analysis results be undoable? Requires integration with potential future undo system.
4. **Batch mode**: CLI option to run analyzers headless for automation?

## References

- Epic: `doc/epics/20251008_Analyzers_System.md`
- MediaFile: `src/models/media_file.py`
- AudioStreamBase: `src/providers/audio/base.py`
- QSettings: `src/models/settings.py`
