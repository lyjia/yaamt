from const import KEY_STREAM_INFO, KEY_TAGS, KEY_PROVIDER, KEY_AVAIL_KEYS, KEY_VALUE
from providers.metadata.mutagen_provider import MutagenProvider


class MediaFile:
    """
    Public interface for accessing audio file metadata.
    """
    def __init__(self, file_path: str):
        self._providers = self._get_providers_for_file(file_path)

        # read combined metadata in as-needed, not at load
        self._combined_metadata = {
            KEY_STREAM_INFO: {}, # bitrate, channels, audio type, etc
            KEY_TAGS: {} # title, artist, album, genre, bpm, key, etc
        }

        self._registered_providers = {
            KEY_STREAM_INFO: [],
            KEY_TAGS: []
        }

        self._tag_provider_lookup = {
            KEY_STREAM_INFO: {},
            KEY_TAGS: {}
        }

        for provider in self._providers:
            # TODO: provider should be added only if it supports the kind of metadata reporting its being registered to
            self._registered_providers[KEY_TAGS].append({
                KEY_PROVIDER: provider,
                KEY_AVAIL_KEYS: provider.available_tags(),
            })
            self._registered_providers[KEY_STREAM_INFO].append({
                KEY_PROVIDER: provider,
                KEY_AVAIL_KEYS: provider.available_stream_info_keys(),
            })

            # create a lookup of available providers on a per-key basis
            # to be used for JIT loading of tag data
            for key in provider.available_tags():
                if not key in self._tag_provider_lookup[KEY_TAGS][key]:
                    self._tag_provider_lookup[KEY_TAGS][key] = []
                self._tag_provider_lookup[KEY_TAGS][key].append(provider)

            for key in provider.available_stream_info_keys():
                if not key in self._tag_provider_lookup[KEY_STREAM_INFO][key]:
                    self._tag_provider_lookup[KEY_STREAM_INFO][key] = []
                self._tag_provider_lookup[KEY_STREAM_INFO][key].append(provider)

    def get_tag_simple(self, key):
        if not self._combined_metadata[KEY_TAGS].get(key):
            self.load_meta_for_tag(key)
        return self._combined_metadata[KEY_TAGS][key][KEY_VALUE][0] #only return first value in array of values

    def load_meta_for_tag(self, key):
        provider_to_use = self._tag_provider_lookup[KEY_TAGS][key][0]
        self._combined_metadata[KEY_TAGS][key] = {
            KEY_VALUE: provider_to_use.get_tag(key),
            KEY_PROVIDER: provider_to_use
        }

    # # TODO: we don't want to use Mutagen as our storage layer for this meta, this should be moved to be handled in this class
    # @property
    # def title(self):
    #     return self._provider.title
    #
    # @title.setter
    # def title(self, value):
    #     self._provider.title = value
    #
    # @property
    # def artist(self):
    #     return self._provider.artist
    #
    # @artist.setter
    # def artist(self, value):
    #     self._provider.artist = value
    #
    # @property
    # def album(self):
    #     return self._provider.album
    #
    # @album.setter
    # def album(self, value):
    #     self._provider.album = value
    #
    # @property
    # def genre(self):
    #     return self._provider.genre
    #
    # @genre.setter
    # def genre(self, value):
    #     self._provider.genre = value
    #
    # @property
    # def bpm(self):
    #     return self._provider.bpm
    #
    # @bpm.setter
    # def bpm(self, value):
    #     self._provider.bpm = value
    #
    # @property
    # def key(self):
    #     return self._provider.key
    #
    # @key.setter
    # def key(self, value):
    #     self._provider.key = value

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
                    "value": value_list[0], #always go with first element for now
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

    def _get_providers_for_file(self, file_path: str):
        """
        Get the MetadataProvider instance(s) most appropriate for the given file in order of preference.
        :param file_path:
        :return:
        """
        return [ MutagenProvider(file_path) ]