# Design for Audio Streaming System

## The audio backend

This section outlines the strategy for reading audio streams, suitable for real-time playback with the device's local audio system, and offline analysis by "analyzer" components. Its purpose is to handle the differences between different audio file formats (i.e. MP3/FLAC/WAV) and present an interface for reading a decoded, possibly normalized version of that audio stream for consumption by other parts of the system. 

For example: a user requests to play back a 320kbit joint stereo MP3 file. Their audio device expects a decoded 48khz lossless audio stream. This system handles the translation from mp3 data to decompressed audio, and presents a class instance that provides a stream of data in the right format. 

This system should read the audio data from a selected audio file, decode it to a format-agnostic audio stream, and present an interface for buffered or non-buffered access. The interface should be suitable for either playback over the local sound device (via something like PyAudio or sounddevice), or for analysis tools such as what is described in `20250825_Mass_Edits.md` section 4: "Analyzer Framework" or libraries like librosa.

This design needs to abstract format-specific concerns for a given file to a generic interface suitable for reading audio data. This interface should present the audio stream in a fashion that is suitable for real-time forwarding to the local audio output, or for analyzers that can read stream data at any speed.

Actual audio playback should be handled separately, and it is not this system's responsibility. Again, 

Here are some additional concerns regarding the backend:

* It should return a class instance that follows the pythonic way for reading audio streams (suitable to pass to the local audio system or an offline analyzer).
* Handles loading a selected audio file (using a library most appropriate for the format, or native python functionality if available) and normalizing it to a stream-type object.
* Within the stream, read/seek operations that are requested via this system's interface are passed to the library or module decoding the audio file. There may be some translation necessary and this system is responsible for handling that.

The following example uses PyAudio to pass audio frames to the sound device. This audio streaming system should replace `wf` / `wave.open` in the following code example:

```python
    import pyaudio
    import wave

    # Example: Playing a WAV file
    filename = 'myfile.wav'
    chunk = 1024
    wf = wave.open(filename, 'rb')
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)
    data = wf.readframes(chunk)
    while data:
        stream.write(data)
        data = wf.readframes(chunk)
    stream.stop_stream()
    stream.close()
    p.terminate()
```