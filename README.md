# YAAMT - Yet Another Audio Metadata Tool

<img src="doc/YAAMT_logo.png" alt="YAAMT Logo">

YET ANOTHER powerful, flexible tool for managing audio file metadata, designed for DJs, music producers, and audiophiles. 

Built with love (and AI) by [Lyjia](http://www.lyjia.us)! This is the music tag tool that I've always wanted!

**THIS PROGRAM IS INCOMPLETE AND UNDER HEAVY DEVELOPMENT. IT IS NOT YET READY FOR MOST USES. Please check back later!**

## Description

**YAAMT is a music information system** for viewing, editing, and analyzing various kinds of metadata (text like title/artist, BPM, musical key, etc.) for various audio file formats (MP3/FLAC/WAV etc.). It is inspired by programs like [TheGodfather](https://www.jtclipper.eu/thegodfather/), [MediaMonkey](https://www.mediamonkey.com/), and [RapidEvolution](https://github.com/djqualia/RapidEvolution3), as well as the MIS aspects of DJ software like [Serato](https://serato.com/) or [Rekordbox](https://rekordbox.com/en/). I am building it to manage my personal media collection, and tame the music intake workflow for my DJing by bringing everything under one roof.

Supports common audio formats like MP3, FLAC, and WAV. Additional formats will be added in the future!

YAAMT currently uses [mutagen](https://mutagen.readthedocs.io/en/latest/) for reading and writing metadata from ASF, FLAC, MP4, Monkey’s Audio, MP3, Musepack, Ogg Opus, Ogg FLAC, Ogg Speex, Ogg Theora, Ogg Vorbis, True Audio, WavPack, OptimFROG, and AIFF metadata. I intend to add support for more formats, such as ACID, in the future.

## Features

-   **Format Agnostic:** Works with a wide range of audio formats (MP3, FLAC, WAV, etc.).
-   **GUI and CLI:** Choose between an intuitive graphical interface or a powerful command-line tool.
-   **Metadata Editing:** Edit common tags like title, artist, album, track number, genre, and more.
-   **Advanced Metadata:** Specialized support for DJ-centric metadata, including BPM (Beats Per Minute) and musical key (with Camelot notation support).
-   **Batch Processing:** Operate on single files or entire directories.
-   **Metadata Analysis:** Analyze audio files to generate metadata like BPM and key.
-   **Audio Playback:** A simple built-in player to preview audio files.
-   **Update Notifications:** Optional, strictly opt-in check that tells you when a new release is available (never downloads or installs anything).

## Installation (from binaries)

Native installers for Windows (`.exe`), Linux (`.deb`/`.rpm`), and macOS (`.dmg`) are published on the [GitHub Releases page](https://github.com/lyjia/yaamt/releases) as they become available. Tagged releases carry stable builds; the rolling `nightly` prerelease tracks the latest development snapshot. See [doc/designs/installers.md](doc/designs/installers.md) for per-platform installation details and filesystem layout.

## Installation (from source code)

This project currently requires a working Python 3.12 (or greater) installation. It is recommended to use a virtual environment.

The following commands will install the project and its dependencies on Linux or macOS (assuming Python is installed):
```bash
git clone git@github.com:lyjia/yaamt.git
cd yaamt
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use `.\.venv\Scripts\activate` instead of `source .venv/bin/activate` in the above sequence.

### Alternate method

Alternatively, you can use the provided `build.py` to install dependencies with `--install-deps`. Note that this will also install build dependencies using your system package manager (chocolatey, apt, or brew):

```bash
git clone git@github.com:lyjia/yaamt.git
cd yaamt
python -m venv .venv
source .venv/bin/activate
python build.py --install-deps
```


## Usage

Convenience scripts are provided in the repository root:
- `yaamt.sh` / `yaamt.bat` - Command-line interface
- `yaamt-gui.sh` / `yaamt-gui.bat` - Graphical interface
- `yaamt-eval.sh` / `yaamt-eval.bat` - Analyzer evaluation tool

These automatically use the virtual environment and are shorthand for running the corresponding Python scripts in `src/`.

**Note:** On Linux/macOS, make the shell scripts executable first: `chmod +x yaamt.sh yaamt-gui.sh yaamt-eval.sh`

### GUI Mode

To launch the graphical user interface, you can use the convenience scripts:

```bash
./yaamt-gui.sh      # Linux/macOS
.\yaamt-gui.bat     # Windows
```

Or start `yaamt-gui.py` directly, from this project's root folder:

```bash
python src/yaamt-gui.py
```

### Command-Line Usage

The command-line interface provides powerful options for scripting and batch processing. YAAMT CLI supports three main commands: `read`, `write`, and `analyze`.

#### Getting Help

**Top-level help:**
```bash
./yaamt.sh --help
```

**Help for specific commands:**
```bash
./yaamt.sh help read
./yaamt.sh help write
./yaamt.sh help analyze
```

**List available analyzers:**
```bash
./yaamt.sh list analyzers
```

**List analyzers by category:**
```bash
./yaamt.sh list analyzers --category bpm
./yaamt.sh list analyzers --category key
```

**Get help on a specific analyzer:**
```bash
./yaamt.sh analyze AubioBPMAnalyzer --help
```

#### Reading Metadata

The `read` command displays metadata from audio files. It supports multiple output formats: `list` (detailed view), `table` (columnar), `csv`, and `json`.

**Display metadata for a single file (detailed list format):**
```bash
./yaamt.sh read "path/to/audio.mp3" -f list
```

**Display metadata for multiple files (table format with separated directory/filename columns):**
```bash
./yaamt.sh read "path/to/folder/*.mp3" -f table
```

**Show only specific tags:**
```bash
./yaamt.sh read "path/to/audio.mp3" --tags title,artist,album,bpm
```

**Export metadata from a folder to CSV:**
```bash
./yaamt.sh read "path/to/folder/*.mp3" -f csv -o metadata.csv
```

**Export metadata to JSON:**
```bash
./yaamt.sh read "path/to/folder/*.mp3" -f json -o metadata.json
```

**Recursively scan subdirectories:**
```bash
./yaamt.sh read "path/to/folder" -R --tags title,artist,bpm -f table
```

#### Writing Metadata

The `write` command modifies metadata tags on audio files. You can use either the generic `--tag` option or convenient shortcut parameters for common tags.

**Using shortcut parameters (recommended for common tags):**
```bash
./yaamt.sh write --title "New Song Title" --artist "Artist Name" "path/to/audio.mp3"
```

**Using the generic --tag option:**
```bash
./yaamt.sh write --tag "title=New Song Title" --tag "artist=Artist Name" "path/to/audio.mp3"
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
./yaamt.sh write --album "My Album Name" "path/to/album/*.mp3"
```

**Write multiple tags at once using shortcuts:**
```bash
./yaamt.sh write \
  --title "Song Title" \
  --artist "Artist Name" \
  --album "Album Name" \
  --tracknumber 1 \
  "path/to/audio.mp3"
```

**Recursively update all files in a directory tree:**
```bash
./yaamt.sh write --albumartist "Various Artists" "path/to/folder" -R
```

#### Analyzing Files

The `analyze` command runs audio analysis algorithms to detect BPM, musical key, loudness, and more.

**Analyze a single file for BPM and write to file metadata:**
```bash
./yaamt.sh analyze AubioBPMAnalyzer "path/to/audio.mp3" -w
```

**Analyze a whole folder for musical key and output to CSV report:**
```bash
./yaamt.sh analyze RE3WaveletKeyAnalyzer "path/to/folder/*.mp3" -f csv -o key_report.csv
```

**Analyze files without writing to metadata (display results only):**
```bash
./yaamt.sh analyze RE3BPMAnalyzer "path/to/audio.mp3" -f table
```

**Skip files that already have values (useful for partial processing):**
```bash
./yaamt.sh analyze AubioBPMAnalyzer "path/to/folder/*.mp3" -w --skip-if-tag-exists
```

**Analyze with custom analyzer options:**
```bash
./yaamt.sh analyze AubioBPMAnalyzer "path/to/audio.mp3" -w --method default --buf-size 1024
```

**Available Analyzers:**

BPM Detection:
- `AubioBPMAnalyzer` - BPM detection using aubio library
- `RE3BPMAnalyzer` - Advanced BPM detection using RapidEvolution3 multiband spectral analysis (debug-only)
- `LibrosaBeatTrackingBPMAnalyzer` - BPM detection using librosa's beat tracking (debug-only)
- `StubBPMAnalyzer` - Fast testing analyzer returning fixed BPM (debug-only)

Musical Key Detection:
- `RE3WaveletKeyAnalyzer` - Musical key detection using RapidEvolution3 wavelet algorithm (debug-only)
- `LibrosaChromagramKeyAnalyzer` - Key detection using librosa chromagram and Krumhansl-Schmuckler algorithm (debug-only)

Loudness:
- `ReplayGainAnalyzer` - ReplayGain 2.0 (EBU R128, -18 LUFS) track + album gain via libebur128 / pyebur128
- `PeakMeterAnalyzer` - Audio peak level measurement in dBFS (debug-only)

**Note:** Analyzers marked as "debug-only" are available when running from source but are excluded from release builds to reduce dependencies and binary size.

For a complete list of available analyzers and their options:
```bash
./yaamt.sh list analyzers
./yaamt.sh analyze <AnalyzerName> --help
```

#### Evaluating Analyzer Performance

The `yaamt-eval` tool compares analyzer outputs against hand-reviewed reference data to measure accuracy. It supports evaluating both key detection (using MIREX scoring) and BPM detection (using custom absolute difference scoring).

**Launch the evaluator:**
```bash
./yaamt-eval.sh      # Linux/macOS
.\yaamt-eval.bat     # Windows
```

**Get help:**
```bash
./yaamt-eval.sh --help
./yaamt-eval.sh key --help
./yaamt-eval.sh bpm --help
```

**Evaluate key detection accuracy:**
```bash
./yaamt-eval.sh key \
  --reference path/to/reference.csv \
  --analysis path/to/key_analysis.csv \
  --output-dir results/
```

**Evaluate BPM detection accuracy:**
```bash
./yaamt-eval.sh bpm \
  --reference path/to/reference.csv \
  --analysis path/to/bpm_analysis.csv \
  --output-dir results/
```

**Evaluate multiple analyzers at once:**
```bash
./yaamt-eval.sh key \
  --reference reference.csv \
  --analysis analyzer1_results.csv analyzer2_results.csv analyzer3_results.csv \
  --output-dir results/
```

**Validate against audio directory (optional):**
```bash
./yaamt-eval.sh key \
  --reference reference.csv \
  --analysis results.csv \
  --audio-dir path/to/audio/files \
  --output-dir results/
```

**Scoring Systems:**

*Key Detection (MIREX):*
- Same key: 1.0 point
- Perfect fifth: 0.5 points
- Relative major/minor: 0.3 points
- Parallel major/minor: 0.2 points
- Other: 0.0 points

*BPM Detection (Custom Absolute Difference):*
- Exact (< 0.01 BPM): 1.0 point
- Nearly exact (< 0.02 BPM): 0.75 points
- Very close (< 0.1 BPM): 0.5 points
- Close (< 0.5 BPM): 0.25 points
- Other: 0.0 points

**Input Formats:**

*Reference CSV:* Consolidated dataset format with columns: `id, artist, title, mix, album, key, bpm, genre, datasets, output_filename`

*Analysis CSV:* Report format from YAAMT CLI with columns: `directory, filename, [AnalyzerName_field], status, error`

**Output Files:**

The evaluator generates two types of CSV reports:

1. **Summary CSV** (`eval_summary_{criteria}_{timestamp}.csv`): Aggregate statistics for all analyzers
2. **Detailed CSV** (`eval_{analyzer_name}_{criteria}_{timestamp}.csv`): Per-file results for each analyzer

### Checking for Updates

YAAMT can tell you when a newer release is available. It only notifies — it never downloads or installs anything on its own, and the startup check is **off by default** (no network calls happen unless you opt in).

- **GUI:** enable *Check for updates on startup* under **Preferences → General → Updates**. A manual check is always available via **Help → About → Check for updates**, regardless of the toggle.
- **CLI:** `./yaamt.sh --check-update`

Results are cached for 24 hours to stay friendly to the GitHub API. See [doc/designs/self_update.md](doc/designs/self_update.md) for the full design.

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

### Continuous Integration

CI runs on a self-hosted [Woodpecker CI](https://woodpecker-ci.org/) server; pipeline definitions live in `.woodpecker/`:

- **Pull requests** run lint + the full pytest suite. The status check to watch is `ci/woodpecker/pr/test`.
- **Pushes to `master`/`development`** additionally build installers and refresh the rolling `nightly` GitHub Release.
- **Tag pushes (`v*.*.*`)** build installers on all platforms and upload them to a versioned GitHub Release.

Pull requests from forks require maintainer approval before their pipeline runs on our hardware. See [doc/designs/ci.md](doc/designs/ci.md) for the full trigger matrix, agent provisioning steps, and security model.

### Building Binaries from Source

This application uses PyInstaller to package binaries for Windows, Linux, and macOS. Build artifacts will be output to `build/`. See [doc/designs/packaging.md](doc/designs/packaging.md) for the build system design.

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
- Build the application using PyInstaller
- Output finished build artifacts to a timestamped directory in `build/` (e.g., `build/debug-20251024-143022/`)

#### Build Script Options

```bash
python build.py --help                    # Show all options
python build.py --install-deps            # Install dependencies and exit (no build)
python build.py --release                 # Build a release version (excludes debug-only analyzers)
python build.py --release --installer     # Build and package a native installer (see "Creating Installers")
python build.py --clean                   # Clean up old timestamped build directories
python build.py --archive                 # Create an archive of build artifacts
python build.py --version-name v1.0.0     # Override version stamp in archive/installer names
                                          # (defaults to the git-derived version)
python build.py --output-dir dist         # Specify custom output directory
python build.py --platform linux          # Override platform detection
python build.py --arch arm64              # Override architecture detection
```

#### Versioning

Version strings are derived from git tags — there is no version constant to edit by hand. Tag a release as `v<major>.<minor>.<patch>`:

- A build on the tag itself reports `0.3.0`.
- A build N commits past the tag reports `0.3.0+5.<short-hash>`; a dirty working tree appends `.dirty`.
- Anything containing a `+` is by definition not a release build.

The build system stamps this string into the binary automatically, and `yaamt --version` / the About window report it at runtime. See [doc/designs/versioning.md](doc/designs/versioning.md) for the format rules, and [doc/RELEASING.md](doc/RELEASING.md) for the release workflow.

#### Platform-Specific Build Details

All platforms use PyInstaller, driven by `yaamt.spec`. Build output is a directory `build/<mode>-YYYYMMDD-HHMMSS/yaamt/` containing both the CLI and GUI executables.

**Windows:** produces `yaamt.exe` and `yaamt-gui.exe`.
**Linux / macOS:** produces `yaamt` and `yaamt-gui`.

**Note:** Build directories are timestamped to allow multiple builds to coexist. Use `python build.py --clean` to remove old build directories.

#### Generating Platform-Specific Application Icons

YAAMT uses the source icon file `resources/icons/app-icon-gui.png` for the application icon. Different platforms require different icon formats for optimal display:

**Linux:**
- Uses PNG format directly ✓
- The existing `app-icon-gui.png` works without conversion

**Windows:**
- Requires `.ico` format containing multiple resolutions
- To generate `app-icon-gui.ico` from the PNG source:

```bash
# Using ImageMagick (recommended):
convert resources/icons/app-icon-gui.png \
  -define icon:auto-resize=256,128,64,48,32,16 \
  resources/icons/app-icon-gui.ico

# Alternative using Python Pillow:
python -c "from PIL import Image; img = Image.open('resources/icons/app-icon-gui.png'); img.save('resources/icons/app-icon-gui.ico', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])"
```

**macOS:**
- Requires `.icns` format containing multiple resolutions
- To generate `app-icon-gui.icns` from the PNG source:

```bash
# Create iconset directory
mkdir -p app-icon-gui.iconset

# Generate all required sizes using sips (macOS built-in tool)
sips -z 16 16     resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_16x16.png
sips -z 32 32     resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_16x16@2x.png
sips -z 32 32     resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_32x32.png
sips -z 64 64     resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_32x32@2x.png
sips -z 128 128   resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_128x128.png
sips -z 256 256   resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_128x128@2x.png
sips -z 256 256   resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_256x256.png
sips -z 512 512   resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_256x256@2x.png
sips -z 512 512   resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_512x512.png
sips -z 1024 1024 resources/icons/app-icon-gui.png --out app-icon-gui.iconset/icon_512x512@2x.png

# Convert iconset to icns
iconutil -c icns app-icon-gui.iconset -o resources/icons/app-icon-gui.icns

# Clean up
rm -rf app-icon-gui.iconset
```

**Icon Requirements Summary:**
- **Source file (all platforms):** `resources/icons/app-icon-gui.png` ✓ Included
- **Windows builds:** `resources/icons/app-icon-gui.ico` (needs generation)
- **macOS builds:** `resources/icons/app-icon-gui.icns` (needs generation)
- **Linux builds:** Uses PNG directly ✓

The application will build successfully without platform-specific icons, but will display a default icon instead. For production builds, generate the appropriate icon format for your target platform.

### Creating Installers

Native installers are produced from the PyInstaller output with a single command on each platform:

```bash
python build.py --release --installer
```

| Platform | Output | Requires |
|---|---|---|
| Windows | `yaamt-<version>-windows-<arch>-setup.exe` | [Inno Setup 6](https://jrsoftware.org/isdl.php) (`iscc` on PATH) |
| Linux | `.deb` and `.rpm` packages | [nfpm](https://nfpm.goreleaser.com/install/) |
| macOS | `yaamt-<version>-macos-<arch>.dmg` | `create-dmg` (`brew install create-dmg`) |

Installers land in the same timestamped `build/release-*/` directory as the build output. Installer configs live in `installer/`. See [doc/designs/installers.md](doc/designs/installers.md) for per-platform details and the installed filesystem layout, and [doc/RELEASING.md](doc/RELEASING.md) for how releases are cut and published.

### Releasing

Releases are cut by pushing a `v<major>.<minor>.<patch>` tag; CI builds installers for every platform and publishes them to GitHub Releases. Nightly development builds are refreshed automatically on every push to `master`/`development`. The complete maintainer playbook — including hotfixes, manual/offline publishing, and recovering from a botched release — is in [doc/RELEASING.md](doc/RELEASING.md).

## License

This project is licensed to you under the terms of the GNU General Public License version 3. Please see `LICENSE.md` for more information.

All original content is copyright 2025 by Lyjia. All rights reserved.
