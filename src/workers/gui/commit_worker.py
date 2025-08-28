from PySide6.QtCore import QObject, Slot, Signal
from models.edit_manager import EditManager
from util.logging import log


class CommitWorkerSignals(QObject):
    """
    Defines the signals available from a running commit worker thread.
    """
    commit_finished = Signal(list, list)  # (saved_files, errors)


class CommitWorker(QObject):
    """
    Worker for committing changes to files in a separate thread.
    """
    def __init__(self, edit_manager: EditManager):
        super().__init__()
        self.edit_manager = edit_manager
        self.signals = CommitWorkerSignals()

    @Slot(dict)
    def commit_changes(self, commit_data: dict):
        log.debug("CommitWorker.commit_changes() called")
        """
        Slot to receive commit data and save changes to files.
        """
        log.debug("CommitWorker: Received commit_requested signal.")
        saved_media_files = []
        errors = []
        with self.edit_manager._write_lock:
            for file_id, changes in commit_data.items():
                media_file = self.edit_manager._media_files.get(file_id)
                if media_file:
                    try:
                        log.debug(f"Saving changes for {media_file.file_path}")
                        media_file.save(changes)
                        saved_media_files.append(media_file)
                    except Exception as e:
                        log.error(f"Error saving file {media_file.file_path}: {e}")
                        errors.append({
                            'file_path': media_file.file_path,
                            'changes': changes,
                            'error': str(e)
                        })

        self.signals.commit_finished.emit(saved_media_files, errors)
