# Tag Value Transformations Design Specification

**Epic**: `doc/epics/20251013_Tag_Value_Transformations.md`

## Overview

The Tag Value Transformations system provides centralized formatting and normalization of metadata tag values before they are written to files. This ensures consistent formatting across analyzer outputs and user edits, and eliminates the need for analyzers to handle formatting logic.

**Important**: Transformations only apply to:
- Analyzer-generated tag values
- User-generated edits (when user preference allows)

Transformations do NOT apply to:
- Tag data read directly from files (imports)
- Internal tag operations

## Goals

1. Centralize all tag value transformation logic in one place
2. Apply user preferences consistently to analyzer outputs and user edits
3. Enable extensibility for new transformation types
4. Remove formatting responsibility from analyzers
5. Support transformations from any input type (int, float, string) to proper output format
6. Allow users to bypass transformations for manual edits when desired

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Data Sources (Analyzers, UI)                               │
│  Returns raw values: 173.94, "Ebmin", "  Title  "          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  MediaFile.save(changes, bypass_transformations=False)       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Check bypass conditions:                           │    │
│  │  - bypass_transformations parameter?                │    │
│  │  - User preference for manual edits?                │    │
│  └────────────────────────────────────────────────────┘    │
│                                   │                          │
│                          ┌────────┴────────┐                │
│                          │                 │                │
│                      Bypass?              No                │
│                          │                 │                │
│                         Yes                ↓                │
│                          │    ┌────────────────────────┐    │
│                          │    │ Transformation Pipeline │    │
│                          │    │ 1. Load preferences     │    │
│                          │    │ 2. For each tag:        │    │
│                          │    │    a. Find transformers │    │
│                          │    │    b. Apply in order    │    │
│                          │    │    c. Replace value     │    │
│                          │    └────────────────────────┘    │
│                          │                 │                │
│                          └────────┬────────┘                │
│                                   ↓                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Write to Providers                                 │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────┐
        │  File written            │
        └──────────────────────────┘
```

### Transformer Registry

```
┌─────────────────────────────────────────────────────────────┐
│  Transformer Registry (module-level)                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Multi-Tag Transformers (applicable_tags list):     │    │
│  │  1. WhitespaceTrimmer                               │    │
│  │     applicable_tags: ['title', 'artist', 'album',   │    │
│  │                       'comment', ...]               │    │
│  │  2. EmptyStringHandler                              │    │
│  │     applicable_tags: ['title', 'artist', 'album',   │    │
│  │                       'bpm', 'key', ...]            │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Single-Tag Transformers:                           │    │
│  │  1. BPMFormatter                                    │    │
│  │     applicable_tags: ['bpm']                        │    │
│  │  2. MusicalKeyFormatter                             │    │
│  │     applicable_tags: ['key']                        │    │
│  │  3. GenreStandardizer (future)                      │    │
│  │     applicable_tags: ['genre']                      │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. TransformerBase (Abstract Base Class)

**Location**: `src/providers/metadata/tag_transformers/base.py`

**Purpose**: Defines interface all tag transformers must implement.

**Class Attributes**:
- `name`: Human-readable transformer name
- `description`: Brief description of what the transformer does
- `version`: Transformer version string
- `applicable_tags`: List of generic tag names this transformer applies to (e.g., `['bpm']` or `['title', 'artist', 'album']`)
- `priority`: Integer controlling transformation order (lower = earlier, default 50)

**Methods**:
- `__init__(settings)`: Initialize with QSettings instance for reading user preferences
- `transform(value, tag_name) -> str`: Transform a raw value to a formatted string. Accepts any type (int, float, str), returns string. Raises ValueError if transformation fails.

**Key Design Points**:
- Each transformer declares which tags it applies to via `applicable_tags` class attribute
- No wildcard support - all applicable tags must be explicitly listed
- Priority system controls application order (lower numbers run first)
- Each transformer is stateless except for QSettings reference
- Transformers receive the generic tag name for context

### 2. Standard Transformers

#### WhitespaceTrimmer

**Location**: `src/providers/metadata/tag_transformers/whitespace_trimmer.py`

**Purpose**: Remove leading/trailing whitespace from string values.

**Configuration**:
- Priority: 10 (run early)
- Applicable tags: All string-based tags (title, artist, album, comment, etc.)
- Logic: Convert value to string, strip leading/trailing whitespace
- No user preferences needed

#### EmptyStringHandler

**Location**: `src/providers/metadata/tag_transformers/empty_string_handler.py`

**Purpose**: Normalize None and empty values to empty string.

**Configuration**:
- Priority: 5 (run first)
- Applicable tags: All tags that support empty values
- Logic: Convert None, empty string, and whitespace-only values to `""`
- No user preferences needed

