import traceback
from argparse import ArgumentError

import mutagen
from mutagen.easyid3 import EasyID3

from models.tag_info import TagInfo
from util.const import KEY_BITRATE, KEY_CHANNELS, KEY_FORMAT, KEY_SAMPLE_RATE, KEY_LENGTH, KEY_BITS_PER_SAMPLE, \
    KEY_TOTAL_SAMPLES, ALL_TAGS, KEY_MUSICAL_KEY
from util.exceptions import SomethingsReallyFuckedUpException, InvalidFileError
from util.logging import log
from .base import MetadataProviderBase

## Here is the list of easy key names and their mappings to ID3, from
# .venv/Lib/site-packages/mutagen/easyid3.py:
# for frameid, key in {
#     "TALB": "album",
#     "TBPM": "bpm",
#     "TCMP": "compilation",  # iTunes extension
#     "TCOM": "composer",
#     "TCOP": "copyright",
#     "TENC": "encodedby",
#     "TEXT": "lyricist",
#     "TLEN": "length",
#     "TMED": "media",
#     "TMOO": "mood",
#     "TIT1": "grouping",
#     "TIT2": "title",
#     "TIT3": "version",
#     "TPE1": "artist",
#     "TPE2": "albumartist",
#     "TPE3": "conductor",
#     "TPE4": "arranger",
#     "TPOS": "discnumber",
#     "TPUB": "organization",
#     "TRCK": "tracknumber",
#     "TOLY": "author",
#     "TSO2": "albumartistsort",  # iTunes extension
#     "TSOA": "albumsort",
#     "TSOC": "composersort",  # iTunes extension
#     "TSOP": "artistsort",
#     "TSOT": "titlesort",
#     "TSRC": "isrc",
#     "TSST": "discsubtitle",
#     "TLAN": "language",
# }.items():

EasyID3.RegisterTextKey('MUSICAL_KEY', 'TKEY')

class MutagenProvider(MetadataProviderBase):
    """
    A concrete implementation of MetadataProvider that uses the mutagen library.
    """
    def __init__(self, file_path: str):
        self._file_path = file_path
        self._write_enabled = False
        self._audio = None

        try:
            self._audio = mutagen.File(file_path, easy=True)
            if self._audio is not None:
                if self._audio == {}:
                    log.debug(f"No audio tags found in file {file_path}.")
                self._write_enabled = True
            else:
                raise InvalidFileError(f"{__class__.__name__} could not load {file_path}")

        except FileNotFoundError:
            log.error(f"Error: File not found at {file_path}")
            raise
        except mutagen.MutagenError as e:
            traceback.print_exc()
            log.error(f"{e.__class__.__name__} loading file {file_path}: {e}")
            raise

    def get_tag(self, key):
        if not self._audio:
            return None
        if key in self._audio:
            return self._audio[key]
        return None

    # Note that 'internal' tags are the tag keys that mutagen's 'easy' interface provides.
    # 'generic' tag keys are names this program presents.
    # for mutagen, mappings between these two are mostly identical.
    def set_tag(self, key, value, is_internal_tag_key = False):
        if not is_internal_tag_key:
            actual_key = self.get_internal_tag_name_for_generic(key)
        else:
            actual_key = key

        self._audio[actual_key] = value

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

    def available_tags(self) -> list[TagInfo]:
        if self._audio is None:
            raise SomethingsReallyFuckedUpException("self._audio is None. This should not happen!")

        all_tag_keys = self._audio.keys() | ALL_TAGS.keys()
        #all_tag_keys = self._audio.keys()
        log.debug("all_tag_keys: " + str(all_tag_keys) + "")
        tag_infos = []
        for tag_name in sorted(list(all_tag_keys)):
            is_generic = tag_name in ALL_TAGS
            tag_infos.append(TagInfo(name=tag_name, is_writable=True, is_generic=is_generic))
        return tag_infos

    def available_stream_info_keys(self):
        return [KEY_BITRATE, KEY_LENGTH, KEY_SAMPLE_RATE, KEY_CHANNELS, KEY_BITS_PER_SAMPLE, KEY_TOTAL_SAMPLES, KEY_FORMAT]

    # def all_tags(self):
    #     return dict(self._audio.tags)

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
        if generic_name in ALL_TAGS:
            return generic_name
        else:
            raise KeyError(f'generic_name "{generic_name}" not found in ALL_TAGS. Available tags: {ALL_TAGS.keys()}')

    def is_readable(self):
        """
        Should we attempt to read tags from this provider?
        :return: 
        """
        return self._audio is not None

    def is_writable(self):
        return self._write_enabled

    def save(self):
        if self._write_enabled and self._audio:
            try:
                self._audio.save(self._file_path)
            except Exception as e:
                if "Permission denied" in str(e):
                    raise PermissionError(f"File is not writable. Mutagen returned: <{e}>. (write_enabled is {self._write_enabled} and _audio is {self._audio})")
                else:
                    raise

        else:
            raise PermissionError("File is not writable. (write_enabled is {self._write_enabled} and _audio is {self._audio})")