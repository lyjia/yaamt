"""
Rename dispatcher for renaming media files based on a format string.

The dispatcher is intentionally shaped like AnalyzerDispatcher so the existing
AnalyzerProgressDialog and AnalyzerSummaryDialog can consume it by duck typing.
Unlike the analyzer dispatcher, renames are quick filesystem operations, so
this runs tasks serially, one worker at a time, via the global thread pool.

Safety model: a batch is fully planned before anything touches the disk.
Renames never leave their directory, so the batch splits into independent
per-directory chunks. Within each chunk, every file whose current name is
another task's new name is first staged at a temporary name (pass 1), then
all renames are committed (pass 2). With contested names vacated up front, no
rename can overwrite another task's still-pending source - chains and swaps
need no special ordering. If a staging rename fails, the chunk is rolled back
and aborted; if a committing rename fails, its staged file is moved back to
its original name once the chunk finishes (or, when that name has been taken,
the temporary location is reported so the file is never lost track of).
"""

from __future__ import annotations

import errno
import os
import sys
from dataclasses import dataclass, field
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

# Prefix for temporary staging names. Descriptive on purpose: if the process
# dies mid-batch, ".yaamt-rename-<originalname>" is recoverable by hand.
_STAGING_NAME_PREFIX = ".yaamt-rename-"


def default_case_insensitive() -> bool:
    """
    Best-effort guess whether filesystem paths are case-insensitive.

    A platform heuristic, not ground truth (macOS can run case-sensitive APFS;
    Linux can mount FAT/SMB). The execution-time same-file guard and
    non-clobbering renames are the safety net when the guess is wrong.
    """
    return os.name == "nt" or sys.platform == "darwin"


def canonical_path_key(path: str, case_insensitive: bool) -> str:
    """Canonical key for comparing paths within a rename batch."""
    key = os.path.abspath(path)
    return key.casefold() if case_insensitive else key


@dataclass
class RenameResult:
    """Outcome of a single rename task."""

    success: bool = False
    skipped: bool = False
    error: str = ""
    # The file's actual current path whenever it moved - even on failure
    # (e.g. a file left at a staging name after its cycle partner failed).
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
    # Basename before any auto-disambiguation suffix was applied, so run-time
    # retries can continue the "(n)" numbering instead of nesting suffixes.
    disambig_base: str = ""
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


# Errnos meaning "this filesystem cannot hardlink" - fall back to a checked
# rename instead of failing the task. ENOTSUP is missing on some platforms.
_HARDLINK_FALLBACK_ERRNOS = frozenset(
    e for e in (
        errno.EPERM,
        errno.EACCES,
        errno.ENOSYS,
        errno.EMLINK,
        errno.EOPNOTSUPP,
        getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
    )
)


def _rename_no_clobber(source: str, destination: str) -> None:
    """
    Rename source to destination, refusing to overwrite an existing file.

    Raises FileExistsError when the destination is occupied (including a
    dangling symlink). On Windows, os.rename already refuses to clobber. On
    POSIX, os.rename silently replaces the destination, so the move is done
    as hardlink + unlink, which fails atomically with EEXIST when the
    destination appears - closing the check-then-rename race. Filesystems
    without hardlink support fall back to a checked rename (small race
    window, best effort).
    """
    if os.name == "nt":
        os.rename(source, destination)
        return

    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError:
        raise
    except (NotImplementedError, OSError) as e:
        if isinstance(e, OSError) and e.errno not in _HARDLINK_FALLBACK_ERRNOS:
            raise
        if os.path.lexists(destination):
            raise FileExistsError(
                errno.EEXIST, "Destination already exists", destination
            )
        os.rename(source, destination)
        return

    try:
        os.unlink(source)
    except OSError:
        # Undo the link so the file does not end up with two names.
        try:
            os.unlink(destination)
        except OSError:
            pass
        raise


def _is_case_only_rename(
    source: str, destination: str, case_insensitive: bool
) -> bool:
    """
    True when destination is the same file as source under a different case.

    samefile alone is not enough: on some network shares st_ino is 0 (false
    positives), and a pre-existing hardlink of the source is samefile without
    being a case variant. Requiring canonical-key equality restricts the fast
    path to genuine case-only renames.
    """
    if canonical_path_key(source, case_insensitive) != canonical_path_key(
        destination, case_insensitive
    ):
        return False
    try:
        return os.path.samefile(source, destination)
    except OSError:
        return False


