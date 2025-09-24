# Audio Subsystem Design

## 1. Overview

This document outlines the design for the Audio Subsystem, which is responsible for reading and decoding various audio file formats into a standardized, streamable format. This unified interface will serve as the foundation for audio playback, analysis, and processing within the application.

The primary goal is to abstract the complexities of different audio codecs (e.g., MP3, FLAC, WAV) behind a simple and consistent API, allowing other components to consume audio data without needing to know the underlying file format.

## 2. Core Requirements

*   **Format Agnostic**: The system must support decoding of common audio formats, starting with WAV, MP3, and FLAC.
*   **Streaming Interface**: It must provide a stream-like interface, offering methods like `read()`, `seek()`, and `close()`. This is crucial for handling large audio files efficiently without loading the entire file into memory.
*   **Metadata Access**: The interface should expose essential audio properties, such as `samplerate`, `number of channels`, and `sample width`.
*   **Extensibility**: The design should be modular, allowing for the addition of new audio decoders in the future with minimal changes to the core system.
*   **Performance**: The decoding process should be efficient to support real-time playback and fast offline analysis.

## 3. Proposed Library: `miniaudio`

After evaluating several libraries, `miniaudio` has been selected as the foundational decoding engine.

### Rationale:

*   **High Performance**: It is a Python wrapper around the highly optimized `miniaudio` C library, ensuring efficient, low-latency audio processing.
*   **Built-in Decoders**: It includes built-in support for our target formats (WAV, FLAC, MP3), eliminating the need for multiple format-specific libraries.
*   **Simple API**: Its API is clean and provides a generator-based approach for streaming audio frames, which maps well to our desired interface.
*   **Cross-Platform**: It is designed to be cross-platform, which aligns with the portability goals of the main application.
*   **No External Dependencies**: `miniaudio` is self-contained and does not require external dependencies like FFmpeg or GStreamer, simplifying installation and deployment.

## 4. System Architecture

The subsystem will be built around three main components: an `AudioStreamProvider` factory, an abstract `AbstractAudioStream` base class, and a concrete `MiniaudioStream` implementation.

```mermaid
classDiagram
    class AudioStreamProvider {
        +get_stream(filepath) AbstractAudioStream
    }

    class AbstractAudioStream {
        <<interface>>
        +read(n_frames) bytes
        +seek(frame_offset) None
        +close() None
        +samplerate : int
        +nchannels : int
        +sample_width : int
    }

    class MiniaudioStream {
        -stream_generator : Generator
        -decoder : miniaudio.StreamableSource
        +read(n_frames) bytes
        +seek(frame_offset) None
        +close() None
    }

    AudioStreamProvider ..> AbstractAudioStream : creates
    AbstractAudioStream <|-- MiniaudioStream```

### 4.1. `AbstractAudioStream`

This abstract base class defines the common interface for all audio streams. It ensures that any component consuming audio data can rely on a consistent set of methods and properties.

**API Specification:**

*   `read(n_frames: int) -> bytes`: Reads a specified number of audio frames and returns them as a byte string.
*   `seek(frame_offset: int) -> None`: Seeks to a specific frame in the audio stream.
*   `close() -> None`: Closes the stream and releases any associated file handles.
*   `samplerate` (property): The sample rate of the audio in Hz.
*   `nchannels` (property): The number of audio channels (1 for mono, 2 for stereo).
*   `sample_width` (property): The number of bytes per sample (e.g., 2 for 16-bit audio).

### 4.2. `MiniaudioStream`

This is the concrete implementation of `AbstractAudioStream` that uses `miniaudio` for decoding.

**Implementation Details:**

*   The constructor will take a file path and initialize a `miniaudio.stream_file()` generator.
*   The `read()` method will pull data from the `miniaudio` stream generator.
*   The `seek()` method will leverage the underlying stream's seek capability.
*   The properties (`samplerate`, `nchannels`, `sample_width`) will be populated from the `miniaudio` decoder instance.

### 4.3. `AudioStreamProvider`

This factory class is the main entry point for the subsystem. It is responsible for creating the appropriate audio stream object for a given file.

**Implementation Details:**

*   It will have a single static method, `get_stream(filepath: str) -> AbstractAudioStream`.
*   Initially, this method will simply instantiate and return a `MiniaudioStream` object.
*   In the future, it could be extended to inspect the file extension or content to select different stream implementations if we decide to support more formats or use other libraries.

## 5. Usage Examples

### 5.1. Playback with PyAudio

This example demonstrates how the new subsystem can replace `wave.open` to play any supported audio format.

```python
import pyaudio
from providers.audio import AudioStreamProvider # Assuming this is where the provider lives

filename = 'myfile.mp3' # or .flac, .wav
chunk_size = 1024

audio_stream = AudioStreamProvider.get_stream(filename)

p = pyaudio.PyAudio()
stream = p.open(format=p.get_format_from_width(audio_stream.sample_width),
                channels=audio_stream.nchannels,
                rate=audio_stream.samplerate,
                output=True)

data = audio_stream.read(chunk_size)
while data:
    stream.write(data)
    data = audio_stream.read(chunk_size)

stream.stop_stream()
stream.close()
p.terminate()
audio_stream.close()
```

### 5.2. Analysis with Librosa

This example shows how the stream can be used with an analysis library. While `librosa` can load files directly, this demonstrates how our streaming interface could be adapted for libraries that can operate on raw audio data buffers.

```python
import numpy as np
import librosa
from providers.audio import AudioStreamProvider

filename = 'myfile.flac'
audio_stream = AudioStreamProvider.get_stream(filename)

# Read the entire file into a buffer for analysis
# Note: For a true streaming analysis, a different approach would be needed,
# but this demonstrates data access.
full_buffer = b''
while True:
    data = audio_stream.read(4096)
    if not data:
        break
    full_buffer += data

# Convert byte buffer to a numpy array for librosa
# The dtype depends on the sample width
if audio_stream.sample_width == 2:
    dtype = np.int16
elif audio_stream.sample_width == 4:
    dtype = np.int32
else:
    raise ValueError("Unsupported sample width")

y = np.frombuffer(full_buffer, dtype=dtype)

# Now you can use librosa for analysis
tempo, beat_frames = librosa.beat.beat_track(y=y.astype(float),
                                             sr=audio_stream.samplerate)

print(f"Estimated tempo: {tempo:.2f} BPM")

audio_stream.close()
```

## 6. Future Enhancements

*   **Additional Format Support**: New `AbstractAudioStream` implementations can be created for other libraries (e.g., `audioread` for formats not covered by `miniaudio`).
*   **Error Handling**: Implement robust error handling for file-not-found, corrupted files, or unsupported formats.