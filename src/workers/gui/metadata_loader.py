import time
from PySide6.QtCore import QRunnable, QObject, Signal
from models.media_file import MediaFile


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal()
    progress = Signal(int)
    result = Signal(object)


class MetadataLoader(QRunnable):
    """
    Worker thread for processing metadata.
    """
    def __init__(self, files):
        super().__init__()
        self.files = files
        self.signals = WorkerSignals()

    def run(self):
        """
        Reads metadata and emits progress.
        """
        total_files = len(self.files)
        for i, file_path in enumerate(self.files):
            progress_percentage = int(((i + 1) / total_files) * 100)
            self.signals.progress.emit(progress_percentage)
            try:
                media_file = MediaFile(file_path)
                metadata = {
                    "file_path": file_path,
                    "title": media_file.title,
                    "artist": media_file.artist,
                    "album": media_file.album,
                    "genre": media_file.genre,
                    "bpm": media_file.bpm,
                    "key": media_file.key,
                }
                self.signals.result.emit(metadata)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        self.signals.finished.emit()