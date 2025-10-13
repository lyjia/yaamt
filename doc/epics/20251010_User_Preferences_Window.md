We need to add a Preferences window to store user preferences.

It should be accessible from the File menu, under "Preferences". (Except for Mac, where it should be in the usual place.)

The window should have two three main sections:
* A category list sidebar
* An area for the preferences pane, with widgets for each preference (and optionally tabs)
* A button bar at the button with "Save" and "Cancel" buttons.

The window should support up to two levels of categorization:
* A category sidebar/navigation pane, where each category has a name and an icon. (The top level)
* (Optional) The preferences pane should be able to have a tab widget for each subcategory. (the mid level)

The window should be resizable.

We are be using QT's built-in QSettings class for storing preferences.

Right now, we need to store the following preferences:

* General category:
  * Set dir to last location on startup, or set dir to a preferred location?
  * Preferred audio device for playback (with a dropdown of supported audio devices)
  * Preferred UI skin
* Metadata category:
  * Preferred analyzers for each analyzer category (e.g. BPM, Key, etc) 
  * BPM detection range (e.g. 80-200)
  * Number of decimal places for BPM saved by analyzers (0-2)
  * Preferred musical key notation format:
    * Standard with abbreviations ("Cmin", "Amaj", etc)
    * Standard with single letter ("Cm", "A", etc)
    * Camelot ("6A", "8B", etc)
    * Open Key ("1m", "12d", etc)

Each category should exist in its own file and be loaded from the Preferences window when it is brought up. Each category should read preferences from QSettings and set its widgets accordingly.

When the user hits "Save", their selections are harvested from each preference pane and saved to QSettings.

