# YAAMT - Yet Another Audio Metadata Tool

<img src="doc/YAAMT_logo.png" alt="YAAMT Logo">

YET ANOTHER powerful, flexible tool for managing audio file metadata, designed for DJs, music producers, and audiophiles.

## Description

YAAMT intends to be a complete music information system for viewing, editing, and analyzing metadata in various audio file formats. Users can choose between a GUI or command-line interface, and use it to manage, analyze, and edit metadata for single files or entire directories of audio files.

The tool is built with Python, using PySide6 for the GUI and the `mutagen` library for robust metadata manipulation.

## Features

-   **Format Agnostic:** Works with a wide range of audio formats (MP3, FLAC, WAV, etc.).
-   **GUI and CLI:** Choose between an intuitive graphical interface or a powerful command-line tool.
-   **Metadata Editing:** Edit common tags like title, artist, album, track number, genre, and more.
-   **Advanced Metadata:** Specialized support for DJ-centric metadata, including BPM (Beats Per Minute) and musical key (with Camelot notation support).
-   **Batch Processing:** Operate on single files or entire directories.
-   **Metadata Analysis:** Analyze audio files to generate metadata like BPM and key.
-   **Audio Playback:** A simple built-in player to preview audio files.

## Installation (from binaries)

Binary builds are currently a work-in-progress. Check back soon for updates!

## Installation (from source code)

This project currently requires a working Python 3.12 (or greater) installation. It is recommended to use a virtual environment.

The following commands will install the project and its dependencies on Linux or macOS:
```bash
git clone git@github.com:lyjia/yaamt.git
cd yaamt
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use `.\.venv\Scripts\activate` instead of `source .venv/bin/activate` in the above sequence.

## Usage

In all usecases, it is best to activate the virtual environment before running the application.

Linux/macOS:
```bash
cd yaamt
source .venv/bin/activate
```

Windows:
```powershell
cd yaamt
.venv\Scripts\activate
```

### GUI Mode

To launch the graphical user interface, run:

```bash
python src/gui.py
```

### Command-Line Usage

The command-line interface provides powerful options for scripting and batch processing. YAAMT CLI supports three main commands: `read`, `write`, and `analyze`.

#### Getting Help

**Top-level help:**
```bash
python src/main.py --help
```

**Help for specific commands:**
```bash
python src/main.py help read
python src/main.py help write
python src/main.py help analyze
```

**List available analyzers:**
```bash
python src/main.py list analyzers
```

**List analyzers by category:**
```bash
python src/main.py list analyzers --category bpm
python src/main.py list analyzers --category key
```

**Get help on a specific analyzer:**
```bash
python src/main.py analyze StubBPMAnalyzer --help
```

#### Reading Metadata

The `read` command displays metadata from audio files. It supports multiple output formats: `list` (detailed view), `table` (columnar), `csv`, and `json`.

**Display metadata for a single file (detailed list format):**
```bash
python src/main.py read "path/to/audio.mp3" -f list
```

**Display metadata for multiple files (table format with separated directory/filename columns):**
```bash
python src/main.py read "path/to/folder/*.mp3" -f table
```

**Show only specific tags:**
```bash
python src/main.py read "path/to/audio.mp3" --tags title,artist,album,bpm
```

**Export metadata from a folder to CSV:**
```bash
python src/main.py read "path/to/folder/*.mp3" -f csv -o metadata.csv
```

**Export metadata to JSON:**
```bash
python src/main.py read "path/to/folder/*.mp3" -f json -o metadata.json
```

**Recursively scan subdirectories:**
```bash
python src/main.py read "path/to/folder" -R --tags title,artist,bpm -f table
```

#### Writing Metadata

The `write` command modifies metadata tags on audio files. You can use either the generic `--tag` option or convenient shortcut parameters for common tags.

**Using shortcut parameters (recommended for common tags):**
```bash
python src/main.py write --title "New Song Title" --artist "Artist Name" "path/to/audio.mp3"
```

**Using the generic --tag option:**
```bash
python src/main.py write --tag "title=New Song Title" --tag "artist=Artist Name" "path/to/audio.mp3"
```

**Available shortcut parameters:**
- `--title`, `--artist`, `--album`, `--albumartist`
- `--tracknumber`, `--tracktotal`, `--discnumber`, `--disctotal`
- `--genre`, `--date`, `--year`, `--composer`
- `--bpm`, `--initial_key` (musical key)
- `--comment`, `--grouping`, `--mood`
- `--isrc`, `--language`, `--encodedby`

**Mass-write album tag to all files in a folder (e.g., for an album):**
```bash
python src/main.py write --album "My Album Name" "path/to/album/*.mp3"
```

**Write multiple tags at once using shortcuts:**
```bash
python src/main.py write \
  --title "Song Title" \
  --artist "Artist Name" \
  --album "Album Name" \
  --tracknumber 1 \
  "path/to/audio.mp3"
