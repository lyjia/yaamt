"""
Regression tests for the Properties window's Main tab layout.

Bug: the ReplayGain QGroupBox at the bottom of the Main tab rendered with no
visible rows. The line edits contained the correct values (data path was
healthy), but the window's explicit setMinimumSize(400, 300) overrode Qt's
layout-derived minimum (~549 px for the form), letting the window open or be
resized small enough that the last widget in the form — the group box — was
crushed below its minimum height and its contents clipped.

Fix: no explicit minimum on PropertiesWindow. With none set, Qt imposes the
layouts' computed minimum on the top-level window, so it can never shrink to
a size where the form clips. Default size raised to 720x600 so everything is
visible on open.
"""

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QGroupBox

from models.edit_manager import EditManager
from models.media_file import MediaFile
from util.const import (
    IN_GITHUB_RUNNER,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_TAG_GENERIC,
)


FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "metadata" / "sample_dtmf_original.flac"
)

TRACK_GAIN = "-9.07 dB"
ALBUM_GAIN = "-8.55 dB"


@pytest.fixture
def rg_tagged_file(tmp_path):
    """A temp copy of a FLAC fixture with ReplayGain gain tags written."""
    if not FIXTURE.exists():
        pytest.skip("fixture missing")
    dst = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, dst)
    mf = MediaFile(str(dst), enable_write=True)
    mf.save({KEY_TAG_GENERIC: {
        KEY_REPLAYGAIN_TRACK_GAIN: TRACK_GAIN,
        KEY_REPLAYGAIN_ALBUM_GAIN: ALBUM_GAIN,
    }})
    return dst


@pytest.fixture
def properties_window(qapp, rg_tagged_file):
    """An open PropertiesWindow on the tagged file, cleaned up after the test."""
    from windows.properties_window import PropertiesWindow

    em = EditManager()
    em.reset_changes()
    mf = MediaFile(str(rg_tagged_file), enable_write=True)
    win = PropertiesWindow([mf], em)
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    qapp.processEvents()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainTabReplayGainVisibility:

    def test_replaygain_values_populate_labels(self, properties_window):
        """Data path: on-disk gains must land in the Main tab's value labels."""
        tab = properties_window.main_tab
        assert tab.replaygain_track_label.text() == TRACK_GAIN
        assert tab.replaygain_album_label.text() == ALBUM_GAIN

    def test_groupbox_not_crushed_at_default_size(self, properties_window, qapp):
        """The group box must get at least its minimum height on open.

        On the buggy code it rendered at ~24 px against a ~91 px minimum,
        clipping both rows out of view.
        """
        group = properties_window.main_tab.findChild(QGroupBox)
        assert group is not None
        assert group.height() >= group.minimumSizeHint().height()

    def test_replaygain_label_visible_within_window_at_default_size(
        self, properties_window
    ):
        """The track-gain label's bottom edge must be inside the window."""
        win = properties_window
        label = win.main_tab.replaygain_track_label
        bottom_y = label.mapTo(win, label.rect().bottomLeft()).y()
        assert bottom_y <= win.height()

    def test_window_cannot_shrink_into_clipping(self, properties_window, qapp):
        """Resizing below the form's minimum must be clamped by Qt.

        This is the regression guard for the original bug report: the old
        explicit setMinimumSize(400, 300) overrode the layout-derived
        minimum and allowed exactly this resize.
        """
        win = properties_window
        group = win.main_tab.findChild(QGroupBox)

        win.resize(720, 300)  # attempt to recreate the user's bad state
        qapp.processEvents()

        assert win.height() > 300, (
            "window accepted a height below its content minimum — an "
            "explicit setMinimumSize() is overriding the layout minimum again"
        )
        assert group.height() >= group.minimumSizeHint().height()