def _auto_disambig_candidates(destination: str, disambig_base: str):
    """Yield destination, then " (2)", " (3)", ... variants of its base name."""
    yield destination
    directory = os.path.dirname(destination)
    ext = os.path.splitext(destination)[1]
    if disambig_base:
        base = os.path.join(directory, disambig_base)
    else:
        base = os.path.splitext(destination)[0]
    for n in range(2, _MAX_DISAMBIG_SUFFIX + 1):
        candidate = f"{base} ({n}){ext}"
        if candidate != destination:
            yield candidate


def perform_rename(
    source: str,
    destination: str,
    collision_mode: str,
    disambig_base: str = "",
    planned_target_keys: set[str] | None = None,
    case_insensitive: bool | None = None,
) -> RenameResult:
    """
    Execute a single rename against on-disk state and return its result.

    Pure filesystem logic - no Qt, no MediaFile mutation - so it is directly
    testable. planned_target_keys are canonical keys reserved by other tasks
    in the batch; auto-disambiguation retries never take one of those names.
    """
    if planned_target_keys is None:
        planned_target_keys = set()
    if case_insensitive is None:
        case_insensitive = default_case_insensitive()

    if os.path.abspath(source) == os.path.abspath(destination):
        # Exact no-op: report as a skip so the summary says nothing changed.
        return RenameResult(
            success=True,
            skipped=True,
            error="Source and target filenames are identical",
            new_path=destination,
        )

    occupied = os.path.lexists(destination)
    if occupied and _is_case_only_rename(source, destination, case_insensitive):
        # Same file under a different case: a plain rename re-cases it; this
        # must never be treated as a collision.
        os.rename(source, destination)
        return RenameResult(success=True, new_path=destination)

    if collision_mode == RENAME_COLLISION_OVERWRITE:
        # Deliberate clobber; batch planning guarantees the destination is
        # never another batch file's still-pending source.
        os.replace(source, destination)
        return RenameResult(success=True, new_path=destination)

    if collision_mode == RENAME_COLLISION_SKIP:
        already_exists = RenameResult(
            success=False,
            error=f"Target file already exists: {os.path.basename(destination)}",
        )
        if occupied:
            return already_exists
        try:
            _rename_no_clobber(source, destination)
        except FileExistsError:
            return already_exists
        return RenameResult(success=True, new_path=destination)

    # Auto-disambiguate: try the planned name, then " (n)" variants, never
    # taking a name another task in the batch has planned.
    for candidate in _auto_disambig_candidates(destination, disambig_base):
        if candidate != destination:
            key = canonical_path_key(candidate, case_insensitive)
            if key in planned_target_keys:
                continue
        if os.path.lexists(candidate):
            continue
        try:
            _rename_no_clobber(source, candidate)
        except FileExistsError:
            continue
        return RenameResult(success=True, new_path=candidate)

    return RenameResult(
        success=False,
        error=f"No available name found for: {os.path.basename(destination)}",
    )


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


def resolve_within_batch_collisions(
    tasks: list[RenameTask], case_insensitive: bool | None = None
) -> None:
    """
    When multiple tasks in a batch target the same path, adjust them in-place
    according to each task's collision mode.

    - Auto-disambiguate: append " (2)", " (3)" suffixes so all targets are unique.
    - Skip: mark later duplicates with a preset failing result.
    - Overwrite: leave as-is (last write wins at run time).

    Paths are compared case-insensitively only on platforms whose filesystems
    are, so distinct Foo.mp3/foo.mp3 targets on Linux are not false collisions.
    A task whose target is its own source under the canonical key (a no-op or
    a case-only rename) already owns that name and is never suffixed or
    skipped; competing tasks in its bucket are resolved against it.
    """
    if case_insensitive is None:
        case_insensitive = default_case_insensitive()

    # Group by canonical target key for tasks that have a non-empty target.
    seen: dict[str, list[RenameTask]] = {}
    for task in tasks:
        if not task.target_path:
            continue
        key = canonical_path_key(task.target_path, case_insensitive)
        seen.setdefault(key, []).append(task)

    for key, bucket in seen.items():
        if len(bucket) <= 1:
            continue
        # A task keeping its own name (case-only rename or no-op) wins the
        # name outright; move it to the front so it is the keeper.
        for pos, task in enumerate(bucket):
            if task.media_file is None:
                continue
            source_key = canonical_path_key(task.media_file.file_path,
                                            case_insensitive)
            if source_key == key:
                bucket.insert(0, bucket.pop(pos))
                break

        mode = bucket[0].collision_mode
        if mode == RENAME_COLLISION_AUTO_DISAMBIGUATE:
            # First task keeps the original; subsequent get " (2)", " (3)", ...
            suffix_n = 2
            for task in bucket[1:]:
                if task.result is not None:
                    continue  # Pre-failed tasks keep their rendered name.
                base, ext = os.path.splitext(task.target_path)
                task.disambig_base = task.target_basename
                task.target_path = f"{base} ({suffix_n}){ext}"
                task.target_basename = f"{task.target_basename} ({suffix_n})"
                suffix_n += 1
        elif mode == RENAME_COLLISION_SKIP:
            for task in bucket[1:]:
                if task.result is not None:
                    continue
                task.result = RenameResult(
                    success=False,
                    error=(f"Another file in this batch also targets "
                           f"'{os.path.basename(task.target_path)}'"),
                )


