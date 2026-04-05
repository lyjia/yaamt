# Audio Format Adaptation Design Specification

**Epic**: `doc/epics/20251013_Audio_Format_Adaptation.md`

## Overview

The Audio Format Adaptation system enables transparent on-the-fly conversion of audio stream formats. Consumers specify their desired audio format (sample rate, channels, bit depth), and receive a stream in that format regardless of the source file's native format. This eliminates code duplication and allows analyzers and playback systems to focus on their core functionality.

## Goals

1. Provide transparent format conversion for audio streams
2. Support sample rate conversion, channel mixing, and bit depth conversion
3. Maintain AudioStreamBase interface compatibility
4. Enable seeking on adapted streams where possible
5. Use packaging-friendly libraries (scipy, NumPy)
6. Minimize performance overhead and memory usage

## Architecture

### Component Overview

```
Consumer (Analyzer/Playback)
       ↓
   Requests format via AudioFormatDescriptor
       ↓
MediaFile.get_audio_stream(format_descriptor)
       ↓
AudioStreamFactory.get_stream(filepath, format_descriptor)
       ↓
   Creates base stream (MiniaudioStream)
       ↓
   Compares native format vs requested format
       ↓
   If different: wrap with adapter(s)
       ↓
┌──────────────────────────────────────┐
│  Adapter Chain (if needed):          │
│  ResamplingAdapter                   │
│    ↓                                 │
│  ChannelMixingAdapter                │
│    ↓                                 │
│  BitDepthAdapter                     │
└──────────────────────────────────────┘
       ↓
   Return adapted stream (implements AudioStreamBase)
       ↓
Consumer reads/seeks transparently
```

### Decorator Pattern

Each adapter wraps an AudioStreamBase and presents the same interface:

```
┌─────────────────────────────────────────┐
│  ResamplingAdapter (AudioStreamBase)    │
│  ┌───────────────────────────────────┐  │
│  │  ChannelMixingAdapter             │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  MiniaudioStream (native)   │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Core Components

### 1. AudioFormatDescriptor

**Location**: `src/providers/audio/format_descriptor.py`

**Purpose**: Describes desired audio format parameters.

**Attributes**:
- `sample_rate`: Desired sample rate in Hz (None = accept native)
- `channels`: Desired number of channels (None = accept native)
- `sample_width`: Desired sample width in bytes (None = accept native)
- `sample_format`: 'int' or 'float' (None = accept native)

**Behavior**:
- Constructor accepts all four attributes as optional parameters
- Provides a `matches()` method to compare two descriptors (accounting for None as wildcard)
- Provides human-readable string representation

**Usage Examples**:
- Mono at 22050 Hz, 16-bit int: specify all four parameters
- Accept native format: specify no parameters (all None)
- Mono only, accept other native parameters: specify only channels=1

**Key Design Points**:
- None values mean "accept native format"
- Immutable once created
- Provides matching logic for determining if adaptation is needed

### 2. AdapterBase (Abstract)

**Location**: `src/providers/audio/adapters/base.py`

**Purpose**: Base class for all stream adapters. Implements the decorator pattern to wrap an existing AudioStreamBase and transform its output.

**Behavior**:
- Inherits from AudioStreamBase to maintain interface compatibility
- Constructor accepts a source AudioStreamBase to wrap
- Maintains internal state tracking whether the adapter is closed
- Abstract `read()` method must be implemented by subclasses
- `seek()` method may raise NotImplementedError if seeking not supported by adapter
- `close()` method closes both the adapter and the wrapped source stream
- Properties (`samplerate`, `nchannels`, `sample_width`, `duration_seconds`) return adapted format characteristics
- Supports context manager protocol (with statement)

**Key Design Points**:
- Wraps another AudioStreamBase (source)
- Implements full AudioStreamBase interface
- Seeking may not be supported by all adapters (raises NotImplementedError)
- Closes source stream when closed

### 3. ResamplingAdapter

**Location**: `src/providers/audio/adapters/resampling_adapter.py`

**Purpose**: Convert sample rate using scipy.signal.resample_poly.

**Implementation Strategy**:
- Use scipy.signal.resample_poly for efficiency with rational ratios
- Configure Kaiser window with beta=5.0 for good quality (beta=8.0 for critical quality)
- Maintain small internal buffer for filter edge effects
- Handle both upsampling and downsampling

**Constructor**:
- Accepts source stream and target sample rate
- Calculates up/down factors for resample_poly
- Initializes internal buffer for edge effects

**Read Behavior**:
1. Calculate how many source frames needed for requested output frames
2. Read from source (may combine buffered data + new data)
3. Apply resample_poly to audio data
4. Convert processed audio back to bytes
5. Update internal buffer with remaining samples

**Seek Behavior**:
1. Calculate corresponding source frame position
2. Seek source stream to that frame
3. Clear internal buffer
4. Note: May have slight inaccuracy (±1-2 frames) due to filter edge effects

**Properties**:
- `samplerate` returns the target sample rate

**Quality Parameters**:
- Window: Kaiser (scipy default), beta=5.0 minimum
- For critical quality: beta=8.0 or higher
- Future enhancement: Make beta configurable via preferences

### 4. ChannelMixingAdapter

**Location**: `src/providers/audio/adapters/channel_mixing_adapter.py`

**Purpose**: Convert between mono and stereo.

**Constructor**:
- Accepts source stream and target channel count (1 or 2)

**Read Behavior**:
1. Read requested frames from source stream
2. Convert bytes to numpy array
3. Apply channel conversion:
   - If stereo→mono: average channels with 1/√2 scaling to preserve RMS power
   - If mono→stereo: duplicate mono channel to both left and right
4. Convert processed audio back to bytes

**Seek Behavior**:
- Pass-through to source stream (channel mixing doesn't affect frame positions)

**Properties**:
- `nchannels` returns the target channel count

**Channel Mixing Algorithms**:
- Stereo→Mono: `mono = (left + right) / sqrt(2)`
- Mono→Stereo: `left = right = mono`
- Preserves RMS power level

### 5. BitDepthAdapter

**Location**: `src/providers/audio/adapters/bit_depth_adapter.py`

**Purpose**: Convert between different bit depths (16-bit, 24-bit, 32-bit, float).

**Constructor**:
- Accepts source stream, target sample width in bytes, and target sample format ('int' or 'float')

**Read Behavior**:
1. Read requested frames from source stream
2. Convert bytes to appropriate numpy dtype
3. Apply bit depth conversion based on source and target formats:
   - int→int: scale by ratio of maximum values
   - int→float: divide by 2^(bits-1), normalizing to [-1.0, 1.0]
   - float→int: multiply by 2^(bits-1)-1, clip to valid range, convert to integer
4. Convert processed audio back to bytes

**Seek Behavior**:
- Pass-through to source stream (bit depth doesn't affect frame positions)

**Properties**:
- `sample_width` returns the target sample width

**Conversion Formulas**:
- Int16→Float32: `float_val = int_val / 32768.0`
- Float32→Int16: `int_val = clip(float_val * 32767.0, -32768, 32767)`
- Int24→Int16: `int16_val = int24_val >> 8` (right shift 8 bits)
- Int16→Int24: `int24_val = int16_val << 8` (left shift 8 bits)

**Implementation Notes**:
- Handle int→int, int→float, float→int conversions
- Clip values to prevent overflow
- No dithering in Phase 1 (future enhancement)

### 6. MiniaudioStream Format Invariant

**Location**: `src/providers/audio/miniaudio_stream.py`

**Invariant**: The `sample_rate`, `channels_qty`, and `sample_width` properties
must exactly describe the bytes returned by `read()`.

MiniaudioStream is the single raw audio source for both playback and analysis.
It delivers audio as close to the source file's native format as possible:

- **Sample rate**: Native (passed explicitly to `miniaudio.stream_file()`).
- **Channels**: Native (passed explicitly to `miniaudio.stream_file()`).
- **Sample format**: Mapped to a streamable output format since not all native
  formats are streamable by miniaudio. The mapping preserves the codebase-wide
  convention that `sample_width == 4` implies float32:

| Source format | Stream output | Reported `sample_width` | Reason                             |
|---------------|---------------|-------------------------|------------------------------------|
| UNSIGNED8     | SIGNED16      | 2                       | Unsigned/signed mismatch in adapters |
| SIGNED16      | SIGNED16      | 2                       | Pass-through                       |
| SIGNED24      | FLOAT32       | 4                       | SIGNED24 not streamable by miniaudio |
| SIGNED32      | FLOAT32       | 4                       | Avoids width=4 int/float ambiguity |
| FLOAT32       | FLOAT32       | 4                       | Pass-through                       |

Consumers that need a different format (e.g., mono, different sample rate, int16)
request it via `AudioFormatDescriptor`, and the adapter chain handles conversion.
MiniaudioStream itself performs no conversion beyond the format mapping above.

### 7. AudioStreamFactory Enhancement

**Location**: `src/providers/audio/factory.py`

**Modified get_stream() Method**:

**Signature**:
- Accepts filepath and optional format_descriptor
- Returns AudioStreamBase

**Strategy**:
1. Create base stream (MiniaudioStream) from filepath
2. If format_descriptor is None, return base stream (native format)
3. Compare native format to requested format
4. Build adapter chain as needed:
   - Wrap with ResamplingAdapter if sample rates differ
   - Wrap with ChannelMixingAdapter if channel counts differ
   - Wrap with BitDepthAdapter if sample widths differ
5. Return adapted stream (or base stream if no adaptation needed)

**Pseudocode**:
```
function get_stream(filepath, format_descriptor):
    base_stream = create MiniaudioStream from filepath

    if format_descriptor is None:
        return base_stream

    stream = base_stream

    if format_descriptor.sample_rate differs from base_stream.samplerate:
        stream = wrap stream with ResamplingAdapter

    if format_descriptor.channels differs from base_stream.nchannels:
        stream = wrap stream with ChannelMixingAdapter

    if format_descriptor.sample_width differs from base_stream.sample_width:
        stream = wrap stream with BitDepthAdapter

    return stream
