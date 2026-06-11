# Epic: Audio Stream Format Adaptation

**Created**: 2025-10-13

## Problem Statement

Currently, audio stream consumers (analyzers, playback interfaces) must handle audio format conversion themselves. This creates several issues:

1. **Code Duplication**: Each consumer must implement resampling, channel mixing, and bit depth conversion
2. **Complexity**: Analyzers need to understand audio processing, not just their analysis algorithms
3. **Inconsistency**: Different consumers might handle conversions differently
4. **Limited Flexibility**: Users cannot play files that exceed their audio hardware capabilities

## Proposed Solution

Create an audio stream adaptation layer that transparently converts audio formats on-the-fly. Consumers specify their requirements (sample rate, channels, bit depth), and the audio subsystem delivers a stream in that format regardless of the source file's format.

## Use Cases

### Use Case 1: Mono Analyzer on Stereo File
**Consumer**: aubio BPM analyzer (requires mono audio)
**Source File**: 44.1kHz, 16-bit, stereo WAV
**Request**: 44.1kHz, 16-bit, mono
**Adaptation**: Mix stereo channels to mono (average)
**Result**: Analyzer receives mono stream, no conversion code needed

### Use Case 2: Playback on Limited Hardware
**Consumer**: Audio playback system (hardware supports max 48kHz, 16-bit, stereo)
**Source File**: 96kHz, 32-bit float, stereo FLAC
**Request**: 48kHz, 16-bit, stereo
**Adaptation**: Downsample 96kHz→48kHz, convert 32-bit float→16-bit int
**Result**: User can play high-res audio on standard hardware

### Use Case 3: Analyzer Requires Specific Sample Rate
**Consumer**: Some analyzer (algorithm tuned for 22050 Hz)
**Source File**: 44.1kHz, 16-bit, mono WAV
**Request**: 22050 Hz, 16-bit, mono
**Adaptation**: Downsample 44.1kHz→22050Hz
**Result**: Analyzer receives audio at its preferred rate

### Use Case 4: No Adaptation Needed
**Consumer**: Waveform display (accepts any format)
**Source File**: 48kHz, 24-bit, stereo
**Request**: None (accept native format)
**Adaptation**: None (pass-through)
**Result**: Efficient streaming without unnecessary processing

## Requirements

### Functional Requirements

1. **Format Specification**: Consumers can specify desired audio format (sample rate, channels, bit depth)
2. **Optional Requirements**: Consumers can request native format if no specific requirements
3. **Transparent Streaming**: Adapted streams implement AudioStreamBase interface
4. **Multiple Conversions**: Support combining multiple adaptations (resample + channel mix + bit convert)
5. **Seeking Support**: Seek operations work correctly on adapted streams
6. **Native Pass-through**: If no adaptation needed, return native stream efficiently

### Non-Functional Requirements

1. **Performance**: Minimize CPU overhead, stream without loading entire file
2. **Quality**: Use appropriate resampling algorithms (avoid aliasing, preserve fidelity)
3. **Memory Efficiency**: Buffer only necessary chunks, no large allocations
4. **Latency**: Keep latency reasonable for real-time playback
5. **Accuracy**: Seeking should be frame-accurate in adapted streams
6. **Packaging**: Must work with PyInstaller on Windows/macOS/Linux

## Architecture Goals

1. **Decorator Pattern**: Wrap base streams with adapter streams
2. **Composability**: Chain multiple adapters (resample→mix→convert)
3. **Lazy Evaluation**: Only create adapters when needed
4. **Format Descriptor**: Explicit format specification objects
5. **Factory Integration**: MediaFile/AudioStreamFactory handles adapter creation

## Success Criteria

- [ ] Consumers request audio formats via format descriptor
- [ ] MediaFile.get_audio_stream() returns adapted streams transparently
- [ ] Adapters implement AudioStreamBase interface
- [ ] Seekable streams remain seekable after adaptation
- [ ] No code duplication for format conversion across analyzers
- [ ] aubio BPM analyzer updated to use format adaptation
- [ ] Test coverage for all adaptation combinations
- [ ] Performance acceptable for real-time playback
- [ ] Packages successfully with PyInstaller on all platforms

## Scope

### Phase 1 (This Epic)
- Real-time pitch shifting or time stretching
- Audio effects (reverb, EQ, compression)
- Multi-file mixing or crossfading
- Format conversion for file writing (only streaming read)
- Adaptive quality based on system load
- Dithering during bit depth reduction

## Technical Considerations

### Resampling Library Choice

**Primary**: scipy.signal.resample_poly
- Reliable cross-platform installation
- Works with PyInstaller packaging
- No LLVM/numba dependencies
- Good quality with proper parameters (Kaiser window, β=5.0+)
- Efficient for rational sample rate ratios

**Future Optional**: samplerate library (if quality needs increase)
- Higher quality than scipy
- C library with Python bindings
- Binary wheels available for major platforms
- Can be added as optional dependency later

### Channel Mixing Algorithms
- **Stereo→Mono**: Average channels with coefficient 1/√2 (preserves RMS power)
- **Mono→Stereo**: Duplicate to both channels
- **Multi-channel→Stereo**: Not in Phase 1

### Bit Depth Conversion
- **Float→Int**: Scale by (2^(bits-1) - 1), clip to range
- **Int→Float**: Divide by (2^(bits-1)), normalize to [-1.0, 1.0]
- **Int→Int**: Scale appropriately (e.g., 24-bit→16-bit: right shift 8 bits)
- No dithering in Phase 1 (can add later if needed)

### Buffering Strategy
- Chunk-based processing matching consumer's read size
- Resampling may require look-ahead (filter kernel size)
- Maintain small internal buffer for edge effects
- Minimize memory footprint

### Seeking Challenges
- Resampling changes frame count (source frames ≠ output frames)
- Track mapping: output_frame = (input_frame * target_sr) / source_sr
- Seek to calculated source frame, discard partial samples to align
- Document seek accuracy limitations

## Dependencies

- **Required**: NumPy (already used), scipy (add to requirements.txt)
- **Existing**: AudioStreamBase, MiniaudioStream, MediaFile
- **No new dependencies**: Avoid librosa, resampy due to packaging issues

## Related Work

- Audio Subsystem (`doc/designs/audio-subsystem.md`)
- MediaFile (`src/models/media_file.py`)
- Analyzer System (`doc/designs/analyzer_system.md`)
- aubio BPM Analyzer (`doc/designs/aubio_bpm_analyzer.md`)

## Open Questions

1. **Caching**: Should adapted streams cache converted chunks for repeated reads?
2. **Format Negotiation**: Should consumers specify "preferred" vs "required" formats?
3. **Normalization**: Should we normalize volume during bit depth conversion?
4. **Thread Safety**: Are adapted streams thread-safe if base stream is?
5. **Error Handling**: How to handle unsupported format conversions gracefully?
6. **Quality Settings**: Should resampling quality be user-configurable in preferences?
