from PySide6.QtCore import QObject, Slot, Signal
from models.edit_manager import EditManager
from util.logging import log


class CommitWorkerSignals(QObject):
    """
    Defines the signals available from a running commit worker thread.
    """
    commit_successful = Signal(list)  # List of modified file paths
    commit_failed = Signal(str)       # Error message


class CommitWorker(QObject):
    """
    Worker for committing changes to files in a separate thread.
    """
    def __init__(self, edit_manager: EditManager):
        super().__init__()
        self.edit_manager = edit_manager
        self.signals = CommitWorkerSignals()

    @Slot(dict)
    def run(self, commit_data: dict):
        """
        Slot to receive commit data and save changes to files.
        """
        log.debug("CommitWorker: Received commit_requested signal.")
        saved_file_paths = []
        errors = []
        try:
            with self.edit_manager._write_lock:
                for file_id, changes in commit_data.items():
                    media_file = self.edit_manager._media_files.get(file_id)
                    if media_file:
                        try:
                            log.debug(f"Saving changes for {media_file.file_path}")
                            media_file.save(changes)
                            saved_file_paths.append(media_file.file_path)
                        except Exception as e:
                            log.error(f"Error saving file {media_file.file_path}: {e}")
                            errors.append(f"{media_file.file_path}: {e}")

            if errors:
                self.signals.commit_failed.emit("\n".join(errors))
            else:
                self.signals.commit_successful.emit(saved_file_paths)
        except Exception as e:
            log.error(f"An unexpected error occurred in CommitWorker: {e}")
            self.signals.commit_failed.emit(f"An unexpected error occurred: {e}")