```

**Key Design Points**:
- Backward compatible: None format_descriptor = native stream
- Order matters: resample first, then mix, then convert bit depth
- Only creates adapters when needed (efficient)

### 8. MediaFile Integration

**Location**: `src/models/media_file.py`

**Modified get_audio_stream() Method**:

**Signature**:
- Accepts optional format_descriptor parameter
- Returns AudioStreamBase instance

**Behavior**:
- Delegates to AudioStreamFactory.get_stream() with file path and format_descriptor
- If format_descriptor is None, returns native format stream (backward compatible)
- If format_descriptor is provided, returns adapted stream matching requested format
- Raises exception if audio stream cannot be created

**Usage Examples**:
- Get native format stream: call with no arguments
- Get mono stream at 22050 Hz: call with AudioFormatDescriptor(sample_rate=22050, channels=1)

**Key Design Points**:
- Backward compatible: existing code works without changes
- Consumers now have choice: native or adapted format

## Module Structure

```
src/
└── providers/
    └── audio/
        ├── __init__.py
        ├── base.py                      # AudioStreamBase (existing)
        ├── factory.py                   # AudioStreamFactory (enhanced)
        ├── miniaudio_stream.py          # MiniaudioStream (existing)
        ├── format_descriptor.py         # NEW: AudioFormatDescriptor
        └── adapters/
            ├── __init__.py
            ├── base.py                  # NEW: AdapterBase
            ├── resampling_adapter.py    # NEW: ResamplingAdapter
            ├── channel_mixing_adapter.py # NEW: ChannelMixingAdapter
            └── bit_depth_adapter.py     # NEW: BitDepthAdapter
```

## Usage Examples

### Example 1: Analyzer Requesting Mono

An analyzer (e.g., aubio BPM analyzer) that requires mono audio:
1. Create AudioFormatDescriptor with channels=1, leaving other parameters as None
2. Request audio stream from MediaFile with this descriptor
3. Receive stream guaranteed to be mono (adapted if source is stereo)
4. Process audio in chunks by repeatedly calling read()
5. Stream automatically handles conversion from stereo to mono if needed

```
# In aubio_bpm.py
from providers.audio.format_descriptor import AudioFormatDescriptor

