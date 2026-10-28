"""
Regression test for the process-pool singleton race in analyzer_dispatcher.

Many Qt worker threads start nearly simultaneously and each call
_get_process_pool(). Without a lock they all see the global as None and each
create their own ProcessPoolExecutor, spawning N*max_workers subprocesses and
exhausting the machine until the OS kills workers (BrokenProcessPool). This
test hammers the getter from many threads and asserts exactly one pool is ever
constructed. No real subprocesses are spawned, so it is CI-safe.
"""

import concurrent.futures
import threading
import time

import workers.analyzer_dispatcher as dispatcher
from workers.analyzer_dispatcher import _get_process_pool


class _FakePool:
    """Stand-in for ProcessPoolExecutor that spawns nothing."""

    def __init__(self, max_workers: int, max_tasks_per_child: int | None = None):
        self._max_workers = max_workers
        self._max_tasks_per_child = max_tasks_per_child

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        pass


def test_get_process_pool_created_once_under_thread_race(monkeypatch):
    construct_count = 0
    count_lock = threading.Lock()

    def _fake_ctor(max_workers: int, **kwargs) -> _FakePool:
        nonlocal construct_count
        with count_lock:
            construct_count += 1
        # Model the real ProcessPoolExecutor's slow construction (it spawns
        # subprocesses). Without this window the check-then-create race never
        # interleaves under the GIL, and the test couldn't catch a regression.
        time.sleep(0.02)
        return _FakePool(max_workers, **kwargs)

    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", _fake_ctor)

    # Start from a clean global so the getter must create the pool.
    dispatcher._process_pool_executor = None
    try:
        n_threads = 32
        gate = threading.Barrier(n_threads)
        results: list = [None] * n_threads

        def worker(i: int) -> None:
            gate.wait()  # release all threads at once to force the race
            results[i] = _get_process_pool(4)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert construct_count == 1, f"expected one pool, created {construct_count}"
        assert all(r is results[0] for r in results)
    finally:
        dispatcher._process_pool_executor = None


def test_get_process_pool_recycles_workers(monkeypatch):
    # Workers must be recycled so memory does not accumulate across passes (#88).
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", _FakePool)
    dispatcher._process_pool_executor = None
    try:
        pool = _get_process_pool(4)
        assert pool._max_tasks_per_child == dispatcher._PROCESS_POOL_MAX_TASKS_PER_CHILD
    finally:
        dispatcher._process_pool_executor = None
