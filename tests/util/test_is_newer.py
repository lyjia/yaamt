"""
Unit tests for util.version.is_newer.

Comparator semantics from doc/designs/self_update.md: only the
Major.Minor.Patch component is compared; local-version metadata
('+5.abc1234', '.dirty') is ignored.
"""

import pytest

from util.version import is_newer


class TestIsNewer:
    @pytest.mark.parametrize("candidate,baseline,expected", [
        # Strict ordering on M.m.p
        ("0.4.0", "0.3.0", True),
        ("0.3.1", "0.3.0", True),
        ("1.0.0", "0.9.99", True),
        ("0.3.0", "0.3.0", False),
        ("0.3.0", "0.4.0", False),
        ("0.3.0", "0.3.1", False),

        # Leading 'v' (raw GitHub tag) is tolerated on either side
        ("v0.4.0", "0.3.0", True),
        ("0.4.0", "v0.3.0", True),
        ("v1.0.0", "v0.9.0", True),

        # Local-version metadata is ignored: a user past 0.3.0 is not
        # notified about 0.3.0 itself
        ("0.3.0", "0.3.0+5.abc1234", False),
        ("0.3.0", "0.3.0+5.abc1234.dirty", False),

        # ...but they are notified about the next release line
        ("0.3.1", "0.3.0+5.abc1234", True),
        ("0.4.0", "0.3.0+5.abc1234.dirty", True),

        # Comparing two local-version strings still uses M.m.p only
        ("0.4.0+1.abc", "0.3.0+99.def", True),
        ("0.3.0+1.abc", "0.3.0+99.def", False),
    ])
    def test_comparison(self, candidate, baseline, expected):
        assert is_newer(candidate, baseline) is expected

    @pytest.mark.parametrize("garbage", ["", "not-a-version", "1.2", "v", "abc.def.ghi"])
    def test_unparseable_returns_false(self, garbage):
        # Never push a notification we cannot justify.
        assert is_newer(garbage, "0.3.0") is False
        assert is_newer("0.3.0", garbage) is False
