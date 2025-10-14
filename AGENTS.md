# Project AGENTS.md Guide for AI Agents (OpenAI Codex, Roo Code, Cline, Claude Code, etc)

This document describes this codebase, and outlines code conventions and architectural patterns used in its
development. All code, AI-generated or not, must adhere to these guidelines to ensure consistency, readability, and maintainability.

This codebase is a Python project. It uses:
* `PySide6` for its graphical user interface (GUI), 
* `mutagen` for handling audio metadata, 
* `pytest` for testing,
* `cx_freeze` or `nuitka` for packaging the application into standalone executables.

This document is to follow the AGENTS.md spec at https://ampcode.com/AGENT.md

## About this project

This project implements an audio file metadata manager, through a few primary components:

* A Python class ("MediaFile") that is responsible for reading and writing metadata (ID3, ACID, etc) to a single media file. This class represents a single media file (for now we are focusing on audio files only -- WAV/MP3/FLAC/etc). It should have internal fields representing all of the major kinds of metadata that describe a media file, such as title, artist, album, and so on. (Refer to the ID3 specification as needed.) In particular, we need to have fields for storing BPM and musical key.
* A command-line Python entrypoint that uses MediaFile to interact with, analyze, and edit metadata on media files requested by the user. It should support operating on both a single file or a directory of files. (Entrypoint is `src/main.py`)
* A GUI that implements a file+directory browser. This component also uses MediaFile to both display metadata to the user (as configurable columns in the file browser), and to interact with, analyze, and edit metadata on behalf of the user. (Entrypoint is `src/gui.py`)

## AI-specific Considerations

* As an AI coding agent, your role is to assist the user, not entertain them.
* In all interactions, please adopt a serious, sober, and professional tone. Minimize sycophancy.
* Do not emoji, slang, profanity, or cuteness.
* While you are free to point out genuinely good ideas, do not blindly agree with or praise the user. Instead, encourage them to continue that line of thinking, and provide thought-provoking questions or supportive context where appropriate.
* Point out bad ideas by providing the user with constructive criticism, alternate strategies, and thought-provoking questions.
* When the user's wishes specifically contradict the points listed above, always defer to the user's wishes.
* When prompted to do something, ask exploratory questions and for clarifying details before beginning work. Always prefer addressing details earlier rather than later or mid-process.
* If asked to do something that relies on an assumption that is not true, explain why and ask for clarification.
* Always use context7 when code generation is needed, or for setup or configuration steps, or library/API documentation. This means you should automatically use the Context7 MCP tools to resolve library id and get library docs without me having to explicitly ask.

## Design Document Conventions

* Refer to the design specs in @docs/DESIGN.md and @docs/designs/ 
* Keep these documents concise and to-the-point. These documents may be passed to an AI agent, and it is important not to blow out their context window.
* Do not include Python code. All requirements must be articulated in plain English, a diagram, or SHORT pseudocode. Favor plain English or a diagram.
* Mention the epic that this design document came from just below the title.
* If details agreed-upon while writing the design document contradict the corresponding epic, update the epic with those details.
* The epic and the design document should be kept in sync.

## Code Conventions

* Refer to the design specs in @docs/DESIGN.md and @docs/designs/ 
* Keep your commits small; focus on a single change.
* Explain complicated logic using comments.
* When adding large systems, document them as a new markdown file in `docs/designs` if they are not already there.
* All interface changes, model changes, or changes that write data, must have test coverage and pass all checks in `pytest`.
* The `src/` directory is added to the system path. Imports should not attempt importing from `src`. (See the note under Testing)
* Logging should be done using `log`, which is provided by `util.logging`. 
* PySide6 has a bug where emitting a QT signal with a dict with non-string keys behaves unexpectedly. To work around this, if you must emit a dict with a signal, all keys inside of it must be strings. (See https://stackoverflow.com/questions/76579504/how-dose-pyside6-signal-emit-transfer-data-for-dictionary-data-why-the-behavio)
* Use type hints for all functions and methods. Use `Any` for any type that cannot be inferred.
* Libraries brought in must be able to be compiled into a standalone executable using `nuitka`.

## YAAMT Design Conventions

* Read a file's audio data using the stream interface provided by the `MediaFile` instance for that file. (`.get_audio_stream()`.) Do not call `AudioStreamFactory` directly.
* Read a file's metadata using the interface provided by the `MediaFile` instance for that file. (`.get_tags()`.) Do not use the underlying tagging library directly.
* Write a file's metadata using the interface provided by the `MediaFile` instance for that file. (`.set_tags()`.) Do not use the underlying tagging library directly.
* MetadataProviders have a two-tiered system for reading and writing metadata: 'generic' tags, which are single set of tag names referenced and used by most areas of the program. These map to a tagging library's 'internal' tags, which are the actual tags that are stored in the file determined by its metadata format. Always use 'generic' tags wherever possible.
* Do not pass around references to files as filepath strings. Your code should accept a `MediaFile` instance instead.

## AI-specific instructions

* Do not make assumptions about the interfaces -- look them up! Either by reading the file directly or referencing documentation through a websearch or the Context7 MCP that is provided to you.
* Break large edits up into smaller, bite-size chunks.
* At the end of a task:
  * Run the test suite to make sure that you did not break anything.
  * If all tests pass, ask to create a git commit if you are able to do so.
  * It is OK to leaves tests broken if your current changes are part of a larger task, but you need to make sure that all tests pass and changes have test coverage before the large task can be considered done.

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
*   **User Preferences:** Store user preferences using QSettings via model in `settings.py`

### Testing

A unit test suite (using pytest) can be found in `tests` in the project root.

* DO NOT WRITE TO THE TEST FIXTURES in `tests/fixtures`. Instead, copy the original file to a temporary location and perform your tests on that. THIS IS VERY IMPORTANT!
* Be extremely cautious about making edits to the program itself when fixing test failures. There is a lot of functionality in the GUI that is not easily tested, and you may break something outside the scope of your visibility.
* Tests requiring a QApplication object cannot be run in a Github runner and must be skipped in that case. To do so, `from util.const import IN_GITHUB_RUNNER` in your tests' header and add the `@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")` decorator to your test. These tests still need to pass locally.

#### Notes

When writing tests, please note that `conftest.py` in the `tests` directory adds the `src` directory to the system path. This means that you do not need to prefix imports with `src`. For example, to import the `MediaFile` class, you would use the following statement:

```python
from models.media_file import MediaFile
```

#### Running tests

`pytest` to run all tests or `pytest tests/test_my_test.py` to run tests in a specific file.