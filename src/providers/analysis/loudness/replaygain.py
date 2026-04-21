"""
ReplayGain 2.0 analyzer.

Per-track and album gain + peak are computed by the libebur128 C library
via the ``pyebur128`` Python bindings. libebur128 is the reference
implementation of ITU-R BS.1770-4 / EBU R 128 and is also the engine
behind ffmpeg's ``ebur128`` filter, rsgain, loudgain, and bs1770gain —
values produced here should match those tools.

Why libebur128 instead of rolling our own:
    - ReplayGain/BS.1770 involves a K-weighting IIR filter pair, 400 ms
      block RMS with 75% overlap, and a two-stage (absolute + relative)
      gating algorithm. Reimplementing that correctly is ~150 lines of
      numerical code that every reviewer would need to verify against
      the spec. libebur128 is a stable, widely-used reference.
    - ``pyebur128.get_loudness_global_multiple()`` performs spec-correct
      album-level integration by combining per-track measurement states,
      which is exactly the operation we need for album gain.

Citations:
    - ITU-R BS.1770-4 (Oct 2015), "Algorithms to measure audio programme
      loudness and true-peak audio level": https://www.itu.int/rec/R-REC-BS.1770
    - EBU R 128 v4.0 (Jun 2020), "Loudness normalisation and permitted
      maximum level of audio signals": https://tech.ebu.ch/publications/r128
    - ReplayGain 2.0 specification (Hydrogenaudio Knowledgebase):
      https://wiki.hydrogenaud.io/index.php?title=ReplayGain_2.0_specification
      - Reference loudness: -18 LUFS
      - Gain tag value format: ``"%+.2f dB"`` (sign optional on positive
        values in practice; we emit ``"-1.23 dB"`` / ``"1.23 dB"``)
      - Peak tag value format: ``"%.6f"`` (linear amplitude, 6 decimals)
    - libebur128 (reference impl, Jan Kokemüller):
      https://github.com/jiixyj/libebur128
    - pyebur128 (Python bindings, Henrik Enquist):
      https://github.com/HEnquist/pyebur128

Album grouping is by ``(album.casefold(), album_artist.casefold())`` so
compilations tagged with ``album_artist="Various Artists"`` stay coherent
even when per-track ``artist`` differs. Tracks with a blank ``album`` tag
are excluded from album aggregation so we never emit misleading metadata.
"""

from typing import Any

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


# ReplayGain 2.0 reference loudness (LUFS). Per the Hydrogenaudio spec linked
# at the top of this file.
REFERENCE_LUFS = -18.0

# Comment-line markers used when ``append_to_comments`` is enabled. Kept
# consistent across runs so repeated analysis replaces the earlier line
# instead of stacking duplicates.
COMMENT_MARKER_TRACK = "ReplayGain Track:"
COMMENT_MARKER_ALBUM = "ReplayGain Album:"

# Analyzer option keys.
OPT_COMPUTE_TRACK = 'compute_track_gain'
OPT_COMPUTE_ALBUM = 'compute_album_gain'
OPT_APPEND_COMMENTS = 'append_to_comments'

# aggregation_data keys. These flow from analyze() (which may run in a worker
# process) to aggregate_results() (always in the main process) and must be
# picklable, so R128State objects are NOT stored here — aggregate_results
# rebuilds them by re-reading the audio when computing album gain.
_AGG_TRACK_LUFS = 'track_lufs'
_AGG_TRACK_PEAK = 'track_peak'
_AGG_ALBUM_KEY = 'album_key'


def _format_gain_db(gain_db: float) -> str:
    """ReplayGain-spec tag format: ``%+.2f dB`` (sign on positive omitted)."""
    return f"{gain_db:.2f} dB"


def _format_peak(peak: float) -> str:
    """ReplayGain-spec peak format: linear amplitude, 6 decimals."""
    return f"{peak:.6f}"


def _measure_track(media_file) -> tuple["R128State", float, float] | None:
    """
    Read the audio for ``media_file`` and return
    ``(R128State, integrated_lufs, sample_peak_max_of_channels)``.

    The returned R128State has been fully populated with the track's audio
    and is ready to be passed to ``get_loudness_global_multiple`` for album
    aggregation. Returns ``None`` if the audio is shorter than the 400 ms
    gating block (libebur128 would report -inf LUFS in that case, which is
    indistinguishable from silence).
    """
    import pyebur128 as eb
    import numpy as np

    descriptor = AudioFormatDescriptor(sample_width=4, sample_format='float')
    stream = media_file.get_audio_stream(descriptor)
    try:
        samples, sr = audio_stream_to_numpy(stream)
    finally:
        stream.close()

    if samples.ndim == 1:
        channels = 1
        n_frames = samples.shape[0]
        interleaved = np.ascontiguousarray(samples, dtype=np.float32)
    else:
        # audio_stream_to_numpy returns (C, N); libebur128 needs interleaved.
        channels, n_frames = samples.shape
        interleaved = np.ascontiguousarray(samples.T.reshape(-1), dtype=np.float32)

    # 400 ms minimum per BS.1770-4 block size.
    if n_frames < int(sr * 0.4):
        return None

    state = eb.R128State(
        channels,
        sr,
        eb.MeasurementMode.MODE_I | eb.MeasurementMode.MODE_SAMPLE_PEAK,
    )
    state.add_frames(interleaved, n_frames)
    track_lufs = eb.get_loudness_global(state)
    track_peak = max(eb.get_sample_peak(state, ch) for ch in range(channels))
    return state, float(track_lufs), float(track_peak)


