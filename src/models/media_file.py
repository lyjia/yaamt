import os

from util.const import KEY_STREAM_INFO, KEY_TAGS, KEY_PROVIDER, KEY_AVAIL_KEYS, KEY_VALUE, KEY_ALL_PROVIDERS, \
    KEY_ALL_VALUES, KEY_INTERNAL, KEY_FILE_PATH, KEY_IS_MEDIA, KEY_FILE_TYPE, KEY_FILE_SIZE, KEY_FILE_MTIME, \
    KEY_FILE_CTIME, KEY_FILE_ATIME, KEY_IS_WRITABLE
from providers.metadata.mutagen_provider import MutagenProvider
from util.logging import log


class MediaFile:
    """
    Public interface for accessing audio file metadata.
    """
    def __init__(self, file_path: str, enable_write=False):
        self._file_path = os.path.abspath(file_path)
        self._file_name = os.path.basename(file_path)
        self._providers = self._get_providers_for_file()
        self._write_enabled = enable_write

        # read combined metadata in as-needed, not at load
        self._combined_metadata = {
            KEY_STREAM_INFO: {}, # bitrate, channels, audio type, etc
            KEY_TAGS: {}, # title, artist, album, genre, bpm, key, etc
            KEY_INTERNAL: { #fs/internal data
                KEY_FILE_PATH: file_path,
                KEY_FILE_TYPE: os.path.splitext(file_path)[1].replace(".", ""),
                KEY_FILE_SIZE: os.path.getsize(file_path),
                KEY_FILE_MTIME: os.path.getmtime(file_path),
                KEY_FILE_CTIME: os.path.getctime(file_path),
                # KEY_FILE_ATIME: os.path.getatime(file_path),
                KEY_IS_MEDIA: False,
                KEY_IS_WRITABLE: False
            }
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

            # TODO: temporary while we only support one provider
            if provider.is_readable():
                self._combined_metadata[KEY_INTERNAL][KEY_IS_MEDIA] = True

            if provider.is_readable() and self._write_enabled:
                self._combined_metadata[KEY_INTERNAL][KEY_IS_WRITABLE] = True
            else:
                if self._write_enabled:
                    log(f"{self._file_name}: Write is enabled but file is not readable by metadata providers. Disabling write!")

        # TODO: refine this when we have more provider support, KEY_IS_MEDIA should only be true if the file being loaded is a media file we care about
        # if len(self._tag_provider_lookup[KEY_TAGS]) > 0 and len(self._tag_provider_lookup[KEY_STREAM_INFO]) > 0:
        #     self._combined_metadata[KEY_INTERNAL][KEY_IS_MEDIA] = True

        pass #for debugger attach

    def get_tag_all_values(self, key):
        if not self._combined_metadata[KEY_TAGS].get(key):
            self.load_meta_for_tag(key)
        return self._combined_metadata[KEY_TAGS].get(key, {}).get(KEY_VALUE)

    def get_tag_simple(self, key):
        grab = self.get_tag_all_values(key)
        if grab:
            return grab[0]
        return None

    def load_meta_for_tag(self, key):
        providers = self._tag_provider_lookup[KEY_TAGS].get(key, [])
        if len(providers) > 0:
            provider_to_use = providers[0]
            self._combined_metadata[KEY_TAGS][key] = {
                KEY_VALUE: provider_to_use.get_tag(key),
                KEY_PROVIDER: provider_to_use
            }
        else:
            self._combined_metadata[KEY_TAGS][key] = {}

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

    def get_internal_data(self, key):
        return self._combined_metadata[KEY_INTERNAL].get(key)

    def save(self):
        self._provider.save()

    def to_dict(self):
        """
        Returns a dictionary representation of the media file's metadata.
        """
        to_ret = {
            KEY_STREAM_INFO: {},
            KEY_TAGS: {},
            KEY_INTERNAL: {}
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

        to_ret[KEY_INTERNAL] = self._combined_metadata[KEY_INTERNAL]

        return to_ret

    @property
    def metadata(self):
        return self.to_dict()

    def _get_providers_for_file(self):
        """
        Get the MetadataProvider instance(s) most appropriate for the given file in order of preference.
        :param file_path:
        :return:
        """
        return [ MutagenProvider(self._file_path) ]