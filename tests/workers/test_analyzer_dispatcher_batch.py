"""
Tests for AnalyzerDispatcher's BatchAnalyzerBase deferral and EditManager
staging. These tests exercise the dispatcher's runtime contract without
going through the full Qt thread pool — we inject tasks and drive the
lifecycle manually so the behaviour is deterministic.
"""

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from models.edit_manager import EditManager
from models.media_file import MediaFile
from providers.analysis import AnalyzerCategory
from providers.analysis.base import AnalyzerBase, AnalyzerResult, BatchAnalyzerBase
from util.const import (
    KEY_COMMENT,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_TAG_GENERIC,
)
from workers.analyzer_dispatcher import (
    AnalysisTask,
    AnalyzerDispatcher,
)


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "metadata"


# ---------------------------------------------------------------- analyzer stubs


class _StubBatchAnalyzer(BatchAnalyzerBase):
    """Minimal batch analyzer: per-file emits a fake track_gain; aggregate
    emits a fake album_gain derived from concatenating the per-file values."""

    name = "Stub Batch Analyzer"
    description = "test"
    category = "loudness"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        return AnalyzerResult(
            success=True,
            data={KEY_REPLAYGAIN_TRACK_GAIN: '-3.00 dB'},
            aggregation_data={'marker': 'x'},
        )

    @classmethod
    def aggregate_results(cls, completed_tasks, options):
        return {
            t.media_file.file_path: {
                KEY_REPLAYGAIN_ALBUM_GAIN: '-4.00 dB',
            }
            for t in completed_tasks
        }


class _StubNonBatchAnalyzer(AnalyzerBase):
    name = "Stub Per-File Analyzer"
    description = "test"
    category = "loudness"
    version = "1.0.0"

    def analyze(self) -> AnalyzerResult:
        return AnalyzerResult(
            success=True,
            data={KEY_COMMENT: "stub per-file"},
        )


# ---------------------------------------------------------------- helpers


@pytest.fixture
def flac_copies(tmp_path):
    src = FIXTURE_DIR / "sample_dtmf_original.flac"
    if not src.exists():
        pytest.skip("fixture missing")
    dsts = []
    for i in range(3):
        dst = tmp_path / f"track_{i}.flac"
        shutil.copy(src, dst)
        dsts.append(dst)
    return dsts


def _make_task(analyzer_cls, media_file, options=None):
    task = AnalysisTask(analyzer_cls, media_file, options or {})
    task.result = analyzer_cls(media_file).analyze()
    return task


def _dispatcher_for(analyzer_cls, *, write_to_tags=True):
    d = AnalyzerDispatcher()
    d.reset()
    d.write_to_tags = write_to_tags
    d.analyzer_name = analyzer_cls.__name__
    d.analyzer_class = analyzer_cls
    return d


def _reset_edit_manager():
    em = EditManager()
    em.reset_changes()
    em.set_autosave(True)
    return em


# ---------------------------------------------------------------- tests


class TestBatchDeferral:
    """Verifies the dispatcher only applies per-file tag writes after the
    batch aggregation step for BatchAnalyzerBase analyzers."""

    def test_batch_analyzer_detected(self):
        d = _dispatcher_for(_StubBatchAnalyzer)
        assert d._is_batch_analyzer() is True

        d = _dispatcher_for(_StubNonBatchAnalyzer)
        assert d._is_batch_analyzer() is False

    def test_aggregation_merges_per_file_and_album_data(self, flac_copies):
        em = _reset_edit_manager()
        d = _dispatcher_for(_StubBatchAnalyzer)

        media_files = [MediaFile(str(p), enable_write=True) for p in flac_copies]
        for mf in media_files:
            d.completed_tasks.append(_make_task(_StubBatchAnalyzer, mf))

        d._run_batch_aggregation()
        d._finalize_writes()

        # Every file must now have both track_gain and album_gain on disk
        # because EditManager.commit_changes_sync ran synchronously (no Qt app
        # in this test — the dispatcher takes the headless branch).
        for p in flac_copies:
            mf = MediaFile(str(p))
            assert mf.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) == '-3.00 dB'
            assert mf.get_tag_simple(KEY_REPLAYGAIN_ALBUM_GAIN) == '-4.00 dB'

    def test_batch_skips_aggregation_when_no_successful_tasks(self):
        em = _reset_edit_manager()
        d = _dispatcher_for(_StubBatchAnalyzer)

        # Simulate a task that errored out.
        from unittest.mock import MagicMock
        t = AnalysisTask(_StubBatchAnalyzer, MagicMock(), {})
        t.result = AnalyzerResult(success=False, error="boom")
        d.completed_tasks.append(t)

        # No exception — just a no-op.
        d._run_batch_aggregation()

        assert not em.has_staged_changes()


