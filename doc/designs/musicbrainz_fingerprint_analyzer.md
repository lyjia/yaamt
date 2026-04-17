# MusicBrainz AcoustID Fingerprint Analyzer

**Source**: user request to add an acoustic-fingerprint analyzer that can
populate a canonical MusicBrainz Recording ID on each file.

## Overview

A new analyzer under the existing `Fingerprint` category that:

1. Computes a Chromaprint acoustic fingerprint for the media file using
   `fpcalc` (invoked through `pyacoustid`).
2. Submits the fingerprint to the AcoustID web service.
3. On a confident, unambiguous match, writes the MusicBrainz Recording ID
   and the AcoustID UUID back to the file. The Chromaprint fingerprint
   itself is only stored when the user opts in.

Populating `title` / `artist` / `album` from MusicBrainz is explicitly out
of scope; this analyzer only writes identifiers.

## Tag Mapping

Follows MusicBrainz Picard's canonical layout so files remain
interoperable with Picard, beets, Serato, etc.

| Value | ID3 (MP3) | Vorbis (FLAC/OGG) |
|-------|-----------|--------------------|
| MusicBrainz Recording ID | `UFID:http://musicbrainz.org` + `TXXX:MusicBrainz Track Id` | `MUSICBRAINZ_RECORDINGID` |
| AcoustID ID | `TXXX:Acoustid Id` | `ACOUSTID_ID` |
| AcoustID Fingerprint (opt-in) | `TXXX:Acoustid Fingerprint` | `ACOUSTID_FINGERPRINT` |

The MBID is written to both the binary `UFID` frame (Picard's canonical
location) and a text `TXXX` copy for players that only parse text frames.
Reads prefer `UFID` and fall back to `TXXX`.

## Dependencies (external)

- **`pyacoustid`** Python package — pip-installable; gracefully reported
  as missing if absent.
- **Chromaprint `fpcalc`** — user-installed binary (e.g.
  `apt install libchromaprint-tools`, `brew install chromaprint`).
  Path is configurable in Preferences > Resources, or via the `FPCALC`
  environment variable, or discovered on `$PATH`.
- **AcoustID API key** — a bundled yaamt key ships by default; users may
  override with their own key in Preferences > Resources.

All three are resolved at analyze time. If any is missing, the analyzer
returns a clear error message rather than crashing.

## Analyzer Options

| Option | Type | Default | Purpose |
|--------|------|---------|---------|
| `min_score` | float 0.0–1.0 | 0.85 | Minimum AcoustID match score; below this, skip file |
| `require_unique_match` | bool | True | Skip when multiple results exceed the score threshold |
| `store_fingerprint` | bool | False | Also write the raw Chromaprint value (~1–3 KB per file) |
| `append_to_comments` | bool | False | Append / replace an `MBID: <uuid>` line in the Comments field |

Plus the common `skip_if_tag_exists` option inherited from `AnalyzerBase`.

## Match Arbitration

```
results = [r for r in response.results if r.score >= min_score
                                       and r.recordings]
```

- 0 qualifying results → `AnalyzerResult(skipped=True, error="No AcoustID match...")`
- 1 qualifying result → success. Write the top recording's MBID and the
  result's AcoustID UUID.
- 2+ qualifying results → if `require_unique_match` is True, skip with
  "Ambiguous"; otherwise take the highest-scored result.

## Threading & Rate Limits

AcoustID rate-limits to roughly 3 requests/sec per key. `get_thread_count()`
hard-returns 1 so a batch of files stays well under that budget, no
additional throttling framework required.

## Validation

`validate_file` rejects files that are not readable and files shorter than
10 seconds (below which Chromaprint's fingerprint is unreliable per
AcoustID's published guidance).

## Limitations

- Requires network access.
- Requires user to install `fpcalc` separately.
- Minimum 10-second source duration.
- Does not download the MusicBrainz database; every lookup round-trips
  to acoustid.org.

## References

- Canonical tag names: https://picard-docs.musicbrainz.org/en/appendices/tag_mapping.html
- AcoustID web service: https://acoustid.org/webservice
- Chromaprint: https://acoustid.org/chromaprint
- `pyacoustid` bindings: https://pypi.org/project/pyacoustid/
