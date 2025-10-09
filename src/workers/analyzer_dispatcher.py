"""
Analyzer dispatcher for managing queue and execution of analysis tasks.

This module provides a singleton dispatcher that manages a queue of analysis
tasks, executes them in worker threads, and emits Qt signals for progress updates.
"""

from typing import List, Type, Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, Slot

from models.media_file import MediaFile
from providers.analysis.base import AnalyzerBase, AnalyzerResult
from providers.audio.base import AudioStreamBase
from util.const import KEY_TAG_GENERIC
from util.logging import log


class AnalysisTask:
    """
    Represents a single file analysis task.

    Attributes:
        analyzer_class: The analyzer class to instantiate
        media_file: The MediaFile instance to analyze
        options: Dictionary of analyzer options
        result: The AnalyzerResult after execution (None before execution)
    """

    def __init__(self, analyzer_class: Type[AnalyzerBase], media_file: MediaFile,
                 options: Optional[Dict[str, Any]] = None):
        """
        Initialize an analysis task.

        Args:
            analyzer_class: The analyzer class to use
            media_file: The MediaFile to analyze
            options: Dictionary of analyzer options (e.g., {'overwrite_existing': True})
        """
        self.analyzer_class = analyzer_class
        self.media_file = media_file
        self.options = options or {}
        self.result: Optional[AnalyzerResult] = None
        self.analyzer_instance: Optional[AnalyzerBase] = None


class AnalyzerWorker(QRunnable):
    """
    Worker runnable for executing an analyzer in a thread pool.

    This runnable executes a single analysis task and emits signals
    upon completion or error.
    """

    def __init__(self, task: AnalysisTask, signals: QObject):
        """
        Initialize the worker.

        Args:
            task: The AnalysisTask to execute
            signals: Signal object for emitting completion signals
        """
        super().__init__()
        self.task = task
        self.signals = signals

    @Slot()
    def run(self):
        """Execute the analysis task."""
        try:
            # Create the analyzer instance with options
            analyzer = self.task.analyzer_class(self.task.media_file, self.task.options)
            self.task.analyzer_instance = analyzer

            log.debug(f"Starting analysis: {analyzer.name} on {self.task.media_file.file_path}")

            # Execute the analysis
            # Analyzers get audio stream from media_file.get_audio_stream() if needed
            result = analyzer.analyze()
            self.task.result = result

            log.debug(f"Analysis complete: {analyzer.name} on {self.task.media_file.file_path} - "
                     f"Success: {result.success}, Skipped: {result.skipped}")

        except Exception as e:
            log.error(f"Analysis failed with exception: {e}", exc_info=True)
            self.task.result = AnalyzerResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

        # Emit completion signal
        self.signals.worker_finished.emit(self.task)


class WorkerSignals(QObject):
    """
    Signals emitted by analyzer workers.

    These signals are used to communicate from worker threads back to the
    main thread in a thread-safe manner.
    """
    worker_finished = Signal(object)  # Emits AnalysisTask when worker completes


