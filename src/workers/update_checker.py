"""
GitHub releases poller for the in-app update notification.

Hits the GitHub Releases API and reports whether a newer release is
available. See doc/designs/self_update.md for design and the strict
opt-in requirement.

The worker is split from the network primitive so the CLI's
synchronous `--check-update` path can call `check_latest_release`
directly without instantiating a Qt worker.
"""

import json
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QRunnable, Signal

from util.const import (
    SETTINGS_LAST_KNOWN_LATEST_VERSION,
    SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP,
    UPDATE_CHECK_API_URL,
    UPDATE_CHECK_INTERVAL_SECONDS,
)
from util.logging import log
from util.version import is_newer

USER_AGENT = "yaamt-update-check"
HTTP_TIMEOUT_SECONDS = 10


class UpdateCheckerSignals(QObject):
    """Signals emitted by an UpdateChecker run.

    Exactly one of update_available / no_update / failed fires per run.
    """

    update_available = Signal(str, str)   # latest_version, html_url
    no_update = Signal()
    failed = Signal(str)                  # error message


def check_latest_release(api_url: str = UPDATE_CHECK_API_URL) -> tuple[str, str]:
    """Fetch the latest release tag and HTML URL.

    Returns (tag_without_v_prefix, html_url). Raises on any HTTP or
    parse error so callers can decide whether to surface it.
    """
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read())

    tag = payload.get("tag_name", "")
    if not tag:
        raise ValueError("GitHub release payload missing 'tag_name'")

    if tag.startswith("v"):
        tag = tag[1:]

    html_url = payload.get("html_url", "")
    return tag, html_url


def cache_is_fresh(last_check_timestamp: int | None,
                   now: float | None = None,
                   interval_seconds: int = UPDATE_CHECK_INTERVAL_SECONDS) -> bool:
    """True when the last check happened within the cache interval."""
    if not last_check_timestamp:
        return False
    current = now if now is not None else time.time()
    return (current - last_check_timestamp) < interval_seconds


class UpdateChecker(QRunnable):
    """Polls the GitHub Releases API and reports the result via signals.

    Single-shot - one network call per instance. Submit to a QThreadPool;
    do not invoke run() directly from the GUI thread.
    """

    def __init__(self, current_version: str, settings=None,
                 use_cache: bool = True):
        super().__init__()
        self.current_version = current_version
        self.signals = UpdateCheckerSignals()
        # Late-bound to avoid pulling QSettings into module-import time
        # for tests that don't need a real Qt application context.
        self._settings = settings
        self._use_cache = use_cache

    def _resolve_settings(self):
        if self._settings is not None:
            return self._settings
        from models.settings import get_qsettings
        return get_qsettings()

    def _maybe_serve_from_cache(self) -> bool:
        if not self._use_cache:
            return False
        settings = self._resolve_settings()
        last_check = settings.value(SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP, 0, type=int)
        if not cache_is_fresh(last_check):
            return False
        cached_latest = settings.value(SETTINGS_LAST_KNOWN_LATEST_VERSION, "", type=str)
        if not cached_latest:
            return False
        if is_newer(cached_latest, self.current_version):
            self.signals.update_available.emit(cached_latest, "")
        else:
            self.signals.no_update.emit()
        return True

    def _persist_check(self, latest: str) -> None:
        settings = self._resolve_settings()
        settings.setValue(SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP, int(time.time()))
        settings.setValue(SETTINGS_LAST_KNOWN_LATEST_VERSION, latest)

    def run(self) -> None:
        if self._maybe_serve_from_cache():
            return

        try:
            latest, html_url = check_latest_release()
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, OSError) as e:
            log.warning(f"Update check failed: {e}")
            self.signals.failed.emit(str(e))
            return

        try:
            self._persist_check(latest)
        except Exception as e:
            # Cache write failures are not fatal - just log and proceed.
            log.warning(f"Failed to persist update-check cache: {e}")

        if is_newer(latest, self.current_version):
            self.signals.update_available.emit(latest, html_url)
        else:
            self.signals.no_update.emit()
