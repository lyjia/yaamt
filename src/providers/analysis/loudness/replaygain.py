"""
ReplayGain 2.0 analyzer.

Computes BS.1770 / EBU R128 integrated loudness per track, then aggregates
across tracks grouped by (album, album_artist) to produce album-level gain.

Why this is a BatchAnalyzer:
- Track gain depends only on the file itself and could be written immediately.
- Album gain depends on every track in the album, so writes must be deferred
  until the whole batch has been measured. BatchAnalyzerBase + the dispatcher's
  aggregation hook make this clean: analyze() emits both the per-track tag data
  AND an ``aggregation_data`` payload carrying the 400 ms K-weighted block
  mean-squares. aggregate_results() concatenates those per-album, re-runs
  BS.1770 gating, and merges album_gain/album_peak (and optional comment
  annotations) into each task's final write-out.

Grouping key is ``(album.strip().lower(), album_artist.strip().lower())``
so compilations grouped by ``album_artist='Various Artists'`` stay coherent
even when per-track ``artist`` differs. Tracks with a blank ``album`` tag are
skipped for album aggregation so we never emit misleading album metadata.
"""

from typing import TYPE_CHECKING, Any

import numpy as np

from providers.analysis import AnalyzerCategory, AnalyzerResult
from providers.analysis.base import BatchAnalyzerBase
from providers import analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption
from util.audio_numpy import audio_stream_to_numpy
from util.const import (
    KEY_ALBUM,
    KEY_ALBUM_ARTIST,
    KEY_COMMENT,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_ALBUM_PEAK,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK,
)
from util.logging import log

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


# ReplayGain 2.0 reference loudness per spec.
REFERENCE_LUFS = -18.0

# Marker string used when annotating the Comments field. Shared between the
# per-track analyze() and the album-level aggregation so we don't accumulate
# duplicate lines across re-runs.
COMMENT_MARKER_TRACK = "ReplayGain Track:"
COMMENT_MARKER_ALBUM = "ReplayGain Album:"

# Option keys.
OPT_COMPUTE_TRACK = 'compute_track_gain'
OPT_COMPUTE_ALBUM = 'compute_album_gain'
OPT_APPEND_COMMENTS = 'append_to_comments'

# Internal aggregation_data keys.
_AGG_BLOCK_MS = 'block_ms'
_AGG_SAMPLE_RATE = 'sample_rate'
_AGG_CHANNELS = 'channels'
_AGG_TRACK_PEAK = 'track_peak'
_AGG_TRACK_LUFS = 'track_lufs'
_AGG_DURATION = 'duration_sec'
_AGG_ALBUM_KEY = 'album_key'


