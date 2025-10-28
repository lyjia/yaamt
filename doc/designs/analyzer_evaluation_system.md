# Analyzer Evaluation System Design

**Epic:** @doc/epics/20251028_Add_Analyzer_Evaluation_System.md

## Overview

Create a CLI-based evaluation script (`scripts/eval_analyzer.py`) that compares analyzer outputs against hand-reviewed reference data and calculates MIREX scores for key detection and custom scores for BPM detection.

## Core Components

### 1. Main Script: `scripts/eval_analyzer.py`

**Purpose:** Standalone CLI tool (similar to MusicalKeyCNN's eval.py)

**Arguments:**
- `--audio-dir`: Directory containing audio files
- `--reference`: Reference CSV file (consolidated dataset format)
- `--analysis`: Analysis result CSV(s) - accepts multiple files
- `--criteria`: Either "key" or "bpm" (required)
- `--output-dir`: Where to write result CSVs (default: current directory)

### 2. Scoring Module: `src/util/eval_scoring.py`

Contains scoring logic for both criteria types.

#### Key Scoring (MIREX)

Uses mingus library for relationship detection.

**Function:** `calculate_key_relationship(ref_pitch_class, ref_is_minor, analyzed_pitch_class, analyzed_is_minor) -> (score, category)`

**Algorithm:**

1. Convert pitch_class to mingus note format:
   - `note_names = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']`
   - `ref_note = note_names[ref_pitch_class]`
   - `analyzed_note = note_names[analyzed_pitch_class]`

2. Determine relationship:
   - **Same key:** tonic == tonic AND mode == mode → 1.0 point
   - **Parallel major/minor:** tonic == tonic AND mode != mode → 0.2 points
   - **Relative major/minor:** mode != mode AND semitone distance == 3 → 0.3 points
     - Use `mingus.core.intervals.measure(ref_note, analyzed_note)`
   - **Perfect fifth:** mode == mode AND semitone distance == 7 → 0.5 points
     - Use `mingus.core.intervals.measure(ref_note, analyzed_note)`
   - **Other:** → 0.0 points

3. Return `(score, category_name)` for tracking

**Category Tracking:**

Count results for: 'same key', 'perfect fifth', 'relative major/minor', 'parallel major/minor', 'other'

#### BPM Scoring (Custom)

- Difference < 0.01 BPM: 1.0 point
- Within 1/10 of reference (±10%): 0.5 points
- Within 1/5 of reference (±20%): 0.25 points
- Other: 0.0 points
- All values rounded to 2 decimal places

### 3. Key Relationship Detection

**Use existing utilities:**
- `src/util/diatonic_key.py::parse_key()` - Parse all key formats to (pitch_class, is_minor)
- Internal pitch_class (0-11) maps directly to mingus notes
- Use mingus only for interval calculation via `mingus.core.intervals.measure()`

**No new conversion module needed** - existing utilities handle all formats (Camelot, OpenKey, standard)

### 4. CSV Input/Output Formats

#### Reference CSV (consolidated dataset format)

```
id, artist, title, mix, album, key, bpm, genre, datasets, output_filename
```

#### Analysis CSV (report format from CLI)

```
directory, filename, [AnalyzerName_field], status, error
```

Example columns: `LibrosaChromagramKeyAnalyzer_initial_key`, `StubBPMAnalyzer_bpm`

#### Output CSVs

**1. Combined Summary** (`eval_summary_{criteria}_{timestamp}.csv`):

For key:
```
analyzer_name, total_files, scored_files, skipped_files, total_score, max_score, average_score, same_key_count, perfect_fifth_count, relative_count, parallel_count, other_count
```

For BPM:
```
analyzer_name, total_files, scored_files, skipped_files, total_score, max_score, average_score
```

Where:
- `total_score`: Sum of all scores achieved across all files
- `max_score`: Maximum possible score (1.0 × scored_files)
- `average_score`: total_score / max_score (equivalent to total_score / scored_files for normalized view)

**2. Detailed Per-Analyzer** (`eval_{analyzer_name}_{criteria}_{timestamp}.csv`):

For key:
```
filename, reference_key, analyzed_key, score, category, notes
```

For BPM:
```
filename, reference_bpm, analyzed_bpm, score, delta, notes
```

### 5. File Matching Logic

- Match files by filename only (strip directory from analysis CSV)
- Handle missing/invalid data:
  - Reference file missing from audio dir: Skip with warning
  - Reference value blank/unparseable: Skip with warning
  - Analyzer value missing (blank/status != success): Score as 0.0 points
  - File in analysis but not in reference: Skip with warning
- Track all skips with reasons in detailed output

### 6. Key Notation Handling

- Use `diatonic_key.parse_key()` for both reference and analyzed keys
- Auto-detects all formats: Camelot, OpenKey, standard abbreviations
- Parsing failures → skip file with error message
- No format conversion needed for output (preserve original strings in detailed CSV)

## Dependencies

- **mingus**: Music theory library (add to requirements.txt)
  - Used for: `mingus.core.intervals.measure()` to calculate semitone distances
  - May need `debug_only=True` if it doesn't compile with nuitka
- **pandas**: Already in use (CSV handling)
- **pathlib**: Already in use (file path handling)
- **existing utilities**: `diatonic_key.py` (key parsing)

## Implementation Steps

1. Add mingus to requirements.txt
2. Create `src/util/eval_scoring.py`:
   - `calculate_key_relationship()` - uses mingus for interval detection
   - `calculate_key_score()` - wrapper that returns MIREX score
   - `calculate_bpm_score()` - custom BPM scoring logic
3. Create `scripts/eval_analyzer.py`:
   - CLI argument parsing
   - Load reference CSV (consolidated dataset format)
   - Load analysis CSV(s) (report format)
   - Match files by filename
   - Calculate scores using eval_scoring functions
   - Generate both summary and detailed CSV outputs
4. Error handling and logging throughout
5. Write unit tests in `tests/test_eval_scoring.py`:
   - Test all MIREX relationship categories
   - Test BPM scoring thresholds
   - Test file matching logic
   - Test skip conditions
6. Update documentation with usage examples
7. Test with actual data from tmp/ directory

## Key Design Decisions

- **CLI Only**: No GUI integration (can be added later)
- **Lenient Validation**: Skip problematic files, continue processing
- **Reuse Existing Utilities**: Leverage `diatonic_key.py` instead of duplicating
- **Mingus for Theory**: Use mingus.core.intervals for accurate interval calculation
- **Dual Output**: Both summary and detailed results
- **Timestamp-based Output**: Preserve previous evaluation runs
- **Debug-only consideration**: If mingus can't compile with nuitka, mark eval script as debug_only

References:

Mingus:
* https://bspaans.github.io/python-mingus/
* https://bspaans.github.io/python-mingus/doc/wiki/tutorialNote.html
* https://bspaans.github.io/python-mingus/doc/wiki/tutorialDiatonic.html
* https://bspaans.github.io/python-mingus/doc/wiki/tutorialIntervals.html

MIREX:
* https://www.music-ir.org/mirex/wiki/2025:Audio_Key_Detection