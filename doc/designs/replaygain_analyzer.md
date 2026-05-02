# ReplayGain Analyzer

**Source**: user request to add per-track and per-album ReplayGain scanning under the existing Loudness category.

## Overview

A new Loudness analyzer that:

1. Computes ITU-R BS.1770 / EBU R128 integrated loudness and sample peak per track via the `libebur128` C library (the same engine used by ffmpeg, rsgain, loudgain, and bs1770gain).
2. Aggregates per-track measurements into a spec-correct **album** loudness for tracks sharing an album, by way of `pyebur128.get_loudness_global_multiple`.
3. Writes the canonical ReplayGain 2.0 tags into each format's standard location, optionally annotating the Comments field as well.

ReplayGain is the default Loudness analyzer. PeakMeter remains in the source tree but is `debug_only=True` — only the dev/debug build exposes it.

## Why libebur128 / pyebur128

The BS.1770 algorithm involves a K-weighting IIR filter pair, 400 ms block RMS with 75% overlap, and a two-stage (absolute + relative) gating step. Reimplementing it correctly is on the order of 150 lines of numerical code that any reviewer would have to verify against the spec.

`pyebur128` exposes the reference C library directly, including `get_loudness_global_multiple` for spec-correct cross-track album integration. Output values match `ffmpeg -af ebur128` to within ~0.03 LU (floating-point noise within spec tolerance), which gives us interop with the entire ReplayGain tooling ecosystem for free.

Library survey performed before adopting `pyebur128`:

| Library | Verdict |
|---|---|
| `pyebur128` | **Chosen.** Reference C library, prebuilt wheels for win/mac/linux, native album-aggregation API. |
| `pyloudnorm` | Pure-Python BS.1770. No public API for spec-correct cross-track aggregation, would have required reimplementing the gating step. Rejected. |
| `r128gain` | Wraps an external `ffmpeg` binary. Bundling a binary through PyInstaller is heavier than necessary when `pyebur128` exists. Rejected. |
| `bs1770gain` | Not on PyPI. |
| `essentia` | Heavyweight C++; weak Windows / packager support. |

## Options

| Option | Default | Effect |
|---|---|---|
| `compute_track_gain` | `True` | Emit `replaygain_track_gain` and `replaygain_track_peak` per file. |
| `compute_album_gain` | `True` | Group tracks by `(album, album_artist)`, compute album LUFS, emit `replaygain_album_gain` and `replaygain_album_peak` for each track in the group. |
| `append_to_comments` | `False` | Also append a human-readable `ReplayGain Track: ... dB (peak ...)` and `ReplayGain Album: ...` line to the Comments field. |

## Tag Mapping

Follows the [Hydrogenaudio ReplayGain 2.0 spec](https://wiki.hydrogenaud.io/index.php?title=ReplayGain_2.0_specification) and the foobar2000 / r128gain / rsgain convention.

| Value | ID3 (MP3) | Vorbis (FLAC/OGG) | iTunes MP4 (M4A) |
|---|---|---|---|
| Track gain | `TXXX:replaygain_track_gain` | `replaygain_track_gain` | `----:com.apple.iTunes:replaygain_track_gain` |
| Album gain | `TXXX:replaygain_album_gain` | `replaygain_album_gain` | `----:com.apple.iTunes:replaygain_album_gain` |
| Track peak | `TXXX:replaygain_track_peak` | `replaygain_track_peak` | `----:com.apple.iTunes:replaygain_track_peak` |
| Album peak | `TXXX:replaygain_album_peak` | `replaygain_album_peak` | `----:com.apple.iTunes:replaygain_album_peak` |

The four key bindings are registered with `EasyID3.RegisterTXXXKey` and `EasyMP4Tags.RegisterFreeformKey` at module load in `MutagenProvider`. FLAC/Vorbis lowercase keys flow through mutagen's native FLAC interface without registration.

**Value formats** (per spec):
- Gain: `"%+.2f dB"` — e.g. `"-6.24 dB"`, `"1.30 dB"`. Tools that expect a literal `+` on positive values will tolerate either.
- Peak: linear amplitude with 6 decimals — e.g. `"0.987654"`, `"1.000000"`.

## Reference Loudness

`-18 LUFS`, per ReplayGain 2.0 / EBU R128. `track_gain = -18 - track_lufs`.

## Album Grouping Rules

The grouping key is `(album.casefold().strip(), album_artist.casefold().strip())`.

- Compilations: `album_artist="Various Artists"` (or whatever Picard wrote) keeps every track on the same album in the same group, even when per-track `artist` differs. We deliberately do **not** group by `artist`.
- Files with a blank `album` tag are excluded from album aggregation entirely — we do not emit album-level metadata for orphan tracks.
- Silent tracks (integrated LUFS = `-inf`) are excluded from album aggregation so a single dud track does not poison the album LUFS.
- Mismatched sample rates or channel counts within a group fall back to a duration-weighted energy mean of per-track LUFS values, with a logged warning.

## Integration With the Dispatcher

`ReplayGainAnalyzer` extends `BatchAnalyzerBase` (see `analyzer_system.md` for the contract). The dispatcher:

1. Per file: runs `analyze()` (potentially in a worker process). Returns track tags in `data` and `aggregation_data` containing `track_lufs`, `track_peak`, and the album grouping key.
2. After every per-file task in the batch finishes: calls `ReplayGainAnalyzer.aggregate_results(completed_tasks, options)` once on the main process.
3. The aggregator re-reads each track's audio, builds a fresh `R128State` per track (the C state is not picklable across the process pool), and calls `pyebur128.get_loudness_global_multiple` for spec-correct album LUFS. Re-reading is cheap relative to disk I/O — pyebur128 processes a 4-minute stereo track in ~250 ms.
4. Album updates are merged into each task's `result.data`, then staged via `EditManager.stage_change`. The dispatcher commits synchronously at end-of-batch when autosave is on, or leaves changes pending when it is off.

## References

- ITU-R BS.1770-4 (Oct 2015), "Algorithms to measure audio programme loudness and true-peak audio level": <https://www.itu.int/rec/R-REC-BS.1770>
- EBU R 128 v4.0 (Jun 2020): <https://tech.ebu.ch/publications/r128>
- ReplayGain 2.0 specification (Hydrogenaudio): <https://wiki.hydrogenaud.io/index.php?title=ReplayGain_2.0_specification>
- libebur128 (reference impl, Jan Kokemüller): <https://github.com/jiixyj/libebur128>
- pyebur128 (Python bindings, Henrik Enquist): <https://github.com/HEnquist/pyebur128>
