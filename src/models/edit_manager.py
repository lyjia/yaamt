import threading
import copy

from PySide6.QtCore import QObject, Signal, QThread
from typing import Dict, List, Any, Optional
from models.media_file import MediaFile
from models.tag_info import TagInfo
from util.const import KEY_TAG_GENERIC, KEY_TAG_INTERNAL, KEY_VALUE, KEY_PROVIDER
from util.logging import log


class _CommitWorker(QObject):
    """
    Worker for committing changes to files in a separate thread.
    """
    commit_progress = Signal(int, int)
    commit_finished = Signal(list)
    commit_failed = Signal(list)

    def __init__(self, edit_manager: 'EditManager', commit_data: dict):
        super().__init__()
        self.edit_manager = edit_manager
        self.commit_data = commit_data

    def run(self):
        """
        Slot to receive commit data and save changes to files.
        """
        log.debug(f"CommitWorker: Saving {len(self.commit_data.keys())} files...")
        saved_file_paths = []
        errors = []
        total_files = len(self.commit_data)
        try:
            with self.edit_manager._write_lock:
                for i, (file_id, changes) in enumerate(self.commit_data.items()):
                    media_file = self.edit_manager._media_files.get(file_id)
                    if media_file:
                        try:
                            log.debug(f"Saving changes for {media_file.file_path}")
                            media_file.save(changes)
                            saved_file_paths.append(media_file.file_path)
                        except Exception as e:
                            log.error(f"Error saving file {media_file.file_path}: {e}")
                            errors.append(f"{media_file.file_path}: {e}")
                    self.commit_progress.emit(i + 1, total_files)

            if errors:
                self.commit_failed.emit(errors)
            else:
                self.commit_finished.emit(saved_file_paths)
        except Exception as e:
            log.error(f"An unexpected error occurred in CommitWorker: {e}")
            self.commit_failed.emit([f"An unexpected error occurred: {e}"])


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
    commit_finished = Signal(list)  # Signal emitted when commit is successful, with list of file ids
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
        self._autosave = False
        self._commit_thread = None
        self._commit_worker = None
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
        Stage a change for one or more files.

        Args:
            media_files: List of MediaFile objects to apply the change to
            tag: The tag name (generic or internal)
            value: The new value for the tag
            is_internal_tag: Whether the tag is an internal tag name
            provider: The provider instance for internal tags (required if is_internal_tag=True)
        """
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

    def _save_changes(self, commit_data: dict):
        """
        Saves the changes to the files in a background thread.
        """
        self._commit_thread = QThread()
        self._commit_worker = _CommitWorker(self, commit_data)
        self._commit_worker.moveToThread(self._commit_thread)

        self._commit_worker.commit_progress.connect(self.commit_progress)
        self._commit_worker.commit_finished.connect(self.commit_finished)
        self._commit_worker.commit_failed.connect(self.commit_failed)
        self._commit_thread.started.connect(self._commit_worker.run)
        self._commit_worker.commit_finished.connect(self._commit_thread.quit)
        self._commit_worker.commit_failed.connect(self._commit_thread.quit)
        self._commit_thread.finished.connect(self._commit_worker.deleteLater)
        self._commit_thread.finished.connect(self._commit_thread.deleteLater)

        self.commit_started.emit()
        self._commit_thread.start()

    def commit_changes(self):
        """
        Commit all staged changes to the files by running the save operation in a background thread.
        """
        with self._write_lock:
            if not self.has_staged_changes():
                self.staged_changes_exist.emit(False)
                return

            # Prepare commit data with provider context
            commit_data = {}
            for file_id, changes in self._staged_changes.items():
                media_file = self._media_files.get(file_id)
                if not media_file:
                    continue

                commit_data[str(media_file.file_id)] = {
                    KEY_TAG_GENERIC: changes[KEY_TAG_GENERIC].copy(),
                    KEY_TAG_INTERNAL: {}
                }

                # Process internal tags with provider context
                for internal_tag, tag_data in changes[KEY_TAG_INTERNAL].items():
                    commit_data[str(media_file.file_id)][KEY_TAG_INTERNAL][internal_tag] = {
                        KEY_VALUE: tag_data[KEY_VALUE],
                        KEY_PROVIDER: tag_data[KEY_PROVIDER]
                    }
        
        self._save_changes(copy.deepcopy(commit_data))

        # Clear staged changes after starting the commit
        self.reset_changes()



    def reset_changes(self):
        """
        Reset all staged changes.
        """
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

    def emit_commit_successful(self, media_files: List[MediaFile]):
        """
        Emit the commit_successful signal with the list of successfully updated file ids.

        Args:
            media_files: List of MediaFile objects that were successfully updated
        """
        self.commit_successful.emit([media_file.file_id for media_file in media_files])

    def get_staged_value(self, media_file: MediaFile, tag: str, is_internal_tag: bool = False) -> Optional[Any]:
        """
        Get the staged value for a specific tag in a file.

        Args:
            media_file: The MediaFile object to check
            tag: The tag name to look for
            is_internal_tag: Whether the tag is an internal tag name

        Returns:
            The staged value if found, None otherwise
        """
        file_id = media_file.file_id
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
        return self._staged_changes.get(media_file.file_id, {KEY_TAG_GENERIC: {}, KEY_TAG_INTERNAL: {}})
