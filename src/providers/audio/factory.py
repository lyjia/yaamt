"""
Factory for providing audio stream instances.
"""
from typing import Optional
from .base import AudioStreamBase
from .miniaudio_stream import MiniaudioStream
from .format_descriptor import AudioFormatDescriptor


class AudioStreamFactory:
    """
    A factory class for creating audio stream instances.

    This factory can create base streams or adapted streams that convert
    audio format on-the-fly using the decorator pattern.
    """
    @staticmethod
    def get_stream(
        filepath: str,
        format_descriptor: Optional[AudioFormatDescriptor] = None
    ) -> AudioStreamBase:
        """
        Creates and returns an audio stream for the given file path.

        If format_descriptor is None, returns the stream in its native format.
        If format_descriptor is provided, wraps the stream with adapters as
        needed to match the requested format.

        NOTE! This method is intended to be called only by MediaFile. In most
        cases you should use MediaFile.get_audio_stream() instead.

        Args:
            filepath: The path to the audio file.
            format_descriptor: Optional descriptor specifying the desired audio
                format. If None, returns native format stream.

        Returns:
            An instance of AudioStreamBase, potentially wrapped with adapters.
        """
        # Create the base stream (native format)
        base_stream = MiniaudioStream(filepath)

        # If no format descriptor provided, return native stream
        if format_descriptor is None:
            return base_stream

        # Phase 1: No adapters implemented yet, just return base stream
        # In Phase 2 and 3, we'll build the adapter chain here based on
        # the difference between native format and requested format
        stream = base_stream

        # TODO: Add adapter chain building logic in Phase 3:
        # if format_descriptor.sample_rate differs from base_stream.samplerate:
        #     stream = ResamplingAdapter(stream, format_descriptor.sample_rate)
        #
        # if format_descriptor.channels differs from base_stream.nchannels:
        #     stream = ChannelMixingAdapter(stream, format_descriptor.channels)
        #
        # if format_descriptor.sample_width differs from base_stream.sample_width:
        #     stream = BitDepthAdapter(stream, format_descriptor.sample_width,
        #                              format_descriptor.sample_format)

        return stream