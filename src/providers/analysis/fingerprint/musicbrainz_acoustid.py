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

import contextlib
import os
import shutil
from typing import Any

from models.settings import get_qsettings
from providers import analyzer
from providers.analysis import AnalyzerBase, AnalyzerCategory, AnalyzerResult
from util.analyzer_options import AnalyzerOption
from util.const import (
    KEY_ACOUSTID_FINGERPRINT,
    KEY_ACOUSTID_ID,
    KEY_ACOUSTID_SCORE,
    KEY_COMMENT,
    KEY_LENGTH,
    KEY_MUSICBRAINZ_RECORDING_ID,
    SETTINGS_ACOUSTID_API_KEY,
)
from util.logging import log
from util.resource_manager import ResourceMetadata, get_resource_manager


# AcoustID's own requirement for a usable fingerprint. Below this we don't
# even bother calling fpcalc.
MIN_DURATION_SECONDS = 10

# AcoustID rate-limits submissions to ~3/s per key; keep this analyzer
# single-threaded to stay well inside that budget.
ANALYZER_THREAD_COUNT = 1

# Marker used when appending the MBID to the Comments field.
COMMENT_MARKER = "MBID:"

# Resource identifier for the Chromaprint fpcalc binary, registered with
# the global ResourceManager so it shows up in Preferences > Resources.
FPCALC_RESOURCE_ID = "chromaprint_fpcalc"
FPCALC_BINARY_NAME = "fpcalc.exe" if os.name == "nt" else "fpcalc"
CHROMAPRINT_DOWNLOAD_URL = "https://acoustid.org/chromaprint"


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
                error=(
                    "Chromaprint fpcalc not found. Install it from "
                    f"{CHROMAPRINT_DOWNLOAD_URL} and locate it in "
                    "Preferences > Resources."
                ),
            )

        api_key = _resolve_api_key()
        if not api_key:
            return AnalyzerResult(
                success=False,
                error="AcoustID API key not configured. Set one in Preferences > Integrations.",
            )

        min_score = float(self.options.get("min_score", 0.90))
        require_unique_match = bool(self.options.get("require_unique_match", True))
        store_fingerprint = bool(self.options.get("store_fingerprint", False))
        append_to_comments = bool(self.options.get("append_to_comments", False))

        # pyacoustid's ``fingerprint_file`` resolves its fpcalc binary
        # exclusively through ``os.environ.get('FPCALC', 'fpcalc')`` — there
        # is no path argument. ``force_fpcalc`` is a boolean toggle that
        # only chooses between the in-process Chromaprint library (via
        # audioread) and the external fpcalc binary; passing a path string
        # to it is silently ignored (the truthy value just selects the
        # binary backend). The only way to direct pyacoustid at a specific
        # fpcalc executable is to set the FPCALC env var, which the
        # ``_fpcalc_env`` context manager does for the duration of the
        # call and unwinds on exit so we don't leak into other workers.
        # We pass ``force_fpcalc=True`` to skip the audioread/Chromaprint
        # in-process path altogether — it depends on optional native
        # libraries (libav/ffmpeg) that yaamt doesn't currently bundle, so
        # behaviour stays predictable across machines.
        try:
            with _fpcalc_env(fpcalc_path):
                duration, fingerprint = acoustid.fingerprint_file(
                    self.media_file.file_path,
                    force_fpcalc=True,
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
            err_obj = response.get("error", {}) if isinstance(response, dict) else {}
            err_message = err_obj.get("message", "unknown AcoustID error")
            err_code = err_obj.get("code")
            log.error(
                f"AcoustID rejected lookup for {self.media_file.file_path}: "
                f"code={err_code}, message={err_message!r}, "
                f"raw_response={response!r}"
            )
            # AcoustID error code 4 ("Invalid API key") is by far the most
            # common confused-key case: users grab the personal key from
            # acoustid.org/api-key (intended for submissions) and try to
            # use it for lookups. Steer them at the application registration
            # page in the surfaced error so the fix is one click away.
            if err_code == 4:
                return AnalyzerResult(
                    success=False,
                    error=(
                        "AcoustID rejected the API key. Lookups require an "
                        "application API key, NOT the personal key from "
                        "acoustid.org/api-key. Register one at "
                        "https://acoustid.org/new-application and paste it "
                        "into Preferences > Integrations."
                    ),
                )
            return AnalyzerResult(success=False, error=f"AcoustID: {err_message}")

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

        # The score AcoustID reports describes the confidence of the whole
        # result cluster (AcoustID UUID + linked recordings), not an
        # individual MBID — that's why the stored tag is acoustid_score.
        # Trim to 4 decimal places per user spec; anything beyond that is
        # noise and just bloats the tag text.
        score_raw = top.get("score")
        score_str = f"{float(score_raw):.4f}" if score_raw is not None else None

        result_data: dict[str, Any] = {
            KEY_MUSICBRAINZ_RECORDING_ID: mbid,
            KEY_ACOUSTID_ID: acoustid_uuid,
        }
        if score_str is not None:
            result_data[KEY_ACOUSTID_SCORE] = score_str
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
                default=0.90,
                min=0.0,
                max=1.0,
                interval=0.05,
                help="Minimum AcoustID match score",
                tooltip=(
                    "The minimum AcoustID match confidence required to "
                    "accept a result. Files scoring below this are "
                    "skipped. Typical ranges:\n"
                    "\n"
                    "  0.95+  Essentially identical fingerprint; same "
                    "encoding of the same recording.\n"
                    "  0.85–0.95  Same recording, different encoding "
                    "(e.g. different bitrate or format).\n"
                    "  0.70–0.85  Probably the same recording, but "
                    "encoding differences are large enough that mismatches "
                    "start to appear.\n"
                    "  0.50–0.70  Risky — could be a different take, "
                    "remix, remaster, or cover.\n"
                    "  below 0.50  AcoustID's own threshold for treating "
                    "a result as low-confidence.\n"
                    "\n"
                    "The default 0.90 is conservative for automated "
                    "tagging: few false positives, at the cost of more "
                    "unmatched tracks. Lower it if you want to tag more "
                    "aggressively and are willing to review results."
                ),
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
    def get_settings_widget(cls):
        """Build the analyzer's settings widget.

        Prepends a Requirements status group above the auto-generated option
        widgets so the user can see at a glance whether fpcalc and the
        AcoustID API key are configured, with inline links that deep-link
        into the matching preferences pane.
        """
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        from windows.analyzer.option_widgets import build_widget_from_option

        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(_build_requirements_group())

        settings_group = f"analyzers/{cls.__name__}"
        for option in cls.get_options_metadata():
            layout.addWidget(build_widget_from_option(option, settings_group))

        widget.setLayout(layout)
        return widget

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

    @classmethod
    def get_required_resources(cls) -> list[ResourceMetadata]:
        # Chromaprint's fpcalc is distributed as a standalone binary. We list
        # it in Preferences > Resources with a browser-opening Download action
        # so the user lands on the Chromaprint download page and can install
        # whichever build matches their OS. Locate... uses
        # ``discovery_executable`` to preload the file dialog at the path
        # reported by ``shutil.which`` if fpcalc is already on PATH.
        return [
            ResourceMetadata(
                resource_id=FPCALC_RESOURCE_ID,
                url=CHROMAPRINT_DOWNLOAD_URL,
                filename=FPCALC_BINARY_NAME,
                expected_size=0,
                category="tools",
                subdirectory="chromaprint",
                display_name="Chromaprint fpcalc",
                description=(
                    "Command-line tool that computes Chromaprint acoustic "
                    "fingerprints. Required by the MusicBrainz AcoustID "
                    "analyzer."
                ),
                download_type="browser",
                required_by="MusicBrainzAcoustIDAnalyzer",
                discovery_executable="fpcalc",
            )
        ]


def _resolve_fpcalc_path() -> str | None:
    """Resource-manager custom location > FPCALC env var > PATH."""
    rm = get_resource_manager()
    custom = rm.get_custom_location(FPCALC_RESOURCE_ID)
    if custom and custom.is_file():
        return str(custom)
    env = os.environ.get("FPCALC")
    if env and os.path.isfile(env):
        return env
    return shutil.which("fpcalc")


@contextlib.contextmanager
def _fpcalc_env(path: str):
    """Temporarily point ``FPCALC`` at the resolved binary for pyacoustid.

    Background: pyacoustid's ``fingerprint_file`` (and any helper that
    calls it) discovers the fpcalc binary purely through
    ``os.environ.get('FPCALC', 'fpcalc')``. Its ``force_fpcalc`` kwarg is
    a backend selector (audioread vs. fpcalc), not a path override —
    handing it a string silently no-ops. Mutating the env var for the
    duration of the call is therefore the only sanctioned way to direct
    pyacoustid at a specific executable, e.g. one the user picked via
    Preferences > Resources > Locate... or one we found via
    ``shutil.which`` that we want to lock in for the call.

    The previous value is captured up front and restored on exit so
    parallel analyzer workers (or unrelated subprocesses inheriting our
    environment) keep the value the user actually set in their shell.
    """
    saved = os.environ.get("FPCALC")
    os.environ["FPCALC"] = path
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("FPCALC", None)
        else:
            os.environ["FPCALC"] = saved


def _resolve_api_key() -> str:
    """Read the AcoustID API key from QSettings. No bundled fallback — the
    user must supply their own key via Preferences > Integrations."""
    return get_qsettings().value(SETTINGS_ACOUSTID_API_KEY, "", type=str)


# AcoustID API key validation -----------------------------------------------
#
# Intentionally a no-op. We tried calling out to /v2/lookup with a probe
# fingerprint, but AcoustID validates request parameters before the client
# key — a malformed probe returns HTTP 400 (no structured error code to
# inspect), and finding a valid-but-tiny Chromaprint payload that AcoustID
# accepts proved fragile across API revisions. The first analysis run
# surfaces AcoustID's own error message in the analyzer summary if the key
# is bad, which is a more reliable signal than guessing in Preferences.
#
# The function is kept (rather than removed) so the ``ApiKeyField``
# verifier-callable plumbing stays in place for any future integration
# whose service does have a cheap ping endpoint.


def verify_acoustid_api_key(api_key: str) -> tuple[bool, str | None]:
    """No-op verifier: any value the user typed is accepted as-is."""
    log.debug("AcoustID verify: accepting key (no remote validation performed)")
    return True, None


# HTML rendered inside QLabel for the Requirements section. Both the
# check/X glyph and the optional Configure... link live in the same label
# so they flow on one line together.
_OK_MARK = '<span style="color:#2a7;">&#x2713;</span>'
_FAIL_MARK = '<span style="color:#c33;">&#x2717;</span>'
_CONFIGURE_LINK = '<a href="#prefs">Configure...</a>'
_PANE_RESOURCES = "Resources"
_PANE_INTEGRATIONS = "Integrations"


def _fpcalc_status_html() -> tuple[str, str | None]:
    """Return ``(html, tooltip)`` describing the current fpcalc state.

    The label text is deliberately short so the preferences/setup dialog
    doesn't stretch when the resolved path is long (common on Windows).
    The full path, when available, is surfaced as the label's tooltip
    instead of being rendered inline.
    """
    path = _resolve_fpcalc_path()
    if path:
        return (
            f"{_OK_MARK} Chromaprint <code>fpcalc</code> found",
            path,
        )
    return (
        f"{_FAIL_MARK} Chromaprint <code>fpcalc</code> not found. "
        f"{_CONFIGURE_LINK}",
        None,
    )


def _api_key_status_html() -> str:
    """Return HTML describing the current AcoustID API key state."""
    if _resolve_api_key():
        return f"{_OK_MARK} AcoustID API key configured"
    return f"{_FAIL_MARK} AcoustID API key not set. {_CONFIGURE_LINK}"


def _build_requirements_group():
    """Build the "Requirements" groupbox shown above the analyzer options.

    Two labels (fpcalc, API key) render with a green check or red X plus an
    inline Configure... link when the requirement isn't satisfied. Clicking
    the link opens the Preferences window scrolled to the relevant pane,
    and the labels refresh when preferences close so the user sees the
    effect of their edit without reopening this dialog.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

    group = QGroupBox("Requirements")
    layout = QVBoxLayout()

    fpcalc_label = QLabel()
    fpcalc_label.setObjectName("requirement_fpcalc")
    fpcalc_label.setTextFormat(Qt.TextFormat.RichText)
    fpcalc_label.setOpenExternalLinks(False)

    api_key_label = QLabel()
    api_key_label.setObjectName("requirement_acoustid_api_key")
    api_key_label.setTextFormat(Qt.TextFormat.RichText)
    api_key_label.setOpenExternalLinks(False)

    def refresh() -> None:
        fpcalc_html, fpcalc_tooltip = _fpcalc_status_html()
        fpcalc_label.setText(fpcalc_html)
        fpcalc_label.setToolTip(fpcalc_tooltip or "")
        api_key_label.setText(_api_key_status_html())

    def open_prefs(pane_name: str) -> None:
        from windows.preferences_window import PreferencesWindow
        prefs = PreferencesWindow(group.window())
        prefs.select_pane(pane_name)
        prefs.exec()
        refresh()

    fpcalc_label.linkActivated.connect(lambda _: open_prefs(_PANE_RESOURCES))
    api_key_label.linkActivated.connect(lambda _: open_prefs(_PANE_INTEGRATIONS))

    refresh()

    layout.addWidget(fpcalc_label)
    layout.addWidget(api_key_label)
    group.setLayout(layout)
    return group
