# Project AGENTS.md Guide for AI Agents (OpenAI Codex, Roo Code, Cline, Claude Code, etc)

This document describes this codebase, and outlines the coding conventions and architectural patterns used in its
development, 
All AI-generated code must adhere to these guidelines to ensure consistency, readability, and maintainability.

This codebase is a Python project. The project utilizes PySide6 for its graphical user interface (GUI), `mutagen` for handling audio metadata, and `cx_freeze` for packaging the application into standalone executables.

This document is written following the AGENTS.md spec located at https://ampcode.com/AGENT.md

## About this project

This project implements an audio file metadata manager, through a few primary components:

* A Python class ("MediaFile") that is responsible for reading and writing metadata (ID3, ACID, etc) to a single media file. This class represents a single media file (for now we are focusing on audio files only -- WAV/MP3/FLAC/etc). It should have internal fields representing all of the major kinds of metadata that describe a media file, such as title, artist, album, and so on. (Refer to the ID3 specification as needed.) In particular, we need to have fields for storing BPM and musical key.
* A command-line Python entrypoint that uses MediaFile to interact with, analyze, and edit metadata on media files requested by the user. It should support operating on both a single file or a directory of files.
* A user interface, written in PySide6, that implements a file+directory browser. This component also uses MediaFile to both display metadata to the user (as configurable columns in the file browser), and to interact with, analyze, and edit metadata on behalf of the user.

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
  the user. Please minimize any sycophancy.
* While your writing should be lively and easy to read, please avoid the use of emoji, generational slang, profanity,
  and/or cuteness. Emoji are permitted in an explanatory or illustrative context, but should not be used decoratively.
* While you are free to point out genuinely good ideas, do not blindly agree with or praise the user. Instead, encourage
  them to continue that line of thinking, and provide thought-provoking questions or supportive context where
  appropriate.
* On the other hand, please point out bad ideas by providing the user with constructive criticism, alternate strategies,
  and thought-provoking questions.
* When the user's wishes specifically contradict the points listed above, always defer to the user's wishes.
* Always remember why we are here: to build great software!
* When prompted to do something, do not hesistate to ask exploratory questions or clarifying details before beginning
  work. Always prefer ironing out details earlier rather than later or mid-process.
  Here are the updated instructions for the AI agent, now including best practices for utilizing the `mutagen` library.

### Project Initialization and Structure

The agent shall adhere to a structured project layout to ensure maintainability and scalability.

**Recommended Project Structure:**

