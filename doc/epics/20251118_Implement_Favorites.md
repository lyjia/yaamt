We need a system for storing and recalling a user's favorite folders in the directory tree. Users should be able to pull up a menu with saved locations and, upon selecting one, the file browser should automatically navigate to that location.

The favorites menu should be accessible from two locations, and they should both open the same menu:

1. The main toolbar, left of the path textbox. It should have a 'heart' (of 'favorites') icon, and upon being clicked should display the favorites menu. Perhaps it could also have some indicator that it will behave as a menu, like a little down triangle. (Use whatever QT provides)
2. A new "Favorites" menu item in the menu bar.

The favorites menu itself should be as follows:

* A list of the user's saved locations, in alphabetical order, as a menu entry.
* Then, a separator line
* An "Add Favorite..." entry, which saves the current location to the user's list of favorites.
* A "Remove Favorite" entry, which spawns a submenu listing the user's saved locations. Clicking one presents a confirmation dialog, and upon confirmation removes that location from the list.

Each favorite should be persisted in the preference store (see `Settings` model), as a dictionary with one key: the folder path. For now, to keep things simple, limit the maximum number of favorites to 25. 