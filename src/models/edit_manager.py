import threading

from PySide6.QtCore import QObject, Signal, QThread, Slot
from typing import Any
from models.media_file import MediaFile
from models.tag_info import TagInfo
from util.const import KEY_TAG_GENERIC, KEY_TAG_INTERNAL, KEY_VALUE, KEY_PROVIDER
from util.logging import log

# Upper bound for blocking on an in-flight background commit (e.g. at quit
# time). Generous: a commit is a handful of tag writes, not a transcode.
DEFAULT_COMMIT_WAIT_TIMEOUT_MS = 30_000

# commit_progress is emitted as (percent_complete, 100).
PROGRESS_TOTAL_PERCENT = 100


class _CommitWorker(QObject):
    """
    Runs EditManager's save loop inside the commit QThread.

    EditManager itself lives in the GUI thread. Connecting QThread.started
    directly to one of its methods makes Qt deliver the signal as a queued
    call in the *receiver's* thread — the GUI thread — so the "background"
    save silently ran on the main thread and froze the UI during file I/O.
    Moving this worker to the commit thread makes run() execute there.
    """

    def __init__(self, edit_manager: "EditManager") -> None:
        super().__init__()
        self._edit_manager = edit_manager

    @Slot()
    def run(self) -> None:
        try:
            self._edit_manager._save_changes()
        finally:
            # Quit the thread's event loop with a direct call (QThread.quit
            # is thread-safe). Routing this through a signal would queue it
            # on the GUI thread's event loop, deadlocking any caller that
            # blocks in wait_for_pending_commit() without spinning events.
            thread = self.thread()
            if thread is not None:
                thread.quit()


