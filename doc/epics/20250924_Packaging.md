One of this project's objectives is to distribute pre-compiled binaries for all the major platforms (Windows, Mac, Linux, BSD) using PyInstaller, as well as publish them using Github's build artifacts and releases system. Right now I just want to focus on getting the build system up and running locally.

(Historical note: cx_freeze and Nuitka were both evaluated as build backends. PyInstaller is the only one currently active in `build.py`; the Nuitka backend is commented out — see the `NuitkaBuilder` class in `build.py` — because it never produced a usable release given the analyzer dependency mix.)

1. We need to integrate PyInstaller to generate:
* Application binaries for both CLI (src/yaamt.py) and GUI (src/yaamt-gui.py) for Windows, MacOS, Linux, and BSD
* An `.app` package for MacOS
* An `.msi` installer for Windows
* A `.deb` installer for debian linux variants

2. Builds should be labelled with their version, which should be dynamically generated from a release tag and short form of the last revision. This version number should be displayed in any packages generated, as well as in the CLI and the About window of the GUI.
