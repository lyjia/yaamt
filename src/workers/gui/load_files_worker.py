import os
import traceback
from threading import Lock
from PySide6.QtCore import QRunnable, QObject, Signal

from models.media_file import MediaFile
from models.qt.metadata_model import MetadataTableModel
from util.logging import log
from util.const import (
    KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_CTIME,
    KEY_FILE_TYPE, KEY_IS_MEDIA, KEY_FILE_ID, KEY_TITLE
)


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal()
    progress = Signal(int)
    result = Signal(object)

    # New signals for two-stage loading
    files_discovered = Signal(list)  # Emitted during Stage 1 with list of basic file data
    file_updated = Signal(int, dict)  # Emitted during Stage 2 with row index and metadata
    discovery_finished = Signal(int)  # Emitted when Stage 1 completes with total file count
    enrichment_progress = Signal(int, int)  # Emitted during Stage 2 with (current, total)


class LoadFilesWorker(QRunnable):
    """
    Worker thread for processing metadata in two stages:
    Stage 1: Fast discovery of files using os.scandir
    Stage 2: Enrichment with full metadata
    """
    def __init__(self, directory_path):
        super().__init__()
        self.directory_path = directory_path
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._priority_lock = Lock()
        self._priority_range = (0, 100)  # Start and end indices for viewport
        self._discovered_files = []  # List of file paths discovered in Stage 1
        self.DISCOVERY_BATCH_SIZE = 100  # Batch size for Stage 1 emissions

    def run(self):
        """
        Two-stage file loading process.
        """
        try:
            # Stage 1: Discovery
            if not self._run_discovery():
                return

            # Stage 2: Enrichment
            self._run_enrichment()

        except Exception as e:
            log.error(f"LoadFilesWorker error: {e}")
            traceback.print_exc()
        finally:
            self.signals.finished.emit()

    def _run_discovery(self) -> bool:
        """
        Stage 1: Fast file discovery using os.scandir.
        Returns False if cancelled, True otherwise.
        """
        log.debug(f"Stage 1: Discovery started for {self.directory_path}")
        batch = []

        try:
            with os.scandir(self.directory_path) as entries:
                for entry in entries:
                    if self._is_cancelled:
                        log.debug("LoadFilesWorker cancelled during discovery")
                        return False

                    # Only process files, not directories
                    if not entry.is_file():
                        continue

                    # Get basic filesystem info
                    try:
                        stat_info = entry.stat()
                        file_path = entry.path
                        self._discovered_files.append(file_path)

                        # Create basic file data dictionary
                        basic_data = {
                            KEY_FILE_PATH: file_path,
                            KEY_FILE_SIZE: stat_info.st_size,
                            KEY_FILE_MTIME: stat_info.st_mtime,
                            KEY_FILE_CTIME: stat_info.st_ctime,
                            KEY_FILE_TYPE: os.path.splitext(file_path)[1].lstrip('.').upper(),
                            KEY_IS_MEDIA: None,  # Unknown until Stage 2
                            KEY_FILE_ID: None,  # Will be set in Stage 2
                            KEY_TITLE: "Loading...",  # Placeholder
                        }

                        batch.append(basic_data)

                        # Emit batch when it reaches the batch size
                        if len(batch) >= self.DISCOVERY_BATCH_SIZE:
                            self.signals.files_discovered.emit(batch)
                            batch = []

                    except OSError as e:
                        log.debug(f"Error reading file stats for {entry.path}: {e}")
                        continue

            # Emit remaining files in the batch
            if batch:
                self.signals.files_discovered.emit(batch)

            # Emit discovery finished signal with total count
            total_files = len(self._discovered_files)
            self.signals.discovery_finished.emit(total_files)
            log.debug(f"Stage 1: Discovery finished. Found {total_files} files")
            return True

        except Exception as e:
            log.error(f"Error during discovery: {e}")
            traceback.print_exc()
            return False

    def _run_enrichment(self):
        """
        Stage 2: Enrich files with full metadata.
        Prioritizes files in the viewport.
        """
        log.debug("Stage 2: Enrichment started")
        total_files = len(self._discovered_files)

        if total_files == 0:
            return

        # Build a list of indices to process, with priority for viewport
        indices_to_process = self._get_prioritized_indices()

        for processed_count, file_index in enumerate(indices_to_process):
            if self._is_cancelled:
                log.debug(f"LoadFilesWorker cancelled during enrichment after {processed_count}/{total_files} files")
                return

            file_path = self._discovered_files[file_index]

            try:
                # Load full metadata
                media_file = MediaFile(file_path)
                metadata = MetadataTableModel.get_metadata_from_media_file(media_file)

                # Emit update for this specific row
                self.signals.file_updated.emit(file_index, metadata)

            except Exception as e:
                log.debug(f"{e.__class__.__name__} processing {file_path}: {e}")
                # Even on error, emit an update to clear "Loading..." placeholder
                error_data = {
                    KEY_FILE_PATH: file_path,
                    KEY_IS_MEDIA: False,
                    KEY_TITLE: "Error loading file",
                }
                self.signals.file_updated.emit(file_index, error_data)

            # Emit enrichment progress
            self.signals.enrichment_progress.emit(processed_count + 1, total_files)

        log.debug(f"Stage 2: Enrichment finished. Processed {total_files} files")

    def _get_prioritized_indices(self) -> list:
        """
        Get a list of file indices to process, with viewport files prioritized.
        Returns a list of indices in processing order.
        """
        total_files = len(self._discovered_files)
        if total_files == 0:
            return []

        with self._priority_lock:
            start, end = self._priority_range

        # Clamp to valid range
        start = max(0, min(start, total_files - 1))
        end = max(0, min(end, total_files))

        # Build priority list: viewport files first, then the rest
        priority_indices = list(range(start, end))
        remaining_indices = [i for i in range(total_files) if i < start or i >= end]

        return priority_indices + remaining_indices

    def set_priority_range(self, start: int, end: int):
        """
        Update the priority range for viewport-aware loading.

        Args:
            start: Starting row index of visible range
            end: Ending row index of visible range
        """
        with self._priority_lock:
            self._priority_range = (start, end)
        log.debug(f"Priority range updated to: {start}-{end}")

    def cancel(self):
        """
        Request cancellation of the worker.
        This sets a flag that is checked in the run loop.
        """
        self._is_cancelled = True
        log.debug("LoadFilesWorker cancellation requested.")
