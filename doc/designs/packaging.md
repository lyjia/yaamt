# Packaging and Distribution Design

This document outlines the design for packaging and distributing the audio-metadata-tool for Windows, macOS, and Linux platforms using `cx_freeze`.

## 1. Objectives

- Generate standalone application binaries for both the CLI (`src/main.py`) and GUI (`src/gui.py`).
- Create platform-specific installers:
    - `.msi` for Windows
    - `.app` for macOS
    - `.deb` for Debian-based Linux distributions
- Implement dynamic versioning based on Git tags and revision hashes.
- Display the application version in the CLI and the GUI's "About" window.

## 2. Implementation Plan

### 2.1. `setup.py` Configuration

A `setup.py` file will be created in the project root to configure the `cx_freeze` build process. It will define two main executables:

- **`yaamt-cli`**: The command-line interface, from `src/main.py`.
- **`yaamt-gui`**: The graphical user interface, from `src/gui.py`.

The configuration will include:
- **`build_exe` options**: To specify included/excluded packages, and to ensure all necessary resources (like icons) are bundled.
- **Platform-specific logic**: To adjust the `base` for the GUI executable on Windows (`Win32GUI`).
- **Bdist options**: To configure the creation of installers (`bdist_msi`, `bdist_mac`, `bdist_deb`).

### 2.2. Dynamic Versioning

A helper script, possibly `src/util/version.py`, will be created to generate the version number.

**Strategy:**
1.  Use the `subprocess` module to run `git describe --tags --dirty --always`.
2.  This command produces a version string like `v0.1.0-g1234567-dirty`.
3.  This version string will be written to a file (e.g., `src/VERSION`) during the build process.
4.  The application will read this `VERSION` file at runtime to get its version.

This approach decouples the build environment (which has git) from the runtime environment (which won't).

The `setup.py` will execute this script as part of its build process to generate the version file before the executables are frozen.

### 2.3. Platform-Specific Packages

The `setup.py` file will contain configurations for different distribution formats.

- **Windows (`.msi`)**:
    - The `bdist_msi` command will be used.
    - Options will be set to define the installer's metadata (e.g., `upgrade_code`, `product_name`).
- **macOS (`.app`)**:
    - The `bdist_mac` command will be used to create a standard `.app` bundle.
    - An `Info.plist` file will be referenced to define application metadata, including the icon.
- **Debian (`.deb`)**:
    - The `bdist_deb` command will be used.
    - Options will specify package metadata like maintainer, description, and dependencies.

### 2.4. Displaying the Version in the Application

The version number, stored in the `src/VERSION` file, will be read and displayed in the following locations:

- **CLI**: The `main.py` script will be modified to include a `--version` argument that prints the version and exits.
- **GUI**: The `windows/about_window.py` will be modified to read the version file and display it in the "About" dialog. A utility function in `src/util/version.py` will handle reading the file.

## 3. Build Process

The following commands will be used to build the application and packages:

- **Build executables**: `python setup.py build`
- **Create Windows installer**: `python setup.py bdist_msi`
- **Create macOS app bundle**: `python setup.py bdist_mac`
- **Create Debian package**: `python setup.py bdist_deb`

A comprehensive build script (e.g., `build.sh` or `build.bat`) could be created later to automate these steps.

## 4. Diagram: Build Workflow

```mermaid
graph TD
    A[Start Build] --> B{Get Version};
    B -->|git describe| C[Generate src/VERSION file];
    C --> D[Run cx_freeze];
    D --> E{Build Executables};
    E --> F[CLI: yaamt-cli];
    E --> G[GUI: yaamt-gui];
    D --> H{Create Packages};
    H --> I[Windows: .msi];
    H --> J[macOS: .app];
    H --> K[Linux: .deb];