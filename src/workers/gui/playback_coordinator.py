import os
import threading

from PySide6.QtCore import QObject, Signal

from models.media_file import MediaFile
from util.logging import log
from workers.gui.playback_worker import PlaybackWorker


class PlaybackCoordinator(QObject):
    """
    Coordinates file access between components that write to files
    (EditManager's save thread, the rename flow) and PlaybackWorker
    (playback thread).

    Before a file that is currently playing is written to or renamed, the
    coordinator asks PlaybackWorker to release it (pause + close stream),
    waits for confirmation, and afterwards signals PlaybackWorker to
    reopen and resume from the saved position.
    """

    request_release = Signal(str, object)   # file_path, threading.Event
    request_reacquire = Signal(object)      # new file path (str) or None

    RELEASE_TIMEOUT_SECONDS = 10.0

    def __init__(self, playback_worker: PlaybackWorker):
        super().__init__()
        self._playback_worker = playback_worker
        self._released_file_path: str | None = None
        # The batch source whose file is released while a rename batch
        # runs. The rename dispatcher repoints this instance in place, so
        # by end_rename_batch() its file_path is wherever the file
        # actually ended up (renamed, restored, or unchanged).
        self._rename_media_file: MediaFile | None = None

        self.request_release.connect(playback_worker.release_for_write)
        self.request_reacquire.connect(playback_worker.reacquire_after_write)

    def _normalize(self, file_path: str) -> str:
        return os.path.normcase(os.path.abspath(file_path))

    def _release_and_wait(self, file_path: str) -> None:
        """Asks PlaybackWorker to release file_path and blocks until it has."""
        event = threading.Event()
        self.request_release.emit(file_path, event)

        if not event.wait(timeout=self.RELEASE_TIMEOUT_SECONDS):
            log.warning(
                f"PlaybackCoordinator: timed out waiting for playback to release {file_path}. "
                f"The write will proceed but may fail with a permission error."
            )

    def acquire_file(self, file_path: str) -> None:
        """
        Called from the save thread before writing to a file.
        If PlaybackWorker has this file open, blocks until the file is released.
        """
        if self._rename_media_file is not None:
            # A rename batch already holds the playback release, so the
            # playing file is closed and the save can proceed as-is.
            log.warning(
                f"PlaybackCoordinator: save of {file_path} requested while a "
                f"rename batch holds the playback release; proceeding."
            )
            return

        normalized = self._normalize(file_path)

        current = self._playback_worker.current_file
        if current is None or self._normalize(current) != normalized:
            return  # Not playing this file

        log.info(f"PlaybackCoordinator: acquiring file for write: {file_path}")

        self._released_file_path = normalized
        self._release_and_wait(file_path)

    def release_file(self, file_path: str) -> None:
        """
        Called from the save thread after writing to a file.
        If playback was interrupted for this file, signals PlaybackWorker to resume.
        """
        normalized = self._normalize(file_path)

        if self._released_file_path == normalized:
            log.info(f"PlaybackCoordinator: releasing file after write: {file_path}")
            self._released_file_path = None
            self.request_reacquire.emit(None)

    def begin_rename_batch(self, media_files: list[MediaFile]) -> None:
        """
        Called on the main thread before a rename batch starts. If the
        currently playing file is one of the batch's sources, releases it
        for the duration of the batch.

        Rename batches run under a modal progress dialog, so no
        user-driven save or second batch can start concurrently -- no
        locking is needed around the rename state.
        """
        current = self._playback_worker.current_file
        if current is None:
            return

        normalized_current = self._normalize(current)
        for media_file in media_files:
            if self._normalize(media_file.file_path) == normalized_current:
                log.info(
                    f"PlaybackCoordinator: releasing {current} for rename batch"
                )
                self._rename_media_file = media_file
                self._release_and_wait(media_file.file_path)
                return

    def end_rename_batch(self) -> None:
        """
        Called on the main thread when a rename batch completes or is
        cancelled. Idempotent. Resumes playback at wherever the released
        file's MediaFile instance points now: the rename dispatcher
        repoints it in place on success and on failure/restore alike, so
        no path computation is needed here. The playback panel picks up
        the (possibly new) file name from the resulting playback_started.
        """
        media_file = self._rename_media_file
        if media_file is None:
            return

        self._rename_media_file = None
        log.info(
            f"PlaybackCoordinator: rename batch done; "
            f"reacquiring {media_file.file_path}"
        )
        self.request_reacquire.emit(media_file.file_path)