@dataclass
class RenameOp:
    """One filesystem operation in a planned batch, in execution order."""

    task: RenameTask
    source: str
    dest: str
    # Staging ops park a contested file at a temporary name so the rest of
    # its directory can proceed; they carry no task result of their own.
    is_staging: bool = False
    # Index of the per-directory chunk this op belongs to. Chunks are
    # independent: a failure in one never affects another.
    chunk_id: int = 0
    staging_error: str = ""


@dataclass
class BatchPlan:
    """
    Execution plan for a rename batch, computed before anything touches disk.

    Per directory: contested files (whose current name is another task's new
    name) are staged at temporary names first, then all renames commit. Tasks
    that can never succeed - target held by a batch file that is not moving -
    are pre-failed here with a clear error.
    """

    ops: list[RenameOp] = field(default_factory=list)
    tasks: list[RenameTask] = field(default_factory=list)
    planned_target_keys: set[str] = field(default_factory=set)
    # id(task) -> (temp_path, original_source) for contested files that get
    # staged out of the way in pass 1.
    stagings: dict[int, tuple[str, str]] = field(default_factory=dict)
    case_insensitive: bool = False
    _task_ids: set[int] = field(default_factory=set)


def _fail_task(task: RenameTask, error: str) -> None:
    task.result = RenameResult(success=False, error=error)


def _make_staging_path(
    source: str, avoid_keys: set[str], case_insensitive: bool
) -> str:
    """Pick a temporary name beside source that nothing on disk or in the
    batch is using."""
    directory, basename = os.path.split(source)
    candidate = os.path.join(directory, f"{_STAGING_NAME_PREFIX}{basename}")
    n = 1
    while (canonical_path_key(candidate, case_insensitive) in avoid_keys
           or os.path.lexists(candidate)):
        n += 1
        if n > _MAX_DISAMBIG_SUFFIX:
            raise RuntimeError(f"No available staging name for {source}")
        candidate = os.path.join(
            directory, f"{_STAGING_NAME_PREFIX}{n}-{basename}"
        )
    return candidate


