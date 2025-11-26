import traceback
from argparse import ArgumentError

import mutagen
from mutagen.easyid3 import EasyID3

from models.tag_info import TagInfo
from util.const import KEY_BITRATE, KEY_CHANNELS, KEY_FORMAT, KEY_SAMPLE_RATE, KEY_LENGTH, KEY_BITS_PER_SAMPLE, \
    KEY_TOTAL_SAMPLES, ALL_TAGS, KEY_INITIAL_KEY, KEY_ALBUM, KEY_BPM, KEY_COMPOSER, KEY_COPYRIGHT, KEY_ENCODED_BY, \
    KEY_LYRICIST, KEY_LENGTH as KEY_LENGTH_TAG, KEY_MEDIA, KEY_MOOD, KEY_GROUPING, KEY_TITLE, KEY_VERSION, KEY_ARTIST, \
    KEY_ALBUM_ARTIST, KEY_CONDUCTOR, KEY_ARRANGER, KEY_DISC_NUMBER, KEY_ORGANIZATION, KEY_TRACK_NUMBER, KEY_AUTHOR, \
    KEY_ALBUM_ARTIST_SORT, KEY_ALBUM_SORT, KEY_COMPOSER_SORT, KEY_ARTIST_SORT, KEY_TITLE_SORT, KEY_ISRC, \
    KEY_DISC_SUBTITLE, KEY_LANGUAGE, KEY_GENRE, KEY_COMMENT
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

# Register comment field with proper COMM frame handling
def comment_get(id3, key):
    """Get comment from COMM frame(s) with empty description."""
    from mutagen.id3 import COMM
    for frame in id3.values():
        if isinstance(frame, COMM) and frame.desc == '':
            # Return the first COMM frame with empty description
            return list(frame.text) if frame.text else []
    return []

def comment_set(id3, key, value):
    """Set comment in COMM frame with empty description."""
    from mutagen.id3 import COMM, Encoding
    # Remove all existing COMM frames with empty description
    id3.delall('COMM:')
    # Add new COMM frame if value is provided
    if value:
        text_value = value[0] if isinstance(value, list) else str(value)
        if text_value:  # Only add if not empty
            id3.add(COMM(encoding=Encoding.UTF8, lang='eng', desc='', text=text_value))

def comment_delete(id3, key):
    """Delete COMM frame with empty description."""
    id3.delall('COMM:')

EasyID3.RegisterTextKey(KEY_INITIAL_KEY, 'TKEY')
EasyID3.RegisterKey(KEY_COMMENT, comment_get, comment_set, comment_delete)

MUT_EASY_TAG_NAMES = ['album',
                      'bpm',
                      'compilation',
                      'composer',
                      'copyright',
                      'encodedby',
                      'lyricist',
                      'length',
                      'media',
                      'mood',
                      'grouping',
                      'title',
                      'version',
                      'artist',
                      'albumartist',
                      'conductor',
                      'arranger',
                      'discnumber',
                      'organization',
                      'tracknumber',
                      'author',
                      'albumartistsort',
                      'albumsort',
                      'composersort',
                      'artistsort',
                      'titlesort',
                      'isrc',
                      'discsubtitle',
                      'language',
                      # added manually, above
                      KEY_INITIAL_KEY,
                      KEY_COMMENT,
                      # doesnt appear in above comment for some reason?
                      'genre'] #TODO: figure out why

