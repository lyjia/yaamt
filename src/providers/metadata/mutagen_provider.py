import mutagen
from .metadata_provider import MetadataProvider


class MutagenProvider(MetadataProvider):
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

    def _get_tag(self, keys):
        if not self._audio:
            return None
        for key in keys:
            if key in self._audio:
                return self._audio[key]
        return None

    def _set_tag(self, key, value):
        if self._audio:
            self._audio[key] = value

    @property
    def title(self):
        tag = self._get_tag(['title', 'TIT2'])
        return tag if tag else None

    @title.setter
    def title(self, value):
        self._set_tag('TIT2', value)

    @property
    def artist(self):
        tag = self._get_tag(['artist', 'TPE1'])
        return tag if tag else None

    @artist.setter
    def artist(self, value):
        self._set_tag('TPE1', value)

    @property
    def album(self):
        tag = self._get_tag(['album', 'TALB'])
        return tag if tag else None

    @album.setter
    def album(self, value):
        self._set_tag('TALB', value)

    @property
    def genre(self):
        tag = self._get_tag(['genre', 'TCON'])
        return tag if tag else None

    @genre.setter
    def genre(self, value):
        self._set_tag('TCON', value)

    @property
    def bpm(self):
        tag = self._get_tag(['bpm', 'TBPM'])
        if tag:
            try:
                return float(tag)
            except (ValueError, TypeError):
                return None
        return None

    @bpm.setter
    def bpm(self, value):
        self._set_tag('TBPM', str(value))

    @property
    def key(self):
        tag = self._get_tag(['key', 'TKEY'])
        return tag if tag else None

    @key.setter
    def key(self, value):
        self._set_tag('TKEY', value)

    def save(self):
        if self._audio:
            self._audio.save()