def plan_batch(
    tasks: list[RenameTask], case_insensitive: bool | None = None
) -> BatchPlan:
    """
    Plan a batch so no rename can destroy another task's source.

    Run after resolve_within_batch_collisions. Targets always live in their
    source's directory (see plan_rename), so the batch splits into independent
    per-directory chunks. In each chunk, files whose current name is another
    task's target are staged at temporary names first; once those names are
    vacated, the commit pass cannot collide with any pending source, however
    the renames chain or swap. A task targeting the name of a batch file that
    will never move (pre-failed, no-op, or case-only rename) is pre-failed
    with a clear error instead of clobbering, suffixing, or spuriously
    reporting a collision.
    """
    if case_insensitive is None:
        case_insensitive = default_case_insensitive()
    plan = BatchPlan(tasks=list(tasks), case_insensitive=case_insensitive)
    plan._task_ids = {id(t) for t in tasks}

    def source_key(task: RenameTask) -> str | None:
        if task.media_file is None:
            return None
        return canonical_path_key(task.media_file.file_path, case_insensitive)

    def target_key(task: RenameTask) -> str:
        return canonical_path_key(task.target_path, case_insensitive)

    def runnable_tasks() -> list[RenameTask]:
        return [t for t in tasks if t.target_path and t.result is None]

    plan.planned_target_keys = {target_key(t) for t in runnable_tasks()}

    # Pre-fail tasks whose target is a batch source that never vacates (a
    # pre-failed task, a no-op, or a case-only rename all keep their name).
    # Loop to a fixpoint: each newly failed task now holds its own name too.
    changed = True
    while changed:
        changed = False
        runnable = runnable_tasks()
        runnable_ids = {id(t) for t in runnable}
        held: dict[str, RenameTask] = {}
        for task in tasks:
            skey = source_key(task)
            if skey is None:
                continue
            if id(task) not in runnable_ids or target_key(task) == skey:
                held[skey] = task
        for task in runnable:
            holder = held.get(target_key(task))
            if holder is not None and holder is not task:
                _fail_task(
                    task,
                    f"Target name '{os.path.basename(task.target_path)}' is "
                    f"kept by another file in this batch",
                )
                changed = True

    # Split into per-directory chunks, preserving first-appearance order.
    chunks: dict[str, list[RenameTask]] = {}
    for task in runnable_tasks():
        dir_key = canonical_path_key(
            os.path.dirname(task.media_file.file_path), case_insensitive
        )
        chunks.setdefault(dir_key, []).append(task)

    for chunk_id, chunk_tasks in enumerate(chunks.values()):
        # A file is contested when another task in the chunk targets its
        # current name; it must be staged out of the way before the commits.
        target_owner: dict[str, RenameTask] = {}
        for task in chunk_tasks:
            target_owner.setdefault(target_key(task), task)

        avoid = set(plan.planned_target_keys)
        avoid.update(k for k in (source_key(t) for t in chunk_tasks) if k)

        for task in chunk_tasks:
            skey = source_key(task)
            claimant = target_owner.get(skey) if skey else None
            if claimant is None or claimant is task:
                continue
            temp_path = _make_staging_path(
                task.media_file.file_path, avoid, case_insensitive
            )
            avoid.add(canonical_path_key(temp_path, case_insensitive))
            plan.stagings[id(task)] = (temp_path, task.media_file.file_path)
            plan.ops.append(RenameOp(
                task=task, source=task.media_file.file_path, dest=temp_path,
                is_staging=True, chunk_id=chunk_id,
            ))

        for task in chunk_tasks:
            staging = plan.stagings.get(id(task))
            source = staging[0] if staging else task.media_file.file_path
            plan.ops.append(RenameOp(
                task=task, source=source, dest=task.target_path,
                chunk_id=chunk_id,
            ))

    return plan


class _RenameWorkerSignals(QObject):
    """Internal cross-thread signal bus."""

    worker_finished = Signal(int, object)  # (worker_id, RenameOp)


