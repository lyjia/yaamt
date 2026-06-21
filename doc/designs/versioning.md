# Versioning Design

From the Public Release Readiness epic.

## Goal

Produce a single, predictable version string for both the running application
(displayed in `--version` output and the About window) and the build system
(stamped into release artifacts and installer filenames). The version must:

- Be derivable from the git history alone - no separate manifest to hand-edit.
- Match PEP 440 so packaging tools accept it.
- Make releases visually distinguishable from intermediate builds at a glance.
- Bump only when a maintainer tags a release; never auto-increment the public
  Major.Minor.Patch component.

## Format

The version string takes one of three shapes:

| Situation                          | Example                  |
|------------------------------------|--------------------------|
| HEAD is exactly on a release tag   | `0.3.0`                  |
| N commits past the most recent tag | `0.3.0+5.abc1234`        |
| Working tree is dirty              | `0.3.0+5.abc1234.dirty`  |
| No reachable release tag at all    | `0.0.0+147.abc1234`      |

- `Major.Minor.Patch` always comes verbatim from the most recent reachable
  release tag (`v<M>.<m>.<p>`). It is never modified by tooling.
- The local-version suffix (`+...`) is PEP 440 local-version metadata. It
  carries the commits-since-tag count and the short commit hash. Anything
  with a `+` is by definition not a release.
- `dirty` is appended when the working tree has uncommitted changes.

## Source of Truth

`git describe --tags --long --dirty --match 'v*.*.*'` is the single git
invocation. Its output (e.g. `v0.3.0-5-g1234567-dirty`) is parsed once and
reassembled into the format above. If it fails (no matching tag), fall back
to `git rev-list --count HEAD` + `git rev-parse --short HEAD` for a `0.0.0`
synthetic version.

## Architecture

`src/util/version.py` exposes two public functions:

- `get_version_from_git(project_root: Path | None = None) -> str` - the
  single git-driven implementation. Accepts an optional project root so the
  build system and tests can call it against arbitrary repos.
- `get_version() -> str` - returns the build-time-stamped
  `const.VERSION_STRING` if set, else delegates to `get_version_from_git()`.

`build.py` stops running its own `git describe` invocation and calls
`get_version_from_git()` directly. This removes the duplicated subprocess
logic in `build.py:544-557` and guarantees the build system and the running
app always agree on format.

`const.VERSION_STRING` continues to be patched by
`build.py:prepare_source_for_build` at build time so frozen executables do
not need a `.git` directory to know their own version.

## Failure Modes

- `git` not on PATH: log a warning, return `"0.0.0"`.
- Inside a git repo but no matching tag: fall back to
  `0.0.0+<count>.<hash>` using `rev-list` / `rev-parse`.
- Outside a git repo (no `.git`): log a warning, return `"0.0.0"`.

All failures are logged via `util.logging.log` (warning level). They never
raise to callers; an unprintable version string would block CLI startup and
the GUI About window.

## Files

- `src/util/version.py` - rewrite per above
- `src/util/const.py` - no mechanism change; `VERSION_STRING` placeholder stays
- `build.py` - replace inline `git describe` with a call to
  `get_version_from_git()`
- `tests/util/test_version.py` - new; covers the three format shapes plus
  the no-tag and no-git fallbacks against temp git repos

## Verification

- `pytest tests/util/test_version.py` covers the format matrix.
- Manual check: `python -m util.version` from `src/` should print a
  well-formed version against the live repo.
- Manual check: `python build.py` continues to print the version string
  before running the backend.
