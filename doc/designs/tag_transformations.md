# Tag Value Transformations Design Specification

**Epic**: `doc/epics/20251013_Tag_Value_Transformations.md`

## Overview

The Tag Value Transformations system provides centralized formatting and normalization of metadata tag values before they are written to files. This ensures consistent formatting across all data sources (analyzers, user edits, imports) and eliminates the need for analyzers to handle formatting logic.

## Goals

1. Centralize all tag value transformation logic in one place
2. Apply user preferences consistently to all tag writes
3. Enable extensibility for new transformation types
4. Remove formatting responsibility from analyzers
5. Support transformations from any input type (int, float, string) to proper output format

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Data Sources (Analyzers, UI, Imports)                      │
│  Returns raw values: 173.94, "Ebmin", "  Title  "          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  MediaFile.save(changes)                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Transformation Pipeline                            │    │
│  │  1. Load user preferences from QSettings            │    │
│  │  2. For each tag value in changes:                  │    │
│  │     a. Look up applicable transformers              │    │
│  │     b. Apply transformers in order                  │    │
│  │     c. Replace value with transformed result        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Write to Providers                                 │    │
│  │  (existing MediaFile.save() logic)                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────┐
        │  File written with       │
        │  formatted values        │
        └──────────────────────────┘
```

### Transformer Registry

```
┌─────────────────────────────────────────────────────────────┐
│  Transformer Registry (module-level)                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Universal Transformers (apply to all tags):        │    │
│  │  1. WhitespaceTrimmer                               │    │
│  │  2. EmptyStringHandler                              │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Tag-Specific Transformers:                         │    │
│  │  'bpm' -> [BPMFormatter]                            │    │
│  │  'key' -> [MusicalKeyFormatter]                     │    │
│  │  'genre' -> [GenreStandardizer] (future)            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. TransformerBase (Abstract Base Class)

**Location**: `src/models/tag_transformers/base.py`

**Purpose**: Defines interface all tag transformers must implement.

**Interface**:
```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from PySide6.QtCore import QSettings


class TransformerBase(ABC):
    """
    Abstract base class for tag value transformers.

    Transformers convert raw tag values into properly formatted strings
    according to user preferences. They are called by MediaFile.save()
    before writing tags to files.
    """

    # Class attributes
    name: str = "Unnamed Transformer"
    description: str = ""
    version: str = "1.0.0"

    def __init__(self, settings: Optional[QSettings] = None):
        """
        Initialize transformer with QSettings instance.

        Args:
            settings: QSettings instance for reading user preferences.
                     If None, creates new instance.
        """
        self.settings = settings or QSettings("Lyjia", "Audio Metadata Tool")

    @abstractmethod
    def transform(self, value: Any, tag_name: str) -> str:
        """
        Transform a tag value according to user preferences.

        Args:
            value: Raw value to transform (may be int, float, str, etc.)
            tag_name: Generic tag name being transformed

        Returns:
            Transformed value as string suitable for writing to file

        Raises:
            ValueError: If value cannot be transformed (caller should handle)
        """
        pass

    @classmethod
    def applies_to_tag(cls, tag_name: str) -> bool:
        """
        Check if this transformer should be applied to the given tag.

        Args:
            tag_name: Generic tag name to check

        Returns:
            True if transformer applies to this tag, False otherwise.
            Universal transformers (like trim) should return True for all tags.
        """
        return False

    @property
    def priority(self) -> int:
        """
        Transformation priority (lower = earlier in pipeline).

        Universal transformers (trim, empty string) should have low priority
        to run first. Tag-specific transformers should have higher priority.

        Returns:
            Integer priority value (0-100, default 50)
        """
        return 50
```

**Key Design Points**:
- Each transformer is stateless except for QSettings reference
- Transformers receive the generic tag name for context
- Priority system controls application order
- Universal transformers apply to all tags
- Tag-specific transformers check tag name via `applies_to_tag()`

### 2. Standard Transformers

#### WhitespaceTrimmer (Universal)

**Location**: `src/models/tag_transformers/whitespace_trimmer.py`

**Purpose**: Remove leading/trailing whitespace from all string values.

**Details**:
- Priority: 10 (run early)
- Applies to: All tags
- Logic: `str(value).strip()`
- No user preferences needed

