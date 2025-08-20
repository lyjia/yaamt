import mutagen

from util.const import KEY_BITRATE, KEY_CHANNELS, KEY_FORMAT, KEY_SAMPLE_RATE, KEY_LENGTH, KEY_BITS_PER_SAMPLE, \
    KEY_TOTAL_SAMPLES, ALL_TAGS
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

    def get_stream_info(self, key):
        if not self._audio:
            return None
        if key == KEY_BITRATE:
            return self._audio.info.bitrate
        elif key == KEY_LENGTH:
            return self._audio.info.length
        elif key == KEY_SAMPLE_RATE:
            return self._audio.info.sample_rate
        elif key == KEY_CHANNELS:
            return self._audio.info.channels
        elif key == KEY_BITS_PER_SAMPLE:
            return getattr(self._audio.info, 'bits_per_sample', None)
        elif key == KEY_TOTAL_SAMPLES:
            return self._audio.info.length * self._audio.info.channels
        elif key == KEY_FORMAT:
            return self._audio.info.pprint().split(',')[0]
        return None

    def available_tags(self):
        if self._audio:
            return set(self._audio.tags.keys() | ALL_TAGS.keys())
        return []

    def available_stream_info_keys(self):
        return [KEY_BITRATE, KEY_LENGTH, KEY_SAMPLE_RATE, KEY_CHANNELS, KEY_BITS_PER_SAMPLE, KEY_TOTAL_SAMPLES, KEY_FORMAT]

    def all_tags(self):
        return dict(self._audio.tags)

    def all_stream_infos(self):
        return {
            KEY_BITRATE: self.get_stream_info(KEY_BITRATE),
            KEY_LENGTH: self.get_stream_info(KEY_LENGTH),
            KEY_SAMPLE_RATE: self.get_stream_info(KEY_SAMPLE_RATE),
            KEY_CHANNELS: self.get_stream_info(KEY_CHANNELS),
            KEY_FORMAT: self.get_stream_info(KEY_FORMAT)
        }

    def get_internal_tag_name_for_generic(self, generic_name: str)-> str:
        """
        Maps the internal tag name native to this provider, from the given higher-level generic tag name.
        :param generic_name:
        :rtype: str
        :return:
        """
        # if generic_name == KEY_TITLE: #example
        #     return 'title'
        # TODO: we may need to audit the list in ALL_TAGS and make sure that they correctly map to mutagen's Easy keys
        return generic_name

    def is_readable(self):
        """
        Should we attempt to read tags from this provider?
        :return: 
        """
        return self._audio is not None

    def is_writable(self):
        return False #disable all writes for now

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