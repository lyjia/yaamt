# Epic: Tag Value Transformations System

**Created**: 2025-10-13

## Problem Statement

Currently, each analyzer is responsible for formatting its output values according to user preferences (e.g., BPM decimal places, musical key notation). This creates several issues:

1. **Code Duplication**: Each analyzer must implement the same formatting logic
2. **Inconsistency Risk**: Different analyzers might format values differently due to bugs or oversights
3. **Maintenance Burden**: Adding new formatting rules requires touching every affected analyzer
4. **Limited Scope**: Formatting only applies to analyzer outputs, not user edits or imported data

## Proposed Solution

Centralize all tag value transformation logic in MediaFile, creating a pipeline that processes tag values before they are written to files. This system should:

- Apply transformations based on user preferences from QSettings
- Work consistently for all data sources (analyzers, user edits, imports)
- Be extensible for new transformation types
- Use a registry pattern similar to the analyzer system

## Use Cases

### BPM Decimal Place Formatting
**Input**: `173.94` (float from analyzer)
**User Preference**: 0 decimal places
**Output**: `"174"` (string)

### Musical Key Notation Conversion
**Input**: `"Ebmin"` (standard notation from analyzer)
**User Preference**: Camelot notation
**Output**: `"2A"` (Camelot notation)

### Whitespace Trimming
**Input**: `"  My Song Title  "` (user input with spaces)
**Output**: `"My Song Title"` (trimmed)

### Future: Genre Standardization
**Input**: `"Hip-Hop"` (various spellings)
**User Preference**: Standardize to MusicBrainz genres
**Output**: `"Hip Hop"` (standardized)

## Requirements

1. **Single Responsibility**: Transformers handle one specific type of transformation
2. **Generic Tag Focus**: Transformations operate on generic tag names (not internal tags)
3. **Preferences Integration**: Read configuration from QSettings
4. **Order Control**: Transformations must apply in a predictable order
5. **Error Handling**: Invalid inputs should be handled gracefully
6. **Type Flexibility**: Accept various input types (int, float, string) and normalize
7. **Transparency**: Users should understand what transformations are being applied
8. **Performance**: Transformations must be efficient (called frequently)

## Success Criteria

- [ ] Analyzers can return raw values without formatting concerns
- [ ] User preferences control all tag value formatting consistently
- [ ] StubBPMAnalyzer updated to use transformation system
- [ ] All tag writes (analyzer, user edit, import) go through transformations
- [ ] New transformations can be added without modifying MediaFile.save()
- [ ] Test coverage for all standard transformers
- [ ] Documentation explains how to add new transformers

## Out of Scope

- Validation of tag values (that's separate from transformation)
- Reading/displaying tag values (transformations only apply on write)
- Provider-specific internal tag transformations
- Complex multi-tag transformations (e.g., "fix album artist based on artist")

## Technical Considerations

- Transformation order matters (trim spaces before other operations)
- Some transformations are universal (trim), others tag-specific (BPM format)
- Need to handle missing preferences gracefully (sensible defaults)
- Performance: minimize QSettings reads (cache preferences?)
- Thread safety: transformations may be called from worker threads

## Dependencies

- QSettings for user preferences (already implemented)
- Preferences window with metadata settings (already implemented)
- Generic tag name system (already in MediaFile)

## Related Work

- Analyzer System (`doc/designs/analyzer_system.md`)
- Preferences Window (`doc/designs/preferences_window.md`)
- MediaFile (`src/models/media_file.py`)
