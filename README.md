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
    Automatic dependency installation depends on the following package managers:
   * Windows: [Chocolatey](https://chocolatey.org/)
   * Linux (Debian derivatives only): [apt](https://linuxize.com/post/how-to-install-packages-on-ubuntu-20-04/)
   * macOS: [Homebrew](https://brew.sh/)

```bash
   python build.py --install-deps
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

This application uses Nuitka (for Windows and Linux) or cx_Freeze (for macOS) to package binaries for supported platforms. Build artifacts will be output to `build/`.

### Quick Build (Recommended)

The `build.py` script provides a streamlined build process for your current platform.

#### First-time Setup

Install dependencies before your first build:

```bash
python build.py --install-deps
```

This will:
- Detect your platform (Windows, Linux, or macOS)
- Detect your architecture (x64 or arm64)
- Install required system dependencies
- Install required Python dependencies (including build tools)

#### Building

Once dependencies are installed, build the application:

```bash
python build.py
```

This will:
- Detect your platform and architecture
- Build the application using the appropriate build tool (Nuitka or cx_Freeze)
- Output binaries to the `build/` directory

#### Build Script Options

```bash
python build.py --help                    # Show all options
python build.py --install-deps            # Install dependencies and exit (no build)
python build.py --archive                 # Create an archive of build artifacts
python build.py --version-name v1.0.0     # Specify version name for archive
python build.py --output-dir dist         # Specify custom output directory
python build.py --platform linux          # Override platform detection
python build.py --arch arm64              # Override architecture detection
```

#### Platform-Specific Build Details

**Windows:**
- Uses Nuitka with MinGW64
- Produces standalone executables: `main.exe` and `gui.exe`
- Build output: `build/nuitka-dist/`

**Linux:**
- Uses Nuitka
- Produces standalone executables: `main.bin` and `gui.bin`
- Build output: `build/nuitka-dist/`

**macOS:**
- Uses cx_Freeze (Nuitka support pending)
- Produces executables: `yaamt` and `yaamt-gui`
- Build output: `build/exe.*/`

### Manual Build (Advanced)

If you prefer to build manually or need more control:

#### Windows
```bash
pip install nuitka ordered-set zstandard
choco install ccache  # Optional but recommended
python -m nuitka --mingw64 --assume-yes-for-downloads --onefile --standalone src/main.py --output-dir=build/nuitka-dist
python -m nuitka --mingw64 --assume-yes-for-downloads --onefile --standalone --plugin-enable=pyside6 --include-module=cffi --follow-imports src/gui.py --output-dir=build/nuitka-dist
```

#### Linux
```bash
pip install nuitka ordered-set zstandard
sudo apt-get install -y ccache patchelf
nuitka --standalone --onefile src/main.py --output-dir=build/nuitka-dist
nuitka --onefile --standalone --plugin-enable=pyside6 --include-module=cffi --follow-imports src/gui.py --output-dir=build/nuitka-dist
```

#### macOS
```bash
pip install cx_freeze
brew install ccache portaudio
python setup.py build
```

### Creating Installers

Installer builds are currently disabled during the Nuitka transition. The following installer types will be re-enabled in a future release:
- Windows: MSI installers
- macOS: DMG disk images
- Linux: DEB packages
