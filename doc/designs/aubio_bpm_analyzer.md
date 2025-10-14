# Aubio BPM Analyzer Design Specification

**Epic**: `doc/epics/20251013_Add_aubio_bpm_analysis.md`

## Overview

This design specifies the implementation of a real BPM analyzer using the `aubio` library. The analyzer will follow the established analyzer system patterns and provide configurable BPM detection with streaming audio support.

## Goals

1. Implement a functional BPM analyzer using `aubio.tempo` for beat detection
2. Follow the existing analyzer system design pattern (StubBPMAnalyzer as reference)
3. Stream audio data without loading entire files into memory
4. Expose aubio's configurable parameters for future tuning
5. Return raw BPM values (float) - formatting handled by tag transformation system
6. Request mono audio format via audio format adaptation system

## Component Details

### File Location

**Path**: `src/providers/analysis/bpm/aubio_bpm.py`

### Class Definition

**Name**: `AubioBPMAnalyzer`

**Base Class**: `AnalyzerBase` (from `providers.analysis.base`)

**Class Attributes**:
- `name`: "Aubio BPM Analyzer"
- `description`: "Detects tempo using aubio's beat tracking algorithm"
- `category`: "bpm"
- `version`: "1.0.0"

### Core Functionality

#### Algorithm Overview

The analyzer will use aubio's tempo detection approach:

1. Create an `aubio.tempo` object with configurable parameters
2. Stream audio chunks from the MediaFile's audio stream
3. Feed audio chunks to the tempo detector
4. Collect detected beat timestamps
5. Calculate BPM from beat intervals using median of differences
6. Return BPM as string for metadata storage

#### Audio Streaming Integration

**Stream Access**:
- Use `self.media_file.get_audio_stream(format_descriptor)` with AudioFormatDescriptor requesting mono audio
- Audio Format Adaptation system handles stereo→mono conversion automatically
- Do NOT call `AudioStreamFactory` directly (violates design convention)
- Close the audio stream in a `finally` block to ensure cleanup

**Audio Format Requirements**:
- Request mono audio via AudioFormatDescriptor
- Accept native sample rate (aubio adapts to any sample rate)
- Convert bytes from audio stream to numpy float32 arrays
- No manual channel mixing needed (format adapter handles it)

#### Configurable Parameters

All aubio parameters must be exposed as configurable options, even if not initially presented to users:

**Primary Parameters**:
- `method` (string): Beat detection method
  - Default: `"default"`
  - Options: `"default"`, `"specdiff"`, `"energy"`, `"hfc"`, `"complex"`, `"phase"`, `"wphase"`, `"kl"`, `"mkl"`, `"specflux"`
  - Description: Algorithm used for onset detection

- `buf_size` / `win_s` (int): Window size in samples
  - Default: `1024`
  - Description: Size of analysis window

- `hop_size` (int): Hop size in samples
  - Default: `512`
  - Description: Number of samples between successive analysis windows

