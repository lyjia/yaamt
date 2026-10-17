# Installers Design

From the Public Release Readiness epic.

## Goal

Produce a sensible native installer for each supported platform from
the same PyInstaller output. One command (`build.py --installer`) on
each runner, dispatching to a platform-specific backend.

## Tooling Matrix

| Platform | Format               | Tooling                           |
|----------|----------------------|-----------------------------------|
| Windows  | `.exe`               | Inno Setup (`iscc`)               |
| Linux    | `.deb` and `.rpm`    | `nfpm` (single config, two formats)|
| macOS    | `.dmg` (with `.app`) | `create-dmg` + ad-hoc codesign    |

`nfpm` was chosen over `fpm` (no Ruby dependency) and over native
`dpkg-deb` / `rpmbuild` (one tool, one config, both formats from a
single YAML). It is a single Go binary; the Linux runner installs it
once during agent provisioning.

`create-dmg` was chosen over raw `hdiutil` for its volume styling and
background-image support.

## Architecture

`_create_installer` in `build.py` becomes a thin dispatcher:

```
_create_installer(config, version_name)
    if windows: _create_windows_installer(...)
    elif linux: _create_linux_installer(...)
    elif macos: _create_macos_installer(...)
```

Each backend:
1. Locates the PyInstaller output at `config.output_dir / "yaamt"`.
2. Reads the resolved version (via `util.version.get_version_from_git`,
   identical to what `Builder.build` uses - no separate format).
3. Invokes the platform tool against a config file in `installer/`.
4. Writes the resulting installer file into `config.output_dir`.

A backend whose tool is missing from PATH logs a warning and exits
non-zero so the CI pipeline fails loudly rather than silently
skipping the upload step.

## Filesystem Layout (Installed)

| Platform | Binaries                     | User data                                   |
|----------|------------------------------|---------------------------------------------|
| Windows  | `%PROGRAMFILES%\YAAMT\`      | `%LOCALAPPDATA%\Lyjia\YAAMT\` (QSettings)   |
| Linux    | `/usr/lib/yaamt/`            | `~/.config/Lyjia/YAAMT/` (XDG)              |
| macOS    | `/Applications/YAAMT.app/`   | `~/Library/Application Support/Lyjia/YAAMT/`|

On Linux, `/usr/bin/yaamt` is a symlink to `/usr/lib/yaamt/yaamt` so
the CLI is on PATH out of the box. The GUI is launched via the
generated `.desktop` entry.

## Linux: nfpm

`installer/nfpm.yaml` declares both formats from a single source. Key
fields:

- `name: yaamt`
- `version: <stamped at build time via env var or `--version` flag>`
- `maintainer: Lyjia <...>`
- `depends:` system shared libraries that PyInstaller does not bundle
  (e.g. `libegl1`, `libxkbcommon0`, `libportaudio2`)
- `contents:` maps the `yaamt/` PyInstaller output into
  `/usr/lib/yaamt/`, the `.desktop` file into
  `/usr/share/applications/`, and creates the `/usr/bin/yaamt` symlink.

The build backend invokes nfpm twice:

```
nfpm package --config installer/nfpm.yaml --target dist/ --packager deb
nfpm package --config installer/nfpm.yaml --target dist/ --packager rpm
```

## macOS: .app + .dmg

`yaamt.spec` adds a PyInstaller `BUNDLE` step on macOS that wraps the
COLLECT output in `YAAMT.app` (next to the one-folder `yaamt/`).
PyInstaller places data files in `Contents/Resources`, writes
`Info.plist` (version from `YAAMT_VERSION`, set by `build.py`), and
ad-hoc signs the bundle, so Gatekeeper warns rather than refuses.
`yaamt-gui` is the bundle executable; the CLI ships at
`YAAMT.app/Contents/MacOS/yaamt`.

`installer/build_dmg.sh` stages the `.app` and runs `create-dmg` to
make a drag-to-Applications image:
`yaamt-<version>-macos-<arch>.dmg`.

## Release Artifacts

All artifacts share the stem `yaamt-<version>-<platform>-<arch>` and
land in `build/release-<timestamp>/`:

| Platform | `--archive`                 | `--installer`             |
|----------|-----------------------------|---------------------------|
| Windows  | `.zip` (one top-level dir)  | `-setup.exe` (Inno Setup) |
| Linux    | `.tar.gz` (one top-level dir)| `.deb`, `.rpm` (nfpm); x64 and arm64 |
| macOS    | (not used)                  | `.dmg` containing `.app`  |

Linux arm64 binaries need glibc 2.39+ (Ubuntu 24.04, Debian 13,
Fedora 40 or newer) because PySide6's aarch64 wheels are built against
it; x64 binaries need glibc 2.35+.

Linux builds install torch from the PyTorch CPU-only index; PyPI's
Linux wheel is a CUDA build that adds ~4 GB of NVIDIA libraries.

## Files

- `installer/yaamt.iss` (existing) - minor polish: read version via
  `/DAppVersion` (already wired); no structural change.
- `installer/nfpm.yaml` (new)
- `yaamt.spec` - macOS `BUNDLE` step (bundle metadata lives here)
- `installer/build_dmg.sh` (new) - macOS .dmg script
- `build.py:666` - generalize `_create_installer` into a dispatcher
  with three platform backends

## Out of Scope

These all sit downstream of code signing, which the plan defers:

- Developer ID code signing (macOS) and notarization
- Authenticode code signing (Windows)
- GPG-signed RPM packages
- Homebrew tap (`homebrew-yaamt`)
- winget / Chocolatey manifests
- Linux package repositories (PPA, COPR)

Adding any of these later does not require changing the dispatcher
architecture - they slot in as additional steps in the relevant
backend.

## Verification

- `.github/workflows/release.yml` builds every platform and runs
  `scripts/smoke_test.py` against both the raw bundle and the
  installed package (`.deb` via apt, `setup.exe` silent install, the
  `.app` inside the mounted `.dmg` plus `codesign --verify`).
- The smoke test checks the stamped version, imports all analyzers,
  runs offline analyzers on a fixture copy, and starts the GUI under
  Qt's offscreen platform.
- `build.py --install-deps` installs `nfpm`, `create-dmg`, or Inno
  Setup as appropriate.
