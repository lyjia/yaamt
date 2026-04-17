"""
MusicBrainz AcoustID fingerprint analyzer.

Computes an acoustic fingerprint via Chromaprint (``fpcalc``) and submits it
to the AcoustID service to obtain the MusicBrainz Recording ID for a file.
On a confident, unambiguous match the analyzer writes the MusicBrainz
Recording ID plus the AcoustID UUID to the file; the raw Chromaprint
fingerprint is written only when the ``store_fingerprint`` option is enabled.

The analyzer depends on:
- ``pyacoustid`` (Python binding, available via ``pip install pyacoustid``)
- Chromaprint's ``fpcalc`` binary (installed separately; path configurable
  in Preferences > Resources or via the ``FPCALC`` environment variable)
- An AcoustID API key (bundled default, user-overridable in Preferences)
"""

import os
import shutil
from typing import Any

from models.settings import get_qsettings
from providers import analyzer
from providers.analysis import AnalyzerBase, AnalyzerCategory, AnalyzerResult
from util.analyzer_options import AnalyzerOption
from util.const import (
    DEFAULT_ACOUSTID_API_KEY,
    KEY_ACOUSTID_FINGERPRINT,
    KEY_ACOUSTID_ID,
    KEY_COMMENT,
    KEY_LENGTH,
    KEY_MUSICBRAINZ_RECORDING_ID,
    SETTINGS_ACOUSTID_API_KEY,
    SETTINGS_FPCALC_PATH,
)
from util.logging import log


# AcoustID's own requirement for a usable fingerprint. Below this we don't
# even bother calling fpcalc.
MIN_DURATION_SECONDS = 10

# AcoustID rate-limits submissions to ~3/s per key; keep this analyzer
# single-threaded to stay well inside that budget.
ANALYZER_THREAD_COUNT = 1

# Marker used when appending the MBID to the Comments field.
COMMENT_MARKER = "MBID:"


