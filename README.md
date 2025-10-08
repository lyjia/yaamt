# YAAMT - Yet Another Audio Metadata Tool

<img src="doc/YAAMT_logo.png" alt="YAAMT Logo">

A powerful and flexible tool for managing audio file metadata, designed for DJs, music producers, and audiophiles.

## Description

This application provides a comprehensive solution for viewing, editing, and analyzing metadata in various audio file formats. It features both a graphical user interface (GUI) for easy visual editing and a command-line interface (CLI) for scripting and batch operations.

The tool is built with Python, using PySide6 for the GUI and the `mutagen` library for robust metadata manipulation.

## Features

-   **Format Agnostic:** Works with a wide range of audio formats (MP3, FLAC, WAV, etc.).
-   **GUI and CLI:** Choose between an intuitive graphical interface or a powerful command-line tool.
-   **Metadata Editing:** Edit common tags like title, artist, album, track number, genre, and more.
-   **Advanced Metadata:** Specialized support for DJ-centric metadata, including BPM (Beats Per Minute) and musical key (with Camelot notation support).
-   **Batch Processing:** Operate on single files or entire directories.
-   **Metadata Analysis:** Analyze audio files to generate metadata like BPM and key.
-   **Audio Playback:** A simple built-in player to preview audio files.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/audio-metadata-tool.git
    cd audio-metadata-tool
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    sudo apt-get install -y libegl1 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 xvfb libxkbcommon-x11-0 portaudio19-dev alien
    pip install -r requirements.txt
    ```

## Usage

### GUI Mode

To launch the graphical user interface, run:

```bash
python src/gui.py
```

### Command-Line Usage

The command-line interface provides powerful options for scripting and batch processing.

#### Reading Metadata

To view all metadata for a specific file, use the `view` command:

```bash
python src/main.py view "path/to/your/audio.mp3"
```

#### Writing Metadata

You can write metadata in several ways:

**1. Using Shortcut Arguments**

For common tags, you can use dedicated shortcut arguments. For example, to set the title:

```bash
python src/main.py set --title "New Title" "path/to/your/audio.mp3"
```

**2. Using Generic Tag Arguments**

To update any standard metadata tag, use the `--update-tag` argument with a `KEY=VALUE` pair:

```bash
python src/main.py set --update-tag "ALBUM=New Album" "path/to/your/audio.mp3"
```

**3. Using Internal Tag Arguments**

For internal or non-standard tags, use the `--update-internal-tag` argument:

```bash
python src/main.py set --update-internal-tag "ENCODER=My Encoder" "path/to/your/audio.mp3"
```

For a full list of commands and options, use the help flag:
```bash
python src/main.py --help
```

## Contributing

Contributions are welcome! If you'd like to contribute, please follow these steps:

1. Fork the repository.
2. Checkout the `development` branch. (`git checkout development`)
3. Create a new branch (`git checkout -b feature/your-feature-name`) from `development` branch.
4. Make your changes.
5. Commit your changes (`git commit -m 'Add some feature'`).
6. Push to the branch (`git push origin feature/your-feature-name`).
7. Open a pull request. *ALL PULL REQUESTS MUST BE BASED FROM DEVELOPMENT BRANCH!* Do NOT base them from `master`!

Please make sure to update tests as appropriate.

**Failure to follow these steps may result in your pull request being rejected!**

## License

This project is licensed under the MIT License. (Note: A `LICENSE` file has not yet been created).

## Building from Source

This application uses cx_freeze to package binaries and installers for supported platforms. Build artifacts will be output to `build/`.

To build the application from source, you can use the following commands:

### All Platforms (basic binary build)

```bash
python setup.py build
```
This command builds the application executables for your current platform.

### Windows
```bash
python setup.py bdist_msi
```
This command creates a Windows installer (.msi) package for distribution on Windows systems.

UPDATED FOR NUITKA:
```
nuitka --mingw64 --clang --onefile --standalone  .\src\main.py
nuitka --mingw64 --clang --onefile --standalone --plugin-enable=pyside6 --include-module=cffi --follow-imports .\src\gui.py # note- `--windows-icon-from-ico=resources/icons/app-icon-gui.png` seems to break the build
```

### MacOS
```bash
python setup.py bdist_dmg
```
This command creates a macOS disk image (.dmg) for distribution on macOS systems.

UPDATED FOR NUITKA:
```
nuitka --macos-create-app-bundle --macos-app-icon=resources/icons/app-icon-cmd.png --standalone --onefile src/main.py
nuitka --macos-create-app-bundle --macos-app-icon=resources/icons/app-icon-gui.png --standalone --onefile --enable-plugin=pyside6 --include-module=cffi --follow-imports src/gui.py **broken** 
```

### Linux (Debian & Derivatives)
```bash
python setup.py bdist_deb
```
This command creates a Debian package (.deb) for distribution on Debian-based Linux systems.

UPDATE FOR NUITKA:
```
nuitka --standalone --onefile src/main.py
nuitka --onefile --standalone --plugin-enable=pyside6 --include-module=cffi --follow-imports src/gui.py
```
