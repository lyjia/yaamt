# YAAMT Design

YAAMT (Yet Another Audio Metadata Tool) gives the user a format-agnostic metadata editor that can be used at the command-line or in a GUI. This metadata is then consumed and used in other software, such as FLStudio, Sound Forge, Serato, RekordBox, Foobar2000, and the like. It will primarily be a tool for DJs to intake new music and prepare the files' metadata to their specification.

In particular, we want the user to be able to perform the following (note that when we mention a MediaFile, we mean both a media file itself, a list of media files, or a directory of media files):

* Display the contents of a folder in a tabular format, as columns in the file browser (GUI only) 
* Destroy and recreate the metadata on a MediaFile
* Analyze the audio streams of a file and generate useful metadata, such as BPM, key, MusicBrainz ID, or an acoustic fingerprint.
* Edit specific metadata fields of a MediaFile, such as title, track, album, key, or bpm
* Seamlessly translate the contents of the key field between different representations for musical key, including Camelot notation
* Play back the MediaFile using a simple playback interface with Play, Pause/Stop, Volume, and Playback Position controls
* Write data to the user's precious files only when requested, and as safely as possible, so as to minimize the risk of screwing up the user's carefully curated audio metadata. We want to avoid creating the same disaster that iTunes did when it started spontaneously saving scan results to metadata and potentially corrupting users' files without their explicit permission.
## Properties Window

The Properties Window provides a user-friendly interface for viewing and editing the metadata of a selected audio file. It is designed to be intuitive and efficient, with two main tabs for simplified and advanced editing.

### Features

*   **Simplified Tab:** This tab presents the most common metadata fields in a clear and concise layout, using generic, user-friendly tag names.
*   **Advanced Tab:** This tab provides a tree-based view of all metadata tags, grouped by their respective providers. This allows for fine-grained control over all available metadata.
*   **Two-Way Synchronization:** Changes made in either the "Simplified" or "Advanced" tab are instantly reflected in the other, ensuring a consistent and seamless editing experience.
*   **Threaded Saving:** To prevent the application from becoming unresponsive during file I/O operations, all changes are saved in a separate thread. This provides a smooth user experience, even when working with large files or slow storage devices.
*   **UI Feedback:** During the save process, the UI is disabled and a loading indicator is displayed, providing clear feedback to the user that an operation is in progress.

### Design Rationale

The decision to use `MediaFile`'s internal change buffer, rather than a separate one in the `PropertiesWindow`, was made to simplify the design and reduce code duplication. This approach centralizes the change management logic in the `MediaFile` class, making the application easier to maintain and reason about.

The use of a `QThread` for the save operation is a critical design choice that ensures the GUI remains responsive at all times. By offloading the file I/O to a separate thread, we prevent the main event loop from being blocked, resulting in a much smoother and more professional user experience.