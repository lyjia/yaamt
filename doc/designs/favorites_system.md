# Favorites System Design Specification

## Overview

This document outlines the design for a system that allows users to save, manage, and quickly navigate to their favorite folders. This feature will enhance user workflow by providing one-click access to frequently used directories.

## Epic

This design addresses the epic: [20251118_Implement_Favorites.md](../epics/20251118_Implement_Favorites.md)

## Data Model

The favorites will be stored in the application's settings. A new dataclass will be added to [`src/models/settings.py`](src/models/settings.py) to manage this data.

### `Favorite` Dataclass

A simple dataclass to represent a single favorite location.

```python
# In src/models/settings.py

@dataclass
class Favorite:
    """Represents a single favorite location."""
    path: str
```

### `FavoritesSettings` Dataclass

This dataclass will be added to the main `Settings` class to hold the list of favorites.

```python
# In src/models/settings.py

@dataclass
class FavoritesSettings:
    """Stores settings related to user favorites."""
    locations: List[Favorite] = field(default_factory=list)

# In the main Settings dataclass
@dataclass
class Settings:
    """Stores the main application settings."""
    file_list: FileListSettings = field(default_factory=FileListSettings)
    general: GeneralSettings = field(default_factory=GeneralSettings)
    analyzers: AnalyzerSettings = field(default_factory=AnalyzerSettings)
    favorites: FavoritesSettings = field(default_factory=FavoritesSettings) # New addition
```

### Persistence

The favorites will be persisted in the `QSettings` store under the group `Favorites`. The data will be stored as a list of strings (paths).

**QSettings Keys**:
- `Favorites/locations`: A list of folder paths.

## UI Implementation

The favorites functionality will be accessible from two locations in the main window, as described in the epic. These changes will be implemented in [`src/windows/main_window.py`](src/windows/main_window.py).

### 1. Toolbar Button

-   A `QToolButton` will be added to the main toolbar, positioned to the left of the `path_textbox`.
-   The button will display a "heart" icon (`SP_FavoriteIcon` or a custom resource).
-   It will have a `QMenu` attached, which will be dynamically generated.
-   The button's `popupMode` will be set to `QToolButton.MenuButtonPopup` to indicate it has a dropdown menu.

### 2. Menu Bar Entry

-   A new top-level menu named "&Favorites" will be added to the main menu bar.
-   This menu will be an instance of the same `QMenu` used by the toolbar button, ensuring consistency.

### Dynamic Favorites Menu (`_create_favorites_menu`)

A private method, `_create_favorites_menu`, will be responsible for creating and populating the favorites menu. This method will be called to build the menu whenever it is about to be shown.

The menu structure will be as follows:

1.  **Favorite Locations**:
    -   The list of saved favorites will be retrieved from the `Settings` model.
    -   The list will be sorted alphabetically by path.
    -   For each favorite, a `QAction` will be created with the path as its text.
    -   Each action's `triggered` signal will be connected to a slot that navigates to the associated path (`self.set_path(path)`).

2.  **Separator**: A separator will be added after the list of favorites.

3.  **"Add Favorite..." Action**:
    -   A `QAction` with the text "Add Favorite...".
    -   Its `triggered` signal will be connected to a slot (`_on_add_favorite`) that adds the current directory to the favorites list.

4.  **"Remove Favorite" Submenu**:
    -   A `QMenu` with the title "Remove Favorite".
    -   This submenu will be populated with the list of saved favorites (alphabetically sorted).
    -   Each favorite in the submenu will be a `QAction` connected to a slot (`_on_remove_favorite`) that prompts the user for confirmation and then removes the selected favorite.

## User Workflow

### Adding a Favorite

1.  The user navigates to a desired folder.
2.  The user opens the Favorites menu (from the toolbar or menu bar) and clicks "Add Favorite...".
3.  The application retrieves the current path from `self._current_path`.
4.  It checks if the path is already in the favorites list and if the maximum number of favorites (25) has been reached.
5.  If the path can be added, it is appended to the `settings.favorites.locations` list, and the settings are saved.
6.  The favorites menu is rebuilt to reflect the change.

### Removing a Favorite

1.  The user opens the Favorites menu and navigates to the "Remove Favorite" submenu.
2.  The user clicks on the path they wish to remove.
3.  A `QMessageBox.question` dialog appears, asking for confirmation: "Are you sure you want to remove this favorite?".
4.  If the user confirms, the selected path is removed from `settings.favorites.locations`, and the settings are saved.
5.  The favorites menu is rebuilt.

### Navigating to a Favorite

1.  The user opens the Favorites menu.
2.  The user clicks on one of the saved location actions.
3.  The `set_path()` method in `MainWindow` is called with the favorite's path, triggering the file browser to navigate to that directory.

## Implementation Plan

Here is a high-level plan for implementing this feature.

-   **[ ] 1. Update Settings Model**:
    -   Add `Favorite` and `FavoritesSettings` dataclasses to [`src/models/settings.py`](src/models/settings.py).
    -   Add the `favorites` field to the main `Settings` dataclass.

-   **[ ] 2. Implement UI Elements in MainWindow**:
    -   In [`src/windows/main_window.py`](src/windows/main_window.py), add a new `_create_favorites_menu` method.
    -   Add a `QToolButton` to the toolbar and a "&Favorites" menu to the menu bar.
    -   Connect these UI elements to the menu creation logic.

-   **[ ] 3. Implement Favorite Management Logic**:
    -   Create the `_on_add_favorite` slot to handle adding the current path.
    -   Create the `_on_remove_favorite` slot to handle the confirmation and removal process.
    -   Implement the logic to load/save favorites from/to `QSettings`.

-   **[ ] 4. Write Unit Tests**:
    -   Create tests for the settings model to ensure favorites are loaded and saved correctly.
    -   Write tests for the `MainWindow` logic, mocking UI interactions where necessary.