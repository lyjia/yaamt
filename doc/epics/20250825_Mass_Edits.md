The next set of changes are somewhat complicated and interrelated, but they all support workflows for editing and analyzing media file metadata. I want to make sure that the systems implementing these above features are congruent and harmonious with each other and that we have a solid architecture for expanding the system outwards. These objectives represent some significant changes and will be some of the most important features of this program.

The objectives are as follows:

* Add a new edit-in-place feature to the file pane in MainWindow:
  * Double-clicking the value in a column should pop open a small textbox, showing the current value, and allow the user to make edits. 
  * The text inside the textbox should be highlighted when the textbox is opened. Once the textbox loses focus, or the user hits Enter, it should (optionally) persist the value that was entered into the appropriate metadata tag that that column represents. 
  * Note that this feature should only be available where the writer for the selected tag defines it as write-enabled. 

* Add a new feature called "Autosave" to MainWindow. 
  * The option to control this should be in the File menu, as a toggle labeled "Autosave", as well as a toggle in MainWindow's toolbar.
    * A "Commit Changes" action should be available from both the File menu and the toolbar
    * A "Reset changes" button should also be available, in the same spots as above, which clears staged changes and reverts the UI to show the original data. 
    * Both Commit and Reset options should only be enabled when Autosave is disabled and there are changes staged. Otherwise they should be disabled.
  * When autosave is enabled, 
    * changes to metadata in MainWindow, made with edit-in-place are immediately persisted to disk. 
    * changes to metadata in PropertiesWindow are persisted to disk only when the user hits "OK"
  * When autosave is disabled,
    * changes to metadata in MainWindow, made with edit-in-place are staged, and the values of tags with staged changes are shown in bold. 
    * changes to metadata in PropertiesWindow are staged when the user hits "OK", and those staged changes should appear as specified above in MainWindow (namely, bolded).
    * staged changes should only be written to disk when the user hits "Save".
  * If a save fails for some reason, changes that could not be persisted should continue to be staged. This can result in a "Save" action where some staged tags in some files are persisted to disk, while others are not.
  * If the user tries to quit the application and autosave is disabled, pop up a confirmation box confirming that they want to save before quitting (yes/no/cancel)
    * If the user hits "yes" this should be the same as hitting "Save". If that save fails do not exit the application and follow the save failure workflow above.

* Users should be able to select multiple files and edit tags en masse. 
  * This should be able to occur both in the file pane of MainWindow, or in PropertiesWindow: 
    * For MainWindow, the selected files should remain highlighted after the edit-in-place textbox appears and continue to be highlighted after editing is complete. The workflow for this should be otherwise identical to single-file edit-in-place, which each column edited highlighted if Autosave is disabled. 
    * For PropertiesWindow, there are two possibilities, based on whether values for a given tag differ between all files:
      * If they differ, text boxes should display "<< multiple values >>" slightly grayed-out. 
        * If the user wants to edit that tag in all files and clicks the textbox, then the textbox becomes blank and wait for input, then stage that change for all selected files; 
      * If they are all the same, it should display that value for editing.
        * Behavior here should have the same workflow as editing a single file.

* Build the foundations for a new feature called "analyzers": 
  * which are specialized modules that read the media file's data stream and produce some sort of metadata output. 
  * For example: a BPM detector or Musicbrainz ID detector. 
  * Analyzers will be implemented similar to Providers, in that there is a base class defining an interface and individual analyzers inherit from that base class. 
    * For performance reasons, I would prefer the audio streams only be stored in memory once, and that analyzers are passed a reference to read the stream as opposed to each analyzer reading it themselves. (What they do with it beyond that is beyond the scope of this objective.) 
  * Users activate analyzers through the right-click menu, the File menu, or dedicated toolbar buttons. 
  * We will also make an extremely simple 'analyzer', which will read the audio stream and return the peak volume level 

---
## Proposed Architecture and Implementation Plan

This section outlines the proposed architecture to implement the features described above, focusing on centralization of state, testability, and extensibility.

### 1. Core Architecture: The `EditManager` Singleton

