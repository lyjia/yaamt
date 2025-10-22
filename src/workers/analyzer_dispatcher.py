"""
Analyzer dispatcher for managing queue and execution of analysis tasks.

This module provides a singleton dispatcher that manages a queue of analysis
tasks, executes them in worker threads, and emits Qt signals for progress updates.
"""

from typing import List, Type, Optional, Dict, Any
import time
import concurrent.futures
import os
from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, Slot, QSettings

from models.media_file import MediaFile
from providers.analysis.base import AnalyzerBase, AnalyzerResult
from providers.audio.base import AudioStreamBase
from util.const import KEY_TAG_GENERIC, KEY_COMMENT, KEY_INITIAL_KEY, KEY_DIATONIC_MODE
from util.logging import log


# Global process pool executor (module-level to be shared across instances)
_process_pool_executor: Optional[concurrent.futures.ProcessPoolExecutor] = None


def _get_process_pool(max_workers: int) -> concurrent.futures.ProcessPoolExecutor:
    """
    Get or create the global process pool executor.

    Args:
        max_workers: Maximum number of worker processes

    Returns:
        ProcessPoolExecutor instance
    """
    global _process_pool_executor

    if _process_pool_executor is None or _process_pool_executor._max_workers != max_workers:
        # Shutdown existing pool if it exists
        if _process_pool_executor is not None:
            _process_pool_executor.shutdown(wait=False)

        # Create new pool with requested size
        _process_pool_executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_workers)
        log.info(f"Created process pool with {max_workers} workers")

    return _process_pool_executor


def _analyze_in_process(analyzer_class_name: str, file_path: str, options: Dict[str, Any]) -> AnalyzerResult:
    """
    Worker function that runs in a separate process to perform analysis.

    This function must be picklable, so it takes primitive types and reconstructs
    objects from module imports.

    Args:
        analyzer_class_name: Fully qualified name of analyzer class
        file_path: Path to the media file
        options: Analyzer options dictionary

    Returns:
        AnalyzerResult from the analysis
    """
    try:
        # Add src to path if needed (for subprocess)
        import sys
        from pathlib import Path

        # Find the src directory
        current_file = Path(__file__).resolve()
        src_dir = current_file.parent.parent

        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        # Import here to ensure each process has its own imports
        from providers import get_analyzer_by_name, discover_providers
        from models.media_file import MediaFile

        # Ensure providers are discovered in this process
        discover_providers()

        # Get the analyzer class by name
        analyzer_class = get_analyzer_by_name(analyzer_class_name)
        if analyzer_class is None:
            return AnalyzerResult(
                success=False,
                error=f"Analyzer class '{analyzer_class_name}' not found"
            )

        # Create MediaFile instance
        media_file = MediaFile(file_path)

        # Create analyzer and run analysis
        analyzer = analyzer_class(media_file, options)
        result = analyzer.analyze()

        return result

    except Exception as e:
        import traceback
        return AnalyzerResult(
            success=False,
            error=f"Process worker error: {str(e)}\n{traceback.format_exc()}"
        )


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

    def __init__(self, task: AnalysisTask, signals: QObject, worker_id: int):
        """
        Initialize the worker.

        Args:
            task: The AnalysisTask to execute
            signals: Signal object for emitting completion signals
            worker_id: Unique identifier for this worker
        """
        super().__init__()
        self.task = task
        self.signals = signals
        self.worker_id = worker_id

    @Slot()
    def run(self):
        """Execute the analysis task, using process pool for parallel execution or direct execution for single-threaded mode."""
        try:
            analyzer_name = self.task.analyzer_class.name
            file_path = self.task.media_file.file_path

            log.debug(f"Starting analysis: {analyzer_name} on {file_path}")

            # Check if we should use multiprocessing
            # For thread_pool_size=1, run directly in this thread (no process pool overhead)
            qsettings = QSettings("Lyjia", "Audio Metadata Tool")
            thread_pool_size = qsettings.value("Analyzers/thread_pool_size", 1, type=int)

            if thread_pool_size == 1:
                # Single-threaded mode: run directly without process pool
                log.debug(f"Running in single-threaded mode (no multiprocessing)")
                analyzer = self.task.analyzer_class(self.task.media_file, self.task.options)
                self.task.analyzer_instance = analyzer
                result = analyzer.analyze()
                self.task.result = result
            else:
                # Multi-threaded mode: use process pool for true parallelism
                log.debug(f"Running in multi-threaded mode with process pool")
                analyzer_class_name = self.task.analyzer_class.__name__

                # Submit to process pool and wait for result
                # Note: This blocks the thread, but releases the GIL, allowing other threads to run
                process_pool = _get_process_pool(os.cpu_count() or 4)

                future = process_pool.submit(
                    _analyze_in_process,
                    analyzer_class_name,
                    file_path,
                    self.task.options
                )

                # Wait for the result (this blocks but releases GIL)
                result = future.result()
                self.task.result = result

            log.debug(f"Analysis complete: {analyzer_name} on {file_path} - "
                     f"Success: {result.success}, Skipped: {result.skipped}")

        except Exception as e:
            log.error(f"Analysis failed with exception: {e}", exc_info=True)
            self.task.result = AnalyzerResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

        # Emit completion signal with worker ID
        self.signals.worker_finished.emit(self.worker_id, self.task)


