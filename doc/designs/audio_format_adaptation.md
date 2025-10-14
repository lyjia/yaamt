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

**Class Definition**:
```
class AudioFormatDescriptor:
    """
    Describes the desired format for an audio stream.

    Attributes:
        sample_rate: Desired sample rate in Hz (None = accept native)
        channels: Desired number of channels (None = accept native)
        sample_width: Desired sample width in bytes (None = accept native)
        sample_format: 'int' or 'float' (None = accept native)
    """

    def __init__(self,
                 sample_rate: Optional[int] = None,
                 channels: Optional[int] = None,
                 sample_width: Optional[int] = None,
                 sample_format: Optional[str] = None):
        """
        Initialize format descriptor.

        Args:
            sample_rate: Target sample rate (Hz), None for native
            channels: Target channel count (1=mono, 2=stereo), None for native
            sample_width: Target sample width in bytes (2=16-bit, 4=32-bit), None for native
            sample_format: 'int' or 'float', None for native

        Examples:
            # Mono at 22050 Hz, 16-bit int
            AudioFormatDescriptor(sample_rate=22050, channels=1, sample_width=2, sample_format='int')

            # Accept native format
            AudioFormatDescriptor()

            # Mono only, accept other native parameters
            AudioFormatDescriptor(channels=1)
        """

    def matches(self, other: 'AudioFormatDescriptor') -> bool:
        """Check if this format matches another (accounting for None = wildcard)."""

    def __repr__(self) -> str:
        """Human-readable representation."""
```

**Key Design Points**:
- None values mean "accept native format"
- Immutable once created
- Provides matching logic for determining if adaptation is needed

### 2. AdapterBase (Abstract)

**Location**: `src/providers/audio/adapters/base.py`

**Purpose**: Base class for all stream adapters.

**Interface**:
```
class AdapterBase(AudioStreamBase):
    """
    Abstract base class for audio stream adapters.

    Adapters wrap an existing AudioStreamBase and transform its output
    according to specific rules (resampling, channel mixing, etc).
    """

    def __init__(self, source_stream: AudioStreamBase):
        """
        Initialize adapter with source stream.

        Args:
            source_stream: The stream to adapt
        """
        self._source = source_stream
        self._is_closed = False

    @abstractmethod
    def read(self, n_frames: int) -> bytes:
        """Read adapted audio frames."""

    def seek(self, frame_offset: int) -> None:
        """Seek to frame in adapted stream (may not be supported by all adapters)."""
        raise NotImplementedError("Seeking not supported by this adapter")

    def close(self) -> None:
        """Close adapter and source stream."""
        if not self._is_closed:
            self._source.close()
            self._is_closed = True

    @property
    def samplerate(self) -> int:
        """Return adapted sample rate."""

    @property
    def nchannels(self) -> int:
        """Return adapted channel count."""

    @property
    def sample_width(self) -> int:
        """Return adapted sample width."""

    @property
    def duration_seconds(self) -> float:
        """Return duration (may be estimate for adapted streams)."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

**Key Design Points**:
- Wraps another AudioStreamBase (source)
- Implements full AudioStreamBase interface
- Seeking may not be supported by all adapters (raises NotImplementedError)
- Closes source stream when closed

### 3. ResamplingAdapter

**Location**: `src/providers/audio/adapters/resampling_adapter.py`

**Purpose**: Convert sample rate using scipy.signal.resample_poly.

**Implementation Notes**:
- Use scipy.signal.resample_poly for efficiency with rational ratios
- Configure Kaiser window with beta=5.0 for good quality
- Maintain small internal buffer for filter edge effects
- Handle both upsampling and downsampling

**Key Methods**:
```
class ResamplingAdapter(AdapterBase):
    """
    Adapter that resamples audio to a different sample rate.

    Uses scipy.signal.resample_poly with Kaiser windowing for high quality.
    """

    def __init__(self, source_stream: AudioStreamBase, target_samplerate: int):
        """
        Initialize resampling adapter.

        Args:
            source_stream: Source audio stream
            target_samplerate: Desired output sample rate
        """
        # Calculate up/down factors for resample_poly
        # Maintain internal buffer for edge effects
        # Initialize scipy resampler

    def read(self, n_frames: int) -> bytes:
        """
        Read resampled frames.

        Strategy:
        1. Calculate how many source frames needed for n_frames output
        2. Read from source (may need buffer + new data)
        3. Apply resample_poly
        4. Convert back to bytes
        5. Update buffer with remaining samples
        """

    def seek(self, frame_offset: int) -> None:
        """
        Seek in resampled stream.

        Strategy:
        1. Calculate corresponding source frame
        2. Seek source to that frame
        3. Clear internal buffer
        4. May have slight inaccuracy due to filter edge effects
        """

    @property
    def samplerate(self) -> int:
        return self._target_samplerate
