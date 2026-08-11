"""
Tests for PlaybackCoordinator: the release/reacquire handshake around
metadata saves and the batch-level release around file renames.

Worker and coordinator live on the same thread here, so the coordinator's
signals are delivered synchronously (direct connections) and acquire never
has to wait on the release event.
"""

from unittest.mock import MagicMock, patch

import pytest

from models.media_file import MediaFile
from util.const import IN_GITHUB_RUNNER
from workers.gui.playback_coordinator import PlaybackCoordinator
from workers.gui.playback_worker import PLAYING, PAUSED, STOPPED

THREE_SECONDS_IN_FRAMES = 44100 * 3


@pytest.fixture
def coordinator(playback_worker):
    return PlaybackCoordinator(playback_worker)


def _make_media_file_mock(file_path: str, mock_audio_stream) -> MagicMock:
    mf = MagicMock(spec=MediaFile)
    mf.file_path = file_path
    mf.get_audio_stream.return_value = mock_audio_stream
    return mf


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
class TestSaveHandshake:

    def test_acquire_release_roundtrip_resumes_playback(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        playback_worker.total_frames_read = THREE_SECONDS_IN_FRAMES

        coordinator.acquire_file("test.mp3")

        assert playback_worker.state == STOPPED
        mock_audio_stream.close.assert_called_once()

        with patch('workers.gui.playback_worker.MediaFile',
                   return_value=mock_media_file) as media_file_cls:
            coordinator.release_file("test.mp3")

        media_file_cls.assert_called_once_with("test.mp3")
        assert playback_worker.state == PLAYING
        assert playback_worker.total_frames_read == THREE_SECONDS_IN_FRAMES

    def test_acquire_file_not_playing_is_noop(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)

        coordinator.acquire_file("other.mp3")

        assert playback_worker.state == PLAYING
        mock_audio_stream.close.assert_not_called()

        # And the paired release must not trigger a reacquire.
        with patch('workers.gui.playback_worker.MediaFile') as media_file_cls:
            coordinator.release_file("other.mp3")
        media_file_cls.assert_not_called()

    def test_roundtrip_preserves_paused_state(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        playback_worker.pause()

        coordinator.acquire_file("test.mp3")
        with patch('workers.gui.playback_worker.MediaFile',
                   return_value=mock_media_file):
            coordinator.release_file("test.mp3")

        assert playback_worker.state == PAUSED


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Crashes in github runner on qapp")
class TestRenameBatch:

    def test_begin_end_reacquires_at_updated_path(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        playback_worker.total_frames_read = THREE_SECONDS_IN_FRAMES

        coordinator.begin_rename_batch([mock_media_file])
        assert playback_worker.state == STOPPED

        # The dispatcher repoints the MediaFile instance in place as the
        # rename completes; the coordinator must follow it.
        mock_media_file.file_path = "renamed.mp3"
        renamed_mf = _make_media_file_mock("renamed.mp3", mock_audio_stream)

        with patch('workers.gui.playback_worker.MediaFile',
                   return_value=renamed_mf) as media_file_cls:
            coordinator.end_rename_batch()

        media_file_cls.assert_called_once_with("renamed.mp3")
        assert playback_worker.state == PLAYING
        assert playback_worker.current_file == "renamed.mp3"
        assert playback_worker.total_frames_read == THREE_SECONDS_IN_FRAMES

    def test_begin_with_no_match_is_noop(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)

        other = _make_media_file_mock("other.mp3", mock_audio_stream)
        coordinator.begin_rename_batch([other])

        assert playback_worker.state == PLAYING

        with patch('workers.gui.playback_worker.MediaFile') as media_file_cls:
            coordinator.end_rename_batch()
        media_file_cls.assert_not_called()
        assert playback_worker.state == PLAYING

    def test_begin_with_nothing_playing_is_noop(
            self, coordinator, playback_worker, mock_media_file):
        coordinator.begin_rename_batch([mock_media_file])
        coordinator.end_rename_batch()
        assert playback_worker.state == STOPPED

    def test_end_is_idempotent(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        coordinator.begin_rename_batch([mock_media_file])

        with patch('workers.gui.playback_worker.MediaFile',
                   return_value=mock_media_file) as media_file_cls:
            coordinator.end_rename_batch()
            coordinator.end_rename_batch()

        media_file_cls.assert_called_once()

    def test_user_stop_during_batch_wins(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        coordinator.begin_rename_batch([mock_media_file])

        playback_worker.stop()

        with patch('workers.gui.playback_worker.MediaFile') as media_file_cls:
            coordinator.end_rename_batch()

        media_file_cls.assert_not_called()
        assert playback_worker.state == STOPPED

    def test_acquire_during_batch_skips_handshake(
            self, coordinator, playback_worker, mock_media_file,
            mock_audio_stream, mock_miniaudio):
        playback_worker.start_playback(mock_media_file)
        coordinator.begin_rename_batch([mock_media_file])

        release_spy = MagicMock()
        coordinator.request_release.connect(release_spy)

        # A save arriving mid-batch must proceed without a second handshake.
        coordinator.acquire_file("test.mp3")
        release_spy.assert_not_called()
