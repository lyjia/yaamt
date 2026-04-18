"""
Rename dispatcher for renaming media files based on a format string.

The dispatcher is intentionally shaped like AnalyzerDispatcher so the existing
AnalyzerProgressDialog and AnalyzerSummaryDialog can consume it by duck typing.
Unlike the analyzer dispatcher, renames are quick filesystem operations, so
this runs tasks serially in a single QRunnable via the global thread pool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool

from models.media_file import MediaFile
from util.const import (
    RENAME_COLLISION_AUTO_DISAMBIGUATE,
    RENAME_COLLISION_OVERWRITE,
    RENAME_COLLISION_SKIP,
)
from util.logging import log
from util.rename_formatter import (
    FormatParseError,
    build_token_map,
    format_filename,
    sanitize_filename,
)


# Label shown in the progress dialog's per-file list. Mirrors an analyzer name.
RENAME_TASK_LABEL = "Rename"

# Safety cap for auto-disambiguation iteration.
_MAX_DISAMBIG_SUFFIX = 999


@dataclass
class RenameResult:
    """Outcome of a single rename task."""

    success: bool = False
    skipped: bool = False
    error: str = ""
    new_path: str = ""


@dataclass
class RenameTask:
    """A single file-rename task."""

    media_file: MediaFile
    target_basename: str  # without extension, may be empty if rendering failed
    extension: str
    collision_mode: str
    # Populated at planning time so within-batch collisions can be resolved up
    # front and surfaced in the preview.
    target_path: str = ""
    result: RenameResult | None = None


@dataclass
class RenameSummary:
    """Summary of a completed rename batch - matches AnalyzerDispatcher's shape."""

    total: int = 0
    successful: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": list(self.failed),
            "skipped": list(self.skipped),
        }


class _RenameWorkerSignals(QObject):
    """Internal cross-thread signal bus."""

    worker_finished = Signal(int, object)  # (worker_id, RenameTask)


class _RenameWorker(QRunnable):
    """Runs a single rename operation in a worker thread."""

    def __init__(self, task: RenameTask, signals: _RenameWorkerSignals, worker_id: int):
        super().__init__()
        self.task = task
        self.signals = signals
        self.worker_id = worker_id

    @Slot()
    def run(self) -> None:
        try:
            source = self.task.media_file.file_path
            destination = self.task.target_path

            if not destination:
                self.task.result = RenameResult(
                    success=False,
                    error="Rendered filename is empty after sanitization",
                )
            elif os.path.abspath(source) == os.path.abspath(destination):
                # No-op: new name matches current. Treat as a skip so the
                # summary tells the user nothing changed.
                self.task.result = RenameResult(
                    success=True,
                    skipped=True,
                    error="Source and target filenames are identical",
                    new_path=destination,
                )
            else:
                final_dest = self._resolve_destination(source, destination)
                if final_dest is None:
                    # Skip mode with an existing target.
                    self.task.result = RenameResult(
                        success=False,
                        error=f"Target file already exists: "
                              f"{os.path.basename(destination)}",
                    )
                else:
                    if self.task.collision_mode == RENAME_COLLISION_OVERWRITE:
                        os.replace(source, final_dest)
                    else:
                        os.rename(source, final_dest)
                    # Update the MediaFile's cached path so the UI can reflect it.
                    self.task.media_file._file_path = final_dest
                    self.task.result = RenameResult(
                        success=True, new_path=final_dest
                    )
                    log.info(f"Renamed {source} -> {final_dest}")

        except Exception as e:
            log.error(f"Rename failed for {self.task.media_file.file_path}: {e}",
                      exc_info=True)
            self.task.result = RenameResult(
                success=False, error=f"Unexpected error: {e}"
            )

        self.signals.worker_finished.emit(self.worker_id, self.task)

    def _resolve_destination(self, source: str, destination: str) -> str | None:
        """
        Apply the task's collision policy against on-disk state.

        Returns the final destination path to use, or None if the task should
        be treated as a failure (skip mode with existing target).
        """
        mode = self.task.collision_mode
        if not os.path.exists(destination):
            return destination

        if mode == RENAME_COLLISION_OVERWRITE:
            return destination
        if mode == RENAME_COLLISION_SKIP:
            return None
        # Auto-disambiguate: append " (2)", " (3)", ... before the extension.
        base, ext = os.path.splitext(destination)
        for n in range(2, _MAX_DISAMBIG_SUFFIX + 1):
            candidate = f"{base} ({n}){ext}"
            if not os.path.exists(candidate):
                return candidate
        return None