@analyzer(AnalyzerCategory.LOUDNESS)
class ReplayGainAnalyzer(BatchAnalyzerBase):
    """
    ReplayGain 2.0 track + album gain analyzer built on libebur128.

    Per track: emits ``replaygain_track_gain`` and ``replaygain_track_peak``
    in the canonical ReplayGain string format (``"-6.24 dB"`` / ``"0.987654"``).

    After the full batch completes: groups tracks by
    ``(album, album_artist)`` and uses ``pyebur128.get_loudness_global_multiple``
    to compute spec-correct album LUFS across every track in the album, then
    emits ``replaygain_album_gain`` and ``replaygain_album_peak`` for each
    track in the group. Tracks with no album tag receive no album metadata.

    Options:
        - compute_track_gain: emit track-level tags (default True)
        - compute_album_gain: emit album-level tags (default True)
        - append_to_comments: also annotate the Comments field (default False)
    """

    name = "ReplayGain Analyzer"
    description = (
        "Computes ITU-R BS.1770 / EBU R128 integrated loudness and writes "
        "ReplayGain 2.0 track and album gain tags (-18 LUFS reference) using "
        "libebur128."
    )
    category = "loudness"
    version = "1.0.0"

    # ------------------------------------------------------------------ analyze

    def analyze(self) -> AnalyzerResult:
        try:
            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled

            try:
                import pyebur128  # noqa: F401
            except ImportError:
                return AnalyzerResult(
                    success=False,
                    error="pyebur128 not available - install with: pip install pyebur128"
                )

            log.debug(f"ReplayGain analyzing {self.media_file.file_path}")
            measurement = _measure_track(self.media_file)
            if measurement is None:
                return AnalyzerResult(
                    success=False,
                    error="Audio shorter than the 400 ms BS.1770 gating block",
                )

            _state, track_lufs, track_peak = measurement

            if self.is_cancelled:
                return AnalyzerResult(success=False, error=self._CANCELLATION_MESSAGE)

            compute_track = self.options.get(OPT_COMPUTE_TRACK, True)
            append_comments = self.options.get(OPT_APPEND_COMMENTS, False)

            # Only populate track-level fields when the option is on. The
            # aggregation_data payload is always populated because album
            # aggregation re-reads the audio anyway (R128State isn't
            # picklable across the process pool, so we don't carry it here).
            result_data: dict[str, Any] = {}
            track_gain_str = None
            if compute_track and track_lufs != float('-inf'):
                track_gain = REFERENCE_LUFS - track_lufs
                track_gain_str = _format_gain_db(track_gain)
                result_data[KEY_REPLAYGAIN_TRACK_GAIN] = track_gain_str
                result_data[KEY_REPLAYGAIN_TRACK_PEAK] = _format_peak(track_peak)

            if compute_track and append_comments and track_gain_str is not None:
                line = (
                    f"{COMMENT_MARKER_TRACK} {track_gain_str} "
                    f"(peak {_format_peak(track_peak)})"
                )
                existing = self.media_file.get_tag_simple(KEY_COMMENT) or ""
                result_data[KEY_COMMENT] = self.merge_comment_marker(
                    existing, COMMENT_MARKER_TRACK, line,
                )

            return AnalyzerResult(
                success=True,
                data=result_data,
                aggregation_data={
                    _AGG_TRACK_LUFS: track_lufs,
                    _AGG_TRACK_PEAK: track_peak,
                    _AGG_ALBUM_KEY: self._album_key_for_file(),
                },
            )

        except Exception as e:
            log.error(
                f"ReplayGain analysis failed for {self.media_file.file_path}: {e}",
                exc_info=True,
            )
            return AnalyzerResult(success=False, error=str(e))

    def _album_key_for_file(self) -> tuple[str, str] | None:
        """
        Build the ``(album, album_artist)`` grouping key, casefold and
        whitespace-stripped for case- and spacing-insensitive matching.
        Returns ``None`` when the album tag is blank — such files are
        excluded from album aggregation.
        """
        album = self.media_file.get_tag_simple(KEY_ALBUM) or ''
        album_artist = self.media_file.get_tag_simple(KEY_ALBUM_ARTIST) or ''
        album = str(album).strip().casefold()
        album_artist = str(album_artist).strip().casefold()
        if not album:
            return None
        return (album, album_artist)

    # ------------------------------------------------------------ aggregation

    @classmethod
    def aggregate_results(
        cls,
        completed_tasks: list,
        options: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Group completed tasks by album key and emit album_gain / album_peak.

        R128State objects cannot be pickled through the dispatcher's process
        pool, so we re-measure the audio in the main process here. libebur128
        is fast (~200 ms per 4-minute stereo track) so the extra pass is
        cheap relative to disk I/O.
        """
        if not options.get(OPT_COMPUTE_ALBUM, True):
            return {}

        try:
            import pyebur128  # noqa: F401
        except ImportError:
            log.warning("pyebur128 not available; skipping album aggregation")
            return {}

        # Bucket tasks by album key. Silent tracks (track_lufs == -inf) are
        # excluded from album aggregation so they don't drag the album LUFS
        # down — the spec gates them out anyway, but skipping here avoids a
        # wasted re-read.
        groups: dict[tuple[str, str], list] = {}
        for task in completed_tasks:
            agg = getattr(task.result, 'aggregation_data', None)
            if not agg or agg.get(_AGG_ALBUM_KEY) is None:
                continue
            if agg.get(_AGG_TRACK_LUFS, float('-inf')) == float('-inf'):
                continue
            groups.setdefault(agg[_AGG_ALBUM_KEY], []).append(task)

        append_comments = options.get(OPT_APPEND_COMMENTS, False)
        updates: dict[str, dict[str, Any]] = {}

        for album_key, tasks_in_group in groups.items():
            album_lufs = cls._compute_album_lufs(tasks_in_group)
            if album_lufs == float('-inf'):
                log.warning(
                    f"ReplayGain album aggregation produced -inf LUFS for "
                    f"album key {album_key}; skipping album tags"
                )
                continue

            album_peak = max(
                t.result.aggregation_data[_AGG_TRACK_PEAK]
                for t in tasks_in_group
            )
            album_gain = REFERENCE_LUFS - album_lufs
            gain_str = _format_gain_db(album_gain)
            peak_str = _format_peak(album_peak)

            for task in tasks_in_group:
                file_update: dict[str, Any] = {
                    KEY_REPLAYGAIN_ALBUM_GAIN: gain_str,
                    KEY_REPLAYGAIN_ALBUM_PEAK: peak_str,
                }
                if append_comments:
                    line = (
                        f"{COMMENT_MARKER_ALBUM} {gain_str} (peak {peak_str})"
                    )
                    existing = task.result.data.get(KEY_COMMENT)
                    if existing is None:
                        existing = (
                            task.media_file.get_tag_simple(KEY_COMMENT) or ""
                        )
                    file_update[KEY_COMMENT] = cls.merge_comment_marker(
                        existing, COMMENT_MARKER_ALBUM, line,
                    )
                updates[task.media_file.file_path] = file_update

        return updates

    @classmethod
    def _compute_album_lufs(cls, tasks_in_group: list) -> float:
        """
        Spec-correct album LUFS via libebur128's
        ``get_loudness_global_multiple``.

        Rebuilds one R128State per track by re-reading the audio. This is
        required because R128State isn't picklable across the process pool
        boundary — see the comment on aggregation_data above. If rebuilding
        a state fails for any reason (audio unreadable, file moved during
        the run, etc.), that track is dropped from the album aggregation
        rather than failing the whole album.
        """
        import pyebur128 as eb

        states = []
        for task in tasks_in_group:
            try:
                measurement = _measure_track(task.media_file)
            except Exception as e:
                log.warning(
                    f"Failed to re-measure {task.media_file.file_path} for "
                    f"album aggregation: {e}"
                )
                continue
            if measurement is None:
                continue
            states.append(measurement[0])

        if not states:
            return float('-inf')

        return float(eb.get_loudness_global_multiple(states))

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
                    'Scan and write album-level ReplayGain. Albums are '
                    'grouped by (album, album_artist) so compilations stay '
                    'coherent.'
                ),
            ),
            AnalyzerOption(
                name=OPT_APPEND_COMMENTS,
                type='bool',
                default=False,
                help=(
                    'Also append a human-readable gain/peak line to the '
                    'Comments field'
                ),
            ),
        ]

    @classmethod
    def validate_file(cls, media_file) -> tuple[bool, str | None]:
        if not media_file.is_readable():
            return (False, "File is not readable")
        return (True, None)
