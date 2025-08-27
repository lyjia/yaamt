import threading

from PySide6.QtCore import QObject, Signal
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
    commit_requested = Signal(dict)  # Signal with provider context for committing changes
    commit_successful = Signal(list)  # Signal emitted when commit is successful, with list of file ids
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

    def commit_changes(self):
        """
        Commit all staged changes to the files by emitting the commit_requested signal
        with provider context for each change.
        """
        with self._write_lock:
            if not self.has_staged_changes():
                # Emit signal with empty data to indicate commit operation completed
                self.commit_requested.emit({})
                # Emit staged_changes_exist signal to indicate no changes exist
                self.staged_changes_exist.emit(False)
                return

            # Prepare commit data with provider context
            commit_data = {}
            for file_id, changes in self._staged_changes.items():
                media_file = self._media_files.get(file_id)
                if not media_file:
                    continue # Or handle error

                commit_data[str(media_file.file_id)] = {
                    KEY_TAG_GENERIC: changes[KEY_TAG_GENERIC].copy(), #TODO: is .copy() necessary?
                    KEY_TAG_INTERNAL: {}
                }

                # Process internal tags with provider context
                for internal_tag, tag_data in changes[KEY_TAG_INTERNAL].items():
                    commit_data[str(media_file.file_id)][KEY_TAG_INTERNAL][internal_tag] = {
                        KEY_VALUE: tag_data[KEY_VALUE],
                        KEY_PROVIDER: tag_data[KEY_PROVIDER]
                    }

        # Emit signal with the commit data
        self.commit_requested.emit(commit_data.copy()) #TODO: is .copy() necessary?

        # Clear staged changes after emitting signal
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