def plan_rename(
    media_file: MediaFile, format_string: str, collision_mode: str
) -> RenameTask:
    """
    Build a RenameTask for a single file, computing the intended target basename.

    The returned task has .target_path populated (joined with the original
    directory and the original extension). On render failure, target_basename
    and target_path are left empty; the worker will mark the task failed.
    """
    source = media_file.file_path
    directory = os.path.dirname(source)
    extension = os.path.splitext(source)[1]
    try:
        tokens = build_token_map(media_file)
        rendered = format_filename(format_string, tokens)
    except FormatParseError as e:
        log.warning(f"Format parse error for {source}: {e}")
        return RenameTask(
            media_file=media_file,
            target_basename="",
            extension=extension,
            collision_mode=collision_mode,
            target_path="",
        )

    basename = sanitize_filename(rendered)
    if not basename:
        return RenameTask(
            media_file=media_file,
            target_basename="",
            extension=extension,
            collision_mode=collision_mode,
            target_path="",
        )

    target_path = os.path.join(directory, basename + extension)
    return RenameTask(
        media_file=media_file,
        target_basename=basename,
        extension=extension,
        collision_mode=collision_mode,
        target_path=target_path,
    )


def resolve_within_batch_collisions(tasks: list[RenameTask]) -> None:
    """
    When multiple tasks in a batch target the same path, adjust them in-place
    according to each task's collision mode.

    - Auto-disambiguate: append " (2)", " (3)" suffixes so all targets are unique.
    - Skip: mark later duplicates with a preset failing result.
    - Overwrite: leave as-is (last write wins at run time).
    """
    # Group by target_path for tasks that have a non-empty target.
    seen: dict[str, list[RenameTask]] = {}
    for task in tasks:
        if not task.target_path:
            continue
        seen.setdefault(os.path.abspath(task.target_path).lower(), []).append(task)

    for _, bucket in seen.items():
        if len(bucket) <= 1:
            continue
        mode = bucket[0].collision_mode
        if mode == RENAME_COLLISION_AUTO_DISAMBIGUATE:
            # First task keeps the original; subsequent get " (2)", " (3)", ...
            for i, task in enumerate(bucket[1:], start=2):
                base, ext = os.path.splitext(task.target_path)
                task.target_path = f"{base} ({i}){ext}"
                task.target_basename = f"{task.target_basename} ({i})"
        elif mode == RENAME_COLLISION_SKIP:
            for task in bucket[1:]:
                task.result = RenameResult(
                    success=False,
                    error=(f"Another file in this batch also targets "
                           f"'{os.path.basename(task.target_path)}'"),
                )


