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

## Pipeline Topology

Four pipeline files under `.woodpecker/`:

| File                | Trigger                                    | Runs on            |
|---------------------|--------------------------------------------|--------------------|
| `test.yaml`         | every push, every PR                       | Linux              |
| `build-linux.yaml`  | push to master/development, tag `v*.*.*`   | Linux              |
| `build-windows.yaml`| push to master/development, tag `v*.*.*`   | Windows            |
| `build-macos.yaml`  | push to master/development, tag `v*.*.*`   | macOS              |

`test.yaml` produces no artifacts. The three build pipelines invoke
`build.py --release --installer` and upload the resulting installer to
GitHub Releases via `scripts/release_upload.py`.

## Trigger Matrix

| Event                       | test.yaml | build-*.yaml | Upload target              |
|-----------------------------|-----------|--------------|----------------------------|
| PR (any branch)             | yes       | no           | -                          |
| push to feature branch      | yes       | no           | -                          |
| push to master/development  | yes       | yes          | rolling `nightly` release  |
| push of tag `v<M>.<m>.<p>`  | yes       | yes          | versioned release `v<...>` |

The "nightly" release is a single GitHub Release with the tag `nightly`
that the upload script recreates with the latest artifacts on every
master/development push. Anyone can grab the latest dev build from a
stable URL without browsing the workflow run history.

## Runner Provisioning

Only the Linux Woodpecker agent is connected today. Windows and macOS
agents must be brought online before tag pushes can produce a complete
release. Until they are, tag pushes will publish a Linux-only release;
this is acceptable as an interim state but blocks v1 public release.

### Linux agent (already connected)

Already running. No custom labels required: the Linux pipelines route
on `platform=linux/amd64`, which every agent advertises by default.
The agent must have docker + git available (Woodpecker defaults).
Build pipelines `curl`-install `nfpm` inside the build container (the
official `python:3.12` image does not include it).

Note on Docker steps: each step runs in a fresh container and only
the workspace directory persists between steps. Pipeline steps must
be self-contained - apt/pip installs from one step do not exist in
the next. (Bare-metal local-backend agents do not have this
constraint.)

### Windows agent (to provision)

1. Provision a long-lived Windows host (Server 2022 or Win11 Pro). It
   must reach the Woodpecker server over outbound TCP only - **never
   expose any port inbound**.
2. Install:
   - Python 3.12 (python.org installer, "Add to PATH")
   - Git for Windows
   - Inno Setup 6 (`iscc` on PATH; required for installer builds)
3. Create a dedicated low-privilege Windows user (`woodpecker-agent`).
   Do not use Administrator.
4. Install `woodpecker-agent` from the official release. Run it as a
   Windows service under the dedicated user, configured with
   `WOODPECKER_BACKEND=local` (no Docker on this host). Note: on the
   local backend, the `image` field in pipeline steps names the shell
   used to run commands (`powershell` in `build-windows.yaml`), not a
   container image.
5. Configure the agent with a unique agent token issued by the
   Woodpecker server (one token per agent, rotate independently).
6. Apply runner labels: `backend=local`, `platform=windows/amd64`,
   `os=windows`.
7. Smoke test: trigger `build-windows.yaml` from the Woodpecker UI and
   confirm the artifact is produced.

### macOS agent (to provision)

1. Provision a long-lived macOS host. Apple Silicon is preferred for
   `arm64` artifacts; an Intel host can be added separately for `amd64`.
   Outbound TCP only - no inbound exposure.
2. Install:
   - Xcode Command Line Tools (`xcode-select --install`)
   - Python 3.12 from the python.org installer (avoid Homebrew's Python
     to keep the build environment minimal and reproducible)
   - `create-dmg` (via Homebrew is fine; only the Python install is
     pinned)
3. Create a dedicated user `woodpecker-agent`.
4. Install `woodpecker-agent` and run under launchd as that user,
   configured with `WOODPECKER_BACKEND=local` (no Docker on this
   host). As on Windows, the `image` field in pipeline steps names the
   shell (`bash` in `build-macos.yaml`), not a container image.
5. Apply runner labels: `backend=local`, `platform=darwin/arm64` (or
   `darwin/amd64`), `os=macos`.
6. Smoke test as above.

### Cross-cutting agent rules

- One agent token per agent. Tokens never appear in pipeline YAML.
- No agent ever holds the `GITHUB_RELEASE_TOKEN` as a static config
  value. The token is a Woodpecker server secret, exposed only to
  trusted-tier pipelines (see Security below).
- Agents run as a dedicated low-privilege user. Never as root /
  Administrator.

## Security Model

Self-hosted runners + fork PRs is a remote-code-execution footgun: a fork
attacker controls both the pipeline YAML and the code it runs (tests,
conftest, build scripts, fixtures). Without controls, a fork PR =
arbitrary code on our hardware. The mitigation:

- **Trusted vs untrusted tiers.** Two trust levels:
  - *Untrusted (fork PRs, post-approval):* `test.yaml` only, on Linux,
    in an ephemeral Docker step. No secrets exposed. No release token,
    no signing keys. Cannot reach the Windows/macOS hosts.
  - *Trusted (pushes to master/development by maintainers; tag pushes):*
    full build matrix on all three runners. `GITHUB_RELEASE_TOKEN`
    available. Only maintainers can trigger this tier (only they can
    push to those refs).
- **Manual approval for fork PRs.** Configure Woodpecker to require
  maintainer approval before any fork-PR pipeline runs. The reviewer
  must read the diff before approving and look specifically for
  malicious additions to CI config, conftest, fixtures, and build
  scripts.
- **Branch and tag protection on GitHub.** Only maintainers can push to
  `master`, `development`, or any `v*.*.*` tag.
- **Cache isolation.** Do not share `pip` / `ccache` caches across the
  trust boundary. Either disable caches for fork-PR runs entirely or
  namespace cache keys by trust tier.
- **Secrets are server-side only.** `GITHUB_RELEASE_TOKEN` is a
  Woodpecker server secret, scoped to the trusted-tier pipelines and
  never echoed in logs.

## Release Upload Script

`scripts/release_upload.py` is a stdlib-only Python script that:

- Takes a tag name, a list of artifact paths, and (via the
  `GITHUB_RELEASE_TOKEN` env var) a token.
- Creates the GitHub Release if it does not exist (or recreates it for
  the rolling `nightly` tag).
- Uploads the artifacts as release assets.
- Marks the release as `prerelease=true` for the `nightly` tag and for
  any tag whose version string contains a local-version suffix (`+`).

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
6. Provision the Windows and macOS agents per the sections above.
7. Validate each `build-*.yaml` pipeline produces the expected artifact
   on its target runner.
8. Push a throwaway tag (e.g. `v0.0.0-test`) and confirm the upload
   script populates a release with all three platforms' artifacts. The
   migration is then complete.

## Files

- `.woodpecker/test.yaml` (new)
- `.woodpecker/build-linux.yaml` (new)
- `.woodpecker/build-windows.yaml` (new)
- `.woodpecker/build-macos.yaml` (new)
- `scripts/release_upload.py` (new)
- `.github/workflows/`, `.github/actions/` (deleted)

## Verification

- `python scripts/release_upload.py --help` returns usage.
- The four `.woodpecker/*.yaml` files validate against the Woodpecker
  schema (the server will reject malformed YAML on push).
- Pipeline runs are observed end-to-end per the cutover plan.