#### BPMFormatter

**Location**: `src/providers/metadata/tag_transformers/bpm_formatter.py`

**Purpose**: Format BPM values according to user's decimal places preference.

**Configuration**:
- Priority: 50 (default)
- Applicable tags: `['bpm']`
- Reads preference: `Analyzers/CategoryOptions/bpm/decimal_places` (default: 0, range: 0-3)
- Logic:
  - Parse input as float (handle int, float, string inputs)
  - Round to specified decimal places
  - Format as string (integer format if 0 decimals, float otherwise)
  - Raise ValueError for invalid numeric inputs

#### MusicalKeyFormatter

**Location**: `src/providers/metadata/tag_transformers/musical_key_formatter.py`

**Purpose**: Convert musical key notation according to user preference.

**Configuration**:
- Priority: 50 (default)
- Applicable tags: `['key']`
- Reads preference: `Analyzers/CategoryOptions/key/notation_format` (default: `"standard_abbrev"`)
- Supported formats:
  - `"standard_abbrev"`: Cmin, Amaj
  - `"standard_single"`: Cm, A
  - `"camelot"`: 6A, 8B
  - `"open_key"`: 1m, 12d
- Logic:
  - Parse input key notation (support various input formats: Cmin, C minor, Cm, etc.)
  - Normalize to internal standard form
  - Convert to target notation format
  - Handle major/minor variants
  - Use conversion maps for Camelot/OpenKey formats

### 3. Transformer Registry

**Location**: `src/providers/metadata/tag_transformers/__init__.py`

**Purpose**: Central registry for discovering and applying transformers.

**Functions**:
- `register_transformer(transformer_class)`: Register a transformer by reading its `applicable_tags` attribute
- `get_transformers_for_tag(tag_name)`: Get all transformers that apply to a tag, sorted by priority
- `apply_transformations(tag_name, value, settings)`: Apply all relevant transformers to a value, return formatted string

**Key Design Points**:
- Registry automatically built by reading each transformer's `applicable_tags` class attribute
- Transformers sorted by priority before application
- Single `apply_transformations()` function for use by MediaFile
- Registry populated at module import time
- Adding new transformers: import class and call `register_transformer()`

### 4. MediaFile Integration

**Location**: `src/providers/metadata/media_file.py`

**Integration Point**: `save()` method

**Method Signature**: `save(changes=None, bypass_transformations=False)`

**New Parameter**:
- `bypass_transformations`: Boolean flag to skip transformation pipeline entirely

**Save Logic**:
1. Check if transformations should be bypassed:
   - If `bypass_transformations=True`: skip all transformations
   - If being called from a manual tag edit, caller should check user preference `Metadata/AutoFormatManualEdits` (default: False) and set bypass_transformations accordingly
2. If not bypassing:
   - For each tag in `KEY_TAG_GENERIC` changes:
     - Call `apply_transformations(tag, value, settings)` for each changed tag
     - Replace value with transformed result
     - If transformation fails: log an error, stop whatever process generated bad data and stop save operation.
3. Continue with existing save logic using (potentially transformed) values

**Key Design Points**:
- Transformations only apply to `KEY_TAG_GENERIC` changes (never `KEY_TAG_INTERNAL`)

**User Preference**:
- Key: `Metadata/AutoFormatManualEdits`
- Type: Boolean
- Default: True
- Description: "Automatically format manually-entered tag data"
- Scope: Applies only to manual UI edits (not analyzer outputs)

## Module Structure

```
src/
└── providers/
    └── metadata/
        └── tag_transformers/
            ├── __init__.py                  # Registry and apply_transformations()
            ├── base.py                      # TransformerBase abstract class
            ├── empty_string_handler.py      # EmptyStringHandler
            ├── whitespace_trimmer.py        # WhitespaceTrimmer
            ├── bpm_formatter.py             # BPMFormatter
            └── musical_key_formatter.py     # MusicalKeyFormatter
```

## Transformation Pipeline Examples

### Example 1: BPM from Analyzer

**Input**: `173.94` (float from analyzer)

**User Preference**: 0 decimal places

**Transformers Applied**:
1. EmptyStringHandler: converts to string
2. WhitespaceTrimmer: no change needed
3. BPMFormatter: rounds to 0 decimals → `"174"`

**Result**: `"174"` written to file

### Example 2: Musical Key from Analyzer

**Input**: `"Ebmin"` (standard notation)

**User Preference**: Camelot notation

**Transformers Applied**:
1. EmptyStringHandler: no change needed
2. WhitespaceTrimmer: no change needed
3. MusicalKeyFormatter: converts to Camelot → `"2A"`

