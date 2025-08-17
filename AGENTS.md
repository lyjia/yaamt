# Project AGENTS.md Guide for AI Agents (OpenAI Codex, Roo Code, Cline, Claude Code, etc)

This document describes this codebase, and outlines the coding conventions and architectural patterns used in its
development.
All AI-generated code must adhere to these guidelines to ensure consistency, readability, and maintainability.

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
