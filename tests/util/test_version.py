"""
Unit tests for the version derivation helper.

Covers the format matrix from doc/designs/versioning.md against real
temporary git repositories so we exercise the actual `git describe` /
`git rev-list` pipeline rather than mocking it.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

from util.version import (
    VERSION_FALLBACK,
    get_version_from_git,
)


def _git(cwd: Path, *args: str) -> str:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> None:
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "tag.gpgsign", "false")


def _commit(path: Path, message: str) -> None:
    marker = path / "marker.txt"
    marker.write_text(message)
    _git(path, "add", "marker.txt")
    _git(path, "commit", "-q", "-m", message)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A fresh empty git repository rooted at tmp_path."""
    _init_repo(tmp_path)
    return tmp_path


class TestGetVersionFromGit:
    """Format matrix from doc/designs/versioning.md."""

    def test_clean_tagged_commit_returns_bare_version(self, git_repo: Path):
        _commit(git_repo, "first")
        _git(git_repo, "tag", "v0.3.0")

        assert get_version_from_git(git_repo) == "0.3.0"

    def test_commits_past_tag_emit_local_version_suffix(self, git_repo: Path):
        _commit(git_repo, "first")
        _git(git_repo, "tag", "v0.3.0")
        _commit(git_repo, "second")
        _commit(git_repo, "third")

        version = get_version_from_git(git_repo)

        assert version.startswith("0.3.0+2.")
        assert re.match(r"^0\.3\.0\+2\.[0-9a-f]+$", version), version

    def test_dirty_working_tree_appends_dirty_marker(self, git_repo: Path):
        _commit(git_repo, "first")
        _git(git_repo, "tag", "v0.3.0")
        _commit(git_repo, "second")
        # Modify tracked file without committing.
        (git_repo / "marker.txt").write_text("uncommitted change")

        version = get_version_from_git(git_repo)

        assert version.endswith(".dirty"), version
        assert version.startswith("0.3.0+1."), version

    def test_dirty_on_exact_tag_still_marks_dirty(self, git_repo: Path):
        _commit(git_repo, "first")
        _git(git_repo, "tag", "v0.3.0")
        (git_repo / "marker.txt").write_text("uncommitted change")

        version = get_version_from_git(git_repo)

        # zero commits past tag, but dirty -> still gets a local version.
        assert version.endswith(".dirty"), version
        assert version.startswith("0.3.0+0."), version

    def test_no_release_tag_falls_back_to_synthetic_version(self, git_repo: Path):
        _commit(git_repo, "first")
        _commit(git_repo, "second")
        _commit(git_repo, "third")

        version = get_version_from_git(git_repo)

        assert version.startswith(f"{VERSION_FALLBACK}+3."), version
        assert re.match(r"^0\.0\.0\+3\.[0-9a-f]+$", version), version

    def test_non_release_tags_are_ignored(self, git_repo: Path):
        # Tags like 'nightly' or 'v0.3' (missing patch) must not satisfy
        # the v*.*.* glob and should fall through to the synthetic path.
        _commit(git_repo, "first")
        _git(git_repo, "tag", "nightly")
        _git(git_repo, "tag", "v0.3")

        version = get_version_from_git(git_repo)

        assert version.startswith(f"{VERSION_FALLBACK}+1."), version

    def test_picks_most_recent_release_tag(self, git_repo: Path):
        _commit(git_repo, "first")
        _git(git_repo, "tag", "v0.2.0")
        _commit(git_repo, "second")
        _git(git_repo, "tag", "v0.3.0")
        _commit(git_repo, "third")

        version = get_version_from_git(git_repo)

        assert version.startswith("0.3.0+1."), version

    def test_returns_fallback_outside_a_git_repo(self, tmp_path: Path):
        # tmp_path with no git init.
        assert get_version_from_git(tmp_path) == VERSION_FALLBACK
