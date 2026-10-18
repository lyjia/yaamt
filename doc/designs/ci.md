# CI Design (Woodpecker)

From the Public Release Readiness epic.

## Goal

Move all continuous integration off GitHub Actions onto self-hosted
Woodpecker runners. GitHub keeps source hosting, the issue tracker, and
release hosting; everything that consumes CPU minutes runs on hardware we
control.

## Why move

The free GitHub Actions plan caps storage at 500 MB. A single YAAMT release
build (PyInstaller output across PySide6 + numpy + librosa) is ~700 MB per
platform. The current `python-app.yml` workflow only runs lint + pytest,
not builds, because the artifacts cannot fit. Woodpecker on self-hosted
runners removes both the storage cap and the per-minute meter.

## Server Version

The pipeline files target Woodpecker **3.x** (server currently runs
3.15.0). Notable 3.x schema rules the configs depend on: the step-level
`secrets:` property no longer exists (secrets are injected via
`environment:` + `from_secret`), and every step requires an `image`
(interpreted as the shell name on local-backend agents). Validate
changes locally with a matching CLI before pushing:
`woodpecker-cli lint .woodpecker/`.

## Tag Releases (GitHub Actions)

Versioned releases are built by `.github/workflows/release.yml`, not
Woodpecker: pushing a `v<M>.<m>.<p>` tag builds Linux (x64, arm64), Windows,
and macOS on GitHub-hosted runners, smoke-tests each bundle and installed
package (`scripts/smoke_test.py`), and uploads the artifacts to a
*draft* GitHub Release for the tag. A maintainer tests the draft's
binaries and publishes it by hand (`doc/RELEASING.md`). Rationale: no Windows/macOS Woodpecker agents
exist, release assets do not count against the Actions storage cap,
and standard runners are free for public repositories. Manual dispatch
with a branch name builds and tests without publishing.

Woodpecker is responsible for lint/test only. There are no automatic
dev builds; packaging is exercised by dispatching `release.yml` by hand.

## Pipeline Topology

One pipeline file, `.woodpecker/test.yaml`, on Linux. It runs lint and
the full pytest suite and produces no artifacts.

## Trigger Matrix

| Event                       | Woodpecker `test.yaml` | GitHub Actions `release.yml`      |
|-----------------------------|------------------------|-----------------------------------|
| PR (any branch)             | yes                    | no                                |
| push to feature branch      | no (runs once a PR is open) | no                           |
| push to master/development  | yes                    | no                                |
| push of tag `v<M>.<m>.<p>`  | no                     | yes: draft release `v<...>`       |
| manual dispatch             | -                      | yes: build + smoke test, no upload |

## Runner Provisioning

A single Linux Woodpecker agent. Windows and macOS builds run on
GitHub-hosted runners (see Tag Releases above), so no other agents are
needed.

### Linux agent (already connected)

Already running. No custom labels required: the Linux pipelines route
on `platform=linux/amd64`, which every agent advertises by default.
The agent must have docker + git available (Woodpecker defaults).
`build.py --install-deps` installs a pinned `nfpm` inside the build
container (the official `python:3.12` image does not include it).

Note on Docker steps: each step runs in a fresh container and only
the workspace directory persists between steps. Pipeline steps must
be self-contained - apt/pip installs from one step do not exist in
the next.

### Agent rules

- The agent token never appears in pipeline YAML.
- The agent runs as a dedicated low-privilege user. Never as root /
  Administrator.
- Outbound TCP to the Woodpecker server only - never expose a port
  inbound.

## Security Model

Self-hosted runners + fork PRs is a remote-code-execution footgun: a fork
attacker controls both the pipeline YAML and the code it runs (tests,
conftest, build scripts, fixtures). Without controls, a fork PR =
arbitrary code on our hardware. The mitigation:

- **No secrets on Woodpecker.** `test.yaml` runs in ephemeral Docker
  steps and needs no token. Release publishing happens on GitHub
  Actions with the built-in, per-run `GITHUB_TOKEN`, so there is
  nothing on our hardware for a malicious PR to exfiltrate.
- **Manual approval for fork PRs.** Configure Woodpecker to require
  maintainer approval before any fork-PR pipeline runs. The reviewer
  must read the diff before approving and look specifically for
  malicious additions to CI config, conftest, fixtures, and build
  scripts.
- **Branch and tag protection on GitHub.** Only maintainers can push to
  `master`, `development`, or any `v*.*.*` tag.
- **Cache isolation.** Do not share `pip` caches between fork-PR runs
  and maintainer runs.

## Release Upload Script

`scripts/release_upload.py` is a stdlib-only Python script that:

- Takes a tag name, a list of artifact paths, and (via the
  `GITHUB_RELEASE_TOKEN` env var) a token.
- Creates a draft GitHub Release if none exists for the tag, otherwise
  reuses it.
- Uploads the artifacts as release assets.
- Marks the release as `prerelease=true` for any tag whose version
  string contains a local-version suffix (`+`).

Stdlib-only because it must run on every platform without an extra
install step.

## Cutover Plan

1. ~~Land this design doc and the four `.woodpecker/*.yaml` files.~~ Done.
2. ~~Wire up the `GITHUB_RELEASE_TOKEN` secret on the Woodpecker
   server.~~ Done.
3. ~~Validate `test.yaml` runs green on the Linux agent for a feature
   PR.~~ Done.
4. ~~Delete the GitHub Actions workflows (`python-app.yml`,
   `cleanup-artifacts.yml`, `.github/actions/setup-deps/`).~~ Done -
   lint+test now run exclusively on Woodpecker. (Originally scheduled
   after step 6, pulled forward once test.yaml was validated; GH
   Actions never built artifacts, so nothing else was lost.)
5. Point GitHub branch protection's required status check at
   `ci/woodpecker/pr/test` (repo settings; maintainer action).
6. ~~Provision Windows/macOS agents and Woodpecker build pipelines.~~
   Dropped - tag releases moved to GitHub Actions `release.yml`, and the
   `build-*.yaml` pipelines and rolling `nightly` release were removed.

## Files

- `.woodpecker/test.yaml`
- `.github/workflows/release.yml`
- `scripts/release_upload.py`

## Verification

- `python scripts/release_upload.py --help` returns usage.
- `woodpecker-cli lint .woodpecker/` passes.
- A manual dispatch of `release.yml` builds and smoke-tests every
  platform.
