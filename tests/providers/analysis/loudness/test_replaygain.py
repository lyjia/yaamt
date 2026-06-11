"""
Tests for ReplayGainAnalyzer.

The analyzer is a thin wrapper over libebur128 via the pyebur128 bindings,
so these tests verify the glue (option handling, album grouping rules,
canonical tag formatting, end-to-end MediaFile round-trip) rather than the
BS.1770 math itself — which is already tested upstream by libebur128.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("pyebur128")

from providers.analysis import AnalyzerCategory
from providers.analysis.base import AnalyzerResult, BatchAnalyzerBase
from providers.analysis.loudness.replaygain import (
    OPT_APPEND_COMMENTS,
    OPT_COMPUTE_ALBUM,
    OPT_COMPUTE_TRACK,
    REFERENCE_LUFS,
    ReplayGainAnalyzer,
)
from providers import get_analyzers_by_category
from models.media_file import MediaFile
from util.const import (
    KEY_ALBUM,
    KEY_ALBUM_ARTIST,
    KEY_COMMENT,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_ALBUM_PEAK,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK,
    KEY_TAG_GENERIC,
)


FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"


# ------------------------------------------------------ real-file helpers


def _copy_fixture_with_tags(
    tmp_path: Path,
    name: str,
    *,
    album: str = '',
    album_artist: str = '',
    source: str = "sample_dtmf_original.flac",
) -> Path:
    """Copy a FLAC fixture and stamp its album/album_artist tags.

    Always writes both tags (even when blank) so tests exercising the
    "no album tag" branch don't inherit the fixture's baked-in values.
    """
    src = FIXTURE_DIR / source
    if not src.exists():
        pytest.skip(f"fixture missing: {source}")
    dst = tmp_path / name
    shutil.copy(src, dst)
    mf = MediaFile(str(dst), enable_write=True)
    mf.save({KEY_TAG_GENERIC: {
        KEY_ALBUM: album,
        KEY_ALBUM_ARTIST: album_artist,
    }})
    return dst


def _analyze(path: Path, **options):
    mf = MediaFile(str(path), enable_write=False)
    analyzer = ReplayGainAnalyzer(mf, options)
    return analyzer.analyze(), mf


# ------------------------------------------------------ stubs for aggregate


@dataclass
class _StubTask:
    """Minimal stand-in for AnalysisTask used by aggregate_results tests."""
    media_file: Any
    result: AnalyzerResult
    options: dict = field(default_factory=dict)


def _real_task_for(path: Path, **options) -> _StubTask:
    """Run analyze() against a real file and wrap the result in a stub task."""
    result, mf = _analyze(path, **options)
    assert result.success, result.error
    return _StubTask(media_file=mf, result=result)


# --------------------------------------------------------------- discovery


class TestDiscovery:

    def test_registered_under_loudness_category(self):
        loudness = get_analyzers_by_category(AnalyzerCategory.LOUDNESS)
        assert ReplayGainAnalyzer in loudness

    def test_inherits_batch_base(self):
        assert issubclass(ReplayGainAnalyzer, BatchAnalyzerBase)

    def test_options_metadata(self):
        names = [o.name for o in ReplayGainAnalyzer.get_options_metadata()]
        assert OPT_COMPUTE_TRACK in names
        assert OPT_COMPUTE_ALBUM in names
        assert OPT_APPEND_COMMENTS in names

    def test_append_to_comments_default_off(self):
        by_name = {o.name: o for o in ReplayGainAnalyzer.get_options_metadata()}
        assert by_name[OPT_APPEND_COMMENTS].default is False

    def test_is_first_loudness_analyzer_for_default_selection(self):
        """AnalyzerSetupDialog defaults to combo index 0 when no user
        preference is saved, so ReplayGain must be the first analyzer
        registered under the Loudness category."""
        loudness = get_analyzers_by_category(AnalyzerCategory.LOUDNESS)
        assert loudness, "no loudness analyzers registered"
        assert loudness[0] is ReplayGainAnalyzer

    def test_peak_meter_is_debug_only(self):
        """PeakMeterAnalyzer should be gated behind debug mode so release
        builds surface only ReplayGain under the Loudness category."""
        from providers.analysis.loudness.peak_meter import PeakMeterAnalyzer
        assert PeakMeterAnalyzer.debug_only is True


# --------------------------------------------------------------- per-track


class TestPerTrackAnalysis:

    @pytest.fixture
    def flac_fixture(self, tmp_path):
        return _copy_fixture_with_tags(tmp_path, "x.flac")

    def test_emits_formatted_track_gain_and_peak(self, flac_fixture):
        result, _ = _analyze(flac_fixture, **{
            OPT_COMPUTE_TRACK: True, OPT_COMPUTE_ALBUM: False,
        })

        assert result.success, result.error
        assert not result.skipped

        # Gain tag: canonical ReplayGain "%.2f dB" format.
        gain_str = result.data[KEY_REPLAYGAIN_TRACK_GAIN]
        assert gain_str.endswith(" dB")
        float(gain_str.removesuffix(" dB"))  # must parse as float

        # Peak tag: canonical linear amplitude with 6 decimals.
        peak_str = result.data[KEY_REPLAYGAIN_TRACK_PEAK]
        assert len(peak_str.split('.')[-1]) == 6
        peak_val = float(peak_str)
        assert 0.0 <= peak_val <= 1.5  # float32 inter-sample overs possible

    def test_emits_aggregation_data(self, flac_fixture):
        result, _ = _analyze(flac_fixture)
        assert result.aggregation_data is not None
        for key in ('track_lufs', 'track_peak', 'album_key'):
            assert key in result.aggregation_data

    def test_emits_aggregation_data_even_when_track_disabled(self, flac_fixture):
        """compute_track_gain=False still populates aggregation_data for album use."""
        result, _ = _analyze(flac_fixture, **{
            OPT_COMPUTE_TRACK: False, OPT_COMPUTE_ALBUM: True,
        })
        assert result.success
        assert result.aggregation_data is not None
        assert KEY_REPLAYGAIN_TRACK_GAIN not in result.data
        assert KEY_REPLAYGAIN_TRACK_PEAK not in result.data

    def test_cancellation(self, flac_fixture):
        mf = MediaFile(str(flac_fixture), enable_write=False)
        analyzer = ReplayGainAnalyzer(mf)
        analyzer.cancel()
        result = analyzer.analyze()
        assert result.success is False
        assert 'cancel' in result.error.lower()

    def test_missing_pyebur128(self, flac_fixture):
        mf = MediaFile(str(flac_fixture), enable_write=False)
        with patch.dict('sys.modules', {'pyebur128': None}):
            result = ReplayGainAnalyzer(mf).analyze()
            assert result.success is False
            assert 'pyebur128' in result.error.lower()

    def test_track_gain_points_toward_reference_loudness(self, flac_fixture):
        """track_gain + track_lufs should equal REFERENCE_LUFS by definition."""
        result, _ = _analyze(flac_fixture)
        track_lufs = result.aggregation_data['track_lufs']
        gain_str = result.data[KEY_REPLAYGAIN_TRACK_GAIN]
        track_gain = float(gain_str.removesuffix(' dB'))
        # Rounded string values → tolerate rounding.
        assert abs((track_gain + track_lufs) - REFERENCE_LUFS) < 0.01

    def test_append_to_comments(self, flac_fixture):
        result, _ = _analyze(flac_fixture, **{
            OPT_COMPUTE_TRACK: True, OPT_APPEND_COMMENTS: True,
        })
        assert result.success
        assert KEY_COMMENT in result.data
        assert 'ReplayGain Track:' in result.data[KEY_COMMENT]


# --------------------------------------------------------------- album grouping


class TestAlbumAggregation:

    @pytest.fixture
    def album_of_three(self, tmp_path):
        """Three FLAC tracks tagged as the same album."""
        return [
            _copy_fixture_with_tags(tmp_path, f"a{i}.flac",
                                    album="Album One", album_artist="Artist X")
            for i in range(3)
        ]

    def test_groups_by_album_and_albumartist(self, tmp_path):
        tracks_a = [
            _copy_fixture_with_tags(tmp_path, f"album_a_{i}.flac",
                                    album="Album One", album_artist="Artist X")
            for i in range(2)
        ]
        tracks_b = [
            _copy_fixture_with_tags(tmp_path, f"album_b_{i}.flac",
                                    album="Album Two", album_artist="Artist Y")
            for i in range(2)
        ]

        all_tasks = [_real_task_for(p) for p in tracks_a + tracks_b]
        updates = ReplayGainAnalyzer.aggregate_results(
            all_tasks, {OPT_COMPUTE_ALBUM: True},
        )

        # Every track got an update.
        assert len(updates) == 4
        # Tracks sharing an album have matching album tags.
        gains_a = {updates[str(p)][KEY_REPLAYGAIN_ALBUM_GAIN] for p in tracks_a}
        gains_b = {updates[str(p)][KEY_REPLAYGAIN_ALBUM_GAIN] for p in tracks_b}
        assert len(gains_a) == 1  # consistent within album A
        assert len(gains_b) == 1  # consistent within album B

    def test_compilation_groups_by_albumartist_not_artist(self, tmp_path):
        """Tracks with the same album + album_artist="Various Artists" stay
        together even though per-track artist differs. The analyzer's
        grouping key intentionally uses album_artist, not artist."""
        tracks = [
            _copy_fixture_with_tags(tmp_path, f"comp_{i}.flac",
                                    album="Greatest Hits",
                                    album_artist="Various Artists")
            for i in range(2)
        ]
        tasks = [_real_task_for(p) for p in tracks]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: True},
        )
        assert len(updates) == 2
        gain_values = {updates[str(p)][KEY_REPLAYGAIN_ALBUM_GAIN] for p in tracks}
        assert len(gain_values) == 1

    def test_blank_album_excluded_from_aggregation(self, tmp_path):
        """Files with no album tag must not receive album-level metadata."""
        tracks = [
            _copy_fixture_with_tags(tmp_path, f"orphan_{i}.flac")  # no album
            for i in range(2)
        ]
        tasks = [_real_task_for(p) for p in tracks]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: True},
        )
        assert updates == {}

    def test_compute_album_gain_off_returns_empty(self, album_of_three):
        tasks = [_real_task_for(p) for p in album_of_three]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: False},
        )
        assert updates == {}

    def test_album_peak_is_max_of_track_peaks(self, album_of_three):
        """album_peak is a simple per-track max; album_gain comes from
        libebur128's integrated album LUFS."""
        tasks = [_real_task_for(p) for p in album_of_three]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: True},
        )
        # Every track in the album shares the same album_peak value.
        peaks = {upd[KEY_REPLAYGAIN_ALBUM_PEAK] for upd in updates.values()}
        assert len(peaks) == 1

        # That value equals the max of the per-track peaks (to 6 decimals).
        expected_peak_val = max(
            t.result.aggregation_data['track_peak'] for t in tasks
        )
        assert updates[str(album_of_three[0])][KEY_REPLAYGAIN_ALBUM_PEAK] == \
               f"{expected_peak_val:.6f}"

    def test_album_gain_points_toward_reference(self, album_of_three):
        """album_gain should be a finite dB value pointing toward REFERENCE_LUFS."""
        tasks = [_real_task_for(p) for p in album_of_three]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: True},
        )
        for upd in updates.values():
            gain_str = upd[KEY_REPLAYGAIN_ALBUM_GAIN]
            assert gain_str.endswith(' dB')
            gain_val = float(gain_str.removesuffix(' dB'))
            # Album gain is a sensible finite correction; normalise range.
            assert -60.0 < gain_val < 60.0

    def test_append_to_comments_includes_album_line(self, album_of_three):
        tasks = [_real_task_for(p) for p in album_of_three]
        updates = ReplayGainAnalyzer.aggregate_results(
            tasks, {OPT_COMPUTE_ALBUM: True, OPT_APPEND_COMMENTS: True},
        )
        for upd in updates.values():
            assert KEY_COMMENT in upd
            assert 'ReplayGain Album:' in upd[KEY_COMMENT]


# --------------------------------------------------------------- end-to-end write


class TestEndToEndWrite:
    """
    Exercise the full MediaFile.save() path with RG tags applied via generic
    keys. Validates that provider registration and the analyzer's formatted
    string outputs round-trip through mutagen.
    """

    def test_media_file_persists_analyzer_output(self, tmp_path):
        dst = _copy_fixture_with_tags(tmp_path, "e2e.flac")

        mf = MediaFile(str(dst), enable_write=True)
        analyzer = ReplayGainAnalyzer(mf, {
            OPT_COMPUTE_TRACK: True, OPT_COMPUTE_ALBUM: False,
        })
        result = analyzer.analyze()
        assert result.success, result.error

        mf.save({KEY_TAG_GENERIC: result.data})

        mf2 = MediaFile(str(dst))
        assert mf2.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) == \
               result.data[KEY_REPLAYGAIN_TRACK_GAIN]
        assert mf2.get_tag_simple(KEY_REPLAYGAIN_TRACK_PEAK) == \
               result.data[KEY_REPLAYGAIN_TRACK_PEAK]