class TestAutosaveIntegration:
    """Verifies the dispatcher routes writes through EditManager so the
    autosave flag gates actual disk writes."""

    def test_autosave_on_commits_writes(self, flac_copies):
        em = _reset_edit_manager()
        em.set_autosave(True)

        d = _dispatcher_for(_StubNonBatchAnalyzer)
        mf = MediaFile(str(flac_copies[0]), enable_write=True)
        original_mtime = os.path.getmtime(flac_copies[0])

        task = _make_task(_StubNonBatchAnalyzer, mf)
        d._apply_results(task)
        d._finalize_writes()

        # Disk was written.
        mf2 = MediaFile(str(flac_copies[0]))
        assert mf2.get_tag_simple(KEY_COMMENT) == "stub per-file"

    def test_autosave_off_leaves_changes_staged(self, flac_copies):
        em = _reset_edit_manager()
        em.set_autosave(False)

        d = _dispatcher_for(_StubNonBatchAnalyzer)
        mf = MediaFile(str(flac_copies[0]), enable_write=True)
        original_size = os.path.getsize(flac_copies[0])
        original_mtime = os.path.getmtime(flac_copies[0])

        task = _make_task(_StubNonBatchAnalyzer, mf)
        d._apply_results(task)
        d._finalize_writes()

        # Disk was NOT modified — only staged.
        assert os.path.getmtime(flac_copies[0]) == original_mtime
        assert em.has_staged_changes()
        # The staged change carries the expected value.
        staged = em.get_staged_value_for_file(mf, KEY_COMMENT)
        assert staged == "stub per-file"

        # Cleanup: restore autosave for other tests.
        em.set_autosave(True)
        em.reset_changes()

    def test_write_to_tags_false_skips_staging(self, flac_copies):
        em = _reset_edit_manager()
        em.set_autosave(True)

        d = _dispatcher_for(_StubNonBatchAnalyzer, write_to_tags=False)
        mf = MediaFile(str(flac_copies[0]), enable_write=True)

        task = _make_task(_StubNonBatchAnalyzer, mf)
        d._apply_results(task)
        d._finalize_writes()

        assert not em.has_staged_changes()

    def test_finalize_writes_is_synchronous(self, flac_copies):
        """
        Regression: commit_changes() ran on a QThread and raced with
        main_window's post-analysis clear_staged_changes_for_files call.
        _finalize_writes must now commit synchronously so staged results are
        on disk before the dispatcher emits analysis_completed.
        """
        em = _reset_edit_manager()
        em.set_autosave(True)

        d = _dispatcher_for(_StubNonBatchAnalyzer)
        mf = MediaFile(str(flac_copies[0]), enable_write=True)

        task = _make_task(_StubNonBatchAnalyzer, mf)
        d._apply_results(task)
        d._finalize_writes()

        # Immediately after _finalize_writes returns the file MUST already be
        # written. No thread pump, no sleeps.
        assert not em.has_staged_changes()
        mf2 = MediaFile(str(flac_copies[0]))
        assert mf2.get_tag_simple(KEY_COMMENT) == "stub per-file"


class TestProgressTotal:
    """The progress total must stay equal to the run size across the whole
    run, even when the queue drains into in-flight tasks before any finish."""

    def test_total_counts_in_flight_tasks(self):
        from unittest.mock import MagicMock

        d = _dispatcher_for(_StubNonBatchAnalyzer, write_to_tags=False)
        d._is_running = True

        progress: list[tuple[int, int]] = []
        d.progress_updated.connect(lambda c, t: progress.append((c, t)))

        # Simulate the state _process_next produces with a multi-worker pool:
        # all 3 tasks popped from the queue into active_tasks, none finished.
        tasks = []
        for i in range(3):
            t = AnalysisTask(_StubNonBatchAnalyzer, MagicMock(), {})
            t.result = AnalyzerResult(success=True, data={})
            t.media_file.file_path = f"f{i}.flac"
            d.active_tasks[i] = (t, 1)
            tasks.append(t)
        d._active_workers = 3
        d.threads_in_use = 3

        # Finish workers one at a time; the total must read 3 every time, never 1.
        for worker_id, task in enumerate(tasks):
            d._on_worker_finished(worker_id, task)

        totals = [t for _, t in progress]
        assert all(t == 3 for t in totals), totals
        # Completed climbs 1 -> 2 -> 3.
        assert [c for c, _ in progress] == [1, 2, 3]