To ensure a single, consistent source of truth for all metadata edits, we will introduce a new `EditManager` class, implemented as a singleton. This will centralize all edit-related state and logic, making it accessible and respected throughout the entire application.

*   **Singleton Implementation:** The `EditManager` will be instantiated as a single, module-level object (e.g., `from src.models import edit_manager`). All parts of the application (`MainWindow`, `PropertiesWindow`, etc.) will import and use this same instance.
*   **Responsibilities:**
    *   **State Management:** It will track the global "Autosave" mode (`True`/`False`).
    *   **Staging:** It will hold a dictionary of staged changes, structured as `{file_path: {tag_name: new_value}}`. This replaces the previous staging implementation within the `MediaFile` class.
    *   **Core API:** It will expose a clear API for managing edits:
        *   `stage_change(file_paths: list[str], tag: str, value: any)`
        *   `commit_changes()`
        *   `reset_changes()`
        *   `has_staged_changes() -> bool`
    *   **Signaling:** It will use Qt's signal/slot mechanism to notify the UI of state changes (e.g., `staged_changes_exist(bool)`), allowing UI components like buttons to be enabled or disabled automatically.

### 2. Refactoring and Integration

A key first step is to refactor existing code to use the new `EditManager`.

*   **`MediaFile` Simplification:** The `MediaFile` class will be refactored to remove all staging logic. It will revert to being a simple data object representing the **committed** state of a file's metadata.
*   **`PropertiesWindow` Update:** The `PropertiesWindow` will be modified to interact with the `EditManager` singleton instead of calling methods on `MediaFile` instances.

### 3. UI/UX Implementation Plan

With the backend logic centralized, UI components will primarily be responsible for presentation and delegating actions to the `EditManager`.

*   **In-Place Editing (`MainWindow`):**
    *   A custom `QStyledItemDelegate` will be implemented for the main table view to provide a `QLineEdit` for editing.
    *   The `MetadataModel` will be the intermediary:
        *   `flags()`: Will check if a tag is writable to determine if `Qt.ItemFlag.ItemIsEditable` should be returned.
        *   `data()`: Will query `edit_manager.get_staged_value(file, tag)` to show pending edits and will provide styling hints to visually distinguish them.
        *   `setData()`: Will receive the final value from the delegate and call `edit_manager.stage_change()`, applying the change to all selected files by querying the view's selection model.
*   **Mass Editing (`PropertiesWindow`):**
    *   The window will be initialized with a list of files.
    *   It will compare values for each tag across all files, displaying `<< multiple values >>` if they differ.
    *   Any edits made in the window will be applied to all files by calling `edit_manager.stage_change()`.

### 4. Analyzer Framework

We will build a new, extensible framework for file analysis modules.

*   **Architecture:**
    *   A new directory, `src/analyzers/`, will house all analyzer plugins.
    *   A `BaseAnalyzer` abstract class in `src/analyzers/base.py` will define the interface with a single method: `analyze(audio_stream: io.BytesIO) -> dict`.
    *   An `AnalyzerManager` class will handle the discovery and execution of available analyzers.
*   **Execution Flow:**
    *   Analysis will be performed on a background `QThread` to keep the UI responsive.
    *   The worker thread will read the audio file into an in-memory `io.BytesIO` stream **once**.
    *   This stream is passed to the analyzer's `analyze()` method.
    *   The resulting metadata dictionary is then passed to `edit_manager.stage_change()` to be staged like any other edit.

### 5. Testing Strategy

A rigorous, test-driven approach is essential to protect user data and ensure stability.

*   **`EditManager` First:** A comprehensive suite of unit tests for the `EditManager` class will be written *before* integration. These tests will validate all state management, staging, committing, and resetting logic.
*   **Refactoring with Tests:** Existing tests for `MediaFile` and `PropertiesWindow` will be adapted during the refactoring process. The goal is for the test suite to continue passing, verifying that the new architecture is a correct replacement for the old one.
*   **New Feature Tests:** All new features (in-place editing, mass-edit workflows, each new analyzer) will be developed with dedicated unit and integration tests.