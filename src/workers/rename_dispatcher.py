"""
Rename dispatcher for renaming media files based on a format string.

The dispatcher is intentionally shaped like AnalyzerDispatcher so the existing
AnalyzerProgressDialog and AnalyzerSummaryDialog can consume it by duck typing.
Unlike the analyzer dispatcher, renames are quick filesystem operations, so
this runs tasks serially in a single QRunnable via the global thread pool.
"""

from __future__ import annotations

import errno
import os
import sys
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
            else:
                self.task.result = perform_rename(
                    source,
                    destination,
                    self.task.collision_mode,
                    disambig_base=self.task.disambig_base,
                )
                if self.task.result.success and not self.task.result.skipped:
                    log.info(f"Renamed {source} -> {self.task.result.new_path}")

        except Exception as e:
            log.error(f"Rename failed for {self.task.media_file.file_path}: {e}",
                      exc_info=True)
            self.task.result = RenameResult(
                success=False, error=f"Unexpected error: {e}"
            )

        self.signals.worker_finished.emit(self.worker_id, self.task)


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
    # Staging ops park a cycle member at a temporary name so the rest of the
    # cycle can proceed; they carry no task result of their own.
    is_staging: bool = False
    cycle_id: int = -1
    staging_error: str = ""


@dataclass
class BatchPlan:
    """
    Execution plan for a rename batch, computed against virtual filesystem
    state before anything touches the disk.

    Tasks are ordered so that a rename onto another task's source only runs
    after that source has been vacated; swap/rotation cycles are broken by
    staging one member at a temporary name. Tasks that can never succeed
    (target held by a batch file that is not moving) are pre-failed here.
    """

    ops: list[RenameOp] = field(default_factory=list)
    tasks: list[RenameTask] = field(default_factory=list)
    planned_target_keys: set[str] = field(default_factory=set)
    # Direct dependents by task index: dependents[j] lists tasks whose target
    # is task j's source, i.e. tasks that must be cancelled if j fails.
    dependents: dict[int, list[int]] = field(default_factory=dict)
    # cycle_id -> (temp_path, original_source) for restoring a staged file
    # when the rest of its cycle fails.
    cycle_stages: dict[int, tuple[str, str]] = field(default_factory=dict)
    case_insensitive: bool = False
    _index_by_task: dict[int, int] = field(default_factory=dict)

    def transitive_dependents(self, task: RenameTask) -> list[RenameTask]:
        """All tasks that directly or indirectly require this task's rename."""
        start = self._index_by_task.get(id(task))
        if start is None:
            return []
        out: list[RenameTask] = []
        pending = list(self.dependents.get(start, []))
        seen: set[int] = set()
        while pending:
            i = pending.pop()
            if i in seen:
                continue
            seen.add(i)
            out.append(self.tasks[i])
            pending.extend(self.dependents.get(i, []))
        return out

    def cycle_tasks(self, cycle_id: int) -> list[RenameTask]:
        """Tasks participating in the given staged cycle."""
        return [op.task for op in self.ops
                if op.cycle_id == cycle_id and not op.is_staging]


def _fail_task(task: RenameTask, error: str) -> None:
    task.result = RenameResult(success=False, error=error)


def _prerequisite_error(prerequisite: RenameTask) -> str:
    source = (prerequisite.media_file.file_path
              if prerequisite.media_file else prerequisite.target_path)
    return (f"Not renamed: prerequisite rename of "
            f"'{os.path.basename(source)}' did not complete")


def _make_staging_path(
    directory: str, extension: str, cycle_id: int,
    avoid_keys: set[str], case_insensitive: bool,
) -> str:
    """Pick a temporary name in directory that nothing on disk or in the
    batch is using."""
    for n in range(_MAX_DISAMBIG_SUFFIX + 1):
        name = f".yaamt-rename-{os.getpid()}-{cycle_id}-{n}{extension}"
        candidate = os.path.join(directory, name)
        key = canonical_path_key(candidate, case_insensitive)
        if key in avoid_keys or os.path.lexists(candidate):
            continue
        return candidate
    raise RuntimeError(f"No available staging name in {directory}")