```

**Resampling Quality Parameters**:
- Window: Kaiser (scipy default), beta=5.0 minimum
- For critical quality: beta=8.0 or higher
- Future: Make beta configurable via preferences

### 4. ChannelMixingAdapter

**Location**: `src/providers/audio/adapters/channel_mixing_adapter.py`

**Purpose**: Convert between mono and stereo.

**Implementation Notes**:
- Stereo→Mono: Average channels with 1/√2 coefficient (preserves RMS power)
- Mono→Stereo: Duplicate mono to both channels
- Process per-chunk in read() method

**Key Methods**:
```
class ChannelMixingAdapter(AdapterBase):
    """
    Adapter that mixes channels (mono/stereo conversion).
    """

    def __init__(self, source_stream: AudioStreamBase, target_channels: int):
        """
        Initialize channel mixing adapter.

        Args:
            source_stream: Source audio stream
            target_channels: Desired channel count (1 or 2)
        """

    def read(self, n_frames: int) -> bytes:
        """
        Read channel-mixed frames.

        Strategy:
        1. Read n_frames from source
        2. Convert bytes to numpy array
        3. If stereo→mono: average channels with 1/√2 scaling
        4. If mono→stereo: duplicate to both channels
        5. Convert back to bytes
        """

    def seek(self, frame_offset: int) -> None:
        """Seek source stream (channel mixing doesn't affect frame positions)."""
        self._source.seek(frame_offset)

    @property
    def nchannels(self) -> int:
        return self._target_channels
```

**Channel Mixing Algorithms**:
- Stereo→Mono: `mono = (left + right) / sqrt(2)`
- Mono→Stereo: `left = right = mono`
- Preserves RMS power level

### 5. BitDepthAdapter

**Location**: `src/providers/audio/adapters/bit_depth_adapter.py`

**Purpose**: Convert between different bit depths (16-bit, 24-bit, 32-bit, float).

**Implementation Notes**:
- Handle int→int, int→float, float→int conversions
- Clip values to prevent overflow
- No dithering in Phase 1

**Key Methods**:
```
class BitDepthAdapter(AdapterBase):
    """
    Adapter that converts bit depth and sample format.
    """

    def __init__(self, source_stream: AudioStreamBase,
                 target_sample_width: int,
                 target_sample_format: str):
        """
        Initialize bit depth adapter.

        Args:
            source_stream: Source audio stream
            target_sample_width: Target sample width in bytes
            target_sample_format: 'int' or 'float'
        """

    def read(self, n_frames: int) -> bytes:
        """
        Read bit-depth-converted frames.

        Strategy:
        1. Read n_frames from source
        2. Convert bytes to appropriate numpy dtype
        3. Apply bit depth conversion:
           - int→int: scale by ratio of max values
           - int→float: divide by 2^(bits-1), normalize to [-1.0, 1.0]
           - float→int: multiply by 2^(bits-1)-1, clip, convert
        4. Convert back to bytes
        """

    def seek(self, frame_offset: int) -> None:
        """Seek source stream (bit depth doesn't affect frame positions)."""
        self._source.seek(frame_offset)

    @property
    def sample_width(self) -> int:
        return self._target_sample_width
