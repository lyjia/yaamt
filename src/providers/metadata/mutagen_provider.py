import mutagen
from .base import MetadataProviderBase


class MutagenProvider(MetadataProviderBase):
    """
    A concrete implementation of MetadataProvider that uses the mutagen library.
    """
    def __init__(self, file_path: str):
        self._file_path = file_path
        self._audio = None
        try:
            self._audio = mutagen.File(file_path, easy=True)
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            raise
        except mutagen.MutagenError as e:
            print(f"Error loading file {file_path}: {e}")
            raise

    def get_tag(self, key):
        if not self._audio:
            return None
        if key in self._audio:
            return self._audio[key]
        return None

    def set_tag(self, key, value):
        if self._audio:
            self._audio[key] = value

    def available_tags(self):
        return self._audio.tags.keys()

    def all_tags(self):
        return dict(self._audio.tags)

    # @property
    # def title(self):
    #     tag = self.get_tag(['title', 'TIT2'])
    #     return tag if tag else None
    #
    # @title.setter
    # def title(self, value):
    #     self.set_tag('title', value)
    #
    # @property
    # def artist(self):
    #     tag = self.get_tag(['artist', 'TPE1'])
    #     return tag if tag else None
    #
    # @artist.setter
    # def artist(self, value):
    #     self.set_tag('artist', value)
    #
    # @property
    # def album(self):
    #     tag = self.get_tag(['album', 'TALB'])
    #     return tag if tag else None
    #
    # @album.setter
    # def album(self, value):
    #     self.set_tag('album', value)
    #
    # @property
    # def genre(self):
    #     tag = self.get_tag(['genre', 'TCON'])
    #     return tag if tag else None
    #
    # @genre.setter
    # def genre(self, value):
    #     self.set_tag('genre', value)
    #
    # @property
    # def bpm(self):
    #     tag = self.get_tag(['bpm', 'TBPM'])
    #     if tag:
    #         try:
    #             return float(tag)
    #         except (ValueError, TypeError):
    #             return None
    #     return None
    #
    # @bpm.setter
    # def bpm(self, value):
    #     self.set_tag('bpm', str(value))
    #
    # @property
    # def key(self):
    #     tag = self.get_tag(['key', 'TKEY'])
    #     return tag if tag else None
    #
    # @key.setter
    # def key(self, value):
    #     self.set_tag('key', value)

    def save(self):
        if self._audio:
            self._audio.save()