@analyzer(AnalyzerCategory.LOUDNESS)
class ReplayGainAnalyzer(BatchAnalyzerBase):
    """
    ReplayGain 2.0 (EBU R128, -18 LUFS reference) track + album gain analyzer.

    Per track it emits ``replaygain_track_gain`` and ``replaygain_track_peak``
    in the canonical ReplayGain string format (``"-6.24 dB"`` / ``"0.987654"``).

    After the full batch completes, it groups tracks by their
    (album, album_artist) pair and computes album LUFS by re-gating the
    concatenated per-track block mean-squares, then emits
    ``replaygain_album_gain`` and ``replaygain_album_peak`` for every track in
    each album. Tracks with no album tag are never given album metadata.

    Analyzer options:
        - compute_track_gain: emit track-level tags (default True)
        - compute_album_gain: emit album-level tags (default True)
        - append_to_comments: also annotate the Comments field (default False)
    """

    name = "ReplayGain Analyzer"
    description = (
        "Computes ITU-R BS.1770 / EBU R128 integrated loudness and writes "
        "ReplayGain 2.0 track and album gain tags (-18 LUFS reference)."
    )
    category = "loudness"
    version = "1.0.0"

    # ------------------------------------------------------------------ analyze

    def analyze(self) -> AnalyzerResult:
        audio_stream = None
        try:
            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled

            try:
                import pyloudnorm  # noqa: F401
            except ImportError:
                return AnalyzerResult(
                    success=False,
                    error="pyloudnorm not available - install with: pip install pyloudnorm"
                )

            from util.loudness import (
                compute_block_mean_squares,
                format_gain_db,
                format_peak,
                gated_lufs_from_blocks,
            )
            import pyloudnorm as pyln

            # Request float32 audio at native sample rate and channels. Keep
            # channel count intact so the K-weighting channel gains apply
            # correctly; pyloudnorm supports up to 5 channels.
            descriptor = AudioFormatDescriptor(
                sample_width=4,
                sample_format='float',
            )
            audio_stream = self.media_file.get_audio_stream(descriptor)
            sample_rate = audio_stream.sample_rate
            channels = audio_stream.channels_qty

            samples, _ = audio_stream_to_numpy(audio_stream)
            audio_stream.close()
            audio_stream = None

            # audio_stream_to_numpy returns mono as shape (N,) and multi-channel
            # as (C, N). pyloudnorm and our helper both want (N, C).
            if samples.ndim == 1:
                data = samples.reshape(-1, 1)
            else:
                data = samples.T

            if data.shape[0] < int(sample_rate * 0.4):
                # Shorter than a single 400 ms gating block — bail out rather
                # than produce nonsense.
                return AnalyzerResult(
                    success=False,
                    error="Audio shorter than the 400 ms BS.1770 gating block"
                )

            if self.is_cancelled:
                return AnalyzerResult(success=False, error=self._CANCELLATION_MESSAGE)

            log.debug(
                f"ReplayGain analyzing {self.media_file.file_path}: "
                f"{data.shape[0]} samples, {channels}ch at {sample_rate} Hz"
            )

            track_peak = float(np.max(np.abs(data))) if data.size else 0.0
            block_ms = compute_block_mean_squares(data, sample_rate)
            track_lufs = gated_lufs_from_blocks(block_ms)
            duration = data.shape[0] / sample_rate

            # Options — default to the more-inclusive behaviour for any
            # compute_* option the user didn't explicitly set.
            compute_track = self.options.get(OPT_COMPUTE_TRACK, True)
            append_comments = self.options.get(OPT_APPEND_COMMENTS, False)

            result_data: dict[str, Any] = {}
            comment_lines: list[tuple[str, str]] = []

            if compute_track and np.isfinite(track_lufs):
                track_gain = REFERENCE_LUFS - track_lufs
                result_data[KEY_REPLAYGAIN_TRACK_GAIN] = format_gain_db(track_gain)
                result_data[KEY_REPLAYGAIN_TRACK_PEAK] = format_peak(track_peak)
                if append_comments:
                    comment_lines.append((
                        COMMENT_MARKER_TRACK,
                        f"{COMMENT_MARKER_TRACK} {format_gain_db(track_gain)} "
                        f"(peak {format_peak(track_peak)})"
                    ))

            if comment_lines:
                result_data[KEY_COMMENT] = self._merge_comments(comment_lines)

            album_key = self._album_key_for_file()
            aggregation_data = {
                _AGG_BLOCK_MS: block_ms,
                _AGG_SAMPLE_RATE: sample_rate,
                _AGG_CHANNELS: channels,
                _AGG_TRACK_PEAK: track_peak,
                _AGG_TRACK_LUFS: track_lufs,
                _AGG_DURATION: duration,
                _AGG_ALBUM_KEY: album_key,
            }

            return AnalyzerResult(
                success=True,
                data=result_data,
                aggregation_data=aggregation_data,
            )

        except Exception as e:
            log.error(
                f"ReplayGain analysis failed for {self.media_file.file_path}: {e}",
                exc_info=True,
            )
            return AnalyzerResult(success=False, error=str(e))
        finally:
            if audio_stream is not None:
                try:
                    audio_stream.close()
                except Exception as close_err:
                    log.warning(f"Error closing audio stream: {close_err}")

    def _album_key_for_file(self) -> tuple[str, str] | None:
        """
        Build the album-grouping key for this file, or None if the file
        should be excluded from album-level aggregation.

        Grouping is case- and whitespace-insensitive on both fields. A blank
        album name makes the file a "single" which never receives album tags.
        A blank album_artist falls back to an empty string so that two tracks
        on the same album without album_artist still group together.
        """
        album = self.media_file.get_tag_simple(KEY_ALBUM) or ''
        album_artist = self.media_file.get_tag_simple(KEY_ALBUM_ARTIST) or ''
        album = str(album).strip().casefold()
        album_artist = str(album_artist).strip().casefold()
        if not album:
            return None
        return (album, album_artist)

    def _merge_comments(self, new_lines: list[tuple[str, str]]) -> str:
        """Apply one or more (marker, line) replacements to the existing Comments value."""
        existing = self.media_file.get_tag_simple(KEY_COMMENT) or ""
        for marker, line in new_lines:
            existing = self.merge_comment_marker(existing, marker, line)
        return existing

    # ------------------------------------------------------------ aggregation

    @classmethod
    def aggregate_results(
        cls,
        completed_tasks: list,
        options: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Group tasks by album key and emit album_gain / album_peak (and
        optional Comments annotation) per file.
        """
        if not options.get(OPT_COMPUTE_ALBUM, True):
            return {}

        from util.loudness import (
            aggregate_album_lufs,
            energy_weighted_lufs,
            format_gain_db,
            format_peak,
        )

        # Bucket tasks by album key.
        groups: dict[tuple[str, str], list] = {}
        for task in completed_tasks:
            agg = getattr(task.result, 'aggregation_data', None)
            if not agg or agg.get(_AGG_ALBUM_KEY) is None:
                continue
            if not np.isfinite(agg.get(_AGG_TRACK_LUFS, float('-inf'))):
                # Silent track — exclude from album aggregation.
                continue
            groups.setdefault(agg[_AGG_ALBUM_KEY], []).append(task)

        append_comments = options.get(OPT_APPEND_COMMENTS, False)
        updates: dict[str, dict[str, Any]] = {}

        for album_key, tasks_in_group in groups.items():
            album_lufs = cls._compute_album_lufs(tasks_in_group)
            if not np.isfinite(album_lufs):
                log.warning(
                    f"ReplayGain album aggregation produced non-finite LUFS "
                    f"for album key {album_key}; skipping album tags"
                )
                continue

            album_peak = max(
                t.result.aggregation_data[_AGG_TRACK_PEAK] for t in tasks_in_group
            )
            album_gain = REFERENCE_LUFS - album_lufs
            gain_str = format_gain_db(album_gain)
            peak_str = format_peak(album_peak)

            for task in tasks_in_group:
                file_update: dict[str, Any] = {
                    KEY_REPLAYGAIN_ALBUM_GAIN: gain_str,
                    KEY_REPLAYGAIN_ALBUM_PEAK: peak_str,
                }
                if append_comments:
                    line = f"{COMMENT_MARKER_ALBUM} {gain_str} (peak {peak_str})"
                    existing = task.result.data.get(KEY_COMMENT)
                    if existing is None:
                        existing = task.media_file.get_tag_simple(KEY_COMMENT) or ""
                    file_update[KEY_COMMENT] = cls.merge_comment_marker(
                        existing, COMMENT_MARKER_ALBUM, line,
                    )
                updates[task.media_file.file_path] = file_update

        return updates

    @classmethod
    def _compute_album_lufs(cls, tasks_in_group: list) -> float:
        """
        Compute integrated album LUFS for a list of tasks on the same album.

        Prefer spec-correct block-mean-square concatenation. Fall back to
        duration-weighted energy averaging when channel counts or sample rates
        are mismatched across the group (rare in practice).
        """
        from util.loudness import aggregate_album_lufs, energy_weighted_lufs

        agg_datas = [t.result.aggregation_data for t in tasks_in_group]
        sample_rates = {a[_AGG_SAMPLE_RATE] for a in agg_datas}
        channel_counts = {a[_AGG_CHANNELS] for a in agg_datas}

        if len(sample_rates) == 1 and len(channel_counts) == 1:
            try:
                return aggregate_album_lufs([a[_AGG_BLOCK_MS] for a in agg_datas])
            except ValueError as err:
                log.warning(
                    f"Album block-MS aggregation failed ({err}); falling back "
                    f"to energy-weighted average"
                )

        log.info(
            "Mixed sample rates or channel counts across album "
            f"(sr={sample_rates}, ch={channel_counts}); using energy-weighted LUFS"
        )
        return energy_weighted_lufs(
            [(a[_AGG_TRACK_LUFS], a[_AGG_DURATION]) for a in agg_datas]
        )

    # ------------------------------------------------------------------ options

    @classmethod
    def get_options_metadata(cls) -> list[AnalyzerOption]:
        return [
            AnalyzerOption(
                name=OPT_COMPUTE_TRACK,
                type='bool',
                default=True,
                help='Scan and write track-level ReplayGain (gain + peak)',
            ),
            AnalyzerOption(
                name=OPT_COMPUTE_ALBUM,
                type='bool',
                default=True,
                help=(
                    'Scan and write album-level ReplayGain. Albums are grouped '
                    'by (album, album_artist) so compilations stay coherent.'
                ),
            ),
            AnalyzerOption(
                name=OPT_APPEND_COMMENTS,
                type='bool',
                default=False,
                help='Also append a human-readable gain/peak line to the Comments field',
            ),
        ]

    @classmethod
    def validate_file(cls, media_file) -> tuple[bool, str | None]:
        if not media_file.is_readable():
            return (False, "File is not readable")
        return (True, None)
