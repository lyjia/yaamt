import os
import threading

from PySide6.QtCore import QObject, Signal

from util.logging import log
from workers.gui.playback_worker import PlaybackWorker


class PlaybackCoordinator(QObject):
    """
    Coordinates file access between EditManager (save thread) and
    PlaybackWorker (playback thread).

    Before saving a file that is currently playing, the coordinator asks
    PlaybackWorker to release the file lock (pause + close stream), waits
    for confirmation, and after the save signals PlaybackWorker to reopen
    and resume from the saved position.
    """

    request_release = Signal(str, object)   # file_path, threading.Event
    request_reacquire = Signal()

    RELEASE_TIMEOUT_SECONDS = 10.0

    def __init__(self, playback_worker: PlaybackWorker):
        super().__init__()
        self._playback_worker = playback_worker
        self._released_file_path: str | None = None

        self.request_release.connect(playback_worker.release_for_write)
        self.request_reacquire.connect(playback_worker.reacquire_after_write)

    def _normalize(self, file_path: str) -> str:
        return os.path.normcase(os.path.abspath(file_path))

    def acquire_file(self, file_path: str) -> None:
        """
        Called from the save thread before writing to a file.
        If PlaybackWorker has this file open, blocks until the file is released.
        """
        normalized = self._normalize(file_path)

        current = self._playback_worker.current_file
        if current is None or self._normalize(current) != normalized:
            return  # Not playing this file

        log.info(f"PlaybackCoordinator: acquiring file for write: {file_path}")

        event = threading.Event()
        self._released_file_path = normalized
        self.request_release.emit(file_path, event)

        if not event.wait(timeout=self.RELEASE_TIMEOUT_SECONDS):
            log.warning(
                f"PlaybackCoordinator: timed out waiting for playback to release {file_path}. "
                f"Save will proceed but may fail with a permission error."
            )

    def release_file(self, file_path: str) -> None:
        """
        Called from the save thread after writing to a file.
        If playback was interrupted for this file, signals PlaybackWorker to resume.
        """
        normalized = self._normalize(file_path)

        if self._released_file_path == normalized:
            log.info(f"PlaybackCoordinator: releasing file after write: {file_path}")
            self._released_file_path = None
            self.request_reacquire.emit()
