import traceback
from argparse import ArgumentError
from typing import Any

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4Tags

from models.tag_info import TagInfo
from util.const import KEY_BITRATE, KEY_CHANNELS, KEY_FORMAT, KEY_SAMPLE_RATE, KEY_LENGTH, KEY_BITS_PER_SAMPLE, \
    KEY_TOTAL_SAMPLES, ALL_TAGS, KEY_INITIAL_KEY, KEY_ALBUM, KEY_BPM, KEY_COMPOSER, KEY_COPYRIGHT, KEY_ENCODED_BY, \
    KEY_LYRICIST, KEY_LENGTH as KEY_LENGTH_TAG, KEY_MEDIA, KEY_MOOD, KEY_GROUPING, KEY_TITLE, KEY_VERSION, KEY_ARTIST, \
    KEY_ALBUM_ARTIST, KEY_CONDUCTOR, KEY_ARRANGER, KEY_DISC_NUMBER, KEY_ORGANIZATION, KEY_TRACK_NUMBER, KEY_AUTHOR, \
    KEY_ALBUM_ARTIST_SORT, KEY_ALBUM_SORT, KEY_COMPOSER_SORT, KEY_ARTIST_SORT, KEY_TITLE_SORT, KEY_ISRC, \
    KEY_DISC_SUBTITLE, KEY_LANGUAGE, KEY_GENRE, KEY_COMMENT, KEY_MUSICBRAINZ_RECORDING_ID, KEY_ACOUSTID_ID, \
    KEY_ACOUSTID_FINGERPRINT, KEY_ACOUSTID_SCORE, KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN, \
    KEY_REPLAYGAIN_TRACK_PEAK, KEY_REPLAYGAIN_ALBUM_PEAK
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
def comment_get(id3: Any, key: str) -> list:
    """Get comment from COMM frame(s) with empty description."""
    from mutagen.id3 import COMM
    for frame in id3.values():
        if isinstance(frame, COMM) and frame.desc == '':
            # Return the first COMM frame with empty description
            return list(frame.text) if frame.text else []
    return []

def comment_set(id3: Any, key: str, value: Any) -> None:
    """Set comment in COMM frame with empty description."""
    from mutagen.id3 import COMM, Encoding
    # Remove all existing COMM frames with empty description
    id3.delall('COMM:')
    # Add new COMM frame if value is provided
    if value:
        text_value = value[0] if isinstance(value, list) else str(value)
        if text_value:  # Only add if not empty
            id3.add(COMM(encoding=Encoding.UTF8, lang='eng', desc='', text=text_value))

def comment_delete(id3: Any, key: str) -> None:
    """Delete COMM frame with empty description."""
    id3.delall('COMM:')

EasyID3.RegisterTextKey(KEY_INITIAL_KEY, 'TKEY')
EasyID3.RegisterKey(KEY_COMMENT, comment_get, comment_set, comment_delete)

# MusicBrainz Recording ID: Picard stores this in a UFID frame (canonical,
# binary) and additionally in a TXXX:MusicBrainz Track Id text frame for
# players that only read text frames. We read from either and write to both.
_MBID_OWNER = 'http://musicbrainz.org'
_MBID_TXXX_DESC = 'MusicBrainz Track Id'

def mbid_get(id3: Any, key: str) -> list:
    """Read the MusicBrainz Recording ID from UFID (preferred) or TXXX fallback.

    Raises KeyError when neither frame is present, matching mutagen's easy-mode
    contract so ``key in id3`` returns False for unset tags.
    """
    ufid = id3.get(f'UFID:{_MBID_OWNER}')
    if ufid is not None and ufid.data:
        try:
            return [ufid.data.decode('ascii')]
        except UnicodeDecodeError:
            pass
    txxx = id3.get(f'TXXX:{_MBID_TXXX_DESC}')
    if txxx is not None and txxx.text:
        values = [str(v) for v in txxx.text if v]
        if values:
            return values
    raise KeyError(key)

def mbid_set(id3: Any, key: str, value: Any) -> None:
    """Write the MusicBrainz Recording ID to both UFID and TXXX frames."""
    from mutagen.id3 import UFID, TXXX, Encoding
    text_value = value[0] if isinstance(value, list) else str(value)
    id3.delall(f'UFID:{_MBID_OWNER}')
    id3.delall(f'TXXX:{_MBID_TXXX_DESC}')
    if not text_value:
        return
    id3.add(UFID(owner=_MBID_OWNER, data=text_value.encode('ascii')))
    id3.add(TXXX(encoding=Encoding.UTF8, desc=_MBID_TXXX_DESC, text=text_value))

def mbid_delete(id3: Any, key: str) -> None:
    """Remove both the UFID and TXXX MusicBrainz Recording ID frames."""
    id3.delall(f'UFID:{_MBID_OWNER}')
    id3.delall(f'TXXX:{_MBID_TXXX_DESC}')

EasyID3.RegisterKey(KEY_MUSICBRAINZ_RECORDING_ID, mbid_get, mbid_set, mbid_delete)