def plan_batch(
    tasks: list[RenameTask], case_insensitive: bool | None = None
) -> BatchPlan:
    """
    Order a batch of rename tasks so no rename can destroy another task's
    source, and emit the resulting operation list.

    Run after resolve_within_batch_collisions. Dependency rule: task A must
    run after task B when A's target is B's source. Chains are ordered
    topologically; cycles (swaps/rotations) are broken by staging one member
    at a temporary name first and completing it last. A task whose target is
    the source of a batch file that will never move (pre-failed, no-op, or
    the batch was cancelled at planning) is pre-failed with a clear error
    instead of clobbering, suffixing, or spuriously reporting a collision.
    """
    if case_insensitive is None:
        case_insensitive = default_case_insensitive()
    plan = BatchPlan(tasks=list(tasks), case_insensitive=case_insensitive)
    plan._index_by_task = {id(t): i for i, t in enumerate(tasks)}

    def source_key(task: RenameTask) -> str | None:
        if task.media_file is None:
            return None
        return canonical_path_key(task.media_file.file_path, case_insensitive)

    def target_key(task: RenameTask) -> str:
        return canonical_path_key(task.target_path, case_insensitive)

    runnable = [i for i, t in enumerate(tasks)
                if t.target_path and t.result is None]
    plan.planned_target_keys = {target_key(tasks[i]) for i in runnable}

    # Partition batch sources into ones that will vacate their name (movers)
    # and ones that keep it (pre-failed tasks, no-ops, case-only renames).
    movers: dict[str, int] = {}
    holders: dict[str, int] = {}
    runnable_set = set(runnable)
    for i, task in enumerate(tasks):
        skey = source_key(task)
        if skey is None:
            continue
        if i in runnable_set and target_key(task) != skey:
            movers[skey] = i
        else:
            holders[skey] = i

    # Each runnable task depends on at most one other (source keys are
    # unique), so the graph is disjoint chains and simple cycles.
    dep: dict[int, int] = {}
    failed: set[int] = set()
    for i in runnable:
        tkey = target_key(tasks[i])
        if tkey in movers and movers[tkey] != i:
            dep[i] = movers[tkey]
        elif tkey in holders and holders[tkey] != i:
            _fail_task(tasks[i],
                       f"Target name '{os.path.basename(tasks[i].target_path)}'"
                       f" is kept by another file in this batch")
            failed.add(i)

    for i, j in dep.items():
        plan.dependents.setdefault(j, []).append(i)

    # Tasks depending on a plan-time failure can never succeed either.
    changed = True
    while changed:
        changed = False
        for i, j in dep.items():
            if j in failed and i not in failed:
                _fail_task(tasks[i], _prerequisite_error(tasks[j]))
                failed.add(i)
                changed = True

    active = [i for i in runnable if i not in failed]
    active_set = set(active)

    def emit_ready(emitted: set[int]) -> None:
        """Emit ops for every active task whose dependency is satisfied,
        in stable index order, until no progress is made."""
        progress = True
        while progress:
            progress = False
            for i in active:
                if i in emitted:
                    continue
                j = dep.get(i)
                if j is not None and j in active_set and j not in emitted:
                    continue
                task = tasks[i]
                plan.ops.append(RenameOp(
                    task=task, source=task.media_file.file_path,
                    dest=task.target_path,
                ))
                emitted.add(i)
                progress = True

    emitted: set[int] = set()
    emit_ready(emitted)

    # Whatever is left sits on a cycle (or hangs off one). Break each cycle
    # by staging its lowest-index member, then let the ready sweep finish.
    next_cycle_id = 0
    while len(emitted) < len(active):
        walk = next(i for i in active if i not in emitted)
        seen_order: list[int] = []
        seen_set: set[int] = set()
        while walk not in seen_set:
            seen_order.append(walk)
            seen_set.add(walk)
            walk = dep[walk]
        # walk is now the first repeated node: the cycle starts there.
        cycle = seen_order[seen_order.index(walk):]

        cycle_id = next_cycle_id
        next_cycle_id += 1
        staged_index = min(cycle)
        staged = tasks[staged_index]
        avoid = plan.planned_target_keys | set(movers) | set(holders)
        temp_path = _make_staging_path(
            os.path.dirname(staged.media_file.file_path), staged.extension,
            cycle_id, avoid, case_insensitive,
        )
        plan.cycle_stages[cycle_id] = (temp_path,
                                       staged.media_file.file_path)
        plan.ops.append(RenameOp(
            task=staged, source=staged.media_file.file_path, dest=temp_path,
            is_staging=True, cycle_id=cycle_id,
        ))

        # With the staged member's name vacated, the rest of the cycle is a
        # chain: follow reverse-dependency order from the staged member.
        reverse_dep = {dep[i]: i for i in cycle}
        current = reverse_dep[staged_index]
        while current != staged_index:
            task = tasks[current]
            plan.ops.append(RenameOp(
                task=task, source=task.media_file.file_path,
                dest=task.target_path, cycle_id=cycle_id,
            ))
            emitted.add(current)
            current = reverse_dep[current]
        plan.ops.append(RenameOp(
            task=staged, source=temp_path, dest=staged.target_path,
            cycle_id=cycle_id,
        ))
        emitted.add(staged_index)

        # Tasks hanging off this cycle are now unblocked.
        emit_ready(emitted)

    return plan


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

        # Repoint the MediaFile at its new location here, on the main thread,
        # rather than mutating it from the worker thread.
        if (task.result.success and not task.result.skipped
                and task.result.new_path):
            task.media_file.update_file_path(task.result.new_path)

        self.task_completed.emit(task.media_file.file_path, task.result)
        total = len(self.queue) + len(self.completed_tasks)
        self.progress_updated.emit(len(self.completed_tasks), total)
        self.active_tasks_updated.emit([])

        self._process_next()

    def _finish(self) -> None:
        self._is_running = False
        self.analysis_completed.emit()
