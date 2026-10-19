# Code Review, October 2026

Scope: the whole `src/` tree (about 24k lines), reviewed ahead of the next development pass, whose goals are
(a) more metadata formats (additional mutagen containers, ACID chunks in WAV, possibly REX2) and
(b) reading DJ-application metadata from Serato and Rekordbox, primarily beat grids and cue points.

Method: four domain reviews (metadata/models, audio/analyzers, GUI, CLI/rename/resources/packaging), then
independent verification of the highest-impact claims by running the real code against copies of the
fixtures. Items marked **[verified]** were reproduced; the rest were traced in code. The test suite was
green at the time of review (1044 passed, 26 skipped), so none of the bugs below is covered by a test.

## 1. Executive summary

1. **The metadata layer only works for MP3 and FLAC.** WAV and AIFF expose no generic tags and every write to
   them raises. Most M4A writes raise. These are the exact containers the format-expansion pass targets.
2. **Mutagen "easy" mode is the wrong foundation for the next pass.** It hides every frame it does not know
   about, which is precisely where Serato (GEOB), MusicBrainz (UFID) and ACID (RIFF chunk) data live. The
   `MutagenProvider` docstring forbids raw mode. That rule has to be retired.
3. **The MetadataProvider abstraction is single-provider in practice.** Lookups are keyed by bare internal tag
   name, the first provider wins, every value is coerced to a string, and each provider opens and saves the
   file independently. Two providers on the same ID3 block would overwrite each other's writes.
4. **Qt has leaked into the core.** `MediaFile` cannot be imported without PySide6 and a display library,
   because of an import chain through `models/__init__`, `EditManager`, the provider registry's import-time
   manifest load, and `QtWidgets` imports in analyzers. This is the root cause of the CLI/GUI divergence:
   the CLI re-implements the dispatcher and gets it wrong.
5. **Several silent data-loss and data-corruption paths exist** in saving, renaming, analysis and audio
   adaptation. They are listed in section 2 and should be fixed before any new format work lands.

## 2. Bugs

Severity: S1 = data loss/corruption or core feature broken; S2 = wrong results or stranded state; S3 = minor.

### 2.1 Metadata and models

| # | Sev | Location | Finding |
|---|-----|----------|---------|
| M1 | S1 | `mutagen_provider.py` constructor, `media_file.py` save | **[verified]** WAV/AIFF: no easy wrapper exists, so keys are raw frame IDs. `get_tag_simple(title)` is None; `save({title})` raises `TypeError: not a Frame instance`. |
| M2 | S1 | `mutagen_provider.py` `get_tag`/`get_stream_info`/`save` | **[verified]** `if not self._audio` uses the tag count as truthiness. Untagged files return None for length, bitrate, format; `length_in_seconds` is 0.0. Must be `is None`. |
| M3 | S1 | `media_file.py` save, generic loop | **[verified]** Generic tags with no registered writer (date, year, label, remixer, publisher, tracktotal, disctotal) are skipped silently and the save reports success. `EditManager` then unstages them. |
| M4 | S1 | `mutagen_provider.py` tag tables | M4A: `MUT_EASY_TAG_NAMES` is advertised as writable for every container, but EasyMP4 lacks initialkey, mood, composer, isrc, language, encodedby, acoustid_*, musicbrainz_recordingid. BPM is an int atom, so "173.9" raises. Every key-analyzer write to M4A fails. |
| M5 | S2 | `edit_manager.py` `commit_changes` and its GUI callers | With autosave on, an edit staged while a commit thread is running gets "Save is already in progress" and returns False. No caller re-commits. The bold marker is hidden under autosave, so the edit is invisible until quit. |
| M6 | S2 | `media_file.py` save | A failed `set_tag` or `provider.save()` leaves mutated provider state. Reset never reloads providers, so the discarded value is written by the next unrelated save of that file. |
| M7 | S2 | `media_file.py` save | **[verified]** Clearing a field writes `['']` (empty frame or empty Vorbis comment) instead of deleting the tag. |
| M8 | S2 | `media_file.py` save, internal-tag loop | Internal-tag saves write the value into the `KEY_INTERNAL` filesystem dict (fpath, fsize...), which then leaks into `to_dict()` and CLI output. |
| M9 | S2 | `edit_manager.py` `stage_change`, `advanced_tab.py` | Staged internal changes hold a provider *instance* from one specific `MediaFile`. Multi-file use would write N times to the first file. Latent. |
| M10 | S2 | `mutagen_provider.py` `get_stream_info` | **[verified]** `total_samples` is computed as length × channels (returns 2.4 for a 1.2 s file). Should be length × sample_rate. |
| M11 | S3 | `metadata_model.py` setData | Does not check `KEY_IS_MEDIA` (its sibling `setDataForRows` does), builds a throwaway `MediaFile` synchronously on the GUI thread, and has a dead None check. |
| M12 | S3 | `diatonic_key.py` parse_key | Any unknown suffix parses as major: "Amazing" becomes A major. The formatter's keep-as-is fallback almost never triggers. |
| M13 | S3 | `models/settings.py`, `media_file.py` save | One module-global `QSettings` is read from the commit thread. Reentrant, not thread-safe. |
| M14 | S3 | `media_file.py` | `file_id = hash(abspath)` is salted per process and does not survive rename (`update_file_path` keeps the old id). Rename with pending edits orphans them (see G12). |