```
project_name/
├── src/
│   ├── models/
│   │   └── media_file.py
│   ├── providers/
│   │   ├── metadata/
│   │   │   ├── base.py
│   │   │   └── mutagen_provider.py
│   │   └── media_file.py
│   ├── windows/
│   │   └── main_window.py
│   ├── workers/
│   ├── main.py
|   ├── gui.py
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

**Instructions for the AI Agent:**

1.  **Create the Boilerplate:** Upon project initiation, generate the directory structure as outlined above, including an `audio_metadata.py` file.
2.  **Virtual Environment:** Always work within a Python virtual environment to manage dependencies effectively. Activate the virtual environment before installing any packages.
3.  **Dependency Management:** Maintain a `requirements.txt` file listing all project dependencies.

    *Example `requirements.txt`*:
    ```
    PySide6
    cx_freeze
    mutagen
    ```

### Development Workflow with PySide6

The agent will follow these best practices when developing the PySide6 application.

**UI Development:**

*   **Qt Designer:** Utilize Qt Designer for creating and modifying UI files (`.ui`). This promotes a separation of the UI layout from the application's logic.
*   **UI File Compilation:** Employ the `pyside6-uic` tool to compile `.ui` files into Python source code. The compiled UI file should be placed within the `app` directory.
  *   **Command:** `pyside6-uic ui/main_window.ui -o src/app/ui_main_window.py`
*   **UI Integration:** The generated UI class should be inherited by the main application window class to integrate the UI elements.

**Resource Management:**

*   **Resource Files:** Manage application resources such as icons and images using Qt's resource system (`.qrc` files).
*   **Resource Compilation:** Use `pyside6-rcc` to compile `.qrc` files into a Python module.
  *   **Command:** `pyside6-rcc resources/resources.qrc -o src/resources_rc.py`
*   **Resource Usage:** Import the compiled resource module in the application to access the resources.

**Application Logic:**

*   **Model-View-Controller (MVC):** For complex applications, structure the code following the MVC pattern.
*   **Threading:** To prevent the GUI from becoming unresponsive during long-running tasks, execute them in separate threads (`QThread`). **This is critical for file I/O operations.**
*   **Signals and Slots:** Use Qt's signals and slots mechanism for communication between components.

### Working with `mutagen` for Audio Metadata

The agent will handle all audio file metadata operations using the `mutagen` library, following these best practices to ensure a responsive and robust application.

*   **Non-Blocking Operations:** All file reading and writing operations with `mutagen` are potential blocking calls that can freeze the GUI. **Always perform `mutagen.File()` loading and `audio.save()` calls on a separate `QThread`**. Use signals to communicate the results (the metadata or success/failure status) back to the main UI thread for display.
*   **Graceful Error Handling:** Wrap calls to `mutagen.File()` in a `try...except` block to handle potential errors, such as `FileNotFoundError` or `mutagen.MutagenError` (for corrupted or unsupported files). Report these errors to the user through dialog boxes or status bar messages.
*   **Unicode Support:** When writing metadata, always use Unicode strings to ensure compatibility across different operating systems and file formats.
*   **Handle Multi-Value Tags:** Be aware that `mutagen` returns tag values as a list (e.g., `['My Title']`) because most formats support multiple values per tag. Your code should always anticipate a list, even for tags that typically have a single value.
*   **Album Art Integration:** To display embedded album art, extract the binary data directly from the appropriate tag (e.g., `'APIC:'` for ID3). Load this data directly into a `QPixmap` using `pixmap.loadFromData(tag.data)`. This is highly efficient and avoids the need to save the image to a temporary file.

### Packaging with cx_freeze

The agent will use `cx_freeze` to create standalone executables. `mutagen` is a pure Python library with no external dependencies, so `cx_freeze` should be able to include it automatically without special configuration.

**`setup.py` Configuration:**

A `setup.py` file is required to configure the `cx_freeze` build process.

```python
import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# mutagen is a pure python package and should be detected automatically.
build_exe_options = {
    "packages": ["os", "sys", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
    "excludes": ["tkinter"],
    "include_files": ["resources/"],  # Include the entire resources directory
}

# base="Win32GUI" should be used on Windows for a GUI application
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="YourAppName",
    version="0.1",
    description="Your application description",
    options={"build_exe": build_exe_options},
    executables=[Executable("src/main.py", base=base, target_name="YourAppName")],
)
```

**Instructions for the AI Agent:**

1.  **`setup.py` Generation:** Create a `setup.py` file in the project root with the necessary configurations.
2.  **Dependency Handling:** While `cx_freeze` is excellent at auto-detection, explicitly list core PySide6 modules in the `packages` list to be safe. It is generally not necessary to add `mutagen` here.
3.  **Excluding Unnecessary Packages:** To reduce executable size, exclude unused libraries like `tkinter`.
4.  **Including Files and Directories:** Use the `include_files` option to bundle non-Python assets.
5.  **Platform-Specific Configuration:** Set the `base` to `"Win32GUI"` for Windows GUI applications.
6.  **Building the Executable:** Execute the build process using the command: `python setup.py build`.
7.  **Output:** The packaged application will be in the `build/` directory.
8.  **Installer Creation (Optional):** Use `bdist_msi` on Windows or `bdist_dmg` on macOS to create user-friendly installers.