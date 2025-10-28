import traceback
from PySide6.QtCore import QRunnable, QObject, Signal

from models.media_file import MediaFile
from models.qt.metadata_model import MetadataTableModel
from util.logging import log


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal()
    progress = Signal(int)
    result = Signal(object)


class LoadFilesWorker(QRunnable):
    """
    Worker thread for processing metadata.
    """
    def __init__(self, files):
        super().__init__()
        self.files = files
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def run(self):
        """
        Reads metadata and emits progress.
        """
        total_files = len(self.files)
        for i, file_path in enumerate(self.files):
            # Check if cancelled before processing each file
            if self._is_cancelled:
                log.debug(f"LoadFilesWorker cancelled after processing {i}/{total_files} files")
                self.signals.finished.emit()
                return

            progress_percentage = int(((i + 1) / total_files) * 100)
            self.signals.progress.emit(progress_percentage)
            try:
                media_file = MediaFile(file_path)
                metadata = MetadataTableModel.get_metadata_from_media_file(media_file)
                self.signals.result.emit(metadata)
            except Exception as e:
                traceback.print_exc()
                log.debug(f"{e.__class__.__name__} processing {file_path}: {e}")

        self.signals.finished.emit()

    def cancel(self):
        """
        Request cancellation of the worker.
        This sets a flag that is checked in the run loop.
        """
        self._is_cancelled = True
        log.debug("LoadFilesWorker cancellation requested.")
