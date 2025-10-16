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

        # Build adapter chain based on format differences
        # Order matters: resample first, then channel mix, then bit depth convert
        stream = base_stream

        # 1. Sample rate conversion (if needed)
        if (format_descriptor.sample_rate is not None and
                format_descriptor.sample_rate != stream.sample_rate):
            from .adapters.resampling_adapter import ResamplingAdapter
            stream = ResamplingAdapter(stream, format_descriptor.sample_rate)

        # 2. Channel mixing (if needed)
        if (format_descriptor.channels is not None and
                format_descriptor.channels != stream.channels_qty):
            from .adapters.channel_mixing_adapter import ChannelMixingAdapter
            stream = ChannelMixingAdapter(stream, format_descriptor.channels)

        # 3. Bit depth conversion (if needed)
        # Infer source format from sample width (same logic as BitDepthAdapter)
        source_format = 'int' if base_stream.sample_width in (1, 2, 3) else 'float'

        # Determine target format (default to source format if not specified)
        target_format = format_descriptor.sample_format if format_descriptor.sample_format is not None else source_format

        # Check if bit depth or format conversion needed
        needs_bit_depth_conversion = False
        if format_descriptor.sample_width is not None:
            if format_descriptor.sample_width != stream.sample_width:
                needs_bit_depth_conversion = True
        if format_descriptor.sample_format is not None:
            if format_descriptor.sample_format != source_format:
                needs_bit_depth_conversion = True

        if needs_bit_depth_conversion:
            from .adapters.bit_depth_adapter import BitDepthAdapter
            # Use the current stream's sample width/format if descriptor doesn't specify
            target_width = format_descriptor.sample_width if format_descriptor.sample_width is not None else stream.sample_width
            stream = BitDepthAdapter(stream, target_width, target_format)

        return stream