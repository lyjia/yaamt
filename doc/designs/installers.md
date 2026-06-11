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
| macOS    | `/Applications/Yaamt.app/`   | `~/Library/Application Support/Lyjia/YAAMT/`|

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

The PyInstaller spec produces a folder of binaries, not a `.app`
bundle. The macOS backend wraps that output:

```
installer/yaamt-macos/
    Yaamt.app/
        Contents/
            Info.plist            (templated; %VERSION% substituted)
            MacOS/                (symlinked or copied from PyInstaller output)
            Resources/
                app-icon-gui.icns
```

`installer/build_dmg.sh` is invoked by the backend and:

1. Copies the PyInstaller output into a fresh
   `Yaamt.app/Contents/MacOS/`.
2. Substitutes the version string into `Info.plist`.
3. Runs `codesign --sign - --deep --force Yaamt.app` (ad-hoc signing -
   we are deferring real Developer ID code signing per the plan; this
   at least makes Gatekeeper warn rather than refuse outright).
4. Calls `create-dmg --volname "YAAMT <version>" Yaamt.app dist/`.

Result: `dist/yaamt-<version>-macos-<arch>.dmg`.

## Files

- `installer/yaamt.iss` (existing) - minor polish: read version via
  `/DAppVersion` (already wired); no structural change.
- `installer/nfpm.yaml` (new)
- `installer/yaamt-macos/Info.plist` (new) - templated bundle metadata
- `installer/build_dmg.sh` (new) - macOS assembly script
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

- `python build.py --release --installer` on a Linux runner produces
  `dist/yaamt-<version>-linux-<arch>.deb` and
  `dist/yaamt-<version>-linux-<arch>.rpm`.
- Same command on Windows produces
  `dist/yaamt-<version>-windows-<arch>-setup.exe`.
- Same command on macOS produces
  `dist/yaamt-<version>-macos-<arch>.dmg`.
- Each artifact installs cleanly on a fresh VM and launches both the
  CLI and GUI.
- `nfpm` and `create-dmg` are documented in `doc/designs/ci.md` as
  agent-provisioning prerequisites.
