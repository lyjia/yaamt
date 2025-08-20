# Project AGENTS.md Guide for AI Agents (OpenAI Codex, Roo Code, Cline, Claude Code, etc)

This document describes this codebase, and outlines code conventions and architectural patterns used in its
development. All code, AI-generated or not, must adhere to these guidelines to ensure consistency, readability, and maintainability.

This codebase is a Python project. It uses:
* `PySide6` for its graphical user interface (GUI), 
* `mutagen` for handling audio metadata, 
* `pytest` for testing,
* `cx_freeze` for packaging the application into standalone executables.

This document is to follow the AGENTS.md spec at https://ampcode.com/AGENT.md

## About this project

This project implements an audio file metadata manager, through a few primary components:

* A Python class ("MediaFile") that is responsible for reading and writing metadata (ID3, ACID, etc) to a single media file. This class represents a single media file (for now we are focusing on audio files only -- WAV/MP3/FLAC/etc). It should have internal fields representing all of the major kinds of metadata that describe a media file, such as title, artist, album, and so on. (Refer to the ID3 specification as needed.) In particular, we need to have fields for storing BPM and musical key.
* A command-line Python entrypoint that uses MediaFile to interact with, analyze, and edit metadata on media files requested by the user. It should support operating on both a single file or a directory of files. (Entrypoint is `src/main.py`)
* A GUI that implements a file+directory browser. This component also uses MediaFile to both display metadata to the user (as configurable columns in the file browser), and to interact with, analyze, and edit metadata on behalf of the user. (Entrypoint is `src/gui.py`)

## AI Conversational style

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

## Code Conventions

* Refer to the design spec in `docs/DESIGN.md`
* Keep your commits small; focus on a single change.
* Explain complicated logic using comments.
* When adding large systems, document them as a new markdown file in `docs/designs`.
* All interface changes, model changes, or changes that write data, must have test coverage and pass all checks in `pytest`.
* All other changes should have test coverage where appropriate and reasonable. 
* The `src/` directory is added to the system path. Imports should not attempt importing from `src`. (See the note under Testing)
* 

## Project Structure
Adhere to the following structured project layout to ensure maintainability and scalability:

```
audio-metadata-tool/
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

Follow these best practices when developing the PySide6 application.

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

A unit test suite (using pytest) can be found in `tests` in the project root.

* DO NOT write to the test fixtures in `tests/fixtures`. Instead, copy the original file to a temporary location and perform your tests on that.

#### Notes

When writing tests, please note that `conftest.py` in the `tests` directory adds the `src` directory to the system path. This means that you do not need to prefix imports with `src`. For example, to import the `MediaFile` class, you would use the following statement:

```python
from models.media_file import MediaFile
```

#### Running tests

`pytest` to run all tests or `pytest tests/test_my_test.py` to run tests in a specific file.