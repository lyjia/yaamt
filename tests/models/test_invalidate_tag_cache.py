"""
Regression tests for MediaFile.invalidate_tag_cache.

The Properties window opens its own MediaFile instances. When the analyzer
dispatcher writes tags through a *different* MediaFile pointed at the same
file on disk, the Properties window's cached tag values would otherwise
stay stale forever — its instance has no signal that the file changed and
so keeps returning the cached value (often ``None``) from its first read.

invalidate_tag_cache() must clear the in-memory cache and force the
underlying provider to re-read the file on the next ``get_tag_*`` call.
"""

import shutil
from pathlib import Path

import pytest

from models.media_file import MediaFile
from util.const import (
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_TAG_GENERIC,
)


FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_original.flac"
)


@pytest.fixture
def two_views_of_same_file(tmp_path):
    """Return two independent MediaFile instances pointed at the same path."""
    if not FIXTURE.exists():
        pytest.skip("fixture missing")
    dst = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, dst)
    a = MediaFile(str(dst), enable_write=True)
    b = MediaFile(str(dst), enable_write=False)
    return a, b


def test_second_view_sees_writes_after_invalidation(two_views_of_same_file):
    writer, observer = two_views_of_same_file

    # The observer caches "no value" by reading the unset tag.
    assert observer.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) is None

    # Writer commits a value through its own provider instance.
    writer.save({KEY_TAG_GENERIC: {KEY_REPLAYGAIN_TRACK_GAIN: '-3.45 dB'}})

    # Without invalidation, observer returns stale cached None.
    assert observer.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) is None

    # After invalidation, observer rereads from disk and sees the new value.
    observer.invalidate_tag_cache()
    assert observer.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) == '-3.45 dB'


def test_invalidation_drops_all_cached_keys(two_views_of_same_file):
    """invalidate_tag_cache should empty the entire tag cache, not just one key."""
    _writer, observer = two_views_of_same_file
    # Populate the cache for several tags by reading them.
    observer.get_tag_simple('title')
    observer.get_tag_simple('artist')
    observer.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN)
    assert observer._combined_metadata['tags']  # populated

    observer.invalidate_tag_cache()
    assert observer._combined_metadata['tags'] == {}