class RenameDispatcher(QObject):
    """
    Queue + runner for a batch of file-rename operations.

    Exposes the same signals and get_summary() shape as AnalyzerDispatcher so
    the analyzer progress/summary dialogs can drive it directly.
    """

    # Signal names intentionally mirror AnalyzerDispatcher's so the dialogs
    # can connect to either without branching. "analysis_*" is a misnomer
    # for renames but consolidates the dialog's signal-connection code.
    analysis_started = Signal()
    analysis_completed = Signal()
    task_started = Signal(str, str)  # (file_path, RENAME_TASK_LABEL)
    task_completed = Signal(str, object)  # (file_path, RenameResult)
    progress_updated = Signal(int, int)  # (completed, total)
    active_tasks_updated = Signal(list)  # [(file_path, label)]

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.queue: list[RenameTask] = []
        self.completed_tasks: list[RenameTask] = []
        self._is_running = False
        self._active_workers = 0
        self._next_worker_id = 0
        self._cancelled = False

        # Background threads emit through these signals so result application
        # happens on the main thread.
        self._signals = _RenameWorkerSignals()
        self._signals.worker_finished.connect(self._on_worker_finished)

        self._thread_pool = QThreadPool.globalInstance()

    # -- public API ---------------------------------------------------------

    def enqueue(
        self,
        media_files: list[MediaFile],
        format_string: str,
        collision_mode: str,
    ) -> None:
        """
        Plan a rename for each media file and enqueue the resulting tasks.

        Tasks whose rendering fails (parse error, empty sanitized result) are
        pre-marked as failures and skipped over at run time.
        """
        tasks = [plan_rename(mf, format_string, collision_mode) for mf in media_files]
        resolve_within_batch_collisions(tasks)

        for task in tasks:
            if task.result is not None:
                # Already failed during planning; surface in summary.
                self.completed_tasks.append(task)
            elif not task.target_path:
                task.result = RenameResult(
                    success=False,
                    error="Format string rendered to an empty/invalid filename",
                )
                self.completed_tasks.append(task)
            else:
                self.queue.append(task)

        log.info(f"Rename dispatcher enqueued {len(self.queue)} runnable tasks, "
                 f"{len(self.completed_tasks)} pre-failed")

    def start(self) -> None:
        """Begin processing the queue."""
        if self._is_running:
            log.warning("Rename dispatcher already running")
            return
        if not self.queue and not self.completed_tasks:
            log.info("Rename dispatcher has nothing to do")
            return

        self._is_running = True
        self._cancelled = False
        self.analysis_started.emit()

        total = len(self.queue) + len(self.completed_tasks)
        self.progress_updated.emit(len(self.completed_tasks), total)

        if not self.queue:
            # Everything pre-failed; nothing to run.
            self._finish()
            return

        self._process_next()

    def cancel_all(self) -> None:
        """Drain remaining queued tasks; in-flight tasks complete naturally."""
        log.info("Rename dispatcher cancelling remaining tasks")
        self._cancelled = True
        cancelled = self.queue
        self.queue = []
        for task in cancelled:
            task.result = RenameResult(
                success=False, skipped=True, error="Cancelled by user"
            )
            self.completed_tasks.append(task)
        if self._active_workers == 0:
            self._finish()

    def get_summary(self) -> dict[str, Any]:
        """Return a summary dict matching AnalyzerDispatcher.get_summary()."""
        summary = RenameSummary()
        summary.total = len(self.completed_tasks)
        for task in self.completed_tasks:
            if task.result is None:
                continue
            path = task.media_file.file_path
            if task.result.skipped:
                summary.skipped.append((path, task.result.error))
            elif task.result.success:
                summary.successful += 1
            else:
                summary.failed.append((path, task.result.error))
        return summary.as_dict()

    # -- internals ----------------------------------------------------------

    def _process_next(self) -> None:
        """Launch the next queued task. Serial: only one worker at a time."""
        if not self._is_running:
            return
        if self._cancelled or not self.queue:
            if self._active_workers == 0:
                self._finish()
            return

        task = self.queue.pop(0)
        worker_id = self._next_worker_id
        self._next_worker_id += 1
        self._active_workers += 1

        self.task_started.emit(task.media_file.file_path, RENAME_TASK_LABEL)
        self.active_tasks_updated.emit(
            [(task.media_file.file_path, RENAME_TASK_LABEL)]
        )

        worker = _RenameWorker(task, self._signals, worker_id)
        self._thread_pool.start(worker)

    @Slot(int, object)
    def _on_worker_finished(self, worker_id: int, task: RenameTask) -> None:
        self._active_workers -= 1
        if task.result is None:
            task.result = RenameResult(
                success=False, error="Worker returned without a result"
            )
        self.completed_tasks.append(task)

        self.task_completed.emit(task.media_file.file_path, task.result)
        total = len(self.queue) + len(self.completed_tasks)
        self.progress_updated.emit(len(self.completed_tasks), total)
        self.active_tasks_updated.emit([])

        self._process_next()

    def _finish(self) -> None:
        self._is_running = False
        self.analysis_completed.emit()