@analyzer(AnalyzerCategory.FINGERPRINT)
class MusicBrainzAcoustIDAnalyzer(AnalyzerBase):
    """Acoustic fingerprint lookup against the AcoustID/MusicBrainz database."""

    name = "MusicBrainz AcoustID"
    description = "Acoustic fingerprint lookup against the AcoustID/MusicBrainz database"
    category = "fingerprint"
    version = "1.0.0"

    RESULT_MARKER = COMMENT_MARKER

    def analyze(self) -> AnalyzerResult:
        cancelled = self._check_cancellation()
        if cancelled is not None:
            return cancelled

        skipped = self._check_skip_if_exists(
            KEY_MUSICBRAINZ_RECORDING_ID,
            "MusicBrainz Recording ID already set",
        )
        if skipped is not None:
            return skipped

        try:
            import acoustid
        except ImportError:
            return AnalyzerResult(
                success=False,
                error="pyacoustid library not installed - run: pip install pyacoustid",
            )

        fpcalc_path = _resolve_fpcalc_path()
        if fpcalc_path is None:
            return AnalyzerResult(
                success=False,
                error="Chromaprint fpcalc not found. Set the path in Preferences > Resources.",
            )

        api_key = _resolve_api_key()
        if not api_key:
            return AnalyzerResult(
                success=False,
                error="AcoustID API key not configured. Set one in Preferences > Resources.",
            )

        min_score = float(self.options.get("min_score", 0.85))
        require_unique_match = bool(self.options.get("require_unique_match", True))
        store_fingerprint = bool(self.options.get("store_fingerprint", False))
        append_to_comments = bool(self.options.get("append_to_comments", False))

        try:
            duration, fingerprint = acoustid.fingerprint_file(
                self.media_file.file_path,
                force_fpcalc=fpcalc_path,
            )
        except Exception as e:
            log.error(f"Chromaprint fingerprint failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(success=False, error=f"Fingerprint failed: {e}")

        cancelled = self._check_cancellation()
        if cancelled is not None:
            return cancelled

        try:
            response = acoustid.lookup(api_key, fingerprint, duration, meta="recordings")
        except Exception as e:
            log.error(f"AcoustID lookup failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(success=False, error=f"AcoustID lookup failed: {e}")

        if response.get("status") != "ok":
            err = response.get("error", {}).get("message", "unknown AcoustID error")
            return AnalyzerResult(success=False, error=f"AcoustID: {err}")

        qualifying = [
            r for r in response.get("results", [])
            if r.get("score", 0.0) >= min_score and r.get("recordings")
        ]

        if not qualifying:
            return AnalyzerResult(
                success=True,
                skipped=True,
                error=f"No AcoustID match at or above score {min_score:.2f}",
            )

        if require_unique_match and len(qualifying) > 1:
            return AnalyzerResult(
                success=True,
                skipped=True,
                error=f"Ambiguous: {len(qualifying)} AcoustID matches at or above score {min_score:.2f}",
            )

        top = qualifying[0]
        acoustid_uuid = top.get("id")
        mbid = top["recordings"][0].get("id")
        if not mbid or not acoustid_uuid:
            return AnalyzerResult(
                success=False,
                error="AcoustID response missing required IDs",
            )

        result_data: dict[str, Any] = {
            KEY_MUSICBRAINZ_RECORDING_ID: mbid,
            KEY_ACOUSTID_ID: acoustid_uuid,
        }
        if store_fingerprint:
            result_data[KEY_ACOUSTID_FINGERPRINT] = fingerprint.decode("ascii") if isinstance(fingerprint, bytes) else fingerprint

        if append_to_comments:
            result_data[KEY_COMMENT] = self._update_comments(f"{COMMENT_MARKER} {mbid}")

        log.info(
            f"AcoustID match for {self.media_file.file_path}: "
            f"MBID={mbid}, AcoustID={acoustid_uuid}, score={top.get('score'):.3f}"
        )
        return AnalyzerResult(success=True, data=result_data)

    def _update_comments(self, new_line: str) -> str:
        """Replace an existing MBID marker line or append the new line."""
        existing = self.media_file.get_tag_simple(KEY_COMMENT)
        if not existing:
            return new_line
        if COMMENT_MARKER not in existing:
            return f"{existing}\n{new_line}"
        updated = []
        for line in existing.split("\n"):
            updated.append(new_line if COMMENT_MARKER in line else line)
        return "\n".join(updated)

    @classmethod
    def get_options_metadata(cls) -> list[AnalyzerOption]:
        return [
            AnalyzerOption(
                name="min_score",
                type="float",
                default=0.85,
                min=0.0,
                max=1.0,
                interval=0.05,
                help="Minimum AcoustID match score (0.0-1.0); below this a file is skipped",
            ),
            AnalyzerOption(
                name="require_unique_match",
                type="bool",
                default=True,
                help="Skip files when two or more AcoustID results exceed the score threshold",
            ),
            AnalyzerOption(
                name="store_fingerprint",
                type="bool",
                default=False,
                help="Also write the raw Chromaprint fingerprint (1-3 KB per file)",
            ),
            AnalyzerOption(
                name="append_to_comments",
                type="bool",
                default=False,
                help="Append or update an 'MBID: <uuid>' line in the Comments field",
            ),
        ]

    @classmethod
    def get_thread_count(cls, options: dict[str, Any] | None = None) -> int:
        # AcoustID rate-limits to ~3 requests per second per key; we stay
        # single-threaded so a batch of files never trips the limit.
        return ANALYZER_THREAD_COUNT

    @classmethod
    def validate_file(cls, media_file) -> tuple[bool, str | None]:
        if not media_file.is_readable():
            return (False, "File is not readable")
        length = media_file.get_stream_info_value(KEY_LENGTH)
        if length is not None and length < MIN_DURATION_SECONDS:
            return (
                False,
                f"File shorter than {MIN_DURATION_SECONDS}s; fingerprinting is unreliable",
            )
        return (True, None)


def _resolve_fpcalc_path() -> str | None:
    """QSettings override > FPCALC env var > shutil.which('fpcalc')."""
    configured = get_qsettings().value(SETTINGS_FPCALC_PATH, "", type=str)
    if configured and os.path.isfile(configured):
        return configured
    env = os.environ.get("FPCALC")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("fpcalc")
    return found


def _resolve_api_key() -> str:
    """Configured override (QSettings) takes precedence over bundled default."""
    override = get_qsettings().value(SETTINGS_ACOUSTID_API_KEY, "", type=str)
    if override:
        return override
    return DEFAULT_ACOUSTID_API_KEY
