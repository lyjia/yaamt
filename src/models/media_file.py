from providers.metadata.mutagen_provider import MutagenProvider


class MediaFile:
    """
    Public interface for accessing audio file metadata.
    """
    def __init__(self, file_path: str):
        self._provider = MutagenProvider(file_path)

    @property
    def title(self):
        return self._provider.title

    @title.setter
    def title(self, value):
        self._provider.title = value

    @property
    def artist(self):
        return self._provider.artist

    @artist.setter
    def artist(self, value):
        self._provider.artist = value

    @property
    def album(self):
        return self._provider.album

    @album.setter
    def album(self, value):
        self._provider.album = value

    @property
    def genre(self):
        return self._provider.genre

    @genre.setter
    def genre(self, value):
        self._provider.genre = value

    @property
    def bpm(self):
        return self._provider.bpm

    @bpm.setter
    def bpm(self, value):
        self._provider.bpm = value

    @property
    def key(self):
        return self._provider.key

    @key.setter
    def key(self, value):
        self._provider.key = value

    def save(self):
        self._provider.save()

    def to_dict(self):
        """
        Returns a dictionary representation of the media file's metadata.
        """
        
        fields = ["title", "artist", "album", "genre", "bpm", "key"]
        parsed_data = {}

        for field in fields:
            value_list = getattr(self, field)
            if value_list:
                parsed_data[field] = {
                    "value": value_list,
                    "element_providers": [ self._provider.__class__.__name__ ],
                    "all_elements": value_list,
                    "all_elements_providers": [0]
                }
            else:
                parsed_data[field] = {
                    "value": None,
                    "element_providers": [],
                    "all_elements": [],
                    "all_elements_providers": []
                }

        return {"parsed": parsed_data}