**Result**: `"2A"` written to file

### Example 3: Title from User Edit (with AutoFormat enabled)

**Input**: `"  My Song Title  "` (extra whitespace)

**Transformers Applied**:
1. EmptyStringHandler: not empty, no change
2. WhitespaceTrimmer: strips whitespace → `"My Song Title"`

**Result**: `"My Song Title"` written to file

### Example 4: Title from User Edit (with AutoFormat disabled)

**Input**: `"  My Song Title  "` (extra whitespace)

**User Preference**: `Metadata/AutoFormatManualEdits = False`

**Transformers Applied**: None (bypassed)

**Result**: `"  My Song Title  "` written to file as-is

## Error Handling

### Transformation Failures

**Strategy**: Log error and crash save operation. Leave original value in file.

**Rationale**:
- We want to surface errors ASAP so they are caught early. There should be no reason that operations fail completely; we are working on things that are consistently string data so if something goes wrong there are bigger issues afoot. 

### Invalid User Preferences

**Strategy**: Use sensible defaults and clamp values to valid ranges

**Behavior**: Each transformer validates preference values and falls back to documented defaults if missing or invalid (e.g., BPMFormatter clamps decimal_places to 0-3 range).

## Performance Considerations

### QSettings Caching

**Issue**: Reading QSettings repeatedly is slow.

**Solution**: Pass QSettings instance to transformers via constructor. Each transformer reads its preferences once during initialization.

### Transformer Instance Reuse

**Current Design**: Create new transformer instance for each tag transformation.

**Future Optimization**: Singleton transformers per thread with cached preferences.

**Trade-off**: Current design prioritizes simplicity. Optimize only if profiling shows bottleneck.

## Testing Requirements

### Unit Tests

**Test File**: `tests/providers/metadata/test_tag_transformers.py`

**WhitespaceTrimmer**: Test trimming leading/trailing/both whitespace, empty strings, None values

**EmptyStringHandler**: Test None → empty string, whitespace-only → empty string, preserve non-empty

**BPMFormatter**: Test integer/float inputs, all decimal place options (0-3), clamping invalid preferences, ValueError for invalid inputs

**MusicalKeyFormatter**: Test parsing various input formats, conversion to all notation types, empty/None handling, invalid key notation

**Transformer Registry**: Test registration, get_transformers_for_tag returns correct transformers sorted by priority, apply_transformations calls all in order and handles ValueError

### Integration Tests

**Test File**: `tests/providers/metadata/test_media_file_transformations.py`

**Test Coverage**:
1. MediaFile.save() applies transformations to generic tags (not internal tags)
2. bypass_transformations parameter skips transformations
3. Metadata/AutoFormatManualEdits preference controls manual edit formatting
4. Transformation failures fall back to original value
5. Multiple tags transformed in single save()
6. Analyzer outputs always go through transformations
7. Empty values handled correctly

### Test Fixtures

Use pytest fixtures to mock QSettings with test preferences for consistent testing.

## Migration Plan

### Phase 1: Core System

1. Implement TransformerBase with `applicable_tags` class attribute
2. Implement multi-tag transformers (EmptyStringHandler, WhitespaceTrimmer)
3. Implement transformer registry (reads `applicable_tags` from each transformer)
4. Add unit tests for core components

### Phase 2: MediaFile Integration & Bypass

1. Add `bypass_transformations` parameter to MediaFile.save()
2. Add `Metadata/AutoFormatManualEdits` user preference (default: True)
3. Integrate transformation pipeline with bypass logic
4. Add integration tests for bypass behavior

### Phase 3: Implement transformers

1. Implement BPMFormatter
2. Implement MusicalKeyFormatter
3. Update StubBPMAnalyzer to return raw float
4. Add tests

### Phase 4: Documentation & Cleanup

1. Document how to add new transformers
2. Update analyzer documentation to remove formatting requirements
3. Update aubio BPM analyzer design to remove formatting
4. Document bypass mechanism and user preference

## Future Enhancements

### Performance Optimizations

1. **Preference Caching**: Cache QSettings values, invalidate on preference change
2. **Singleton Transformers**: Reuse transformer instances per thread
3. **Lazy Registration**: Only load transformers when needed

## References

- **Epic**: `doc/epics/20251013_Tag_Value_Transformations.md`
- **MediaFile**: `src/providers/metadata/media_file.py`
- **Preferences Window**: `doc/designs/preferences_window.md`
- **Analyzer System**: `doc/designs/analyzer_system.md`
- **StubBPM Analyzer**: `src/providers/analysis/bpm/stub_bpm.py`