**Implementation**:
```python
class WhitespaceTrimmer(TransformerBase):
    name = "Whitespace Trimmer"
    description = "Removes leading and trailing whitespace from all tag values"
    version = "1.0.0"

    @property
    def priority(self) -> int:
        return 10  # Run early

    @classmethod
    def applies_to_tag(cls, tag_name: str) -> bool:
        return True  # Universal

    def transform(self, value: Any, tag_name: str) -> str:
        if value is None:
            return ""
        return str(value).strip()
```

#### EmptyStringHandler (Universal)

**Location**: `src/models/tag_transformers/empty_string_handler.py`

**Purpose**: Normalize empty/None values to empty string.

**Details**:
- Priority: 5 (run first)
- Applies to: All tags
- Logic: Convert None, empty string, whitespace-only to `""`
- No user preferences needed

**Implementation**:
```python
class EmptyStringHandler(TransformerBase):
    name = "Empty String Handler"
    description = "Normalizes empty, None, and whitespace-only values to empty string"
    version = "1.0.0"

    @property
    def priority(self) -> int:
        return 5  # Run first

    @classmethod
    def applies_to_tag(cls, tag_name: str) -> bool:
        return True  # Universal

    def transform(self, value: Any, tag_name: str) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        return "" if not s else s
```

#### BPMFormatter (Tag-Specific)

**Location**: `src/models/tag_transformers/bpm_formatter.py`

**Purpose**: Format BPM values according to user's decimal places preference.

**Details**:
- Priority: 50 (default)
- Applies to: `'bpm'` tag only
- Reads: `Analyzers/CategoryOptions/bpm/decimal_places` (default: 0, range: 0-3)
- Logic:
  - Parse input as float (handle int, float, string inputs)
  - Round to specified decimal places
  - Format as string (integer if 0 decimals, float otherwise)

**Implementation**:
```python
class BPMFormatter(TransformerBase):
    name = "BPM Formatter"
    description = "Formats BPM values according to user's decimal places preference"
    version = "1.0.0"

    @classmethod
    def applies_to_tag(cls, tag_name: str) -> bool:
        return tag_name == 'bpm'

    def transform(self, value: Any, tag_name: str) -> str:
        # Handle empty/None
        if value is None or value == "":
            return ""

        try:
            # Parse as float
            bpm = float(value)

            # Read decimal places preference
            decimal_places = self.settings.value(
                "Analyzers/CategoryOptions/bpm/decimal_places",
                0,
                type=int
            )
            decimal_places = max(0, min(3, decimal_places))  # Clamp to 0-3

            # Format according to preference
            if decimal_places == 0:
                return str(int(round(bpm)))
            else:
                return f"{bpm:.{decimal_places}f}"

        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot format '{value}' as BPM: {e}")
```

#### MusicalKeyFormatter (Tag-Specific)

**Location**: `src/models/tag_transformers/musical_key_formatter.py`

**Purpose**: Convert musical key notation according to user preference.

**Details**:
- Priority: 50 (default)
- Applies to: `'key'` tag only
- Reads: `Analyzers/CategoryOptions/key/notation_format` (default: `"standard_abbrev"`)
- Supported formats:
  - `"standard_abbrev"`: Cmin, Amaj
  - `"standard_single"`: Cm, A
  - `"camelot"`: 6A, 8B
  - `"open_key"`: 1m, 12d
- Logic:
  - Parse input key notation (support various input formats)
  - Convert to target notation
  - Handle major/minor variants

**Implementation Outline**:
```python
class MusicalKeyFormatter(TransformerBase):
    name = "Musical Key Formatter"
    description = "Converts musical key notation according to user preference"
    version = "1.0.0"

    # Key conversion maps (abbreviated for clarity)
    STANDARD_TO_CAMELOT = {
        "C": "8B", "Cm": "5A",
        "Db": "3B", "Dbm": "12A",
        # ... full mapping
    }

    @classmethod
    def applies_to_tag(cls, tag_name: str) -> bool:
        return tag_name == 'key'

    def transform(self, value: Any, tag_name: str) -> str:
        if value is None or value == "":
            return ""

        # Read notation preference
        target_format = self.settings.value(
            "Analyzers/CategoryOptions/key/notation_format",
            "standard_abbrev",
            type=str
        )

        # Parse input key (normalize to standard form first)
        key_standard = self._parse_key(str(value))

        # Convert to target format
        if target_format == "camelot":
            return self._to_camelot(key_standard)
        elif target_format == "open_key":
            return self._to_open_key(key_standard)
        elif target_format == "standard_single":
            return self._to_standard_single(key_standard)
        else:  # standard_abbrev (default)
            return key_standard

    def _parse_key(self, value: str) -> str:
        """Parse various key formats to standard form."""
        # Implementation: handle Cmin, C minor, c, Cm, etc.
        pass

    def _to_camelot(self, key_standard: str) -> str:
        """Convert standard key to Camelot notation."""
        return self.STANDARD_TO_CAMELOT.get(key_standard, key_standard)

    # ... other conversion methods
```

