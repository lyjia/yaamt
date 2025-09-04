import threading

from PySide6.QtCore import QObject, Signal, QThread, Slot
from typing import Dict, List, Any, Optional
from models.media_file import MediaFile
from models.tag_info import TagInfo
from util.const import KEY_TAG_GENERIC, KEY_TAG_INTERNAL, KEY_VALUE, KEY_PROVIDER
from util.logging import log


class EditManager(QObject):
    """
    A singleton class to manage metadata edits across the application.

    Handles the distinction between generic tags (user-facing) and internal tags (provider-specific),
    ensuring proper mapping and provider context for all metadata operations.
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
        self._staged_changes: Dict[str, Dict[str, Dict]] = {}
        self._media_files: Dict[str, MediaFile] = {}
        self._autosave = True #always enable for now
        self._commit_thread = None
        self._initialized = True

    @property
    def autosave(self) -> bool:
        return self._autosave

    @autosave.setter
    def autosave(self, value: bool):
        if self._autosave != value:
            self._autosave = value
            self.autosave_changed.emit(self._autosave)

    def register_media_files(self, media_files: List[MediaFile]):
        for media_file in media_files:
            if media_file.file_id not in self._media_files:
                self._media_files[media_file.file_id] = media_file

    def stage_change(self, media_files: List[MediaFile], tag: str, value: Any, is_internal_tag: bool = False, provider = None):
        """
        Stage a change for one or more files, pending a call to commit_changes().

        Args:
            media_files: List of MediaFile objects to apply the change to
            tag: The tag name (generic or internal)
            value: The new value for the tag
            is_internal_tag: Whether the tag is an internal tag name
            provider: The provider instance for internal tags (required if is_internal_tag=True)
        """

        # do not try to call self.commit_changes() in here; that should be handled by the caller.
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

    def _save_changes_impl(self):
        """
        Core save logic that can be used by both synchronous and asynchronous operations.
        """
        log.debug("Starting save operation...")
        saved_file_ids = []
        errors = []
        try:
            with self._write_lock:
                total_files = len(self._staged_changes)
                if total_files == 0:
                    return saved_file_ids, errors

                for file_id, changes in self._staged_changes.items():
                    media_file = self._media_files.get(file_id)
                    if media_file:
                        try:
                            log.debug(f"Saving changes for {media_file.file_path}")
                            media_file.save(changes)
                            saved_file_ids.append(file_id)
                        except Exception as e:
                            log.error(f"Error saving file {media_file.file_path}: {e}")
                            errors.append(f"{media_file.file_path}: {e}")

                self._staged_changes.clear()
                self.staged_changes_exist.emit(False)

        except Exception as e:
            log.error(f"An unexpected error occurred in save: {e}")
            errors.append(f"An unexpected error occurred: {e}")

        return saved_file_ids, errors

    @Slot()
    def _save_changes(self):
        """
        Saves staged changes to files. This method is designed to be run in a separate thread.
        """
        saved_file_ids, errors = self._save_changes_impl()

        if errors:
            self.commit_failed.emit(errors)
        else:
            self.commit_finished.emit(saved_file_ids)

        self._commit_thread.quit()

    def commit_changes(self, autosave_override=False):
        """
        Commit all staged changes to the files by running the save operation in a background thread.
        """

        if not self.autosave and not autosave_override:
            log.debug("Autosave is disabled, skipping commit.")
            return

        log.debug("Saving changes in a background thread...")

        if hasattr(self, '_commit_thread') and self._commit_thread and not self._commit_thread.isFinished() and self._commit_thread.isRunning():
            log.warning("Commit is already in progress.")
            return
        
        if not self.has_staged_changes():
            self.staged_changes_exist.emit(False)
            return

        self._commit_thread = QThread()
        worker = QObject()
        worker.moveToThread(self._commit_thread)
        self._commit_thread.started.connect(self._save_changes)
        self.commit_finished.connect(self._commit_thread.quit)
        self.commit_failed.connect(self._commit_thread.quit)
        self._commit_thread.finished.connect(worker.deleteLater)
        self._commit_thread.finished.connect(self._commit_thread.deleteLater)

        self.commit_started.emit()
        self._commit_thread.start()

    def commit_changes_sync(self):
        """
        Commit all staged changes to the files synchronously. Used by the CLI to bypass the background thread.
        """
        saved_file_ids, errors = self._save_changes_impl()
        return saved_file_ids, errors

    def reset_changes(self):
        """
        Reset all staged changes.
        """
        with self._write_lock:
            self._staged_changes.clear()
            self.staged_changes_exist.emit(False)

    def has_staged_changes(self) -> bool:
        """
        Check if there are any staged changes.
        """
        result = False
        for file_changes in self._staged_changes.values():
            if file_changes[KEY_TAG_GENERIC] or file_changes[KEY_TAG_INTERNAL]:
                result = True
                break
        log.debug(f"has_staged_changes returning: {result}")
        return result


    def get_staged_value_for_file(self, media_file: MediaFile, tag: str, is_internal_tag: bool = False) -> Optional[Any]:
        return self.get_staged_value(media_file.file_id, tag, is_internal_tag)

    def get_staged_value(self, file_id: int, tag: str, is_internal_tag: bool = False) -> Optional[Any]:
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



    def get_staged_changes_for_file(self, media_file: MediaFile) -> Dict[str, Dict]:
        """
        Get all staged changes for a specific file.

        Args:
            media_file: The MediaFile object to get changes for

        Returns:
            Dictionary with KEY_TAG_GENERIC and KEY_TAG_INTERNAL keys
        """
        return self.get_staged_changes(media_file.file_id)

    def get_staged_changes(self, file_id: int):
        return self._staged_changes.get(file_id, {KEY_TAG_GENERIC: {}, KEY_TAG_INTERNAL: {}})

    def get_media_file(self, file_id) -> Optional[MediaFile]:
        to_ret = self._media_files.get(file_id)
        if to_ret is None:
            log.warning(f"Media file with id {file_id} not found.")
        return to_ret