def analyze(self) -> AnalyzerResult:
    # Request mono audio at native sample rate
    format_desc = AudioFormatDescriptor(channels=1)

    with self.media_file.get_audio_stream(format_desc) as stream:
        # stream is guaranteed to be mono
        # Process audio...
        while True:
            audio_bytes = stream.read(hop_size)
            if not audio_bytes:
                break
            # Convert to numpy, feed to aubio...
```

### Example 2: Playback System with Hardware Limits

A playback system with hardware constraints (e.g., max 48kHz, 16-bit, stereo):
1. Create AudioFormatDescriptor specifying all hardware limits: sample_rate=48000, channels=2, sample_width=2, sample_format='int'
2. Request audio stream from MediaFile with this descriptor
3. Receive stream adapted to match hardware capabilities
4. Feed audio data directly to hardware output device
5. Stream automatically handles any necessary resampling, channel mixing, and bit depth conversion

```
# In playback system
from providers.audio.format_descriptor import AudioFormatDescriptor

# Hardware supports max 48kHz, 16-bit, stereo
hw_format = AudioFormatDescriptor(
    sample_rate=48000,
    channels=2,
    sample_width=2,
    sample_format='int'
)

stream = media_file.get_audio_stream(hw_format)
# stream is adapted to hardware capabilities
# Feed to audio output device...
```

### Example 3: Native Format (No Adaptation)

A waveform display that accepts any format:
1. Request audio stream from MediaFile with no format_descriptor parameter
2. Receive stream in native format with no overhead
3. Use stream's properties to determine actual format
4. Render waveform according to native format characteristics

```
# Waveform display accepts any format
stream = media_file.get_audio_stream()  # No format_descriptor
# stream is native format, no overhead
```

## Performance Considerations

### Computational Overhead

**Resampling**:
- scipy.signal.resample_poly: ~2-10x realtime (depends on quality, ratio)
- Efficient for rational ratios (44100→22050 faster than 44100→22000)

**Channel Mixing**:
- Negligible: simple NumPy operations
- ~0.1ms per second of audio

**Bit Depth Conversion**:
- Negligible: NumPy scaling and clipping
- ~0.1ms per second of audio

**Combined Pipeline**:
- Expect 5-15x realtime for typical adaptations on modern CPUs
- Real-time playback easily achievable

### Memory Usage

**Resampling**:
- Internal buffer: ~1-2 KB per stream (filter kernel)
- Per-read overhead: proportional to requested frames

**Channel Mixing / Bit Depth**:
- No internal buffers, process per-chunk
- Minimal overhead

### Seeking Performance

**Resampling**:
- Seek overhead: ~5-10ms (need to recalculate positions, clear buffers)
- Frame accuracy: ±1-2 frames due to filter edge effects

**Channel Mixing / Bit Depth**:
- Seek overhead: ~0.1ms (pass-through)
- Frame accuracy: exact

## Error Handling

### Unsupported Conversions

**Strategy**: Raise descriptive exceptions early

**Example**:
- 5.1 surround → stereo: NotImplementedError (Phase 1)
- Invalid sample rates: ValueError
- Invalid bit depths: ValueError

### Adapter Chain Failures

**Strategy**: Close all streams in chain, propagate exception

When building an adapter chain, if any adapter construction fails:
- Close all previously created streams in the chain
- If using context manager (with statement), __exit__ handles cleanup automatically
- Raise AudioAdaptationError describing the failure
- Ensures no resource leaks even when adapter chain creation fails

## Testing Requirements

### Unit Tests

**Test File**: `tests/providers/audio/adapters/test_adapters.py`

**Test Cases**:

**AudioFormatDescriptor**:
1. Create descriptor with all parameters
2. Create descriptor with partial parameters (None for others)
3. Test matches() method with various combinations
4. Test repr()

**ResamplingAdapter**:
1. Downsample 44100→22050 (exact 2:1 ratio)
2. Upsample 22050→44100
3. Non-rational ratio (44100→48000)
4. Seek after resampling
5. Read full file, verify frame count
6. Edge case: very short files (< filter kernel size)

**ChannelMixingAdapter**:
1. Stereo→Mono averaging
2. Mono→Stereo duplication
3. Verify RMS power preservation
4. Seek after channel mixing

**BitDepthAdapter**:
1. Int16→Int24
2. Int24→Int16
3. Int16→Float32
4. Float32→Int16
5. Clipping behavior (values outside range)
6. Seek after bit depth conversion

**Combined Adapters**:
1. Resample + channel mix
2. Channel mix + bit depth convert
3. All three adapters chained
4. Verify final output matches expected format

### Integration Tests

**Test File**: `tests/providers/audio/test_format_adaptation_integration.py`

**Test Cases**:
1. MediaFile.get_audio_stream() with format descriptor
2. MediaFile.get_audio_stream() without format descriptor (native)
3. AudioStreamFactory creates correct adapter chain
4. Full pipeline: file → adapted stream → consume → verify output
5. Test with various file formats (WAV, MP3, FLAC)

### Performance Tests

**Test File**: `tests/providers/audio/test_adapter_performance.py`

**Test Cases**:
1. Benchmark resampling speed (measure frames/second)
2. Benchmark full adaptation pipeline
3. Memory usage profiling
4. Verify real-time playback achievable (process faster than playback)

### Test Fixtures

**Required**:
- WAV files at various sample rates (22050, 44100, 48000, 96000)
- Mono and stereo versions
- Various bit depths (16-bit, 24-bit, 32-bit float)
- Short files (<1s) and longer files (10s+) for edge cases

## Migration Plan

### Phase 1: Core Infrastructure

1. Implement AudioFormatDescriptor
2. Implement AdapterBase
3. Update AudioStreamFactory signature (backward compatible)
4. Add basic unit tests

### Phase 2: Individual Adapters

1. Implement ChannelMixingAdapter (simplest)
2. Add unit tests for channel mixing
3. Implement BitDepthAdapter
4. Add unit tests for bit depth
5. Implement ResamplingAdapter (most complex)
6. Add unit tests for resampling

### Phase 3: Integration

1. Enhance AudioStreamFactory to build adapter chains
2. Update MediaFile.get_audio_stream()
3. Add integration tests

### Phase 4: Consumer Updates

1. Remove manual conversion code from analyzers
2. Update audio playback system
3. Add Debug menu to MainWindow with option to set audio playback sample rate, bit depth, and channels
4. Add unit tests for updated code

### Phase 5: Documentation & Polish

1. Document AudioFormatDescriptor API
2. Add examples to docstrings
4. Performance optimization and tuning based on profiling

## Future Enhancements

### Quality Improvements

1. **Dithering**: Add TPDF dithering for bit depth reduction
2. **Resampling Quality Settings**: User-configurable beta parameter
3. **Optional samplerate Library**: Fallback to higher quality if installed

### Advanced Features

1. **Multi-channel Downmix**: 5.1/7.1 → stereo with proper coefficients
2. **Caching**: Cache converted chunks for repeated reads
3. **Async Adaptation**: Pre-convert in background for smoother playback
4. **Format Negotiation**: Consumer specifies "preferred" vs "required"
5. **Normalization**: Volume normalization during conversion

### Performance Optimizations

1. **Vectorized Operations**: Optimize NumPy operations
2. **Chunk Size Tuning**: Optimize buffer sizes for cache efficiency

## References

- **Epic**: `doc/epics/20251013_Audio_Format_Adaptation.md`
- **Audio Subsystem**: `doc/designs/audio-subsystem.md`
- **MediaFile**: `src/models/media_file.py`
- **AudioStreamBase**: `src/providers/audio/base.py`
- **Analyzer System**: `doc/designs/analyzer_system.md`
- **scipy.signal.resample_poly**: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
