# Project AGENTS.md Guide for AI Agents (OpenAI Codex, Roo Code, Cline, Claude Code, etc)

This document describes this codebase, and outlines the coding conventions and architectural patterns used in its
development, 
All AI-generated code must adhere to these guidelines to ensure consistency, readability, and maintainability.

This codebase is a Python project. The project utilizes PySide6 for its graphical user interface (GUI), `mutagen` for handling audio metadata, and `cx_freeze` for packaging the application into standalone executables.

This document is written following the AGENTS.md spec located at https://ampcode.com/AGENT.md

## About this project

This project implements an audio file metadata manager, through a few primary components:

* A Python class ("MediaFile") that is responsible for reading and writing metadata (ID3, ACID, etc) to a single media file. This class represents a single media file (for now we are focusing on audio files only -- WAV/MP3/FLAC/etc). It should have internal fields representing all of the major kinds of metadata that describe a media file, such as title, artist, album, and so on. (Refer to the ID3 specification as needed.) In particular, we need to have fields for storing BPM and musical key.
* A command-line Python entrypoint that uses MediaFile to interact with, analyze, and edit metadata on media files requested by the user. It should support operating on both a single file or a directory of files. (Entrypoint is `src/main.py`)
* A user interface, written in PySide6, that implements a file+directory browser. This component also uses MediaFile to both display metadata to the user (as configurable columns in the file browser), and to interact with, analyze, and edit metadata on behalf of the user. (Entrypoint is `src/gui.py`)

The goal is to give the user a format-agnostic metadata editor that can be used at the command-line or in a GUI. This metadata is then consumed and used in other software, such as FLStudio, Sound Forge, Serato, RekordBox, Foobar2000, and the like. It will primarily be a tool for DJs to intake new music and prepare the files' metadata to their specification.

In particular, we want the user to be able to perform the following (note that when we mention a MediaFile, we mean both a media file itself, a list of media files, or a directory of media files):

* Display the contents of a folder in a tabular format, as columns in the file browser (GUI only) 
* Destroy and recreate the metadata on a MediaFile
* Analyze the audio streams of a file and generate useful metadata, such as BPM, key, MusicBrainz ID, or an acoustic fingerprint.
* Edit specific metadata fields of a MediaFile, such as title, track, album, key, or bpm
* Seamlessly translate the contents of the key field between different representations for musical key, including Camelot notation
* Play back the MediaFile using a simple playback interface with Play, Pause/Stop, Volume, and Playback Position controls 

## Conversational style

* As an AI coding agent, remember that your role is to assist the user, not entertain them.
* In all interactions, please adopt a serious, sober, and professional tone, regardless of the communication style of
  the user. Please minimize any sycophancy. Please do not reassure the user of how good their plan or actions are.
* Please do not use of emoji, generational slang, profanity, and/or cuteness. Emoji are only permitted in an explanatory or illustrative context, but should not be used decoratively.
* While you are free to point out genuinely good ideas, do not blindly agree with or praise the user. Instead, encourage
  them to continue that line of thinking, and provide thought-provoking questions or supportive context where
  appropriate.
* On the other hand, please point out bad ideas by providing the user with constructive criticism, alternate strategies,
  and thought-provoking questions.
* When the user's wishes specifically contradict the points listed above, always defer to the user's wishes.
* Always remember why we are here: to build great software!
* When prompted to do something, do not hesistate to ask exploratory questions or clarifying details before beginning
  work. Always prefer ironing out details earlier rather than later or mid-process.

### Project Initialization and Structure

The agent shall adhere to a structured project layout to ensure maintainability and scalability.

**Simplified Project Structure:**

```
project_name/
├── src/
│   ├── models/                       # Data model modules, QT models, and Python data classes
│   │   └── media_file.py
│   ├── providers/                    # Provider services used by various parts of the program
│   │   ├── metadata/
│   │   │   ├── base.py
│   │   │   └── mutagen_provider.py
│   │   └── media_file.py
│   ├── util/                         # Utility modules
│   │   └── const.py                  # Program constants
│   ├── windows/                      # Various windows in the program
│   │   └── main_window.py            # The main window
│   ├── workers/
│   ├── main.py                       # Entrypoint for command-line operations
|   ├── gui.py                        # Entrypoint for accessing the desktop GUI
├── resources/
│   ├── icons/
│   │   └── app_icon.png
│   └── resources.qrc
├── tests/
│   ├── fixtures/
│   ├── __init__.py
│   └── test_main_window.py
├── setup.py
├── requirements.txt
└── README.md
```

### Development Workflow with PySide6

The agent will follow these best practices when developing the PySide6 application.

**Resource Management:**

*   **Resource Files:** Manage application resources such as icons and images using Qt's resource system (`.qrc` files).
*   **Resource Compilation:** Use `pyside6-rcc` to compile `.qrc` files into a Python module.
  *   **Command:** `pyside6-rcc resources/resources.qrc -o src/resources_rc.py`
*   **Resource Usage:** Import the compiled resource module in the application to access the resources.

**Application Logic:**

*   **Model-View-Controller (MVC):** For complex applications, structure the code following the MVC pattern.
*   **Threading:** To prevent the GUI from becoming unresponsive during long-running tasks, execute them in separate threads (`QThread`). **This is critical for file I/O operations.**
*   **Signals and Slots:** Use Qt's signals and slots mechanism for communication between components.


### Testing

When writing tests, please note that the `conftest.py` file in the `tests` directory adds the `src` directory to the system path. This means that you do not need to prefix imports with `src`. For example, to import the `MediaFile` class, you would use the following statement:

```python
from models.media_file import MediaFile
```
instead of：

```python
from src.models.media_file import MediaFile
```