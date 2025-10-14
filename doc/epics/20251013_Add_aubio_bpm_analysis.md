We need to add our first BPM analysis using the `aubio` library.

It should follow the same design pattern as the "stub BPM" analyzer, and it should live in `providers.analysis.bpm`. It's goal is to output a BPM value for the input MediaFile object.

We should try to use MediaFile's audio provider to get the audio data. It should be streamed, without loading the whole file into memory.

Remember to expose aubio's parameters as configurable options within the analyzer, even if they're not expected to be used by or presented to the user. We want those options front and center for tweaking later.