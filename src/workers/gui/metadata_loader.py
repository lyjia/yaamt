import os
import traceback
from PySide6.QtCore import QRunnable, QObject, Signal

from util.const import KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY, KEY_FILE_PATH, \
    KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_SIZE_HUMAN, KEY_FILE_MTIME_HUMAN, KEY_FILE_CTIME, KEY_FILE_ATIME
from models.media_file import MediaFile
from util.display import human_readable_size, human_readable_timestamp


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
                mf_size = os.path.getsize(file_path)
                mf_mtime = os.path.getmtime(file_path)
                mf_ctime = os.path.getctime(file_path)
                mf_atime = os.path.getatime(file_path)

                metadata = {
                    # fs attributes
                    KEY_FILE_PATH: file_path,
                    KEY_FILE_SIZE: mf_size,
                    KEY_FILE_MTIME: mf_mtime,
                    KEY_FILE_CTIME: mf_ctime,
                    KEY_FILE_ATIME: mf_atime,

                    # tag attributes
                    KEY_TITLE: media_file.get_tag_simple(KEY_TITLE),
                    KEY_ARTIST: media_file.get_tag_simple(KEY_ARTIST),
                    KEY_ALBUM: media_file.get_tag_simple(KEY_ALBUM),
                    KEY_GENRE: media_file.get_tag_simple(KEY_GENRE),
                    KEY_BPM: media_file.get_tag_simple(KEY_BPM),
                    KEY_MUSICAL_KEY: media_file.get_tag_simple(KEY_MUSICAL_KEY),
                }
                self.signals.result.emit(metadata)
            except Exception as e:
                traceback.print_exc()
                print(f"{e.__class__.__name__} processing {file_path}: {e}")

        self.signals.finished.emit()