### 3. Transformer Registry

**Location**: `src/models/tag_transformers/__init__.py`

**Purpose**: Central registry for discovering and applying transformers.

**Implementation**:
```python
from typing import Dict, List, Type, Any
from .base import TransformerBase
from .whitespace_trimmer import WhitespaceTrimmer
from .empty_string_handler import EmptyStringHandler
from .bpm_formatter import BPMFormatter
from .musical_key_formatter import MusicalKeyFormatter

# Registry: tag_name -> list of transformer classes
# Special key '*' = universal transformers
_TRANSFORMER_REGISTRY: Dict[str, List[Type[TransformerBase]]] = {}


def register_transformer(tag_name: str, transformer_class: Type[TransformerBase]):
    """
    Register a transformer for a specific tag or universally.

    Args:
        tag_name: Generic tag name, or '*' for universal transformers
        transformer_class: Transformer class to register
    """
    if tag_name not in _TRANSFORMER_REGISTRY:
        _TRANSFORMER_REGISTRY[tag_name] = []
    _TRANSFORMER_REGISTRY[tag_name].append(transformer_class)


def get_transformers_for_tag(tag_name: str) -> List[Type[TransformerBase]]:
    """
    Get all transformers that apply to a given tag, sorted by priority.

    Args:
        tag_name: Generic tag name

    Returns:
        List of transformer classes, sorted by priority (low to high)
    """
    transformers = []

    # Add universal transformers
    transformers.extend(_TRANSFORMER_REGISTRY.get('*', []))

    # Add tag-specific transformers
    transformers.extend(_TRANSFORMER_REGISTRY.get(tag_name, []))

    # Sort by priority
    transformers.sort(key=lambda t: t().priority)

    return transformers


def apply_transformations(tag_name: str, value: Any) -> str:
    """
    Apply all relevant transformations to a tag value.

    Args:
        tag_name: Generic tag name
        value: Raw value to transform

    Returns:
        Transformed value as string

    Raises:
        ValueError: If transformation fails
    """
    transformers = get_transformers_for_tag(tag_name)
    result = value

    for transformer_class in transformers:
        transformer = transformer_class()
        result = transformer.transform(result, tag_name)

    return result


# Register standard transformers
register_transformer('*', EmptyStringHandler)
register_transformer('*', WhitespaceTrimmer)
register_transformer('bpm', BPMFormatter)
register_transformer('key', MusicalKeyFormatter)
```

**Key Design Points**:
- Universal transformers use special key `'*'`
- Transformers sorted by priority before application
- Single function `apply_transformations()` for use by MediaFile
- Registry populated at module import time
- Easy to add new transformers without modifying registry code

### 4. MediaFile Integration

**Location**: `src/models/media_file.py`

**Integration Point**: `save()` method

**Modified save() Logic**:
```python
def save(self, changes=None):
    if not self._write_enabled:
        raise PermissionError("Write is not enabled for this file.")

    if changes is None:
        return

    # IMPORTANT: Apply transformations to all generic tag changes
    transformed_changes = changes.copy()

    if KEY_TAG_GENERIC in transformed_changes:
        from models.tag_transformers import apply_transformations

        transformed_generic = {}
        for tag, value in transformed_changes[KEY_TAG_GENERIC].items():
            try:
                transformed_generic[tag] = apply_transformations(tag, value)
            except ValueError as e:
                log.warning(f"Failed to transform {tag}={value}: {e}")
                # Keep original value if transformation fails
                transformed_generic[tag] = str(value)

        transformed_changes[KEY_TAG_GENERIC] = transformed_generic

    # Existing save logic continues with transformed_changes
    modified_providers = set()

    # Process generic tag changes (now with transformed values)
    for tag, value in transformed_changes.get(KEY_TAG_GENERIC, {}).items():
        internal_tag = self._generic_to_internal_map.get(tag, tag)
        if internal_tag in self._tag_writers[KEY_TAGS]:
            provider = self._tag_writers[KEY_TAGS][internal_tag][0]
            provider.set_tag(internal_tag, [value])
            modified_providers.add(provider)

    # ... rest of existing save() logic unchanged
```