### 2.2 Audio and analyzers

| # | Sev | Location | Finding |
|---|-----|----------|---------|
| A1 | S1 | `resampling_adapter.py` read | **[verified]** Leftover *output-rate* samples are prepended to the next *source-rate* chunk and resampled again. 44.1k→22.05k loses 9% of frames (201,254 of 220,500); upsampling grows without bound. Affects aubio fast mode, the CNN key analyzer on 48k/96k files, and playback whenever device rate differs from file rate. |
| A2 | S1 | `aubio_bpm.py`, `re3_bpm.py`, `re3_key.py`, `peak_meter.py` | `MiniaudioStream` promotes 24-bit, 32-bit and float sources to FLOAT32 with width 4. These four analyzers interpret width 4 as `int32`, so float bits are read as integers (effectively hard clipping). The 24-bit fixtures' tests accept 50–260 BPM and hide it. |
| A3 | S1 | `yaamt.py` cmd_analyze | **[verified in code]** The CLI stages raw `result.data` and never calls `_postprocess_result_data`. `analyze -w` therefore stages a `bpm_candidates` list of dataclasses and never writes `bpm`; `diatonic_mode` is staged as a tag; `-f json` crashes on the dataclasses; `--bpm-min/max` are never applied; `--threads` is unused. |
| A4 | S1 | `analyzer_dispatcher.py` cancel_all, _finish_processing | "Discard" does not discard: finished results are already staged, aggregation still runs after cancel, and `_finalize_writes` commits them under autosave. Cancel only reaches the last-started task and never reaches process-pool tasks; stale `worker_finished` signals after `reset()` drive `_active_workers` negative and hang the progress dialog. |
| A5 | S2 | `analyzer_dispatcher.py` _finish_processing | Album aggregation (ReplayGain re-decodes every track) and `commit_changes_sync` run on the GUI thread. |
| A6 | S2 | `channel_mixing_adapter.py` | **[verified]** Stereo→mono is `mean / sqrt(2)`, which is 3 dB low for correlated content (RMS 11313 → 7999 for L=R). The design doc repeats the error. More than 2 channels raises. |
| A7 | S2 | `audio_numpy.py` | Float buffers with peak > 1.0 are normalised to 1.0, and peak > 2.0 is reinterpreted as int32. Both are heuristics standing in for an explicit sample format. ReplayGain peak/loudness on float files with overs is wrong. |
| A8 | S2 | `librosa_key.py` | `n_chroma` 24 or 36 (offered by the UI) fails: the profiles have length 12. |
| A9 | S2 | `analyzer_options.py` | Default-true boolean options become `store_false` flags, so `--trim` turns trimming off. Also violates the yes/no CLI rule. |
| A10 | S3 | `factory.py` | Base stream is not closed if an adapter constructor raises. |
| A11 | S3 | `musicbrainz_acoustid.py` | `get_thread_count` returning 1 does not serialise lookups; `_fpcalc_env` mutates `os.environ` process-wide. |
| A12 | S3 | `eval_scoring.py` | MIREX "relative" accepts ±3 semitones and "fifth" accepts a fourth; `mingus` is pulled in to compute `(a-b) % 12`. |
| A13 | S3 | `musical_cnn_key.py` | Model reloaded per file; `torchaudio` required but unused; `QThread.terminate()` used for download cancel. |

