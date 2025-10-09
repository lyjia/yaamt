"""
Factory for providing audio stream instances.
"""
from .base import AudioStreamBase
from .miniaudio_stream import MiniaudioStream


class AudioStreamFactory:
    """
    A factory class for creating audio stream instances.
    """
    @staticmethod
    def get_stream(filepath: str) -> AudioStreamBase:
        """
        Creates and returns an audio stream for the given file path.

        Currently, this method always returns a MiniaudioStream instance.

        NOTE! This method is intended to be called only by MediaFile. In most cases you should use MediaFile.get_audio_stream() instead.

        Args:
            filepath: The path to the audio file.

        Returns:
            An instance of AbstractAudioStream.
        """
        return MiniaudioStream(filepath)