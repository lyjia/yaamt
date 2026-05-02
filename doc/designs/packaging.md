# Packaging and Distribution Design

This document outlines the design for packaging and distributing YAAMT for Windows, macOS, and Linux platforms using **PyInstaller**.

(Historical note: cx_freeze was the original target and Nuitka was prototyped, but neither survived contact with the analyzer dependency mix. The Nuitka backend remains in `build.py` as commented-out code for reference. PyInstaller is the only currently active backend.)

## 1. Objectives

- Generate standalone application binaries for both the CLI (`src/yaamt.py`) and GUI (`src/yaamt-gui.py`).
- Create platform-specific installers (currently deferred — PyInstaller produces the binaries; native installer wiring is future work):
    - `.msi` for Windows
    - `.dmg` for macOS
    - `.deb` for Debian-based Linux distributions
- Implement dynamic versioning based on Git tags and revision hashes.
- Display the application version in the CLI and the GUI's "About" window.

## 2. Implementation Plan

### 2.1. PyInstaller spec file

`yaamt.spec` in the project root drives the PyInstaller build. It defines two `Analysis` blocks (one each for the CLI and GUI entrypoints), a shared `excludes` list (test frameworks, alternative packagers, known-unused transitive deps), and a `hiddenimports` list for libraries whose static-import detection PyInstaller misses (notably `scipy.*`).

Driven by `build.py` (the high-level orchestrator), which:
- Detects platform and architecture
- Creates a temporary build workspace by copying only `src/` and `resources/`
- Patches `IS_DEBUG_BUILD` for release builds
- Invokes `pyinstaller yaamt.spec`
- Copies the output to a timestamped directory `build/<mode>-YYYYMMDD-HHMMSS/yaamt/`

### 2.2. Dynamic Versioning

`build.py` runs `git describe --tags --dirty --always` and patches the result into `src/util/const.py`'s `VERSION_STRING` constant in the temp build workspace. The runtime application reads that constant directly — no separate `VERSION` file is generated.

### 2.3. Platform-Specific Output

| Platform | Output |
|---|---|
| Windows | `yaamt.exe`, `yaamt-gui.exe` (one-folder bundle with PySide6 / mutagen / etc) |
| Linux   | `yaamt`, `yaamt-gui` (one-folder bundle) |
| macOS   | `yaamt`, `yaamt-gui` (one-folder bundle) |

Native installer formats (MSI / DMG / DEB) are not yet wired through `build.py`; they were configured against the cx_freeze prototype and need re-implementation against the PyInstaller output. Tracked as future work.

### 2.4. Displaying the Version in the Application

- **CLI**: `yaamt.py --version` reads `util.const.VERSION_STRING` and prints it.
- **GUI**: `windows/about_window.py` reads the same constant and renders it in the About dialog.

## 3. Build Process

```bash
# Install Python + system build deps
python build.py --install-deps

# Debug build (default)
python build.py

# Release build (excludes debug-only analyzers via IS_DEBUG_BUILD patch)
python build.py --release

# Tar/zip the build for distribution
python build.py --release --archive --version-name v1.0.0
```

## 4. Diagram: Build Workflow

```mermaid
graph TD
    A[python build.py] --> B{Detect platform/arch};
    B --> C[Create temp build workspace];
    C --> D[Patch IS_DEBUG_BUILD + VERSION_STRING];
    D --> E[Run PyInstaller against yaamt.spec];
    E --> F[CLI binary: yaamt / yaamt.exe];
    E --> G[GUI binary: yaamt-gui / yaamt-gui.exe];
    F --> H[Copy to build/<mode>-<timestamp>/yaamt/];
    G --> H;
    H --> I{--archive?};
    I -->|yes| J[Tar/zip artifact];
    I -->|no| K[Done];
```
