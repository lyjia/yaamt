from const import KEY_STREAM_INFO, KEY_TAGS, KEY_PROVIDER, KEY_AVAIL_KEYS, KEY_VALUE, KEY_ALL_PROVIDERS, KEY_ALL_VALUES
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
                if not key in self._tag_provider_lookup[KEY_TAGS]:
                    self._tag_provider_lookup[KEY_TAGS][key] = []
                self._tag_provider_lookup[KEY_TAGS][key].append(provider)

            for key in provider.available_stream_info_keys():
                if not key in self._tag_provider_lookup[KEY_STREAM_INFO]:
                    self._tag_provider_lookup[KEY_STREAM_INFO][key] = []
                self._tag_provider_lookup[KEY_STREAM_INFO][key].append(provider)

        pass #for debugger attach

    def get_tag_all_values(self, key):
        if not self._combined_metadata[KEY_TAGS].get(key):
            self.load_meta_for_tag(key)
        return self._combined_metadata[KEY_TAGS][key][KEY_VALUE]

    def get_tag_simple(self, key):
        return self.get_tag_all_values(key)[0]

    def load_meta_for_tag(self, key):
        provider_to_use = self._tag_provider_lookup[KEY_TAGS][key][0]
        self._combined_metadata[KEY_TAGS][key] = {
            KEY_VALUE: provider_to_use.get_tag(key),
            KEY_PROVIDER: provider_to_use
        }

    def get_stream_info_value(self, key):
        if not self._combined_metadata[KEY_STREAM_INFO].get(key):
            self.load_meta_for_stream_info(key)
        return self._combined_metadata[KEY_STREAM_INFO][key][KEY_VALUE]  # only return first value in array of values

    def load_meta_for_stream_info(self, key):
        provider_to_use = self._tag_provider_lookup[KEY_STREAM_INFO][key][0]
        self._combined_metadata[KEY_STREAM_INFO][key] = {
            KEY_VALUE: provider_to_use.get_stream_info(key),
            KEY_PROVIDER: provider_to_use
        }

    def save(self):
        self._provider.save()

    def to_dict(self):
        """
        Returns a dictionary representation of the media file's metadata.
        """
        to_ret = {
            KEY_STREAM_INFO: {},
            KEY_TAGS: {}
        }

        for key in self._tag_provider_lookup[KEY_TAGS].keys():
            to_ret[KEY_TAGS][key] = {
                KEY_VALUE: self.get_tag_simple(key),
                KEY_PROVIDER: self._tag_provider_lookup[KEY_TAGS][key][0].__class__.__name__,
                KEY_ALL_VALUES: self.get_tag_all_values(key),
                KEY_ALL_PROVIDERS: [x.__class__.__name__ for x in self._tag_provider_lookup[KEY_TAGS][key]]
            }

        for key in self._tag_provider_lookup[KEY_STREAM_INFO].keys():
            to_ret[KEY_STREAM_INFO][key] = {
                KEY_VALUE: self.get_stream_info_value(key),
                KEY_PROVIDER: self._tag_provider_lookup[KEY_STREAM_INFO][key][0].__class__.__name__,
            }

        return to_ret

    def _get_providers_for_file(self, file_path: str):
        """
        Get the MetadataProvider instance(s) most appropriate for the given file in order of preference.
        :param file_path:
        :return:
        """
        return [ MutagenProvider(file_path) ]