class _RenameWorker(QRunnable):
    """Runs a single planned rename operation in a worker thread."""

    def __init__(
        self,
        op: RenameOp,
        planned_target_keys: set[str],
        case_insensitive: bool,
        signals: _RenameWorkerSignals,
        worker_id: int,
    ):
        super().__init__()
        self.op = op
        self.planned_target_keys = planned_target_keys
        self.case_insensitive = case_insensitive
        self.signals = signals
        self.worker_id = worker_id

    @Slot()
    def run(self) -> None:
        op = self.op
        task = op.task
        try:
            if op.is_staging:
                _rename_no_clobber(op.source, op.dest)
            else:
                task.result = perform_rename(
                    op.source,
                    op.dest,
                    task.collision_mode,
                    disambig_base=task.disambig_base,
                    planned_target_keys=self.planned_target_keys,
                    case_insensitive=self.case_insensitive,
                )
                if task.result.success and not task.result.skipped:
                    log.info(f"Renamed {op.source} -> {task.result.new_path}")

        except Exception as e:
            log.error(f"Rename failed for {op.source}: {e}", exc_info=True)
            if op.is_staging:
                op.staging_error = f"Unexpected error: {e}"
            else:
                task.result = RenameResult(
                    success=False, error=f"Unexpected error: {e}"
                )

        self.signals.worker_finished.emit(self.worker_id, op)


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

    def __init__(self, parent: QObject | None = None,
                 thread_pool: QThreadPool | None = None):
        super().__init__(parent)
        self.queue: list[RenameOp] = []
        self.completed_tasks: list[RenameTask] = []
        self._is_running = False
        self._active_workers = 0
        self._next_worker_id = 0
        self._cancelled = False
        self._plans: list[BatchPlan] = []
        self._total_tasks = 0
        self._next_chunk_offset = 0
        # id(task) for staging renames that completed, so a staged file can
        # be moved back if its committing rename never succeeds.
        self._completed_stagings: set[int] = set()
        # Failed staged tasks awaiting a restore attempt at their chunk's end
        # (restoring earlier could hand the name back to a file that another
        # pending rename in the chunk is about to take).
        self._pending_restores: list[tuple[BatchPlan, RenameTask]] = []

        # Background threads emit through these signals so result application
        # happens on the main thread.
        self._signals = _RenameWorkerSignals()
        self._signals.worker_finished.connect(self._on_worker_finished)

        self._thread_pool = thread_pool or QThreadPool.globalInstance()

    # -- public API ---------------------------------------------------------

    def enqueue(
        self,
        media_files: list[MediaFile],
        format_string: str,
        collision_mode: str,
    ) -> None:
        """Plan a rename for each media file and enqueue the planned operations."""
        self.enqueue_tasks(
            [plan_rename(mf, format_string, collision_mode) for mf in media_files]
        )

    def enqueue_tasks(self, tasks: list[RenameTask]) -> None:
        """
        Plan and enqueue pre-built rename tasks as one batch.

        The whole batch is planned before anything touches the disk: contested
        files are staged per directory so no rename can destroy another task's
        source, and tasks that cannot succeed (render failure, unavailable
        target) are pre-marked as failed.
        """
        # Exact no-ops are decided here so they never reach the disk and never
        # count as name collisions.
        for task in tasks:
            if (task.target_path and os.path.abspath(task.media_file.file_path)
                    == os.path.abspath(task.target_path)):
                task.result = RenameResult(
                    success=True,
                    skipped=True,
                    error="Source and target filenames are identical",
                    new_path=task.target_path,
                )

        case_insensitive = default_case_insensitive()
        resolve_within_batch_collisions(tasks, case_insensitive)
        plan = plan_batch(tasks, case_insensitive)

        # Make chunk ids unique across enqueue calls so queue filtering by
        # chunk is unambiguous.
        for op in plan.ops:
            op.chunk_id += self._next_chunk_offset
        if plan.ops:
            self._next_chunk_offset = plan.ops[-1].chunk_id + 1

        self._plans.append(plan)

        for task in tasks:
            if task.result is not None:
                # Resolved during planning; surface in summary.
                self.completed_tasks.append(task)
            elif not task.target_path:
                task.result = RenameResult(
                    success=False,
                    error="Format string rendered to an empty/invalid filename",
                )
                self.completed_tasks.append(task)

        self.queue.extend(plan.ops)
        self._total_tasks += len(tasks)

        log.info(f"Rename dispatcher enqueued {len(plan.ops)} operations, "
                 f"{len(self.completed_tasks)} tasks resolved at planning")

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

        self.progress_updated.emit(len(self.completed_tasks), self._total_tasks)

        if not self.queue:
            # Everything resolved at planning; nothing to run.
            self._finish()
            return

        self._process_next()

    def cancel_all(self) -> None:
        """Drain remaining queued operations; in-flight ops complete naturally."""
        log.info("Rename dispatcher cancelling remaining tasks")
        self._cancelled = True
        remaining = self.queue
        self.queue = []
        seen: set[int] = set()
        for op in remaining:
            task = op.task
            if id(task) in seen or task.result is not None:
                continue
            seen.add(id(task))
            task.result = RenameResult(
                success=False, skipped=True, error="Cancelled by user"
            )
            self.completed_tasks.append(task)

        # Put already-staged files back where they were (or report the
        # temporary location if their old name has been taken).
        pending, self._pending_restores = self._pending_restores, []
        for plan, task in pending:
            self._restore_staged(plan, task)
        for op in remaining:
            plan = self._plan_for_task(op.task)
            if plan is not None:
                self._restore_staged(plan, op.task)

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
        """Launch the next queued operation. Serial: only one worker at a time."""
        if not self._is_running:
            return
        if self._cancelled or not self.queue:
            if self._active_workers == 0:
                self._finish()
            return

        op = self.queue.pop(0)
        worker_id = self._next_worker_id
        self._next_worker_id += 1
        self._active_workers += 1

        if not op.is_staging:
            # Staging renames are internal plumbing; only a task's committing
            # rename is surfaced in the progress dialog.
            self.task_started.emit(op.task.media_file.file_path,
                                   RENAME_TASK_LABEL)
            self.active_tasks_updated.emit(
                [(op.task.media_file.file_path, RENAME_TASK_LABEL)]
            )

        plan = self._plan_for_task(op.task)
        planned_keys = plan.planned_target_keys if plan else set()
        case_insensitive = (plan.case_insensitive if plan
                            else default_case_insensitive())
        worker = _RenameWorker(op, planned_keys, case_insensitive,
                               self._signals, worker_id)
        self._thread_pool.start(worker)

    @Slot(int, object)
    def _on_worker_finished(self, worker_id: int, op: RenameOp) -> None:
        self._active_workers -= 1
        task = op.task
        plan = self._plan_for_task(task)

        if op.is_staging:
            if op.staging_error:
                self._abort_chunk(plan, op)
            else:
                self._completed_stagings.add(id(task))
            self._flush_restores_at_chunk_boundary(op)
            self._process_next()
            return

        if task.result is None:
            task.result = RenameResult(
                success=False, error="Worker returned without a result"
            )
        self.completed_tasks.append(task)

        # Repoint the MediaFile at its new location here, on the main thread,
        # rather than mutating it from the worker thread.
        if (task.result.success and not task.result.skipped
                and task.result.new_path):
            task.media_file.update_file_path(task.result.new_path)

        self.task_completed.emit(task.media_file.file_path, task.result)

        if (not task.result.success and plan is not None
                and id(task) in self._completed_stagings):
            # The file sits at its staging name; try to send it home once the
            # rest of its chunk has finished with the contested names.
            self._pending_restores.append((plan, task))

        self.progress_updated.emit(len(self.completed_tasks),
                                   self._total_tasks)
        self.active_tasks_updated.emit([])

        self._flush_restores_at_chunk_boundary(op)
        self._process_next()

    def _plan_for_task(self, task: RenameTask) -> BatchPlan | None:
        for plan in self._plans:
            if id(task) in plan._task_ids:
                return plan
        return None

    def _abort_chunk(self, plan: BatchPlan | None, staging_op: RenameOp) -> None:
        """
        A staging rename failed, so some contested name was never vacated and
        the chunk's commits can no longer be trusted not to collide. Nothing
        has committed yet (staging ops all precede commits within a chunk), so
        roll the chunk back: restore its staged files - their original names
        are still free - and fail all its tasks. Other chunks are unaffected.
        """
        chunk_id = staging_op.chunk_id
        removed = [o for o in self.queue if o.chunk_id == chunk_id]
        self.queue = [o for o in self.queue if o.chunk_id != chunk_id]
        chunk_tasks: list[RenameTask] = []
        seen_ids: set[int] = set()
        for task in [staging_op.task] + [o.task for o in removed]:
            if id(task) not in seen_ids:
                seen_ids.add(id(task))
                chunk_tasks.append(task)
        aborted_name = os.path.basename(staging_op.source)
        for task in chunk_tasks:
            if task.result is None:
                if task is staging_op.task:
                    _fail_task(task, staging_op.staging_error)
                else:
                    _fail_task(
                        task,
                        f"Not renamed: renames in this folder were aborted "
                        f"because '{aborted_name}' could not be staged",
                    )
            if plan is not None:
                self._restore_staged(plan, task)
            self.completed_tasks.append(task)
            self.task_completed.emit(task.media_file.file_path, task.result)
        self.progress_updated.emit(len(self.completed_tasks),
                                   self._total_tasks)

    def _restore_staged(self, plan: BatchPlan, task: RenameTask) -> None:
        """
        Move a staged file back to its original name. When that name has been
        taken (by a rename that already committed), report the temporary
        location instead so the file is never lost track of.
        """
        staging = plan.stagings.get(id(task))
        if staging is None or id(task) not in self._completed_stagings:
            return
        self._completed_stagings.discard(id(task))
        temp_path, original_source = staging
        try:
            _rename_no_clobber(temp_path, original_source)
        except OSError:
            if task.result is not None:
                task.result.error += (f"; file left at temporary name "
                                      f"'{os.path.basename(temp_path)}'")
                task.result.new_path = temp_path
            task.media_file.update_file_path(temp_path)
            log.error(f"Could not restore staged file {temp_path} "
                      f"to {original_source}")

    def _flush_restores_at_chunk_boundary(self, op: RenameOp) -> None:
        """Once a chunk's last op finishes, restore its failed staged files."""
        if self.queue and self.queue[0].chunk_id == op.chunk_id:
            return
        pending, self._pending_restores = self._pending_restores, []
        for plan, task in pending:
            self._restore_staged(plan, task)

    def _finish(self) -> None:
        self._is_running = False
        self.analysis_completed.emit()
