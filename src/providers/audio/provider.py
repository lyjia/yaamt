"""
Factory for providing audio stream instances.
"""
from .base import AbstractAudioStream
from .miniaudio_stream import MiniaudioStream


class AudioStreamProvider:
    """
    A factory class for creating audio stream instances.
    """
    @staticmethod
    def get_stream(filepath: str) -> AbstractAudioStream:
        """
        Creates and returns an audio stream for the given file path.

        Currently, this method always returns a MiniaudioStream instance.

        Args:
            filepath: The path to the audio file.

        Returns:
            An instance of AbstractAudioStream.
        """
        return MiniaudioStream(filepath)