```

**Conversion Formulas**:
- Int16→Float32: `float_val = int_val / 32768.0`
- Float32→Int16: `int_val = clip(float_val * 32767.0, -32768, 32767)`
- Int24→Int16: `int16_val = int24_val >> 8`
- Int16→Int24: `int24_val = int16_val << 8`

### 6. AudioStreamFactory Enhancement

**Location**: `src/providers/audio/factory.py`

**Modified get_stream() Method**:
```
class AudioStreamFactory:
    @staticmethod
    def get_stream(filepath: str,
                   format_descriptor: Optional[AudioFormatDescriptor] = None) -> AudioStreamBase:
        """
        Create audio stream with optional format adaptation.

        Args:
            filepath: Path to audio file
            format_descriptor: Desired format (None = native)

        Returns:
            AudioStreamBase that provides audio in requested format

        Strategy:
        1. Create base stream (MiniaudioStream)
        2. If format_descriptor is None, return base stream
        3. Compare native format to requested format
        4. Build adapter chain as needed:
           - Resample if sample rates differ
           - Mix channels if channel counts differ
           - Convert bit depth if sample widths differ
        5. Return adapted stream (or base if no adaptation needed)
        """
        # Create base stream
        base_stream = MiniaudioStream(filepath)

        # If no format requested, return native
        if format_descriptor is None:
            return base_stream

        # Build adapter chain
        stream = base_stream

        # Check if resampling needed
        if (format_descriptor.sample_rate is not None and
            format_descriptor.sample_rate != base_stream.samplerate):
            stream = ResamplingAdapter(stream, format_descriptor.sample_rate)

        # Check if channel mixing needed
        if (format_descriptor.channels is not None and
            format_descriptor.channels != base_stream.nchannels):
            stream = ChannelMixingAdapter(stream, format_descriptor.channels)

        # Check if bit depth conversion needed
        if (format_descriptor.sample_width is not None and
            format_descriptor.sample_width != base_stream.sample_width):
            stream = BitDepthAdapter(stream,
                                    format_descriptor.sample_width,
                                    format_descriptor.sample_format or 'int')

        return stream
```

**Key Design Points**:
- Backward compatible: None format_descriptor = native stream
- Order matters: resample first, then mix, then convert bit depth
- Only creates adapters when needed (efficient)

### 7. MediaFile Integration

**Location**: `src/models/media_file.py`

**Modified get_audio_stream() Method**:
```
def get_audio_stream(self,
                    format_descriptor: Optional[AudioFormatDescriptor] = None) -> AudioStreamBase:
    """
    Get an audio stream for reading audio data from this file.

    Args:
        format_descriptor: Desired audio format (None = native format)

    Returns:
        AudioStreamBase instance providing audio in requested format

    Raises:
        Exception if audio stream cannot be created

    Examples:
        # Get native format stream
        stream = media_file.get_audio_stream()

        # Get mono stream at 22050 Hz
        from providers.audio.format_descriptor import AudioFormatDescriptor
        fmt = AudioFormatDescriptor(sample_rate=22050, channels=1)
        stream = media_file.get_audio_stream(fmt)
    """
    from providers.audio.factory import AudioStreamFactory
    return AudioStreamFactory.get_stream(self._file_path, format_descriptor)
```

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

**Example**:
```
try:
    stream = ResamplingAdapter(base_stream, 22050)
    stream = ChannelMixingAdapter(stream, 1)
except Exception as e:
    # All streams closed via __exit__ if using context manager
    raise AudioAdaptationError(f"Failed to create adapted stream: {e}")
```

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
4. Performance testing and optimization

### Phase 4: Consumer Updates

1. Update aubio BPM analyzer to use format adaptation
2. Remove manual conversion code from analyzer
3. Update other analyzers as needed
4. Update playback system (if exists)

### Phase 5: Documentation & Polish

1. Document AudioFormatDescriptor API
2. Add examples to docstrings
3. Update analyzer documentation
4. Performance tuning based on profiling

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
3. **Multi-threading**: Parallel adaptation for multi-file batches

## References

- **Epic**: `doc/epics/20251013_Audio_Format_Adaptation.md`
- **Audio Subsystem**: `doc/designs/audio-subsystem.md`
- **MediaFile**: `src/models/media_file.py`
- **AudioStreamBase**: `src/providers/audio/base.py`
- **Analyzer System**: `doc/designs/analyzer_system.md`
- **scipy.signal.resample_poly**: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html