### 2.3 GUI

| # | Sev | Location | Finding |
|---|-----|----------|---------|
| G1 | S1 | `main_window.py` closeEvent | Discard and no-prompt branches exit without `wait_for_pending_commit()`; the commit QThread is destroyed mid-write. Teardown (playback thread quit, loader cancel) also happens *before* the prompt, so Cancel leaves a window with a dead playback thread. |
| G2 | S1 | `main_window.py` Reset Columns | Installs a brand-new empty model; the file list goes blank and the old model leaks while the loader keeps emitting into it. |
| G3 | S1 | `preferences_window.py` Reset to Default | Removes the whole `General` group, which also holds `SETTINGS_AUTOSAVE`. A user running with autosave off gets autosave on at next launch. |
| G4 | S2 | `setup_dialog.py` vs `metadata_pane.py` | Preferred analyzer is written as `Analyzers/Preferred/<cat>` and read as `analyzers/preferred_AnalyzerCategory.BPM`. Never honoured. |
| G5 | S2 | `main_window.py` startup | `SETTINGS_STARTUP_DIR_MODE` and `SETTINGS_PREFERRED_DIRECTORY` are written but never read; audio-device preference is a stub; UI skin not applied at startup. |
| G6 | S2 | `metadata_pane.py` save | Empty BPM min/max passes validation then `int("")` raises. |
| G7 | S2 | `progress_dialog.py` | Esc calls `reject()`, which `closeEvent` does not intercept; the batch keeps running with no UI. For renames the safety net reopens the playing file while renames continue. |
| G8 | S2 | `main_window.py` rename flow | If every rename task resolves at planning, `_finish()` fires synchronously before `exec()`, and the dialog hangs open at 0/0. |
| G9 | S2 | `playback_worker.py`, `main_window.py` | Play does nothing after Stop or after natural end (worker stays PLAYING, device and file handle stay open). `stop()` is called from the GUI thread. |
| G10 | S2 | `load_files_worker.py` | Viewport-priority loading never takes effect: `set_priority_range` always arrives after `_get_prioritized_indices()` has run. |
| G11 | S2 | `metadata_model.py` data | DisplayRole returns the staged value; EditRole and UserRole return on-disk values. Inline edit cannot revert a staged value; multi-row editor shows stale values; sorting ignores pending values and compares BPM as strings. |
| G12 | S2 | `main_window.py` rename, `media_file.py` | Renaming files with pending edits orphans them (see M14): marker disappears, Save fails forever, quit prompt keeps firing. |
| G13 | S2 | `advanced_tab.py` | Multi-value tags are shown joined with "; " and editable; an edit writes them back as one scalar. On FLAC, Serato base64 blobs are editable free text today. Reaches into `media_file._providers`. |
| G14 | S2 | all windows/dialogs | PropertiesWindow, PreferencesWindow, About, analyzer setup/progress/summary, rename setup, context submenus and favorites actions are parented to MainWindow and never deleted. Leaked PropertiesWindows stay connected to the singletons and re-read tags on every analysis run. |
| G15 | S3 | `resources_pane.py` | `progress.close()` emits `canceled`, which calls `worker.terminate()`; cancel can leave a partial resource. `finished` signal shadows `QThread.finished`. |
| G16 | S3 | `main_window.py` | Load cancel does not stick ("Ready" overwrites "Loading cancelled"); invalid favorite persists `last_path=""`; Properties "Publisher" field is unwired; column width load crashes on a missing key; selection restore is quadratic. |