class AnalyzerDispatcher(QObject):
    """
    Singleton dispatcher for managing analyzer queue and execution.

    The dispatcher maintains a queue of analysis tasks and executes them
    using a Qt thread pool. It emits signals to update UI components about
    progress and completion.

    Signals:
        analysis_started: Emitted when queue processing begins
        analysis_completed: Emitted when queue is empty and all tasks complete
        task_started: Emitted when a task begins (file_path, analyzer_name)
        task_completed: Emitted when a task finishes (file_path, result)
        progress_updated: Emitted on progress change (completed_count, total_count)
    """

    # Signals
    analysis_started = Signal()
    analysis_completed = Signal()
    task_started = Signal(str, str)  # (file_path, analyzer_name)
    task_completed = Signal(str, object)  # (file_path, AnalyzerResult)
    progress_updated = Signal(int, int)  # (completed_count, total_count)

    _instance = None

    def __new__(cls):
        """Singleton pattern: ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the dispatcher (only once due to singleton)."""
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return

        super().__init__()
        self._initialized = True

        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(1)  # Sequential initially

        self.queue: List[AnalysisTask] = []
        self.completed_tasks: List[AnalysisTask] = []
        self.current_task: Optional[AnalysisTask] = None
        self._is_running = False
        self._active_workers = 0

        # Worker signals for thread-safe communication
        self.worker_signals = WorkerSignals()
        self.worker_signals.worker_finished.connect(self._on_worker_finished)

    def enqueue(self, analyzer_class: Type[AnalyzerBase],
                media_files: List[MediaFile],
                options: Optional[Dict[str, Any]] = None) -> None:
        """
        Add analysis tasks to the queue.

        Args:
            analyzer_class: The analyzer class to use
            media_files: List of MediaFile instances to analyze
            options: Dictionary of analyzer options (e.g., {'overwrite_existing': True})
        """
        options = options or {}

        for mf in media_files:
            # Validate the file first
            is_valid, reason = analyzer_class.validate_file(mf)
            if not is_valid:
                log.info(f"Skipping {mf.file_path}: {reason}")
                # Create a pre-failed task for reporting
                task = AnalysisTask(analyzer_class, mf, options)
                task.result = AnalyzerResult(success=True, skipped=True, error=reason)
                self.completed_tasks.append(task)
            else:
                task = AnalysisTask(analyzer_class, mf, options)
                self.queue.append(task)

        log.info(f"Enqueued {len(media_files)} tasks for {analyzer_class.name}")

    def start(self) -> None:
        """Begin processing the queue."""
        if self._is_running:
            log.warning("Dispatcher already running, ignoring start request")
            return

        if len(self.queue) == 0:
            log.info("Queue is empty, nothing to process")
            return

        self._is_running = True
        self.analysis_started.emit()
        log.info(f"Starting analysis of {len(self.queue)} tasks")

        # Emit initial progress
        self.progress_updated.emit(len(self.completed_tasks),
                                   len(self.completed_tasks) + len(self.queue))

        # Start processing tasks
        self._process_next()

    def cancel_all(self) -> None:
        """Cancel all pending and current tasks."""
        log.info("Canceling all analysis tasks")

        # Clear the queue
        cancelled_count = len(self.queue)
        self.queue.clear()

        # Signal current analyzer to cancel
        if self.current_task and self.current_task.analyzer_instance:
            self.current_task.analyzer_instance.cancel()

        log.info(f"Cancelled {cancelled_count} pending tasks")
        self._is_running = False

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of completed analysis run.

        Returns:
            Dictionary with:
            - total: total number of tasks
            - successful: count of successful analyses
            - failed: list of (file_path, error) tuples
            - skipped: list of (file_path, reason) tuples
        """
        total = len(self.completed_tasks)
        successful = 0
        failed = []
        skipped = []

        for task in self.completed_tasks:
            if task.result:
                if task.result.skipped:
                    skipped.append((task.media_file.file_path, task.result.error))
                elif task.result.success:
                    successful += 1
                else:
                    failed.append((task.media_file.file_path, task.result.error))

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'skipped': skipped
        }

    def reset(self) -> None:
        """Reset the dispatcher state (for testing or new analysis runs)."""
        self.queue.clear()
        self.completed_tasks.clear()
        self.current_task = None
        self._is_running = False
        self._active_workers = 0

    def _process_next(self) -> None:
        """Process the next task in the queue."""
        # Check if we should continue
        if not self._is_running or len(self.queue) == 0:
            if self._active_workers == 0:
                self._finish_processing()
            return

        # Get next task
        task = self.queue.pop(0)
        self.current_task = task

        # Emit task started signal
        self.task_started.emit(
            task.media_file.file_path,
            task.analyzer_class.name
        )

        # Create and start worker
        worker = AnalyzerWorker(task, self.worker_signals)
        self._active_workers += 1
        self.thread_pool.start(worker)

    @Slot(object)
    def _on_worker_finished(self, task: AnalysisTask) -> None:
        """
        Handle completion of a worker task.

        Args:
            task: The completed AnalysisTask
        """
        self._active_workers -= 1

        # Apply results to MediaFile if successful
        self._apply_results(task)

        # Move task to completed list
        self.completed_tasks.append(task)

        # Emit task completed signal
        self.task_completed.emit(task.media_file.file_path, task.result)

        # Update progress
        completed = len(self.completed_tasks)
        total = completed + len(self.queue)
        self.progress_updated.emit(completed, total)

        # Process next task
        self._process_next()

    def _apply_results(self, task: AnalysisTask) -> None:
        """
        Apply analyzer results to MediaFile and handle autosave.

        Args:
            task: The completed AnalysisTask
        """
        if not task.result:
            return

        if task.result.success and not task.result.skipped and task.result.data:
            try:
                # Build changes dictionary using KEY_TAG_GENERIC
                changes = {
                    KEY_TAG_GENERIC: task.result.data
                }

                # Save to MediaFile (autosave will handle persistence if enabled)
                task.media_file.save(changes)

                log.info(f"Applied analysis results to {task.media_file.file_path}: {task.result.data}")

            except Exception as e:
                log.error(f"Failed to apply results for {task.media_file.file_path}: {e}")
                # Update the result to reflect the save failure
                task.result = AnalyzerResult(
                    success=False,
                    error=f"Failed to save results: {str(e)}"
                )

    def _finish_processing(self) -> None:
        """Complete the analysis run and emit completion signal."""
        self._is_running = False
        self.current_task = None

        summary = self.get_summary()
        log.info(f"Analysis complete: {summary['successful']}/{summary['total']} successful, "
                f"{len(summary['failed'])} failed, {len(summary['skipped'])} skipped")

        self.analysis_completed.emit()
