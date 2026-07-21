"""Tests for workers.rename_dispatcher."""
import os
import shutil
import tempfile

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
