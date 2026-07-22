"""Tests for workers.rename_dispatcher."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from util.const import (
    IN_GITHUB_RUNNER,
    RENAME_COLLISION_AUTO_DISAMBIGUATE,
    RENAME_COLLISION_OVERWRITE,
    RENAME_COLLISION_SKIP,
)


FIXTURE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
    "metadata",
)


def _find_fixture_file() -> str:
    for entry in os.listdir(FIXTURE_ROOT):
        path = os.path.join(FIXTURE_ROOT, entry)
        if os.path.isfile(path) and entry.lower().endswith((".mp3", ".flac", ".wav")):
            return path
    raise RuntimeError(f"No audio fixture files under {FIXTURE_ROOT}")


@pytest.fixture
def tmp_audio_copy():
    """Copy a fixture audio file to a fresh temp dir and yield its path."""
    src = _find_fixture_file()
    tmp_dir = tempfile.mkdtemp(prefix="yaamt_rename_test_")
    dest = os.path.join(tmp_dir, os.path.basename(src))
    shutil.copy(src, dest)
    try:
        yield dest
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_plan_rename_produces_target_path(tmp_audio_copy):
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    mf = MediaFile(tmp_audio_copy)
    task = plan_rename(mf, "%ARTIST% - %TITLE%", RENAME_COLLISION_AUTO_DISAMBIGUATE)

    assert task.extension == os.path.splitext(tmp_audio_copy)[1]
    assert task.target_path.startswith(os.path.dirname(tmp_audio_copy))
    # Basename should end with the original extension.
    assert task.target_path.endswith(task.extension)


def test_plan_rename_empty_render_marks_task_unrunnable(tmp_audio_copy):
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    mf = MediaFile(tmp_audio_copy)
    task = plan_rename(mf, "<%NOPE%>", RENAME_COLLISION_SKIP)

    # Empty render -> empty basename, empty target path.
    assert task.target_basename == ""
    assert task.target_path == ""


def test_resolve_within_batch_collisions_auto_disambiguate():
    from workers.rename_dispatcher import (
        RenameTask, resolve_within_batch_collisions,
    )

    # Two tasks targeting the same path - second should get " (2)" suffix.
    t1 = RenameTask(
        media_file=None, target_basename="same", extension=".mp3",
        collision_mode=RENAME_COLLISION_AUTO_DISAMBIGUATE,
        target_path="/tmp/same.mp3",
    )
    t2 = RenameTask(
        media_file=None, target_basename="same", extension=".mp3",
        collision_mode=RENAME_COLLISION_AUTO_DISAMBIGUATE,
        target_path="/tmp/same.mp3",
    )
    resolve_within_batch_collisions([t1, t2])

    assert t1.target_path == "/tmp/same.mp3"
    assert t2.target_path == "/tmp/same (2).mp3"
    assert t2.target_basename == "same (2)"


def test_resolve_within_batch_collisions_skip_marks_later_failures():
    from workers.rename_dispatcher import (
        RenameTask, resolve_within_batch_collisions,
    )

    t1 = RenameTask(
        media_file=None, target_basename="same", extension=".mp3",
        collision_mode=RENAME_COLLISION_SKIP,
        target_path="/tmp/same.mp3",
    )
    t2 = RenameTask(
        media_file=None, target_basename="same", extension=".mp3",
        collision_mode=RENAME_COLLISION_SKIP,
        target_path="/tmp/same.mp3",
    )
    resolve_within_batch_collisions([t1, t2])

    assert t1.result is None
    assert t2.result is not None
    assert t2.result.success is False
    assert "Another file in this batch" in t2.result.error


def _bare_task(target_path, mode=RENAME_COLLISION_AUTO_DISAMBIGUATE,
               source_path=None):
    """Build a RenameTask for pure collision/planner tests."""
    import types
    from workers.rename_dispatcher import RenameTask

    media_file = (
        types.SimpleNamespace(file_path=source_path) if source_path else None
    )
    base = os.path.splitext(os.path.basename(target_path))[0]
    return RenameTask(
        media_file=media_file, target_basename=base,
        extension=os.path.splitext(target_path)[1],
        collision_mode=mode, target_path=target_path,
    )


def test_resolve_within_batch_case_sensitive_no_suffix():
    from workers.rename_dispatcher import resolve_within_batch_collisions

    # On a case-sensitive filesystem Foo.mp3 and foo.mp3 are distinct targets;
    # neither may be suffixed.
    t1 = _bare_task("/tmp/Foo.mp3")
    t2 = _bare_task("/tmp/foo.mp3")
    resolve_within_batch_collisions([t1, t2], case_insensitive=False)

    assert t1.target_path == "/tmp/Foo.mp3"
    assert t2.target_path == "/tmp/foo.mp3"
    assert t1.result is None and t2.result is None


def test_resolve_within_batch_case_insensitive_suffixes():
    from workers.rename_dispatcher import resolve_within_batch_collisions

    # On a case-insensitive filesystem the same pair collides.
    t1 = _bare_task("/tmp/Foo.mp3")
    t2 = _bare_task("/tmp/foo.mp3")
    resolve_within_batch_collisions([t1, t2], case_insensitive=True)

    assert t1.target_path == "/tmp/Foo.mp3"
    assert t2.target_path == "/tmp/foo (2).mp3"
    assert t2.disambig_base == "foo"


def test_resolve_within_batch_case_only_owner_keeps_name():
    from workers.rename_dispatcher import resolve_within_batch_collisions

    # t_owner is a case-only rename (foo.mp3 -> Foo.mp3): it already owns the
    # name and must keep it even when listed after a competing task.
    t_other = _bare_task("/tmp/foo.mp3", source_path="/tmp/bar.mp3")
    t_owner = _bare_task("/tmp/Foo.mp3", source_path="/tmp/foo.mp3")
    resolve_within_batch_collisions([t_other, t_owner], case_insensitive=True)

    assert t_owner.target_path == "/tmp/Foo.mp3"
    assert t_owner.result is None
    assert t_other.target_path == "/tmp/foo (2).mp3"


def test_plan_batch_stages_contested_source_in_chain():
    from workers.rename_dispatcher import plan_batch

    # 1.mp3 -> 2.mp3 while 2.mp3 -> 3.mp3: 2.mp3's current name is another
    # task's target, so it is staged out of the way before the commits.
    t1 = _bare_task("/tmp/2.mp3", source_path="/tmp/1.mp3")
    t2 = _bare_task("/tmp/3.mp3", source_path="/tmp/2.mp3")
    plan = plan_batch([t1, t2], case_insensitive=False)

    assert len(plan.ops) == 3
    stage, commit1, commit2 = plan.ops
    assert stage.is_staging and stage.source == "/tmp/2.mp3"
    assert commit1.source == "/tmp/1.mp3" and commit1.dest == "/tmp/2.mp3"
    assert commit2.source == stage.dest and commit2.dest == "/tmp/3.mp3"
    assert t1.result is None and t2.result is None


def test_plan_batch_swap_stages_both_members():
    from workers.rename_dispatcher import plan_batch

    # a <-> b swap: both names are contested, so both files stage first and
    # the commits cannot collide in either order.
    ta = _bare_task("/tmp/b.mp3", source_path="/tmp/a.mp3")
    tb = _bare_task("/tmp/a.mp3", source_path="/tmp/b.mp3")
    plan = plan_batch([ta, tb], case_insensitive=False)

    assert [op.is_staging for op in plan.ops] == [True, True, False, False]
    stage_a, stage_b, commit_a, commit_b = plan.ops
    assert stage_a.source == "/tmp/a.mp3"
    assert stage_b.source == "/tmp/b.mp3"
    assert commit_a.source == stage_a.dest and commit_a.dest == "/tmp/b.mp3"
    assert commit_b.source == stage_b.dest and commit_b.dest == "/tmp/a.mp3"
    assert plan.stagings[id(ta)] == (stage_a.dest, "/tmp/a.mp3")


def test_plan_batch_case_only_rename_is_single_plain_op():
    from workers.rename_dispatcher import plan_batch

    task = _bare_task("/tmp/Foo.mp3", source_path="/tmp/foo.mp3")
    plan = plan_batch([task], case_insensitive=True)

    assert len(plan.ops) == 1
    assert not plan.ops[0].is_staging
    assert task.result is None


def test_plan_batch_splits_directories_into_chunks():
    from workers.rename_dispatcher import plan_batch

    t1 = _bare_task("/tmp/one/x.mp3", source_path="/tmp/one/a.mp3")
    t2 = _bare_task("/tmp/two/y.mp3", source_path="/tmp/two/b.mp3")
    plan = plan_batch([t1, t2], case_insensitive=False)

    assert len(plan.ops) == 2
    assert plan.ops[0].chunk_id != plan.ops[1].chunk_id


def test_plan_batch_prefails_tasks_targeting_immovable_names():
    from workers.rename_dispatcher import RenameResult, plan_batch

    # t_stuck failed at planning (e.g. render error) so its source never
    # vacates; t_a targets that source and t_b targets t_a's source. Neither
    # may run - in overwrite mode running t_a would destroy t_stuck's file.
    t_stuck = _bare_task("/tmp/whatever.mp3", source_path="/tmp/held.mp3")
    t_stuck.result = RenameResult(success=False, error="render failed")
    t_a = _bare_task("/tmp/held.mp3", source_path="/tmp/a.mp3")
    t_b = _bare_task("/tmp/a.mp3", source_path="/tmp/b.mp3")
    plan = plan_batch([t_stuck, t_a, t_b], case_insensitive=False)

    assert plan.ops == []
    assert t_a.result is not None and t_a.result.success is False
    assert "kept by another file" in t_a.result.error
    assert t_b.result is not None and t_b.result.success is False
    assert "kept by another file" in t_b.result.error


@pytest.mark.skipif(os.name == "nt", reason="POSIX rename semantics")
def test_rename_no_clobber_raises_and_preserves_source(tmp_path):
    from workers.rename_dispatcher import _rename_no_clobber

    source = tmp_path / "source.mp3"
    target = tmp_path / "target.mp3"
    source.write_bytes(b"source audio")
    target.write_bytes(b"precious existing audio")

    with pytest.raises(FileExistsError):
        _rename_no_clobber(str(source), str(target))

    # Neither file may be altered by the refused rename.
    assert source.read_bytes() == b"source audio"
    assert target.read_bytes() == b"precious existing audio"


@pytest.mark.skipif(os.name == "nt", reason="symlinks unreliable on Windows CI")
def test_dangling_symlink_target_not_clobbered(tmp_path):
    from workers.rename_dispatcher import perform_rename

    source = tmp_path / "source.mp3"
    source.write_bytes(b"source audio")
    target = tmp_path / "target.mp3"
    target.symlink_to(tmp_path / "does-not-exist")

    result = perform_rename(str(source), str(target), RENAME_COLLISION_SKIP)

    assert result.success is False
    assert "already exists" in result.error
    # The dangling symlink and the source are both untouched.
    assert os.path.islink(target)
    assert source.read_bytes() == b"source audio"


def test_perform_rename_auto_continues_numbering(tmp_path):
    from workers.rename_dispatcher import perform_rename

    # The planner already assigned "same (2)"; that name is now taken on
    # disk, so the retry must continue to "same (3)" - never "same (2) (2)".
    source = tmp_path / "source.mp3"
    source.write_bytes(b"source audio")
    (tmp_path / "same (2).mp3").write_bytes(b"occupied")

    result = perform_rename(
        str(source), str(tmp_path / "same (2).mp3"),
        RENAME_COLLISION_AUTO_DISAMBIGUATE, disambig_base="same",
    )

    assert result.success is True
    assert os.path.basename(result.new_path) == "same (3).mp3"


def test_perform_rename_auto_skips_planner_reserved_names(tmp_path):
    from workers.rename_dispatcher import canonical_path_key, perform_rename

    # "same.mp3" is taken on disk and "same (2).mp3" is another batch task's
    # planned target: the retry must jump to "same (3)" instead of stealing it.
    source = tmp_path / "source.mp3"
    source.write_bytes(b"source audio")
    (tmp_path / "same.mp3").write_bytes(b"occupied")
    reserved = {canonical_path_key(str(tmp_path / "same (2).mp3"), False)}

    result = perform_rename(
        str(source), str(tmp_path / "same.mp3"),
        RENAME_COLLISION_AUTO_DISAMBIGUATE,
        planned_target_keys=reserved, case_insensitive=False,
    )

    assert result.success is True
    assert os.path.basename(result.new_path) == "same (3).mp3"
    assert not os.path.exists(tmp_path / "same (2).mp3")


@pytest.mark.skipif(
    sys.platform not in ("win32", "darwin"),
    reason="requires a case-insensitive filesystem",
)
def test_case_only_rename_exact_cased_name(tmp_path):
    from workers.rename_dispatcher import perform_rename

    source = tmp_path / "foo.mp3"
    source.write_bytes(b"audio")

    result = perform_rename(
        str(source), str(tmp_path / "Foo.mp3"),
        RENAME_COLLISION_AUTO_DISAMBIGUATE,
    )

    assert result.success is True and result.skipped is False
    assert os.path.basename(result.new_path) == "Foo.mp3"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Foo.mp3"]


class _InlinePool:
    """Synchronous stand-in for QThreadPool: runs each worker immediately.

    Signal emission then happens on the calling thread via direct
    connections, so dispatcher orchestration is testable without a Qt event
    loop (and therefore in the GitHub runner).
    """

    def start(self, runnable):
        runnable.run()


def _copy_fixtures(tmp_path, names):
    """Copy two distinct audio fixtures into tmp_path under the given names."""
    sources = [
        os.path.join(FIXTURE_ROOT, "sample_dtmf_nometa.mp3"),
        os.path.join(FIXTURE_ROOT, "sample_dtmf_unicode.mp3"),
    ]
    paths = []
    for name, fixture in zip(names, sources):
        dest = tmp_path / name
        shutil.copy(fixture, dest)
        paths.append(str(dest))
    return paths


def _run_batch(tasks):
    """Drive a dispatcher over pre-built tasks synchronously; return summary."""
    from workers.rename_dispatcher import RenameDispatcher

    dispatcher = RenameDispatcher(thread_pool=_InlinePool())
    dispatcher.enqueue_tasks(tasks)
    dispatcher.start()
    return dispatcher.get_summary()


@pytest.mark.parametrize("mode", [
    RENAME_COLLISION_AUTO_DISAMBIGUATE,
    RENAME_COLLISION_SKIP,
    RENAME_COLLISION_OVERWRITE,
])
def test_chain_rename_no_data_loss(tmp_path, mode):
    """Renaming 1.mp3 -> 2.mp3 while 2.mp3 -> 3.mp3 must lose no audio."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    path_1, path_2 = _copy_fixtures(tmp_path, ["1.mp3", "2.mp3"])
    content_1 = Path(path_1).read_bytes()
    content_2 = Path(path_2).read_bytes()
    assert content_1 != content_2

    tasks = [
        plan_rename(MediaFile(path_1), "2", mode),
        plan_rename(MediaFile(path_2), "3", mode),
    ]
    summary = _run_batch(tasks)

    assert summary["successful"] == 2, summary
    assert not summary["failed"] and not summary["skipped"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2.mp3", "3.mp3"]
    assert (tmp_path / "2.mp3").read_bytes() == content_1
    assert (tmp_path / "3.mp3").read_bytes() == content_2


def test_swap_rename_no_data_loss(tmp_path):
    """Swapping a.mp3 <-> b.mp3 must exchange contents with no leftovers."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    path_a, path_b = _copy_fixtures(tmp_path, ["a.mp3", "b.mp3"])
    content_a = Path(path_a).read_bytes()
    content_b = Path(path_b).read_bytes()

    tasks = [
        plan_rename(MediaFile(path_a), "b", RENAME_COLLISION_AUTO_DISAMBIGUATE),
        plan_rename(MediaFile(path_b), "a", RENAME_COLLISION_AUTO_DISAMBIGUATE),
    ]
    summary = _run_batch(tasks)

    assert summary["successful"] == 2, summary
    assert not summary["failed"] and not summary["skipped"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp3", "b.mp3"]
    assert (tmp_path / "a.mp3").read_bytes() == content_b
    assert (tmp_path / "b.mp3").read_bytes() == content_a


def test_mid_batch_failure_reports_accurate_results(tmp_path, monkeypatch):
    """A failed commit strands nothing silently and clobbers nothing."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    path_1, path_2 = _copy_fixtures(tmp_path, ["1.mp3", "2.mp3"])
    content_1 = Path(path_1).read_bytes()
    content_2 = Path(path_2).read_bytes()

    # Fail the (staged) 2.mp3 -> 3.mp3 commit after 1.mp3 -> 2.mp3 has taken
    # the vacated name.
    real_replace = os.replace

    def failing_replace(src, dst):
        if os.path.basename(dst) == "3.mp3":
            raise OSError("simulated I/O error")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    tasks = [
        plan_rename(MediaFile(path_1), "2", RENAME_COLLISION_OVERWRITE),
        plan_rename(MediaFile(path_2), "3", RENAME_COLLISION_OVERWRITE),
    ]
    summary = _run_batch(tasks)

    # Per-task accounting: the first rename really succeeded; the second
    # failed with its file's actual location reported (its old name is now
    # legitimately taken, so it stays at the staging name).
    assert summary["successful"] == 1
    assert len(summary["failed"]) == 1, summary
    failed_path, failed_error = summary["failed"][0]
    assert "simulated I/O error" in failed_error
    assert "temporary name" in failed_error
    # No bytes lost: 2.mp3 holds file 1's audio, and file 2's audio is intact
    # at the reported staging location.
    assert (tmp_path / "2.mp3").read_bytes() == content_1
    assert Path(failed_path).read_bytes() == content_2


def test_staging_failure_rolls_back_directory(tmp_path, monkeypatch):
    """If staging fails, already-staged files return home and nothing commits."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    path_a, path_b = _copy_fixtures(tmp_path, ["a.mp3", "b.mp3"])
    content_a = Path(path_a).read_bytes()
    content_b = Path(path_b).read_bytes()

    # In an a <-> b swap both files stage first; fail b.mp3's staging rename
    # so the whole directory is rolled back before any commit runs.
    real_link = os.link

    def failing_link(src, dst, **kwargs):
        if os.path.basename(src) == "b.mp3":
            raise OSError(5, "simulated I/O error")  # EIO
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", failing_link)

    tasks = [
        plan_rename(MediaFile(path_a), "b", RENAME_COLLISION_AUTO_DISAMBIGUATE),
        plan_rename(MediaFile(path_b), "a", RENAME_COLLISION_AUTO_DISAMBIGUATE),
    ]
    summary = _run_batch(tasks)

    assert summary["successful"] == 0
    assert len(summary["failed"]) == 2, summary
    errors = {os.path.basename(p): e for p, e in summary["failed"]}
    assert "simulated I/O error" in errors["b.mp3"]
    assert "aborted" in errors["a.mp3"]
    # Both files are back at their original names, intact - no temp leftovers.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp3", "b.mp3"]
    assert (tmp_path / "a.mp3").read_bytes() == content_a
    assert (tmp_path / "b.mp3").read_bytes() == content_b


def test_failed_commits_restore_staged_files(tmp_path, monkeypatch):
    """Staged files whose commits fail are moved back to their old names."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import _STAGING_NAME_PREFIX, plan_rename

    path_a, path_b = _copy_fixtures(tmp_path, ["a.mp3", "b.mp3"])
    content_a = Path(path_a).read_bytes()
    content_b = Path(path_b).read_bytes()

    # Swap where both commits fail (their sources are staging names); both
    # old names stay free, so both restores must succeed. A restore renames
    # ".yaamt-rename-x.mp3" back to "x.mp3"; only fail the other moves.
    real_link = os.link

    def failing_link(src, dst, **kwargs):
        src_name = os.path.basename(src)
        dst_name = os.path.basename(dst)
        is_restore = src_name == f"{_STAGING_NAME_PREFIX}{dst_name}"
        if src_name.startswith(_STAGING_NAME_PREFIX) and not is_restore:
            raise OSError(5, "simulated I/O error")  # EIO
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", failing_link)

    tasks = [
        plan_rename(MediaFile(path_a), "b", RENAME_COLLISION_AUTO_DISAMBIGUATE),
        plan_rename(MediaFile(path_b), "a", RENAME_COLLISION_AUTO_DISAMBIGUATE),
    ]
    summary = _run_batch(tasks)

    assert summary["successful"] == 0
    assert len(summary["failed"]) == 2, summary
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp3", "b.mp3"]
    assert (tmp_path / "a.mp3").read_bytes() == content_a
    assert (tmp_path / "b.mp3").read_bytes() == content_b


def test_directory_failure_does_not_affect_other_directories(tmp_path, monkeypatch):
    """Chunks are independent: an aborted directory leaves others untouched."""
    from models.media_file import MediaFile
    from workers.rename_dispatcher import plan_rename

    dir_one = tmp_path / "one"
    dir_two = tmp_path / "two"
    dir_one.mkdir()
    dir_two.mkdir()
    path_a, path_b = _copy_fixtures(dir_one, ["a.mp3", "b.mp3"])
    (path_c,) = _copy_fixtures(dir_two, ["c.mp3"])

    # Abort dir_one's swap at staging time; dir_two's rename must proceed.
    real_link = os.link

    def failing_link(src, dst, **kwargs):
        if os.path.basename(src) == "b.mp3":
            raise OSError(5, "simulated I/O error")  # EIO
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", failing_link)

    tasks = [
        plan_rename(MediaFile(path_a), "b", RENAME_COLLISION_AUTO_DISAMBIGUATE),
        plan_rename(MediaFile(path_b), "a", RENAME_COLLISION_AUTO_DISAMBIGUATE),
        plan_rename(MediaFile(path_c), "renamed", RENAME_COLLISION_AUTO_DISAMBIGUATE),
    ]
    summary = _run_batch(tasks)

    assert summary["successful"] == 1
    assert len(summary["failed"]) == 2, summary
    assert sorted(p.name for p in dir_one.iterdir()) == ["a.mp3", "b.mp3"]
    assert sorted(p.name for p in dir_two.iterdir()) == ["renamed.mp3"]


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt signals require running event loop")
def test_dispatcher_renames_file_end_to_end(qapp, tmp_audio_copy):
    from models.media_file import MediaFile
    from workers.rename_dispatcher import RenameDispatcher

    mf = MediaFile(tmp_audio_copy)
    dispatcher = RenameDispatcher()

    completed = []
    dispatcher.analysis_completed.connect(lambda: completed.append(True))

    dispatcher.enqueue([mf], "renamed_%FORMAT%", RENAME_COLLISION_AUTO_DISAMBIGUATE)
    dispatcher.start()

    # Pump the event loop until completion or timeout.
    import time
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not completed:
        QCoreApplication.processEvents()
        time.sleep(0.01)

    assert completed, "Rename dispatcher did not finish within timeout"

    summary = dispatcher.get_summary()
    assert summary["total"] == 1
    assert summary["successful"] == 1
    assert not summary["failed"]

    # Original file should no longer exist; target file should exist.
    assert not os.path.exists(tmp_audio_copy)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt signals require running event loop")
def test_dispatcher_skip_mode_reports_existing_target(qapp, tmp_audio_copy):
    from models.media_file import MediaFile
    from workers.rename_dispatcher import RenameDispatcher

    # Create a file at what will be the target so the rename must collide.
    directory = os.path.dirname(tmp_audio_copy)
    mf = MediaFile(tmp_audio_copy)

    # Use a format that targets a fixed name we can pre-create.
    target_name = "fixed_target"
    ext = os.path.splitext(tmp_audio_copy)[1]
    existing_target = os.path.join(directory, target_name + ext)
    with open(existing_target, "wb") as f:
        f.write(b"not an audio file")

    dispatcher = RenameDispatcher()
    completed = []
    dispatcher.analysis_completed.connect(lambda: completed.append(True))

    dispatcher.enqueue([mf], target_name, RENAME_COLLISION_SKIP)
    dispatcher.start()

    import time
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not completed:
        QCoreApplication.processEvents()
        time.sleep(0.01)

    summary = dispatcher.get_summary()
    assert summary["successful"] == 0
    assert len(summary["failed"]) == 1
    assert "already exists" in summary["failed"][0][1]
    # Source file still exists because rename was skipped.
    assert os.path.exists(tmp_audio_copy)
