import os

from util.const import KEY_STREAM_INFO, KEY_TAGS, KEY_PROVIDER, KEY_AVAIL_KEYS, KEY_VALUE, KEY_ALL_PROVIDERS, \
    KEY_ALL_VALUES, KEY_INTERNAL, KEY_FILE_PATH, KEY_FILE_TYPE, KEY_FILE_SIZE, KEY_FILE_MTIME, \
    KEY_FILE_CTIME, KEY_FILE_ATIME, KEY_IS_MEDIA, KEY_IS_WRITABLE, KEY_TAG_GENERIC, KEY_TAG_INTERNAL, KEY_FILE_ID
from providers.metadata.mutagen_provider import MutagenProvider
from util.logging import log


class MediaFile:
    """
    Public interface for accessing audio file metadata.

    Provides a unified interface for accessing metadata from multiple metadata providers. The assumption is that
    a given tag (such a "title") is available from multiple possible providers, and that the most appropriate provider
    for reading vs writing a tag may differ. So there is a lot of plumbing here to determine which providers are
    fit for task and routing requests accordingly. This area has gotten more complex than I initial expected,
    so it may be worth revisiting this logic in the future.

    One such use-case I was thinking of when I wrote this is for reading/writing Serato tags: the raw ID3 frames are
    picked up by Mutagen, but in the interest of separating concerns we do not want to handle them with MutagenProvider.
    Rather, a separate SeratoProvider should contain the logic for interpreting and writing those frames. Since both
    providers will potentially see the same data it is important to disambiguate which provider should be used for which
    tag.

    Another use-case might be for WAV files with both ID3 and ACID tags. Each of these tag formats provides different
    (and possibly overlapping, like with BPM) tags for a given audio file. The ACID tags may also have markers or regions
    defined. What if the user then loads that WAV into Serato and sets cue points and loop regions? We have to tame
    the inevitable tagging madness!

    Also, note that we have a couple different categories of 'tags':
    * "generic" tags, which reference the labels we present to the user, and are names used internally by YAAMT
    * "internal" tags, which are tags that are used internally by the Provider but not exposed to the user. 
    ** Note that for MutagenProvider many tags have the same name for both categories.
    ** It is the provider's responsibility to accept generic tag names and route them to whatever internal name that provider uses.
    ** Mapping between these two is handled by `get_internal_tag_name_for_generic()`
    """
    def __init__(self, file_path: str, enable_write=False):
        self._file_path = os.path.abspath(file_path)
        self._file_id = hash(self._file_path)
        self._file_name = os.path.basename(file_path)
        self._providers = self._get_providers_for_file()
        self._write_enabled = enable_write
        self._generic_to_internal_map = {}
        self._internal_to_generic_map = {}

        # read combined metadata in as-needed, not at load
        self._combined_metadata = {
            KEY_STREAM_INFO: {}, # bitrate, channels, audio type, etc
            KEY_TAGS: {}, # title, artist, album, genre, bpm, key, etc
            KEY_INTERNAL: { #fs/internal data
                KEY_FILE_PATH: str(file_path),
                KEY_FILE_TYPE: os.path.splitext(file_path)[1].replace(".", ""),
                KEY_FILE_SIZE: os.path.getsize(file_path),
                KEY_FILE_MTIME: os.path.getmtime(file_path),
                KEY_FILE_CTIME: os.path.getctime(file_path),
                # KEY_FILE_ATIME: os.path.getatime(file_path),
                KEY_IS_MEDIA: False,
                KEY_IS_WRITABLE: False,
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

        self._tag_writers = {
            KEY_TAGS: {}
        }

        for provider in self._providers:
            # TODO: provider should be added only if it supports the kind of metadata reporting its being registered to

            available_internal_tags = provider.available_internal_tags()

            self._registered_providers[KEY_TAGS].append({
                KEY_PROVIDER: provider,
                KEY_AVAIL_KEYS: available_internal_tags,
            })

            self._registered_providers[KEY_STREAM_INFO].append({
                KEY_PROVIDER: provider,
                KEY_AVAIL_KEYS: provider.available_stream_info_keys(),
            })

            # create a lookup of available providers on a per-key basis
            # to be used for JIT loading of tag data
            for tag_info in available_internal_tags:
                if tag_info.generic_tag_name:
                    self._generic_to_internal_map[tag_info.generic_tag_name] = tag_info.internal_tag_name
                    self._internal_to_generic_map[tag_info.internal_tag_name] = tag_info.generic_tag_name

                if not tag_info.internal_tag_name in self._tag_provider_lookup[KEY_TAGS]:
                    self._tag_provider_lookup[KEY_TAGS][tag_info.internal_tag_name] = []
                self._tag_provider_lookup[KEY_TAGS][tag_info.internal_tag_name].append(provider)
                if tag_info.is_writable and not tag_info.internal_tag_name in self._tag_writers[KEY_TAGS]: #just store the first provider
                    self._tag_writers[KEY_TAGS][tag_info.internal_tag_name] = [ provider ]

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
                    log.error(f"{self._file_name}: Write is enabled but file is not readable by metadata providers. Disabling write!")

        # TODO: refine this when we have more provider support, KEY_IS_MEDIA should only be true if the file being loaded is a media file we care about
        # if len(self._tag_provider_lookup[KEY_TAGS]) > 0 and len(self._tag_provider_lookup[KEY_STREAM_INFO]) > 0:
        #     self._combined_metadata[KEY_INTERNAL][KEY_IS_MEDIA] = True

        pass #for debugger attach

    def get_tag_all_values(self, key, is_internal_tag_key=False):
        actual_key = key
        if not is_internal_tag_key and key in self._generic_to_internal_map:
            actual_key = self._generic_to_internal_map[key]

        if not self._combined_metadata[KEY_TAGS].get(actual_key):
            self.load_meta_for_tag(actual_key)
        return self._combined_metadata[KEY_TAGS].get(actual_key, {}).get(KEY_VALUE)

    def get_tag_simple(self, key, is_internal_tag_key=False):
        grab = self.get_tag_all_values(key, is_internal_tag_key)
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
        if key in self._combined_metadata[KEY_STREAM_INFO]:
            return self._combined_metadata[KEY_STREAM_INFO][key].get(KEY_VALUE)  # only return first value in array of values
        return None

    def load_meta_for_stream_info(self, key):
        if key in self._tag_provider_lookup[KEY_STREAM_INFO]:
            provider_to_use = self._tag_provider_lookup[KEY_STREAM_INFO][key][0]
            self._combined_metadata[KEY_STREAM_INFO][key] = {
                KEY_VALUE: provider_to_use.get_stream_info(key),
                KEY_PROVIDER: provider_to_use
            }

    def get_internal_data(self, key):
        return self._combined_metadata[KEY_INTERNAL].get(key)

    def save(self, changes=None):
        if not self._write_enabled:
            raise PermissionError("Write is not enabled for this file.")

        if changes is None:
            return

        modified_providers = set()

        # Process generic tag changes
        for tag, value in changes.get(KEY_TAG_GENERIC, {}).items():
            internal_tag = self._generic_to_internal_map.get(tag, tag)
            if internal_tag in self._tag_writers[KEY_TAGS]:
                provider = self._tag_writers[KEY_TAGS][internal_tag][0]
                provider.set_tag(internal_tag, [value])
                modified_providers.add(provider)

        # Process internal tag changes
        for tag, tag_data in changes.get(KEY_TAG_INTERNAL, {}).items():
            provider = tag_data[KEY_PROVIDER]
            provider.set_tag(tag, [tag_data[KEY_VALUE]])
            modified_providers.add(provider)
            # Update internal metadata after saving
            self._combined_metadata[KEY_INTERNAL][tag] = tag_data[KEY_VALUE]

        for provider in modified_providers:
            provider.save()

        # Clear the cache for the tags that were changed
        for tag in changes.get(KEY_TAG_GENERIC, {}).keys():
            internal_tag = self._generic_to_internal_map.get(tag, tag)
            if internal_tag in self._combined_metadata[KEY_TAGS]:
                del self._combined_metadata[KEY_TAGS][internal_tag]

        for tag in changes.get(KEY_TAG_INTERNAL, {}).keys():
            if tag in self._combined_metadata[KEY_TAGS]:
                del self._combined_metadata[KEY_TAGS][tag]


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
                KEY_VALUE: self.get_tag_simple(key, is_internal_tag_key=True),
                KEY_PROVIDER: self._tag_provider_lookup[KEY_TAGS][key][0].__class__.__name__,
                KEY_ALL_VALUES: self.get_tag_all_values(key, is_internal_tag_key=True),
                KEY_ALL_PROVIDERS: [x.__class__.__name__ for x in self._tag_provider_lookup[KEY_TAGS][key]]
            }

        for key in self._tag_provider_lookup[KEY_STREAM_INFO].keys():
            to_ret[KEY_STREAM_INFO][key] = {
                KEY_VALUE: self.get_stream_info_value(key),
                KEY_PROVIDER: self._tag_provider_lookup[KEY_STREAM_INFO][key][0].__class__.__name__,
            }

        # Include all internal data that has been set
        for key, value in self._combined_metadata[KEY_INTERNAL].items():
            to_ret[KEY_INTERNAL][key] = value

        return to_ret

    def is_readable(self):
        return self._combined_metadata[KEY_INTERNAL][KEY_IS_MEDIA]

    @property
    def metadata(self):
        return self.to_dict()

    @property
    def file_path(self):
        return self._file_path

    @property
    def file_id(self):
        return self._file_id

    def get_internal_tag_name_for_generic(self, generic_tag_name):
        return self._generic_to_internal_map.get(generic_tag_name)

    def get_generic_tag_name_for_internal(self, internal_tag_name):
        return self._internal_to_generic_map.get(internal_tag_name)

    def _get_providers_for_file(self):
        """
        Get the MetadataProvider instance(s) most appropriate for the given file in order of preference.
        :param file_path:
        :return:
        """
        potential_providers = [ MutagenProvider ]
        to_ret = []

        for provider in potential_providers:
            try:
                provider_instance = provider(self._file_path)
                if provider_instance.is_readable():
                    to_ret.append( provider_instance )
            except Exception as e:
                log.debug(f"Provider {provider.__name__} failed to load file {self._file_path}: {e}")
                continue

        return to_ret
