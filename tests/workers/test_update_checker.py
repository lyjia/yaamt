"""
Unit tests for the self-update worker.

Covers:
  - check_latest_release strips the leading 'v' from the tag
  - cache_is_fresh boundary behavior
  - UpdateChecker.run dispatches the right signal in each scenario
    (network failure, no update, update available, served from cache)
  - The opt-in cache is honored when use_cache=True and bypassed when
    use_cache=False
"""

import json
import time
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from util.const import (
    SETTINGS_LAST_KNOWN_LATEST_VERSION,
    SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP,
    UPDATE_CHECK_INTERVAL_SECONDS,
)
from workers.update_checker import (
    UpdateChecker,
    cache_is_fresh,
    check_latest_release,
)


def _fake_response(payload: dict):
    """Build a context-manager-compatible fake urlopen response."""
    body = json.dumps(payload).encode("utf-8")
    response = MagicMock()
    response.read.return_value = body
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


class FakeSettings:
    """In-memory QSettings stand-in. Keeps tests free of QApplication."""

    def __init__(self, initial: dict | None = None):
        self._store: dict = dict(initial or {})

    def value(self, key, default=None, type=None):
        if key not in self._store:
            return default
        v = self._store[key]
        if type is bool:
            return bool(v)
        if type is int:
            return int(v)
        if type is str:
            return str(v)
        return v

    def setValue(self, key, value):
        self._store[key] = value


class TestCheckLatestRelease:
    def test_strips_v_prefix(self):
        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.3.5", "html_url": "U"})):
            tag, url = check_latest_release()
        assert tag == "0.3.5"
        assert url == "U"

    def test_passes_through_unprefixed(self):
        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "0.3.5", "html_url": "U"})):
            tag, _ = check_latest_release()
        assert tag == "0.3.5"

    def test_raises_when_tag_missing(self):
        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({})):
            with pytest.raises(ValueError, match="tag_name"):
                check_latest_release()


class TestCacheIsFresh:
    def test_returns_false_when_no_timestamp(self):
        assert cache_is_fresh(None) is False
        assert cache_is_fresh(0) is False

    def test_returns_true_within_interval(self):
        now = 1000000.0
        recent = int(now - 60)
        assert cache_is_fresh(recent, now=now) is True

    def test_returns_false_past_interval(self):
        now = 1000000.0
        old = int(now - UPDATE_CHECK_INTERVAL_SECONDS - 1)
        assert cache_is_fresh(old, now=now) is False


class TestUpdateCheckerRun:
    def test_emits_update_available_when_newer_release_exists(self):
        settings = FakeSettings()
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=False)
        cb = MagicMock()
        checker.signals.update_available.connect(cb)

        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.4.0", "html_url": "U"})):
            checker.run()

        cb.assert_called_once_with("0.4.0", "U")

    def test_emits_no_update_when_same_release(self):
        settings = FakeSettings()
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=False)
        cb = MagicMock()
        checker.signals.no_update.connect(cb)

        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.3.0", "html_url": "U"})):
            checker.run()

        cb.assert_called_once()

    def test_emits_failed_on_network_error(self):
        settings = FakeSettings()
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=False)
        cb = MagicMock()
        checker.signals.failed.connect(cb)

        with patch("workers.update_checker.urllib.request.urlopen",
                   side_effect=URLError("offline")):
            checker.run()

        cb.assert_called_once()

    def test_persists_check_on_success(self):
        settings = FakeSettings()
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=False)

        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.4.0", "html_url": "U"})):
            checker.run()

        assert settings._store[SETTINGS_LAST_KNOWN_LATEST_VERSION] == "0.4.0"
        assert isinstance(settings._store[SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP], int)

    def test_serves_from_fresh_cache_when_use_cache_true(self):
        # Cache says 0.4.0 is the latest; check ran 1 minute ago.
        settings = FakeSettings({
            SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP: int(time.time() - 60),
            SETTINGS_LAST_KNOWN_LATEST_VERSION: "0.4.0",
        })
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=True)
        cb = MagicMock()
        checker.signals.update_available.connect(cb)

        with patch("workers.update_checker.urllib.request.urlopen") as urlopen:
            checker.run()

        urlopen.assert_not_called()
        cb.assert_called_once_with("0.4.0", "")

    def test_bypasses_cache_when_use_cache_false(self):
        # Cache says 0.4.0 from 1 minute ago, but use_cache=False.
        settings = FakeSettings({
            SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP: int(time.time() - 60),
            SETTINGS_LAST_KNOWN_LATEST_VERSION: "0.4.0",
        })
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=False)

        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.5.0", "html_url": "U"})) as urlopen:
            checker.run()

        urlopen.assert_called_once()

    def test_stale_cache_triggers_network_call(self):
        settings = FakeSettings({
            SETTINGS_LAST_UPDATE_CHECK_TIMESTAMP: int(time.time() - UPDATE_CHECK_INTERVAL_SECONDS - 1),
            SETTINGS_LAST_KNOWN_LATEST_VERSION: "0.4.0",
        })
        checker = UpdateChecker(current_version="0.3.0", settings=settings, use_cache=True)

        with patch("workers.update_checker.urllib.request.urlopen",
                   return_value=_fake_response({"tag_name": "v0.5.0", "html_url": "U"})) as urlopen:
            checker.run()

        urlopen.assert_called_once()