class EditManager(QObject):
    """
    Manages operations related to staging, committing, and managing changes for media files.

    This class is a singleton. Passing instantiated objects to other classes will always return the same instance.

    Provides functionality to stage changes, manage autosave, and perform both synchronous and asynchronous
    commits for changes. This class ensures thread safety for operations and emits signals to notify about
    important events such as change staging, commit progress, and completions.

    Signals:
        - staged_changes_exist: Indicates if there are staged changes, parameter is a boolean.
        - autosave_changed: Indicates a change in autosave state, parameter is a boolean.
        - commit_started: Emitted when a commit process starts.
        - commit_progress: Emitted during the commit process. Parameters are current progress and total progress.
        - commit_finished: Emitted upon successful commit, parameter is a list of file IDs.
        - commit_failed: Emitted upon failed commit, parameter is a list of errors.

    :ivar staged_changes_exist: Signal emitted when staged changes exist or no longer exist.
    :type staged_changes_exist: Signal
    :ivar autosave_changed: Signal emitted when autosave state changes.
    :type autosave_changed: Signal
    :ivar commit_started: Signal emitted when a commit is initiated.
    :type commit_started: Signal
    :ivar commit_progress: Signal emitted to report progress during the commit process.
    :type commit_progress: Signal
    :ivar commit_finished: Signal emitted upon successful commit completion, includes list of saved file IDs.
    :type commit_finished: Signal
    :ivar commit_failed: Signal emitted upon commit failure, includes list of errors.
    :type commit_failed: Signal
    """
    staged_changes_exist = Signal(bool)
    autosave_changed = Signal(bool)
    commit_started = Signal()
    commit_progress = Signal(int, int)
    commit_finished = Signal(list)  # Signal emitted when commit is successful, with list of file_ids
    commit_failed = Signal(list)  # Signal emitted when commit fails, with list of errors

    _instance = None
    _write_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EditManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        # Structure: {file_id: {KEY_TAG_GENERIC: {tag: value}, KEY_TAG_INTERNAL: {tag: {KEY_VALUE: value, KEY_PROVIDER: provider}}}}
        self._staged_changes: dict[int, dict[str, dict]] = {}
        self._media_files: dict[int, MediaFile] = {}
        self._autosave = True
        self._commit_thread: QThread | None = None
        self._commit_worker: _CommitWorker | None = None
        # Serializes whole save operations against each other (background
        # commit vs. quit-time sync save). Distinct from _write_lock, which
        # only guards the staged-changes dict and must never be held across
        # file I/O — staging from the GUI thread would block on it.
        self._save_lock = threading.Lock()
        self._playback_coordinator = None
        self._initialized = True

    @property
    def autosave(self) -> bool:
        return self._autosave

    @autosave.setter
    def autosave(self, value: bool):
        # Direct setter no longer emits signal; use set_autosave method for that
        # This deprecated function should only be used by tests if the signal emission is undesirable
        if self._autosave != value:
            self._autosave = value

    @Slot(bool)
    def set_autosave(self, enabled: bool):
        """
        Sets the autosave state and emits the autosave_changed signal.
        This is the preferred way to change autosave status to ensure signal emission.
        """
        if self._autosave != enabled:
            self._autosave = enabled
            log.debug(f"Autosave set to: {enabled}")
            self.autosave_changed.emit(self._autosave)

    def set_playback_coordinator(self, coordinator: Any | None) -> None:
        """
        Set the PlaybackCoordinator used to pause/resume playback around file writes.
        In CLI mode this is never called, leaving the coordinator as None (no-op).
        """
        self._playback_coordinator = coordinator

    def register_media_files(self, media_files: list[MediaFile], force_replace: bool = False) -> None:
        """
        Register MediaFile instances with the EditManager.

        Args:
            media_files: List of MediaFile objects to register
            force_replace: If True, replace existing instances even if already registered
        """
        for media_file in media_files:
            if force_replace or media_file.file_id not in self._media_files:
                self._media_files[media_file.file_id] = media_file

    def stage_change(self, media_files: list[MediaFile], tag: str, value: Any,
                     is_internal_tag: bool = False,
                     provider: Any | None = None) -> None:
        """
        Stage a change for one or more files, pending a call to commit_changes().

        Args:
            media_files: List of MediaFile objects to apply the change to
            tag: The tag name (generic or internal)
            value: The new value for the tag
            is_internal_tag: Whether the tag is an internal tag name
            provider: The provider instance for internal tags (required if is_internal_tag=True)
        """

        # do not try to call self.commit_changes() in here; the caller should handle that.
        with self._write_lock:
            for media_file in media_files:
                file_id = media_file.file_id
                if file_id not in self._staged_changes:
                    self._staged_changes[file_id] = {
                        KEY_TAG_GENERIC: {},
                        KEY_TAG_INTERNAL: {}
                    }

                if is_internal_tag:
                    # For internal tags, store with provider context
                    if provider is None:
                        raise ValueError(f"Provider must be specified for internal tag '{tag}'")
                    self._staged_changes[file_id][KEY_TAG_INTERNAL][tag] = {
                        KEY_VALUE: value,
                        KEY_PROVIDER: provider
                    }
                else:
                    # For generic tags, store directly
                    self._staged_changes[file_id][KEY_TAG_GENERIC][tag] = value

            self.staged_changes_exist.emit(self.has_staged_changes())

    def _save_changes_impl(self) -> tuple[list[int], list[str]]:
        """
        Core save logic that can be used by both synchronous and asynchronous operations.

        Returns:
            Tuple of ``(saved_file_ids, errors)``.
        """
        log.debug("Starting save operation...")
        saved_file_ids: list[int] = []
        unsavable_file_ids: list[int] = []
        errors: list[str] = []

        with self._save_lock:
            # Snapshot the staged changes so the dict lock is not held across
            # file I/O. The snapshot is also what lets us unstage selectively
            # afterward: only what was actually written, and only if the user
            # did not stage a newer value for that file mid-save.
            with self._write_lock:
                snapshot = {
                    file_id: {
                        KEY_TAG_GENERIC: dict(changes[KEY_TAG_GENERIC]),
                        KEY_TAG_INTERNAL: dict(changes[KEY_TAG_INTERNAL]),
                    }
                    for file_id, changes in self._staged_changes.items()
                }

            total_files = len(snapshot)
            if total_files == 0:
                return saved_file_ids, errors

            for index, (file_id, changes) in enumerate(snapshot.items()):
                media_file = self._media_files.get(file_id)
                if media_file is None:
                    # Cannot ever succeed; drop the entry below rather than
                    # leaving it to fail on every subsequent save.
                    log.error(f"No MediaFile registered for file id {file_id}; dropping its staged changes")
                    errors.append(f"file id {file_id}: no registered MediaFile instance")
                    unsavable_file_ids.append(file_id)
                    continue
                try:
                    if self._playback_coordinator:
                        self._playback_coordinator.acquire_file(media_file.file_path)
                    media_file.save(changes)
                    saved_file_ids.append(file_id)
                except Exception as e:
                    log.error(f"Error saving file {media_file.file_path}: {e}")
                    errors.append(f"{media_file.file_path}: {e}")
                finally:
                    if self._playback_coordinator:
                        self._playback_coordinator.release_file(media_file.file_path)
                self.commit_progress.emit(
                    int((index + 1) * PROGRESS_TOTAL_PERCENT / total_files), PROGRESS_TOTAL_PERCENT)

            with self._write_lock:
                # Files that failed to save keep their staged edits so the
                # user's work is never silently discarded; they stay marked
                # as pending and a later save retries them.
                for file_id in saved_file_ids:
                    if self._staged_changes.get(file_id) == snapshot[file_id]:
                        del self._staged_changes[file_id]
                for file_id in unsavable_file_ids:
                    self._staged_changes.pop(file_id, None)
                self.staged_changes_exist.emit(self.has_staged_changes())

        return saved_file_ids, errors

    def _save_changes(self):
        """
        Saves staged changes and reports the outcome via signals. Runs inside
        the commit thread via _CommitWorker (see commit_changes()).
        """
        saved_file_ids, errors = self._save_changes_impl()

        if errors:
            self.commit_failed.emit(errors)
        else:
            self.commit_finished.emit(saved_file_ids)

    def commit_changes(self, autosave_override: bool = False) -> bool:
        """
        Commit all staged changes to the files by running the save operation in a background thread.

        Callers may expect a signal emitted by the commit_finished signal when the operation is complete.
        In cases where this will never happen (due to autosave being disabled, nothing to save, etc),
        it will return False to indicate it is done.
        """

        if not self.autosave and not autosave_override:
            # Normal flow, not an error: with autosave off every edit ends
            # here and stays staged until the user explicitly saves.
            log.debug("Autosave is disabled; changes remain staged until an explicit save.")
            return False

        if self._commit_thread is not None and self._commit_thread.isRunning():
            log.warning("Save is already in progress.")
            return False

        if not self.has_staged_changes():
            self.staged_changes_exist.emit(False)
            return False

        log.debug("Saving changes in a background thread...")
        thread = QThread()
        worker = _CommitWorker(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        # Identity-checked cleanup: if a newer commit replaced the
        # references before this (queued) cleanup runs, leave them alone.
        thread.finished.connect(lambda t=thread: self._on_commit_thread_finished(t))

        # Keep Python references so neither object is garbage-collected
        # while the thread runs; released in _on_commit_thread_finished.
        self._commit_thread = thread
        self._commit_worker = worker

        self.commit_started.emit()
        thread.start()
        return True

    def _on_commit_thread_finished(self, thread: QThread) -> None:
        if self._commit_thread is thread:
            self._commit_thread = None
            self._commit_worker = None

    def wait_for_pending_commit(self, timeout_ms: int = DEFAULT_COMMIT_WAIT_TIMEOUT_MS) -> bool:
        """
        Block until any in-flight background commit has finished.

        Used at quit time (and by tests) so the process does not tear down
        a QThread mid-write. Returns True if no commit was running or it
        completed within the timeout.
        """
        thread = self._commit_thread
        if thread is None:
            return True
        return thread.wait(timeout_ms)

    def commit_changes_sync(self) -> tuple[list[int], list[str]]:
        """
        Commit all staged changes to the files synchronously. Used by the CLI to bypass the background thread.

        Returns:
            Tuple of ``(saved_file_ids, errors)``.
        """
        saved_file_ids, errors = self._save_changes_impl()
        return saved_file_ids, errors

    def reset_changes(self) -> None:
        """
        Reset all staged changes.
        """
        with self._write_lock:
            self._staged_changes.clear()
            self.staged_changes_exist.emit(False)

    def clear_staged_changes_for_files(self, file_ids: list[int]) -> None:
        """
        Clear staged changes for specific files.

        Args:
            file_ids: List of file IDs to clear staged changes for
        """
        with self._write_lock:
            for file_id in file_ids:
                if file_id in self._staged_changes:
                    del self._staged_changes[file_id]
            self.staged_changes_exist.emit(self.has_staged_changes())

    def unstage_change(self, media_files: list[MediaFile], tag: str, is_internal_tag: bool = False) -> None:
        """
        Remove a staged change for one or more files, restoring the tag to
        its on-disk value. The inverse of stage_change(); used by revert
        controls. Unstaged tags are not written on the next save.
        """
        with self._write_lock:
            for media_file in media_files:
                file_changes = self._staged_changes.get(media_file.file_id)
                if not file_changes:
                    continue
                bucket = file_changes[KEY_TAG_INTERNAL if is_internal_tag else KEY_TAG_GENERIC]
                bucket.pop(tag, None)
            self.staged_changes_exist.emit(self.has_staged_changes())

    def has_staged_changes(self) -> bool:
        """
        Check if there are any staged changes.
        """
        result = False
        for file_changes in self._staged_changes.values():
            if file_changes[KEY_TAG_GENERIC] or file_changes[KEY_TAG_INTERNAL]:
                result = True
                break
        return result

    def get_staged_file_ids(self) -> list[int]:
        """
        File ids that currently have at least one staged change. Lets the
        UI know which rows to refresh after a reset.
        """
        return [
            file_id
            for file_id, changes in self._staged_changes.items()
            if changes[KEY_TAG_GENERIC] or changes[KEY_TAG_INTERNAL]
        ]


    def get_staged_value_for_file(self, media_file: MediaFile, tag: str, is_internal_tag: bool = False) -> Any | None:
        return self.get_staged_value(media_file.file_id, tag, is_internal_tag)

    def get_staged_value(self, file_id: int, tag: str, is_internal_tag: bool = False) -> Any | None:
        """
        Get the staged value for a specific tag in a file by file id.

        Args:
            :param file_id: file id to look for changes in.
            tag: The tag name to look for
            is_internal_tag: Whether the tag is an internal tag name

        Returns:
            The staged value if found, None otherwise

        """
        if file_id not in self._staged_changes:
            return None

        if is_internal_tag:
            internal_changes = self._staged_changes[file_id][KEY_TAG_INTERNAL]
            if tag in internal_changes:
                return internal_changes[tag][KEY_VALUE]
        else:
            generic_changes = self._staged_changes[file_id][KEY_TAG_GENERIC]
            if tag in generic_changes:
                return generic_changes[tag]

        return None



    def get_staged_changes_for_file(self, media_file: MediaFile) -> dict[str, dict]:
        """
        Get all staged changes for a specific file.

        Args:
            media_file: The MediaFile object to get changes for

        Returns:
            Dictionary with KEY_TAG_GENERIC and KEY_TAG_INTERNAL keys
        """
        return self.get_staged_changes(media_file.file_id)

    def get_staged_changes(self, file_id: int) -> dict[str, dict]:
        return self._staged_changes.get(file_id, {KEY_TAG_GENERIC: {}, KEY_TAG_INTERNAL: {}})

    def get_media_file(self, file_id: int) -> MediaFile | None:
        to_ret = self._media_files.get(file_id)
        if to_ret is None:
            log.warning(f"Media file with id {file_id} not found.")
        return to_ret