# AcoustID identifiers live in TXXX frames using Picard's canonical
# descriptions. Vorbis/FLAC use lowercase keys of the same name, which
# easy-mode passes through directly so no extra Vorbis registration is needed.
EasyID3.RegisterTXXXKey(KEY_ACOUSTID_ID, 'Acoustid Id')
EasyID3.RegisterTXXXKey(KEY_ACOUSTID_FINGERPRINT, 'Acoustid Fingerprint')
# AcoustID match confidence. Not part of Picard's canonical set but
# follows the same TXXX/Vorbis naming convention so third-party tools can
# read it without guessing.
EasyID3.RegisterTXXXKey(KEY_ACOUSTID_SCORE, 'Acoustid Score')

# Canonical ReplayGain 2.0 tag bindings. ID3: we write lowercase TXXX
# descriptions (foobar2000 / r128gain / rsgain convention) but read both
# lowercase and uppercase variants since many taggers write uppercase
# descriptions (e.g. REPLAYGAIN_TRACK_GAIN). MP4: iTunes-style freeform
# atom under the com.apple.iTunes mean. FLAC/Vorbis require no
# registration — lowercase Vorbis comment keys pass through mutagen's
# native FLAC interface.
_REPLAYGAIN_TAGS = (
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK,
    KEY_REPLAYGAIN_ALBUM_PEAK,
)


def _register_replaygain_txxx_key(key: str, desc: str) -> None:
    """Register an EasyID3 key that reads both lowercase and uppercase TXXX descriptions."""
    frame_lower = "TXXX:" + desc
    frame_upper = "TXXX:" + desc.upper()

    def getter(id3, _key):
        if frame_lower in id3:
            return list(id3[frame_lower])
        if frame_upper in id3:
            return list(id3[frame_upper])
        raise KeyError(key)

    def setter(id3, _key, value):
        # Remove any uppercase variant before writing lowercase
        if frame_upper in id3:
            del id3[frame_upper]
        enc = 0
        for v in value:
            if v and max(v) > '\x7f':
                enc = 3
                break
        id3.add(mutagen.id3.TXXX(encoding=enc, text=value, desc=desc))

    def deleter(id3, _key):
        if frame_lower in id3:
            del id3[frame_lower]
        if frame_upper in id3:
            del id3[frame_upper]

    EasyID3.RegisterKey(key, getter, setter, deleter)


for _rg_key in _REPLAYGAIN_TAGS:
    _register_replaygain_txxx_key(_rg_key, _rg_key)
    EasyMP4Tags.RegisterFreeformKey(_rg_key, _rg_key)

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
                      KEY_MUSICBRAINZ_RECORDING_ID,
                      KEY_ACOUSTID_ID,
                      KEY_ACOUSTID_FINGERPRINT,
                      KEY_ACOUSTID_SCORE,
                      # doesnt appear in above comment for some reason?
                      'genre', #TODO: figure out why
                      # ReplayGain tags (registered with EasyID3 and EasyMP4Tags
                      # at module load). Included here so MediaFile recognises
                      # them as writable even on files that don't yet have them.
                      KEY_REPLAYGAIN_TRACK_GAIN,
                      KEY_REPLAYGAIN_ALBUM_GAIN,
                      KEY_REPLAYGAIN_TRACK_PEAK,
                      KEY_REPLAYGAIN_ALBUM_PEAK]

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
    KEY_INITIAL_KEY: KEY_INITIAL_KEY,
    KEY_COMMENT: KEY_COMMENT,
    KEY_MUSICBRAINZ_RECORDING_ID: KEY_MUSICBRAINZ_RECORDING_ID,
    KEY_ACOUSTID_ID: KEY_ACOUSTID_ID,
    KEY_ACOUSTID_FINGERPRINT: KEY_ACOUSTID_FINGERPRINT,
    KEY_ACOUSTID_SCORE: KEY_ACOUSTID_SCORE,
    'genre': KEY_GENRE,
    # ReplayGain tags (ID3 TXXX / MP4 freeform / Vorbis comment — all map
    # identically to the same lowercase generic name).
    KEY_REPLAYGAIN_TRACK_GAIN: KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_REPLAYGAIN_ALBUM_GAIN: KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK: KEY_REPLAYGAIN_TRACK_PEAK,
    KEY_REPLAYGAIN_ALBUM_PEAK: KEY_REPLAYGAIN_ALBUM_PEAK,
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

    def get_tag(self, key: str) -> list | None:
        if not self._audio:
            return None

        if key in self._audio:
            return self._audio[key]

        return None

    def set_tag(self, key: str, value: list) -> None:
        self._audio[key] = value

    def get_stream_info(self, key: str) -> Any:
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

    def available_stream_info_keys(self) -> list[str]:
        return [KEY_BITRATE, KEY_LENGTH, KEY_SAMPLE_RATE, KEY_CHANNELS, KEY_BITS_PER_SAMPLE, KEY_TOTAL_SAMPLES,
                KEY_FORMAT]

    def is_readable(self) -> bool:
        """
        Should we attempt to read tags from this provider?
        """
        return self._audio is not None

    def reload(self) -> None:
        """
        Re-open the file via mutagen to pick up tag changes that landed on
        disk through a different MediaFile / provider instance. Called by
        ``MediaFile.invalidate_tag_cache``.
        """
        if not self._file_path:
            return
        try:
            self._audio = mutagen.File(self._file_path, easy=True)
        except Exception as e:
            log.warning(f"Failed to reload {self._file_path}: {e}")

    def is_writable(self) -> bool:
        return self._write_enabled

    def save(self) -> None:
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
