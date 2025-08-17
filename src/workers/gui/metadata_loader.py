import time
from PySide6.QtCore import QRunnable, QObject, Signal

from const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY
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
                    "title": media_file.get_tag_simple(KEY_TITLE),
                    "artist": media_file.get_tag_simple(KEY_ARTIST),
                    "album": media_file.get_tag_simple(KEY_ALBUM),
                    "genre": media_file.get_tag_simple(KEY_GENRE),
                    "bpm": media_file.get_tag_simple(KEY_BPM),
                    "key": media_file.get_tag_simple(KEY_MUSICAL_KEY),
                }
                self.signals.result.emit(metadata)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        self.signals.finished.emit()