# This dictionary maps 'easy' mutagen tag names to the generic KEY_ constants.
# This is used to populate the `generic_tag_name` field in the TagInfo objects.
MUTAGEN_TO_GENERIC_MAP = {
    'album': KEY_ALBUM,
    'bpm': KEY_BPM,
    # 'compilation': KEY_COMPILATION, # No generic key for this yet
    'composer': KEY_COMPOSER,
    'copyright': KEY_COPYRIGHT,
    'encodedby': KEY_ENCODED_BY,
    # 'lyricist': KEY_LYRICIST, # No generic key for this yet
    # 'length': KEY_LENGTH_TAG, # This is a stream info key
    # 'media': KEY_MEDIA, # No generic key for this yet
    'mood': KEY_MOOD,
    'grouping': KEY_GROUPING,
    'title': KEY_TITLE,
    # 'version': KEY_VERSION, # No generic key for this yet
    'artist': KEY_ARTIST,
    'albumartist': KEY_ALBUM_ARTIST,
    # 'conductor': KEY_CONDUCTOR, # No generic key for this yet
    # 'arranger': KEY_ARRANGER, # No generic key for this yet
    'discnumber': KEY_DISC_NUMBER,
    # 'organization': KEY_ORGANIZATION, # No generic key for this yet
    'tracknumber': KEY_TRACK_NUMBER,
    # 'author': KEY_AUTHOR, # No generic key for this yet
    # 'albumartistsort': KEY_ALBUM_ARTIST_SORT, # No generic key for this yet
    # 'albumsort': KEY_ALBUM_SORT, # No generic key for this yet
    # 'composersort': KEY_COMPOSER_SORT, # No generic key for this yet
    # 'artistsort': KEY_ARTIST_SORT, # No generic key for this yet
    # 'titlesort': KEY_TITLE_SORT, # No generic key for this yet
    'isrc': KEY_ISRC,
    # 'discsubtitle': KEY_DISC_SUBTITLE, # No generic key for this yet
    'language': KEY_LANGUAGE,
    KEY_INITIAL_KEY: KEY_INITIAL_KEY, #for ID3, this should be 'initial key', but for vorbis, it should be 'initialkey'
    KEY_COMMENT: KEY_COMMENT,
    'genre': KEY_GENRE,
}


class MutagenProvider(MetadataProviderBase):
    """
    A concrete implementation of MetadataProvider that uses the mutagen library.

    WARNING:
    MutagenProvider uses mutagen's 'easy' mode to abstract tag names across metadata formats. Always favor augmenting easy mode (i.e. with `EasyID3.RegisterKey`) over trying to load a file's metadata using mutagen's 'raw' mode.
    """

    def __init__(self, file_path: str):
        self._file_path = file_path
        self._write_enabled = False
        self._audio = None

        try:
            self._audio = mutagen.File(file_path, easy=True)
            if self.is_readable():
                if self._audio == {}:
                    log.debug(f"No audio tags found in file {file_path}.")
                self._write_enabled = True
            # else: # I don't think we need to crash here
            #     raise InvalidFileError(f"{__class__.__name__} could not load {file_path}")

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

    def set_tag(self, key, value):
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

    def available_internal_tags(self) -> list[TagInfo]:
        if self._audio is None:
            raise SomethingsReallyFuckedUpException("self._audio is None. This should not happen!")

        all_tag_keys = set(list(self._audio.keys())) | set(MUT_EASY_TAG_NAMES)
        tag_infos = []

        for tag_name in sorted(list(all_tag_keys)):
            generic_name = MUTAGEN_TO_GENERIC_MAP.get(tag_name)
            tag_infos.append(TagInfo(internal_tag_name=tag_name, is_writable=True, generic_tag_name=generic_name))

        return tag_infos

    def available_stream_info_keys(self):
        return [KEY_BITRATE, KEY_LENGTH, KEY_SAMPLE_RATE, KEY_CHANNELS, KEY_BITS_PER_SAMPLE, KEY_TOTAL_SAMPLES,
                KEY_FORMAT]

    # def all_tags(self):
    #     return dict(self._audio.tags)

    # def all_stream_infos(self): #TODO: delete me
    #     return {
    #         KEY_BITRATE: self.get_stream_info(KEY_BITRATE),
    #         KEY_LENGTH: self.get_stream_info(KEY_LENGTH),
    #         KEY_SAMPLE_RATE: self.get_stream_info(KEY_SAMPLE_RATE),
    #         KEY_CHANNELS: self.get_stream_info(KEY_CHANNELS),
    #         KEY_FORMAT: self.get_stream_info(KEY_FORMAT)
    #     }


    def is_readable(self):
        """
        Should we attempt to read tags from this provider?
        :return: 
        """
        return self._audio is not None

    def is_writable(self):
        return self._write_enabled

    def save(self):
        # log.debug(f"Saving file: {self._file_path}")
        if self._write_enabled and self._audio:
            try:
                self._audio.save(self._file_path)
                log.debug(f"Successfully saved file: {self._file_path}")
            except Exception as e:
                log.error(f"Failed to save file: {self._file_path}, error: {e}")
                if "Permission denied" in str(e):
                    raise PermissionError(
                        f"File is not writable. Mutagen returned: <{e}>. (write_enabled is {self._write_enabled} and _audio is {self._audio})")
                else:
                    raise

        else:
            log.error(f"File not writable: {self._file_path}")
            raise PermissionError(
                "File is not writable. (write_enabled is {self._write_enabled} and _audio is {self._audio})")