**Key Design Points**:
- Transformations only apply to `KEY_TAG_GENERIC` changes
- `KEY_TAG_INTERNAL` bypasses transformations (provider-specific)
- Transformation errors logged but don't block save (fallback to original)
- Creates copy of changes dict to avoid modifying caller's data
- Import is local to avoid circular dependencies

## Module Structure

```
src/
└── models/
    └── tag_transformers/
        ├── __init__.py                  # Registry and apply_transformations()
        ├── base.py                      # TransformerBase abstract class
        ├── empty_string_handler.py      # EmptyStringHandler
        ├── whitespace_trimmer.py        # WhitespaceTrimmer
        ├── bpm_formatter.py             # BPMFormatter
        └── musical_key_formatter.py     # MusicalKeyFormatter
```

## Transformation Pipeline Example

### Example 1: BPM from Analyzer

**Input** (from analyzer):
```python
changes = {
    KEY_TAG_GENERIC: {
        'bpm': 173.94  # float
    }
}
```

**Pipeline**:
1. EmptyStringHandler: `173.94` → `"173.94"` (convert to string)
2. WhitespaceTrimmer: `"173.94"` → `"173.94"` (no change)
3. BPMFormatter: `"173.94"` → `"174"` (rounds to 0 decimals per user pref)

**Output**: `"174"` written to file

### Example 2: Key from Analyzer

**Input**:
```python
changes = {
    KEY_TAG_GENERIC: {
        'key': 'Ebmin'  # standard notation
    }
}
```

**User Preference**: Camelot notation

**Pipeline**:
1. EmptyStringHandler: `'Ebmin'` → `'Ebmin'` (no change)
2. WhitespaceTrimmer: `'Ebmin'` → `'Ebmin'` (no change)
3. MusicalKeyFormatter: `'Ebmin'` → `'2A'` (converts to Camelot)

**Output**: `"2A"` written to file

### Example 3: Title from User Edit

**Input**:
```python
changes = {
    KEY_TAG_GENERIC: {
        'title': '  My Song Title  '  # has extra spaces
    }
}
```

**Pipeline**:
1. EmptyStringHandler: `'  My Song Title  '` → `'  My Song Title  '` (not empty)
2. WhitespaceTrimmer: `'  My Song Title  '` → `'My Song Title'` (trim)
3. (No tag-specific transformers for 'title')

**Output**: `"My Song Title"` written to file

## Error Handling

### Transformation Failures

**Strategy**: Log warning and fall back to original value (coerced to string)

**Rationale**:
- Don't block save operations due to transformation issues
- Preserve user data even if formatting fails
- Log for debugging purposes

**Example**:
```python
try:
    transformed_value = apply_transformations('bpm', 'invalid_bpm')
except ValueError as e:
    log.warning(f"Failed to transform bpm='invalid_bpm': {e}")
    transformed_value = str('invalid_bpm')  # Fallback
```

### Invalid User Preferences

**Strategy**: Use sensible defaults if preferences are invalid

**Example** (in BPMFormatter):
```python
decimal_places = self.settings.value("Analyzers/.../decimal_places", 0, type=int)
decimal_places = max(0, min(3, decimal_places))  # Clamp to valid range
```

## Performance Considerations

### QSettings Caching

**Issue**: Reading QSettings repeatedly for each tag transformation is slow.

**Solution**: Cache QSettings instance in transformer, read preferences once per save.

**Implementation**: Transformers receive QSettings instance in constructor, reuse it.

### Transformer Instance Reuse

**Current Design**: Create new transformer instance for each tag.

**Optimization** (future): Singleton transformers per thread with cached preferences.

**Trade-off**: Current design prioritizes simplicity over performance. Optimize if profiling shows bottleneck.

## Testing Requirements

### Unit Tests

**Test File**: `tests/models/test_tag_transformers.py`

**Test Cases**:

**WhitespaceTrimmer**:
1. Trim leading spaces
2. Trim trailing spaces
3. Trim both leading and trailing
4. Handle empty string
5. Handle None value

**EmptyStringHandler**:
1. Convert None to empty string
2. Convert whitespace-only to empty string
3. Preserve non-empty strings

**BPMFormatter**:
1. Format integer BPM (120 → "120")
2. Format float with 0 decimals (173.94 → "174")
3. Format float with 1 decimal (173.94 → "173.9")
4. Format float with 2 decimals (173.94 → "173.94")
5. Format float with 3 decimals (173.944 → "173.944")
6. Parse string input ("173.94" → "174")
7. Clamp decimal_places to 0-3 range
8. Default to 0 decimals when preference missing
9. Raise ValueError for invalid input ("abc")

**MusicalKeyFormatter**:
1. Parse various input formats (Cmin, C minor, Cm)
2. Convert to Camelot (Cmin → 5A)
3. Convert to Open Key (Cmin → 1m)
4. Convert to standard_single (Cmin → Cm)
5. Preserve standard_abbrev (Cmin → Cmin)
6. Handle empty/None input
7. Default to standard_abbrev when preference missing
8. Handle invalid key notation gracefully

**Transformer Registry**:
1. Register universal transformer
2. Register tag-specific transformer
3. Get transformers for tag (includes universal + specific)
4. Transformers sorted by priority
5. apply_transformations() calls all transformers in order
6. apply_transformations() handles ValueError

### Integration Tests

**Test File**: `tests/models/test_media_file_transformations.py`

**Test Cases**:
1. MediaFile.save() applies transformations to generic tags
2. MediaFile.save() does not transform internal tags
3. Transformation failure falls back to original value
4. Multiple tags transformed in single save()
5. Empty values handled correctly
6. Analyzer result goes through transformations
7. User edit goes through transformations

### Test Fixtures

**QSettings Mocking**: Use pytest fixtures to mock QSettings with test preferences

**Example**:
```python
@pytest.fixture
def mock_bpm_settings(monkeypatch):
    """Mock QSettings to return specific BPM decimal places."""
    def mock_value(key, default, type):
        if key == "Analyzers/CategoryOptions/bpm/decimal_places":
            return 2  # Test with 2 decimal places
        return default

    monkeypatch.setattr(QSettings, "value", mock_value)
```

## Migration Plan

### Phase 1: Core System

1. Implement TransformerBase
2. Implement universal transformers (EmptyStringHandler, WhitespaceTrimmer)
3. Implement transformer registry
4. Add unit tests for core components

### Phase 2: BPM Transformation

1. Implement BPMFormatter
2. Integrate with MediaFile.save()
3. Update StubBPMAnalyzer to return raw float
4. Add integration tests

### Phase 3: Key Transformation

1. Implement MusicalKeyFormatter
2. Add unit tests
3. Add integration tests

### Phase 4: Documentation & Cleanup

1. Document how to add new transformers
2. Update analyzer documentation to remove formatting requirements
3. Update aubio BPM analyzer design to remove formatting

## Future Enhancements

### Additional Transformers

1. **GenreStandardizer**: Map variant genre names to standard forms
2. **DateFormatter**: Normalize date formats (YYYY-MM-DD, YYYY, etc.)
3. **CommentSanitizer**: Remove unwanted prefixes/suffixes from comments
4. **ArtistNormalizer**: Handle "The Beatles" vs "Beatles, The"

### Advanced Features

1. **Conditional Transformations**: Apply transformation based on other tag values
2. **Multi-Tag Transformations**: Sync artist/album_artist automatically
3. **Custom User Transformers**: Allow users to define regex-based transformers
4. **Transformation Preview**: Show user what will change before saving
5. **Transformation History**: Track what transformations were applied when

### Performance Optimizations

1. **Preference Caching**: Cache QSettings values, invalidate on preference change
2. **Singleton Transformers**: Reuse transformer instances per thread
3. **Lazy Registration**: Only load transformers when needed

## References

- **Epic**: `doc/epics/20251013_Tag_Value_Transformations.md`
- **MediaFile**: `src/models/media_file.py`
- **Preferences Window**: `doc/designs/preferences_window.md`
- **Analyzer System**: `doc/designs/analyzer_system.md`
- **StubBPM Analyzer**: `src/providers/analysis/bpm/stub_bpm.py`
