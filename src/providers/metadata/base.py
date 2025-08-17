from abc import ABC, abstractmethod

class MetadataProviderBase(ABC):
    """
    An abstract base class that defines the interface for metadata providers.
    """
    @property
    @abstractmethod
    def get_tag(self, key):
        pass

    @property
    @abstractmethod
    def set_tag(self, key, values):
        pass

    # @property
    # @abstractmethod
    # def title(self):
    #     """Abstract property for the track title."""
    #     pass
    #
    # @property
    # @abstractmethod
    # def artist(self):
    #     """Abstract property for the track artist."""
    #     pass
    #
    # @property
    # @abstractmethod
    # def album(self):
    #     """Abstract property for the track album."""
    #     pass
    #
    # @title.setter
    # @abstractmethod
    # def title(self, value):
    #     """Abstract setter for the track title."""
    #     pass
    #
    # @artist.setter
    # @abstractmethod
    # def artist(self, value):
    #     """Abstract setter for the track artist."""
    #     pass
    #
    # @album.setter
    # @abstractmethod
    # def album(self, value):
    #     """Abstract setter for the track album."""
    #     pass
    #
    # @property
    # @abstractmethod
    # def genre(self):
    #     """Abstract property for the track genre."""
    #     pass
    #
    # @genre.setter
    # @abstractmethod
    # def genre(self, value):
    #     """Abstract setter for the track genre."""
    #     pass
    #
    # @property
    # @abstractmethod
    # def bpm(self):
    #     """Abstract property for the track BPM."""
    #     pass
    #
    # @bpm.setter
    # @abstractmethod
    # def bpm(self, value):
    #     """Abstract setter for the track BPM."""
    #     pass
    #
    # @property
    # @abstractmethod
    # def key(self):
    #     """Abstract property for the track musical key."""
    #     pass
    #
    # @key.setter
    # @abstractmethod
    # def key(self, value):
    #     """Abstract setter for the track musical key."""
    #     pass

    @abstractmethod
    def save(self):
        """Abstract method to save changes to the file."""
        pass