### 2.4 CLI, rename, resources, packaging

| # | Sev | Location | Finding |
|---|-----|----------|---------|
| C1 | S1 | `rename_dispatcher.py` within-batch resolution | Overwrite mode: two files in one batch rendering to the same name. A is renamed to `Foo.mp3`, then `os.replace(B, Foo.mp3)` destroys A. The comment claims planning makes this safe; it does not. |
| C2 | S1 | `resource_manager.py` clear_cache | `rmtree` on the cache root, which the user can point at any existing folder in Preferences. Debug menu only, but destructive. |
| C3 | S2 | `resource_manager.py` | A user-located resource with a checksum mismatch is overwritten by download, then unlinked if the download fails its own check. Lock file is unlinked on `Timeout` (deleting another process's lock). Retry reuses the fd without truncate; non-URLError read errors are not retried; no Content-Length check; default SSL context without certifi, which `update_checker.py` says breaks frozen builds. |
| C4 | S2 | `debug.py` | `--debug` with `nargs='?'` swallows the subcommand: `yaamt --debug read x.mp3` errors. Help text advertises the bare form. |
| C5 | S2 | `yaamt.py` | `--use-saved-prefs` is dead for analyzer-specific options (defaults are never None). One exception aborts the whole run with nothing committed. Save errors still exit 0. Skipped results are counted as successes. |
| C6 | S2 | `providers/__init__.py`, `build.py` | `get_analyzer_by_name` ignores `debug_only`, and the build does not strip DEBUG_ONLY analyzers despite the manifest comment. `yaamt analyze StubBPMAnalyzer -w` writes a fake BPM in release builds. |
| C7 | S2 | `cli_formatters.py` | `read --stream-info`/`--internal` put raw `{value, provider}` dicts in cells; tags, stream info and internals share one flat namespace; `--tags` filter drops stream columns. |
| C8 | S3 | `yaamt.py` | `parse_known_args` silently ignores misspelled flags for every verb; `--tag K=V` keys are unchecked; `SUPPORTED_EXTENSIONS` is hard-coded and differs from GUI detection; paths are not deduplicated or sorted. |
| C9 | S3 | `rename_dispatcher.py`, `rename_formatter.py` | Cancel during an in-flight rename can race an Overwrite; `casefold()` without Unicode normalisation gives false collisions on macOS/Windows; no path-length cap; multi-value tags render as a Python list repr. |
| C10 | S3 | launchers, `build.py` | `yaamt.bat` uses relative paths; `open()` without `encoding` on a file containing non-ASCII. |

## 3. Architecture violations

Ordered by how much they will obstruct the next pass.

1. **Qt in CLI-reachable code.** Confirmed import chain: `models/__init__` → `EditManager` (QObject, QThread) →
   `MediaFile` → `providers/__init__` runs `discover_providers()` at import → `_manifest` → `re3_bpm` imports
   `QtWidgets`. Also `QSettings` in `tag_transformers`, `models/settings`, `ResourceManager`, analyzers and
   dispatcher workers. 20+ non-GUI modules import PySide6. Consequence: the CLI duplicates the dispatcher
   (A3), cannot use the rename planner, and metadata I/O depends on analysis and GUI code.
2. **Import side effects.** `discover_providers()` and `ResourceManager` construction (reading QSettings,
   creating directories) run on any `providers.*` import, before `setApplicationName`.
3. **Easy-mode-only rule in `MutagenProvider`.** Blocks WAV/AIFF, GEOB, PRIV, UFID and MP4 freeform atoms.
4. **Generic tag vocabulary equals mutagen easy names.** `MUTAGEN_TO_GENERIC_MAP` is nearly an identity map;
   the domain vocabulary is tied to one library and carries no type, multiplicity or ownership.
5. **Seven overlapping tag registries.** `ALL_TAGS`, `COMMON_WRITABLE_TAGS`, `EXTRA_RENAME_TAGS`,
   `AVAILABLE_COLUMNS`, `MUTAGEN_TO_GENERIC_MAP`, `MUT_EASY_TAG_NAMES`, and the hard-coded list in
   `MetadataTableModel.get_metadata_from_media_file`. Adding one column means editing three places.
6. **File I/O on the GUI thread.** `refresh_files` re-reads tags after every commit/reset/batch;
   `MainTab` reads tags for every selected file; `_finalize_writes` commits synchronously; album aggregation
   decodes on the main thread.
7. **Settings bypass `models/settings.py`.** Favorites, column layout, `last_path`, analyzer dialog keys and
   rename presets persist from window code; QSettings is reached three different ways; option widgets write
   on every change so Cancel does not revert. The `Settings` dataclasses are unused.
8. **Leaky facade.** `advanced_tab` reads `media_file._providers` and matches providers by class-name string;
   `progress_dialog` reads `dispatcher._is_running`.
9. **Format conversion re-implemented in analyzers.** RE3 BPM, RE3 key, peak meter and aubio each decode
   bytes and sum channels themselves, which is how A2 happened.
10. **GUI code inside providers.** About 220 lines of QThread downloader and dialogs in `musical_cnn_key.py`;
    requirements panel in `musicbrainz_acoustid.py`; providers import `windows.analyzer.option_widgets`.
11. **Magic strings.** `'bpm_candidates'`, `'bpm'`, `'key_notation_format'`, `'write_to_tags'`,
    `'last_path'`, `'playing'/'paused'/'stopped'`, option type names, `category == 'bpm'` where the enum
    exists, `"provider"`/`"value"` where constants exist.
12. **Boolean CLI flags** are store_true/store_false throughout (`--recursive`, `--write-tags`, dynamic
    options) despite the yes|no rule and an existing `parse_bool_arg`.
13. **Documentation drift.** AGENTS.md says `register_analyzer()` at file bottom; code uses `@analyzer`.
    `analyzer_system.md` describes `analyze(audio_stream)`. `tag_transformations.md` describes a
    `bypass_transformations` preference that is not wired. `const.py` says "Default to debug mode" next
    to `IS_DEBUG_BUILD = False`. AGENTS.md refers to both `doc/` and `docs/`.
14. **Tone.** `SomethingsReallyFuckedUpException` conflicts with the project's professionalism rule.

## 4. Complexity and refactor candidates

- **`MediaFile.__init__`** builds four parallel structures; `_registered_providers` is never read. All keyed by
  bare internal name. **`MediaFile.save`** mixes transform, route, write and invalidate; the two cache-clear
  loops duplicate the routing.
- **`AnalyzerDispatcher`** (861 lines) does queueing, thread accounting, process pool, post-processing,
  comment rewriting, notation overrides, aggregation, commit and report generation.
- **Per-analyzer `analyze()` boilerplate** (7 copies): cancel check, skip check, lazy import, open stream,
  try/finally close. **Bytes→float decoding** (5 copies). **Comment-marker merge** (4 copies).
  **BPM range resolution** (3 copies with different None semantics). **24-bit pack/unpack** (3 adapters).
- **`main_window.py`** (1918 lines). Proposed decomposition: menus, debug menu (table-driven), file-list
  controller, Qt-free column layout model, favorites model + menu, shared batch runner (analyzer and rename
  share progress→summary→refresh), playback controller, directory pane, UI style helper. MainWindow becomes
  roughly 250 lines of composition.
- **`rename_dispatcher.py`** (942 lines): collisions resolved in three places plus a per-op QRunnable state
  machine for operations that take microseconds. Move planning and a synchronous `execute_plan` into a
  Qt-free module; keep a thin Qt shell. Gives the CLI a `rename` verb for free.
- **`cli_formatters.py`**: directory/filename split copied four times; JSON branch re-implements filtering;
  no value-rendering hook. One row model, one render hook, a formatter registry keyed by an enum.
- **`metadata_model.py`**: DisplayRole and UserRole repeat the same column switch; `setData` duplicates
  `setDataForRows`; `sort()` is dead (proxy sorts).
- **Dead code**: commented-out abstract properties in `metadata/base.py`; `MAP_INTERNAL_TO_GENERIC`;
  `KEY_FILE_ATIME*`; unused `Settings` dataclasses; `util/modular.py` (empty); `windows/__resources_rc.py`
  (50k-line duplicate of `util/resources_rc.py`); `current_task` (marked deprecated); `DiatonicMode` in
  `wavelet.py`; audio-device stubs; `on_column_resized`/`on_column_moved`; the Tools button and ArtworkTab
  placeholder; ~20 unused imports in `mutagen_provider.py`.

## 5. Design choices that no longer serve the project

| Choice | Why it hurts now | Replace with |
|---|---|---|
| Easy-mode-only mutagen access | Hides WAV/AIFF, GEOB, UFID, MP4 freeform | Raw container stores with explicit per-format bindings |
| One provider instance per file, each doing its own I/O | Serato-inside-ID3 and ACID-beside-ID3 would clobber each other | One store per physical container, loaded once, saved once; providers are interpreters over stores |
| Generic names = mutagen easy names; string scalars everywhere | No place for typed, structured, multi-valued or read-only fields | A field registry with id, label, type, multiplicity, editability, formatter |
| `hash(abspath)` as file identity | Per-process salt; breaks on rename | Path-keyed registry owned by the model layer, stable id per session |
| `EditManager` as a QObject singleton serving the CLI | Qt in core; global commit; "drop commit if busy" loses edits | Plain-Python staging core with a thin Qt signal adapter; queue a follow-up commit instead of dropping |
| QSettings as the transformer and analyzer configuration API, read at analysis time on worker threads | Thread-safety, Qt in core, untestable | Snapshot options at enqueue time; transformers take a settings-reader protocol |
| Implicit "width 4 == float" stream convention | Root cause of A2, A7 | Explicit `sample_format` on streams; one shared bytes→float helper |
| Qt dispatcher with QThreads blocking on process-pool futures | Two layers of bookkeeping; cancel impossible | `concurrent.futures` runner with cancellable futures plus a Qt adapter; CLI calls the runner |
| `parse_known_args` plus a second parse for dynamic options | Hides typos for every verb | Per-analyzer subparsers built up front from the static registry |
| `AUTOSAVE_DEFAULT = True` | Contradicts DESIGN.md "write only when requested" | Default off |
| Advanced tab free-text editing of every internal key | Unsafe once binary/structured frames are visible | Edit only when the provider declares a string codec; structured values read-only |
| Nested modal `exec()` over singleton dispatchers | Esc hole, synchronous-completion hole, per-run connect/disconnect | Shared batch runner owning dialog lifetime |
| RenameDispatcher duck-typing AnalyzerDispatcher's signal names | Couples unrelated workflows | Small shared batch-job protocol |

## 6. Readiness for new formats and DJ metadata

Questions the next pass depends on, answered against the current code:

- **Multiple providers per file: not supported.** `_get_providers_for_file` hard-codes `[MutagenProvider]`;
  the provider registry is typed for analyzers only. Reads take `providers[0]`, writes take the first
  writer, the generic→internal map is 1:1 with last-writer-wins. An ACID `bpm` and an ID3 `bpm` collide.
  Most importantly, each provider parses and rewrites its block whole, so a Serato provider and
  `MutagenProvider` on the same MP3 would erase each other's writes.
- **Structured values: not supported.** Provider contract is a list of scalars; `save` wraps `[value]`;
  `get_tag_simple` takes `[0]`; transformers return `str` with a `str()` fallback; the Qt model renders raw
  values; the delegate always opens a `QLineEdit`; multi-select hashes values (TypeError on lists). On FLAC
  the Serato blobs are already visible as editable base64 strings, which a user can corrupt from the
  Advanced tab. On MP3 they are invisible **[verified: 8 GEOB frames present, 0 visible]**.
- **Read-only and sidecar sources: partial.** `TagInfo.is_writable` exists but provider constructors take
  only a path. Rekordbox XML and ANLZ files are library-scoped, not file-scoped, and need a shared cached
  index keyed by normalised path. Nothing records where a value came from beyond a class name.
- **Analyzer result contract: flat `{generic_tag: value}`** with two hard-coded special cases in the
  dispatcher and none in the CLI. A beat grid would be a third `if` branch. There is no merge semantics
  (an analyzer writing a grid must not overwrite user cues in the same GEOB frame), no provider capability
  declaration ("this format cannot hold X"), and the beat positions librosa and aubio already compute are
  discarded. A grid also needs sample-accurate timestamps on the file's own timeline, which A1 rules out on
  resampled streams, and the audio layer has no notion of MP3 encoder delay.
- **`KEY_IS_MEDIA`** is true only when mutagen can parse the file; REX2 would be classed as non-media.
  REX2 has no pure-Python decoder and would need the proprietary REX SDK via ctypes, so it must be gated
  `debug_only` or deferred.
- **Packaging.** `yaamt.spec` has one hard-coded `hiddenimports` list; Rekordbox libraries such as
  pyrekordbox bring sqlcipher3 and data files. `upx=True` on Qt/torch binaries is a known crash and
  AV-false-positive risk.

### Target shape (plain English)

1. **Container stores.** `MediaFile` owns one store per physical container: ID3 (raw mutagen), Vorbis, MP4,
   a RIFF chunk store (`acid`, `smpl`, `cue `, `id3 `), and read-only library indexes (Rekordbox XML/ANLZ).
   Each is loaded once and saved once, via temp file, fsync and rename.
2. **Interpreter providers** registered in a manifest like analyzers: Common, Serato, ACID, Rekordbox. Each
   declares id, priority, supported containers/extensions, read/write capability per field, and codecs for
   structured fields. Providers read and write through stores, never through the path.
3. **Field registry** replacing the seven tag tables: id, label, value type (text, number, musical key,
   text-list, cue points, beat grid, blob), multiplicity, editability, column formatter, sort key,
   transformers.
4. **Typed values** for cue points (position, kind, index, label, colour) and beat grids (anchor markers
   with position and bpm or beat number) as frozen dataclasses in `models/`.
5. **Explicit bindings**: field → ordered list of (provider, internal key) with read precedence and a write
   policy. `get_all_values(field)` returns per-provider values so conflicts can be shown.
6. **Staging by id**, not by provider object: (file_id, field_id) and (file_id, provider_id, internal_key).
   Staging core is plain Python; Qt signals live in an adapter.
7. **Result post-processing registry** keyed by result type (bpm candidates, detected key, beat grid, cue
   points), used by both CLI and GUI, with a per-field merge policy.

## 7. Recommended course of action

Three phases, each ending in a green suite and a commit. Phase 1 and 2 are prerequisites for the
format/DJ work; attempting Serato on the current `MutagenProvider` would mean building on easy mode and on
a single-provider facade, and the first write would corrupt the second provider's frames.

### Phase 1: Stop the bleeding (small, independent fixes, one commit each)

Fix the verified S1 bugs that do not depend on the refactor, each with a regression test on real fixtures:
M2 (`is None` checks), M3 (raise or report on unwritable generic tags), M7 (delete on empty), M10
(total_samples), A1 (resampler buffer; add exact frame-count and sine-continuity tests), A2 (one shared
bytes→float helper on an explicit float descriptor; tighten the 24-bit fixture BPM tolerance to ±1),
A6 (downmix level), C1 (within-batch overwrite), C2 (clear only registered resource paths), G1 (quit
ordering and wait), G2 (reset columns), G3 (reset only the general pane's own keys), G4 (one preferred-analyzer
key). Also drop the AGENTS.md/`docs/` path inconsistency and the profane exception name.

Estimated size: 15–20 small PRs or one PR with one commit per fix.

### Phase 2: Sever Qt from the core and unify CLI/GUI

1. Remove `discover_providers()` from `providers/__init__` import time; call it from the two entrypoints and
   the dispatcher. Move `QtWidgets` imports in analyzers into their `get_settings_widget` methods or into
   `windows/analyzer/`. Make `MediaFile` importable without PySide6 (test this in CI).
2. Replace QSettings in transformers and analyzers with a settings-reader protocol; snapshot options at
   enqueue time.
3. Extract a Qt-free analysis runner (analyze → post-process → aggregate → stage → commit) on
   `concurrent.futures`; `AnalyzerDispatcher` becomes a Qt adapter; `cmd_analyze` calls the runner. This
   fixes A3, A4, A5 and C5 together.
4. Split `EditManager` into a plain-Python staging core plus a Qt adapter; queue a follow-up commit instead
   of dropping one (M5). Reload providers on failed save and on reset (M6).
5. Extract the rename planner and `execute_plan` into a Qt-free module; add a CLI `rename` verb.

### Phase 3: Metadata layer redesign (the actual enabler for the next pass)

Implement the target shape in section 6 behind the existing `MediaFile` public methods so GUI and CLI keep
working: container stores, interpreter providers with a manifest, field registry, typed values, bindings,
staging by id, result post-processing registry. Land it in this order: (a) field registry and stores
with the Common provider only, replacing easy mode and fixing M1/M4; (b) ACID RIFF chunk provider
(read, then write) as the first second-provider on WAV, which exercises the store-sharing design;
(c) Serato read-only provider over the ID3 and Vorbis stores, with a round-trip test proving an unrelated
title write leaves all eight GEOB frames byte-identical; (d) Rekordbox read-only index provider;
(e) GUI column specs with display/sort formatters and read-only structured columns ("8 cues", grid BPM);
(f) Serato write, with field-level merge, only after (c) has a corruption guard in CI.

Write a design document for Phase 3 first (`doc/designs/metadata_layer_v2.md` and a matching epic), since
it touches every layer. The `main_window.py` decomposition can proceed in parallel with Phase 3 as it is
mostly mechanical, but should wait for Phase 2 so the extracted controllers sit on the new runner.

## 8. Test coverage gaps that matter most

- No WAV, AIFF, M4A or OGG read/write tests; `test_media_file.py` restricts fixtures to mp3/flac, hiding M1
  and M4. Fixture JSONs assert tags only, never stream info (M2).
- No test for unmapped generic tags being dropped, clearing a tag, provider state after a failed save,
  staging during an in-flight commit, or lists through the transformers.
- Resampler tests assert only that chunks are non-empty; the integration test's ±0.1 s tolerance hides a
  9% loss. 24-bit BPM tests accept 50–260 BPM.
- No CLI test for `analyze --write-tags`, JSON output, `--use-saved-prefs`, exit codes, or `--debug` before a
  subcommand.
- No dispatcher cancel tests (keep vs discard, multi-worker, stale signals after reset).
- No rename test for Overwrite with duplicate targets in one batch, cancel with staged files, or Unicode
  normalisation collisions.
- No quit-flow, preferences-pane, progress-dialog Esc, or window-leak tests.
- Serato fixtures exist but are checked only as opaque strings; the key regression guard for the DJ work
  (an unrelated write leaves GEOB frames byte-identical) does not exist yet.
- `test_write_tags` depends on the user's real QSettings; inject a settings stub.
