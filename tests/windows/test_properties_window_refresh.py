"""
Regression test for the Properties Main tab showing empty ReplayGain
fields when the underlying MediaFile carried a cached ``None`` value
from a prior read (e.g. it was queried before the analyzer wrote tags
to disk, or it was passed in pre-populated by another component).

The PropertiesWindow constructor must invalidate every MediaFile's
tag cache before MainTab.refresh() runs so the first read of any tag
reflects current on-disk state.
"""

import shutil
from pathlib import Path

import pytest

from util.const import (
    IN_GITHUB_RUNNER,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_TAG_GENERIC,
)


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_original.flac"
)


def test_properties_main_tab_shows_replaygain_with_pre_stale_cache(qapp, tmp_path):
    """
    Reproduces the original report: Advanced shows ReplayGain values from
    disk while Main shows empty fields. Root cause was a MediaFile that
    had cached ``None`` for the four ReplayGain keys before the tags were
    written; subsequent reads kept returning the cache.

    PropertiesWindow now calls ``invalidate_tag_cache`` on every passed-in
    MediaFile before constructing tabs, so the Main tab's first read goes
    to disk regardless of upstream cache state.
    """
    if not FIXTURE.exists():
        pytest.skip("fixture missing")

    from models.edit_manager import EditManager
    from models.media_file import MediaFile
    from windows.properties_window import PropertiesWindow

    dst = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, dst)

    # Write the canonical ReplayGain tag set to disk (simulates the
    # analyzer dispatcher having committed already).
    MediaFile(str(dst), enable_write=True).save({KEY_TAG_GENERIC: {
        KEY_REPLAYGAIN_TRACK_GAIN: '-1.47 dB',
        KEY_REPLAYGAIN_ALBUM_GAIN: '-1.47 dB',
    }})

    # Construct a MediaFile and forcibly poison its cache with stale ``None``
    # entries — mimicking the failure mode the user hit, where the file
    # model handed the Properties window a MediaFile that had already been
    # queried for those tags before they existed on disk.
    mf = MediaFile(str(dst), enable_write=True)
    provider = mf._providers[0]
    mf._combined_metadata['tags']['replaygain_track_gain'] = {
        'value': None, 'provider': provider,
    }
    mf._combined_metadata['tags']['replaygain_album_gain'] = {
        'value': None, 'provider': provider,
    }
    # Sanity: without any invalidation, get_tag_simple returns the stale None.
    assert mf.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) is None

    em = EditManager()
    em.reset_changes()
    em.set_autosave(True)

    pw = PropertiesWindow([mf], em)

    # Defensive invalidate in __init__ should have triggered a fresh read.
    assert pw.main_tab.replaygain_track_edit.text() == '-1.47 dB'
    assert pw.main_tab.replaygain_album_edit.text() == '-1.47 dB'