```

**Recursively update all files in a directory tree:**
```bash
python src/main.py write --albumartist "Various Artists" "path/to/folder" -R
```

#### Analyzing Files

The `analyze` command runs audio analysis algorithms to detect BPM, musical key, loudness, and more.

**Analyze a single file for BPM and write to file metadata:**
```bash
python src/main.py analyze StubBPMAnalyzer "path/to/audio.mp3" -w
```

**Analyze a whole folder for musical key and output to CSV report:**
```bash
python src/main.py analyze WaveletKeyAnalyzer "path/to/folder/*.mp3" -f csv -o key_report.csv
```

**Analyze files without writing to metadata (display results only):**
```bash
python src/main.py analyze MultibandSpectralBPMAnalyzer "path/to/audio.mp3" -f table
```

**Skip files that already have values (useful for partial processing):**
```bash
python src/main.py analyze StubBPMAnalyzer "path/to/folder/*.mp3" -w --skip-if-tag-exists
```

**Analyze with custom analyzer options:**
```bash
python src/main.py analyze AubioBPMAnalyzer "path/to/audio.mp3" -w --method default --buf-size 1024
```

**Available Analyzers:**
- `StubBPMAnalyzer` - Fast testing analyzer (returns fixed BPM value)
- `AubioBPMAnalyzer` - BPM detection using aubio library
- `MultibandSpectralBPMAnalyzer` - Advanced BPM detection using multiband spectral analysis
- `WaveletKeyAnalyzer` - Musical key detection using wavelet transforms
- `PeakMeterAnalyzer` - Audio loudness/peak level measurement

For a complete list of available analyzers and their options:
```bash
python src/main.py list analyzers
python src/main.py analyze <AnalyzerName> --help
```

## Contributing

### Development Setup

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

### Contributor Instructions

Contributions are welcome! If you'd like to contribute, please follow these steps:

1. Fork the repository.
1. Checkout the `development` branch. (`git checkout development`)
1. Read AGENTS.md for guidelines on code style and convention. Please adhere to existing architecture. This is **VERY IMPORTANT!!!**
1. Create a new branch (`git checkout -b feature/your-feature-name`) from `development` branch.
1. Make your changes. Do not forget to follow code conventions, and make sure you update documentation and the test suite as needed.
1. Commit your changes (`git commit -m 'Add some feature'`).
1. Push to the branch (`git push origin feature/your-feature-name`).
1. Open a pull request. 
    1. *ALL PULL REQUESTS MUST BE BASED FROM DEVELOPMENT BRANCH!* Do NOT base them from `master`!
    1. All tests must pass!

**If a pull request does not meet the above requirements, it will be kicked back to you or closed.**

Also, this is a side project for me, so I may not be able to respond to pull requests immediately. Your patience is appreciated.

### Building Binaries from Source

This application uses Nuitka (for Windows and Linux) or cx_Freeze (for macOS) to package binaries for supported platforms. Build artifacts will be output to `build/`.

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

Once dependencies are installed, you can build statically-linked binaries for your platform by running:

```bash
python build.py
```

This will:
- Detect your platform and architecture
- Build the application using the appropriate build tool (Nuitka or cx_Freeze)
- Output finished build artifacts to the `build/` directory

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

### Creating Installers

Installer builds are currently disabled during the Nuitka transition. The following installer types will be re-enabled in a future release:
- Windows: MSI installers
- macOS: DMG disk images
- Linux: DEB packages

## License

This project is licensed to you under the terms of the GNU General Public License version 3. Please see `LICENSE.md` for more information.

All original content is copyright 2025 by Lyjia. All rights reserved.