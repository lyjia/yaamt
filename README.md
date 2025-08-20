# Audio Metadata Tool

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