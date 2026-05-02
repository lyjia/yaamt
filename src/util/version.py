import os
import re
import subprocess
from pathlib import Path

from .const import VERSION_STRING
from .logging import log

VERSION_FALLBACK = "0.0.0"
RELEASE_TAG_GLOB = "v*.*.*"

_DESCRIBE_PATTERN = re.compile(
    r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"-(?P<count>\d+)"
    r"-g(?P<hash>[0-9a-f]+)"
    r"(?P<dirty>-dirty)?$"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        log.warning("git executable not found on PATH")
        return None
    except subprocess.CalledProcessError as e:
        log.debug(f"git {' '.join(args)} failed: {e.stderr.strip() or e}")
        return None


def _format_version(major: int, minor: int, patch: int, count: int, short_hash: str, dirty: bool) -> str:
    base = f"{major}.{minor}.{patch}"
    if count == 0 and not dirty:
        return base
    suffix = f"{count}.{short_hash}"
    if dirty:
        suffix = f"{suffix}.dirty"
    return f"{base}+{suffix}"


def _format_untagged(count: int, short_hash: str, dirty: bool) -> str:
    suffix = f"{count}.{short_hash}"
    if dirty:
        suffix = f"{suffix}.dirty"
    return f"{VERSION_FALLBACK}+{suffix}"


def get_version_from_git(project_root: Path | None = None) -> str:
    """
    Compute the version string from the git history.

    Format:
      - On a release tag (clean):    'M.m.p'              e.g. '0.3.0'
      - N commits past tag:          'M.m.p+N.<hash>'     e.g. '0.3.0+5.abc1234'
      - Dirty working tree:          appends '.dirty' to the local-version suffix
      - No reachable release tag:    '0.0.0+<count>.<hash>'

    Returns VERSION_FALLBACK on any unrecoverable failure (no git, not a repo).
    All failures are logged; this function never raises to the caller because
    an unprintable version blocks CLI startup and the GUI About window.
    """
    cwd = project_root or _project_root()

    described = _run_git(
        ["describe", "--tags", "--long", "--dirty", "--match", RELEASE_TAG_GLOB],
        cwd,
    )

    if described is not None:
        match = _DESCRIBE_PATTERN.match(described)
        if match:
            return _format_version(
                major=int(match["major"]),
                minor=int(match["minor"]),
                patch=int(match["patch"]),
                count=int(match["count"]),
                short_hash=match["hash"],
                dirty=match["dirty"] is not None,
            )
        log.warning(f"git describe returned unexpected output: {described!r}")

    # No matching release tag - synthesize from commit count and short hash.
    count_raw = _run_git(["rev-list", "--count", "HEAD"], cwd)
    short_hash = _run_git(["rev-parse", "--short", "HEAD"], cwd)
    if count_raw is None or short_hash is None:
        return VERSION_FALLBACK

    status = _run_git(["status", "--porcelain"], cwd)
    dirty = bool(status)

    try:
        count = int(count_raw)
    except ValueError:
        log.warning(f"git rev-list returned non-integer count: {count_raw!r}")
        return VERSION_FALLBACK

    return _format_untagged(count, short_hash, dirty)


def get_version() -> str:
    """
    Return the version string.

    Frozen builds carry a hard-coded VERSION_STRING patched in by build.py.
    Source checkouts derive the version live from git.
    """
    if VERSION_STRING:
        return VERSION_STRING
    return get_version_from_git()


if __name__ == "__main__":
    print(get_version())
