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