- `samplerate` (int): Sample rate in Hz
  - Default: Use the audio stream's native sample rate
  - Description: Sample rate for analysis (0 = use file's native rate)

**Processing Mode** (convenience preset):
- `mode` (string): Preset configuration
  - Default: `"default"`
  - Options:
    - `"default"`: Standard quality (samplerate=44100, win_s=1024, hop_s=512)
    - `"fast"`: Faster processing (samplerate=8000, win_s=512, hop_s=128)
  - Description: Pre-configured parameter set for speed/quality tradeoff

**Common Analyzer Options** (inherited from base):
- `overwrite_existing` (bool): Whether to overwrite existing BPM values
  - Default: `False`
  - Description: If False, skip analysis if BPM already exists

**Note**: BPM formatting (decimal places) is handled by the Tag Transformations system in MediaFile.save(), not by the analyzer. The analyzer returns raw float values.

### Implementation Outline

#### Key Steps

1. **Initialization**:
   - Accept MediaFile instance in constructor
   - Store analyzer options from options dict

2. **Validation**:
   - Check if file is readable via MediaFile
   - Check if BPM already exists (respect `overwrite_existing` option)
   - Verify aubio is available (import check)

3. **Audio Stream Setup**:
   - Create AudioFormatDescriptor requesting mono audio (channels=1)
   - Open adapted audio stream from MediaFile using format descriptor
   - Determine sample rate from adapted stream
   - Initialize aubio.tempo object with parameters

4. **Beat Detection Loop**:
   - Read audio chunks using stream.read()
   - Convert bytes to numpy float32 array (already mono from adapter)
   - Normalize to [-1.0, 1.0] range
   - Feed samples to tempo detector
   - Collect beat timestamps when detector signals a beat
   - Check for cancellation periodically

5. **BPM Calculation**:
   - Calculate intervals between consecutive beats
   - Convert intervals to BPM values (60 / interval_seconds)
   - Use median of BPM values to get final result
   - Handle edge cases (no beats, insufficient beats)
   - Return raw float BPM value (no formatting)

6. **Result Return**:
   - Return `AnalyzerResult` with success status
   - Include raw BPM value in data dict: `{'bpm': <float>}` (e.g., `{'bpm': 173.94}`)
   - Tag transformation system handles formatting during MediaFile.save()
   - Handle errors and return appropriate AnalyzerResult with error message

7. **Cleanup**:
   - Close audio stream in finally block
   - Ensure resources are released even on error

#### Error Handling

**Validation Errors** (return skipped result):
- BPM already exists and overwrite_existing=False
- File too short (less than ~5 seconds)
- Audio stream cannot be opened

**Analysis Errors** (return failed result):
- aubio library not available
- Audio format incompatible
- No beats detected in audio
- Corrupted audio data causing exceptions

**Exception Pattern**:
```
try:
    # validation checks (return skipped if needed)
    # open audio stream
    # perform analysis
    # check for cancellation
    # return success result
except ImportError as e:
    # aubio not available
    return AnalyzerResult(success=False, error="aubio library not available")
except Exception as e:
    # unexpected errors
    log.error(...)
    return AnalyzerResult(success=False, error=str(e))
finally:
    # close audio stream if opened
```

### Settings Widget

The `get_settings_widget()` method should return a QWidget with controls for:

**Controls**:
1. **Method dropdown**: QComboBox with algorithm options
2. **Mode selection**: QComboBox or radio buttons for "default" vs "fast"
3. **Advanced section** (collapsible QGroupBox):
   - Window size: QSpinBox
   - Hop size: QSpinBox
   - Sample rate: QSpinBox (0 = auto)

**Widget Object Names** (for option retrieval):
- `"method"`: Algorithm selection
- `"mode"`: Processing mode
- `"buf_size"`: Window size
- `"hop_size"`: Hop size
- `"samplerate"`: Target sample rate

**Layout**:
- Use QFormLayout for main controls
- Use QGroupBox for advanced section (initially collapsed/hidden)
- Include tooltips explaining each parameter
- Default values should match analyzer defaults

**Note**: Decimal places is NOT included in the analyzer settings widget. It is controlled globally via the Preferences window (Metadata pane) and applies to all BPM analyzers.

### Registration

**Manifest Update**:
Add import to `src/providers/analysis/_manifest.py`:
```
# BPM analyzers
from providers.analysis.bpm import stub_bpm
from providers.analysis.bpm import aubio_bpm  # Add this line
```

This ensures the analyzer is discovered by the analyzer system during startup.

## Data Flow

### Input
- MediaFile instance with audio stream capability
- Options dict containing configuration parameters

### Processing
1. Analyzer creates AudioFormatDescriptor(channels=1) for mono
2. MediaFile.get_audio_stream(format_descriptor) → adapted mono stream
3. Read adapted stream → raw audio bytes (already mono)
4. Raw bytes → numpy float32 arrays
5. Float arrays → aubio.tempo detector
6. Beat timestamps → BPM calculation (median of intervals)
7. Return raw float BPM value

### Output
- AnalyzerResult with:
  - `success=True` and `data={'bpm': 173.94}` on success (raw float)
  - `success=True, skipped=True` with reason if skipped
  - `success=False` with error message if failed

### Integration
- Raw BPM value passed to MediaFile.save() with generic tag `'bpm'`
- Tag Transformations system applies BPMFormatter during save
- BPMFormatter reads decimal_places preference and formats value
- Final formatted string written to file by metadata provider

## Implementation Notes

### aubio Python API Usage

**Import**:
```
import aubio
import numpy as np
from providers.audio.format_descriptor import AudioFormatDescriptor
```

**Request Mono Audio Stream**:
```
# Request mono audio (format adapter handles stereo→mono conversion)
format_desc = AudioFormatDescriptor(channels=1)
audio_stream = self.media_file.get_audio_stream(format_desc)
```

**Tempo Object Creation**:
```
tempo = aubio.tempo(method, win_s, hop_s, samplerate)
```

**Processing Loop Pattern** (simplified - no manual channel mixing):
```
while True:
    audio_bytes = audio_stream.read(hop_size)
    if not audio_bytes:
        break

    # Convert bytes to float32 numpy array
    # Audio is already mono from format adapter
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)

    # Normalize to [-1.0, 1.0] range
    samples = samples / 32768.0

    # Create aubio fvec and process
    fvec = aubio.fvec(len(samples))
    fvec[:] = samples

    is_beat = tempo(fvec)
    if is_beat:
        beat_time = tempo.get_last_s()
        beats.append(beat_time)
```

**BPM Calculation** (returns raw float):
```
if len(beats) > 1:
    intervals = np.diff(beats)  # Time between beats
    bpms = 60.0 / intervals     # Convert to beats per minute
    final_bpm = float(np.median(bpms))

    # Return raw float value - Tag Transformations system handles formatting
    return AnalyzerResult(success=True, data={'bpm': final_bpm})
else:
    # Insufficient data
    return AnalyzerResult(success=False, error="Insufficient beats detected")
```

### Memory Considerations

- Stream audio in chunks (don't load entire file)
- Use hop_size parameter to control chunk size
- Typical hop_size=512 samples = 512*2*2 bytes = 2KB per chunk for 16-bit stereo
- Beat list grows with file length but is minimal (timestamps only)
- Release audio stream as soon as processing completes

### Performance Expectations

**Processing Speed**:
- Default mode: Approximately 10-50x realtime (30s file in 0.5-3s)
- Fast mode: Approximately 50-200x realtime (30s file in 0.15-0.6s)
- Actual speed depends on CPU and file format

**Accuracy**:
- Aubio typically accurate within ±2 BPM for consistent tempo music
- May struggle with:
  - Tempo changes within track
  - Complex polyrhythms
  - Very slow tempos (<60 BPM) or fast tempos (>200 BPM)
  - Non-percussive or ambient music

### Dependencies

**Required**:
- `aubio` Python package (pip install aubio)
- `numpy` (typically already required for audio processing)

**Installation**:
- Add `aubio` to requirements.txt
- Gracefully handle ImportError if not installed

## Testing Requirements

### Unit Tests

**Test File**: `tests/providers/analysis/bpm/test_aubio_bpm.py`

**Test Cases**:
1. Test BPM detection on known-tempo fixture file (verify raw float output)
2. Test overwrite_existing=False skips when BPM exists
3. Test overwrite_existing=True replaces existing BPM
4. Test cancellation during analysis
5. Test error handling for missing aubio library
6. Test error handling for corrupted audio
7. Test mode switching (default vs fast)
8. Test analyzer receives mono stream (verify via AudioFormatDescriptor)
9. Test analyzer works with stereo source file (adapter converts to mono)
10. Test settings widget creation and option retrieval
11. Test raw float BPM value returned (not formatted string)

**Fixture Requirements**:
- Audio file with known steady tempo (e.g., 120 BPM)
- Audio file with ambiguous or varying tempo
- Very short audio file (<5 seconds)

### Integration Tests

1. Verify analyzer appears in BPM category in analyzer registry
2. Verify analyzer is shown in AnalyzerSetupDialog
3. Test full workflow: select files → configure → analyze → verify BPM saved
4. Test with various audio formats (WAV, MP3, FLAC)

### Manual Testing Checklist

- [ ] Analyze a folder of music files with known BPMs
- [ ] Compare results to reference values (DJ software, manual counting)
- [ ] Test cancellation during long-running batch
- [ ] Test with mono and stereo files
- [ ] Test with various sample rates (44.1kHz, 48kHz, 96kHz)
- [ ] Verify memory usage stays reasonable during analysis
- [ ] Test fast mode vs default mode speed and accuracy

## Future Enhancements

### Phase 2
- Expose aubio's confidence scores to user
- Support for tempo range constraints (e.g., "only detect 80-140 BPM")
- Multi-pass analysis for tempo change detection

### Phase 3
- Alternative algorithms (Essentia, madmom) for comparison
- Ensemble method combining multiple analyzer results
- Machine learning post-processing for ambiguous cases (half/double tempo)

## System Dependencies

This analyzer leverages two new systems:

### Tag Transformations System
**Design**: `doc/designs/tag_transformations.md`

The analyzer returns raw float BPM values. The Tag Transformations system:
- Intercepts values in MediaFile.save()
- Applies BPMFormatter transformer
- Reads decimal_places preference from QSettings
- Formats float to string according to user preference
- Result: Consistent formatting across all BPM analyzers

### Audio Format Adaptation System
**Design**: `doc/designs/audio_format_adaptation.md`

The analyzer requests mono audio via AudioFormatDescriptor. The adaptation system:
- Creates ChannelMixingAdapter if source is stereo
- Automatically converts stereo→mono (averages channels with 1/√2 coefficient)
- Returns adapted stream implementing AudioStreamBase
- Result: Analyzer receives mono audio regardless of source format

**Implementation Note**: Both systems must be implemented before this analyzer.

## References

- **Epic**: `doc/epics/20251013_Add_aubio_bpm_analysis.md`
- **Analyzer System**: `doc/designs/analyzer_system.md`
- **Tag Transformations**: `doc/designs/tag_transformations.md`
- **Audio Format Adaptation**: `doc/designs/audio_format_adaptation.md`
- **StubBPMAnalyzer**: `src/providers/analysis/bpm/stub_bpm.py`
- **AnalyzerBase**: `src/providers/analysis/base.py`
- **MediaFile**: `src/models/media_file.py`
- **AudioStreamBase**: `src/providers/audio/base.py`
- **aubio Documentation**: https://aubio.org/manual/latest/
- **aubio Tempo Demo**: https://github.com/aubio/aubio/blob/master/python/demos/demo_bpm_extract.py