class WorkerSignals(QObject):
    """
    Signals emitted by analyzer workers.

    These signals are used to communicate from worker threads back to the
    main thread in a thread-safe manner.
    """
    worker_finished = Signal(int, object)  # Emits (worker_id, AnalysisTask) when worker completes


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
    active_tasks_updated = Signal(list)  # List of (file_path, analyzer_name) tuples

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

        # Load thread pool size from settings
        qsettings = QSettings("Lyjia", "Audio Metadata Tool")
        self.thread_pool_size = qsettings.value("Analyzers/thread_pool_size", 1, type=int)

        self.thread_pool = QThreadPool.globalInstance()
        # Set thread pool max to accommodate the requested thread pool size
        # We need to ensure the Qt thread pool is large enough to hold all our concurrent tasks
        self.thread_pool.setMaxThreadCount(max(self.thread_pool_size, self.thread_pool.maxThreadCount()))

        log.info(f"Analyzer dispatcher initialized with thread_pool_size={self.thread_pool_size}, "
                f"Qt thread pool max={self.thread_pool.maxThreadCount()}")

        self.queue: List[AnalysisTask] = []
        self.completed_tasks: List[AnalysisTask] = []
        self.current_task: Optional[AnalysisTask] = None  # Deprecated, kept for compatibility
        self._is_running = False
        self._active_workers = 0
        self._batch_start_time: Optional[float] = None

        # New fields for parallel processing
        self.active_tasks: Dict[int, tuple[AnalysisTask, int]] = {}  # worker_id -> (task, thread_count)
        self.threads_in_use = 0
        self._next_worker_id = 0  # Counter for worker IDs

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

    def _reload_thread_pool_size(self) -> None:
        """
        Reload thread pool size from settings.

        Called at the start of each analysis run to pick up any changes
        the user made to the thread pool size setting.
        """
        qsettings = QSettings("Lyjia", "Audio Metadata Tool")
        new_thread_pool_size = qsettings.value("Analyzers/thread_pool_size", 1, type=int)

        if new_thread_pool_size != self.thread_pool_size:
            log.info(f"Thread pool size changed from {self.thread_pool_size} to {new_thread_pool_size}")
            self.thread_pool_size = new_thread_pool_size

            # Ensure Qt thread pool is large enough
            self.thread_pool.setMaxThreadCount(max(self.thread_pool_size, self.thread_pool.maxThreadCount()))

    def start(self) -> None:
        """Begin processing the queue."""
        if self._is_running:
            log.warning("Dispatcher already running, ignoring start request")
            return

        if len(self.queue) == 0:
            log.info("Queue is empty, nothing to process")
            return

        # Reload thread pool size from settings in case user changed it
        self._reload_thread_pool_size()

        self._is_running = True
        self._batch_start_time = time.perf_counter()
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
        self.active_tasks.clear()
        self.threads_in_use = 0
        self._next_worker_id = 0

    def _process_next(self) -> None:
        """Process the next task in the queue, starting multiple workers if possible."""
        # Check if we should continue
        if not self._is_running:
            if self._active_workers == 0:
                self._finish_processing()
            return

        # Try to fill all available thread slots
        while self.queue and self.threads_in_use < self.thread_pool_size:
            task = self.queue[0]

            # Get thread count needed for this analyzer
            threads_needed = task.analyzer_class.get_thread_count(task.options)

            # Check if we have enough threads available
            if self.threads_in_use + threads_needed <= self.thread_pool_size:
                # Remove task from queue
                self.queue.pop(0)

                # Generate unique worker ID
                worker_id = self._next_worker_id
                self._next_worker_id += 1

                # Track the task
                self.active_tasks[worker_id] = (task, threads_needed)
                self.threads_in_use += threads_needed
                self._active_workers += 1

                # For compatibility, set current_task to the most recent task
                self.current_task = task

                # Emit task started signal
                self.task_started.emit(
                    task.media_file.file_path,
                    task.analyzer_class.name
                )

                # Create and start worker
                worker = AnalyzerWorker(task, self.worker_signals, worker_id)
                self.thread_pool.start(worker)

                log.debug(f"Started worker {worker_id} for {task.media_file.file_path}, "
                         f"threads_in_use={self.threads_in_use}/{self.thread_pool_size}, "
                         f"active_workers={self._active_workers}, "
                         f"qt_active_threads={self.thread_pool.activeThreadCount()}")

                # Emit active tasks update
                self._emit_active_tasks()
            else:
                # Not enough threads available, wait for some to finish
                break

        # If no tasks are running and queue is empty, finish
        if self._active_workers == 0 and len(self.queue) == 0:
            self._finish_processing()

    def _emit_active_tasks(self) -> None:
        """Emit the list of currently active tasks."""
        active_list = [
            (task.media_file.file_path, task.analyzer_class.name)
            for task, _ in self.active_tasks.values()
        ]
        self.active_tasks_updated.emit(active_list)

    @Slot(int, object)
    def _on_worker_finished(self, worker_id: int, task: AnalysisTask) -> None:
        """
        Handle completion of a worker task.

        Args:
            worker_id: The ID of the worker that finished
            task: The completed AnalysisTask
        """
        self._active_workers -= 1

        # Release threads used by this worker
        if worker_id in self.active_tasks:
            _, thread_count = self.active_tasks[worker_id]
            self.threads_in_use -= thread_count
            del self.active_tasks[worker_id]

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

        # Emit updated active tasks list
        self._emit_active_tasks()

        # Process next task(s)
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
                # Handle special case: mode field from key analyzer
                # Mode should be appended to comments in format "Key: C (ionian)"
                result_data = task.result.data.copy()

                # Note: There isn't a standard way to store diatonic mode so we're just gonna put it in comments
                # if it exists
                if KEY_DIATONIC_MODE in result_data and KEY_INITIAL_KEY in result_data:
                    key_value = result_data[KEY_INITIAL_KEY]
                    mode_value = result_data.pop(KEY_DIATONIC_MODE)  # Remove mode from data

                    # Build the mode comment string
                    mode_comment = f"Key: {key_value} ({mode_value})"

                    # Get existing comments
                    existing_comments = task.media_file.get_tag_simple(KEY_COMMENT)

                    # Check if we already have a mode comment (to avoid duplicates)
                    if existing_comments:
                        # Replace existing "Key: ..." line or append
                        lines = existing_comments.split('\n')
                        updated = False
                        for i, line in enumerate(lines):
                            if line.startswith('Key:'):
                                lines[i] = mode_comment
                                updated = True
                                break

                        if updated:
                            result_data[KEY_COMMENT] = '\n'.join(lines)
                        else:
                            result_data[KEY_COMMENT] = f"{existing_comments}\n{mode_comment}"
                    else:
                        result_data[KEY_COMMENT] = mode_comment

                # Build changes dictionary using KEY_TAG_GENERIC
                changes = {
                    KEY_TAG_GENERIC: result_data
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

        # Calculate batch elapsed time
        batch_elapsed = 0.0
        if self._batch_start_time is not None:
            batch_elapsed = time.perf_counter() - self._batch_start_time

        summary = self.get_summary()
        log.info(f"Analysis complete: {summary['successful']}/{summary['total']} successful, "
                f"{len(summary['failed'])} failed, {len(summary['skipped'])} skipped "
                f"[total time: {batch_elapsed:.2f}s]")

        self.analysis_completed.emit()
