"""
Tests for ReplayGainAnalyzer: per-track analysis against real fixtures and
album aggregation using synthetic AnalysisTask objects.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

pytest.importorskip("pyloudnorm")

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
    KEY_COMMENT,
    KEY_REPLAYGAIN_ALBUM_GAIN,
    KEY_REPLAYGAIN_ALBUM_PEAK,
    KEY_REPLAYGAIN_TRACK_GAIN,
    KEY_REPLAYGAIN_TRACK_PEAK,
    KEY_TAG_GENERIC,
)


FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "metadata"


# ----------------------------------------------------------------- test doubles


@dataclass
class _StubTask:
    """Minimal stand-in for AnalysisTask used by aggregate_results tests."""
    media_file: Any
    result: AnalyzerResult
    options: dict = None


class _StubMediaFile:
    """MediaFile stub with configurable tags — avoids touching real files."""
    def __init__(self, path: str, album: str = '', album_artist: str = '',
                 comment: str = ''):
        self.file_path = path
        self._tags = {
            'album': album,
            'albumartist': album_artist,
            'comment': comment,
        }

    def get_tag_simple(self, key, is_internal_tag_key=False):
        return self._tags.get(key) or None


def _make_stub_task(
    path: str,
    *,
    block_ms: np.ndarray,
    sample_rate: int = 48000,
    channels: int = 2,
    track_peak: float = 0.5,
    track_lufs: float = -20.0,
    duration: float = 10.0,
    album_key: tuple[str, str] | None = ('dark side', 'pink floyd'),
    existing_comment: str = '',
) -> _StubTask:
    agg = {
        'block_ms': block_ms,
        'sample_rate': sample_rate,
        'channels': channels,
        'track_peak': track_peak,
        'track_lufs': track_lufs,
        'duration_sec': duration,
        'album_key': album_key,
    }
    result = AnalyzerResult(success=True, data={}, aggregation_data=agg)
    mf = _StubMediaFile(path, comment=existing_comment)
    return _StubTask(media_file=mf, result=result)


def _rand_block_ms(num_blocks: int = 40, channels: int = 2,
                   seed: int = 0) -> np.ndarray:
    """Generate plausible K-weighted block MS values (positive floats)."""
    rng = np.random.default_rng(seed)
    return rng.uniform(1e-4, 5e-3, size=(channels, num_blocks))


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
        src = FIXTURE_DIR / "sample_dtmf_original.flac"
        if not src.exists():
            pytest.skip("fixture missing")
        dst = tmp_path / src.name
        shutil.copy(src, dst)
        return str(dst)

    def test_emits_track_gain_and_peak(self, flac_fixture):
        mf = MediaFile(flac_fixture, enable_write=False)
        analyzer = ReplayGainAnalyzer(mf, {OPT_COMPUTE_TRACK: True,
                                           OPT_COMPUTE_ALBUM: True})
        result = analyzer.analyze()

        assert result.success, result.error
        assert not result.skipped
        assert KEY_REPLAYGAIN_TRACK_GAIN in result.data
        assert KEY_REPLAYGAIN_TRACK_PEAK in result.data
        # Formatted strings.
        assert result.data[KEY_REPLAYGAIN_TRACK_GAIN].endswith("dB")
        # Peak is a 6-decimal number in [0, 1].
        peak_str = result.data[KEY_REPLAYGAIN_TRACK_PEAK]
        peak_val = float(peak_str)
        assert 0.0 <= peak_val <= 1.5  # might slightly exceed 1.0 for float32 inter-sample overs

    def test_emits_aggregation_data(self, flac_fixture):
        mf = MediaFile(flac_fixture, enable_write=False)
        analyzer = ReplayGainAnalyzer(mf)
        result = analyzer.analyze()

        assert result.aggregation_data is not None
        for key in ('block_ms', 'sample_rate', 'channels', 'track_peak',
                    'track_lufs', 'duration_sec', 'album_key'):
            assert key in result.aggregation_data

    def test_emits_aggregation_data_even_when_track_disabled(self, flac_fixture):
        """compute_track_gain=False still populates aggregation_data for album use."""
        mf = MediaFile(flac_fixture, enable_write=False)
        analyzer = ReplayGainAnalyzer(mf, {OPT_COMPUTE_TRACK: False,
                                           OPT_COMPUTE_ALBUM: True})
        result = analyzer.analyze()

        assert result.success
        assert result.aggregation_data is not None
        # No track tags were written.
        assert KEY_REPLAYGAIN_TRACK_GAIN not in result.data
        assert KEY_REPLAYGAIN_TRACK_PEAK not in result.data

    def test_cancellation(self, flac_fixture):
        mf = MediaFile(flac_fixture, enable_write=False)
        analyzer = ReplayGainAnalyzer(mf)
        analyzer.cancel()
        result = analyzer.analyze()
        assert result.success is False
        assert 'cancel' in result.error.lower()

    def test_missing_pyloudnorm(self, flac_fixture):
        mf = MediaFile(flac_fixture, enable_write=False)
        with patch.dict('sys.modules', {'pyloudnorm': None}):
            analyzer = ReplayGainAnalyzer(mf)
            result = analyzer.analyze()
            assert result.success is False
            assert 'pyloudnorm' in result.error.lower()

    def test_append_to_comments(self, flac_fixture):
        mf = MediaFile(flac_fixture, enable_write=False)
        analyzer = ReplayGainAnalyzer(mf, {OPT_COMPUTE_TRACK: True,
                                           OPT_APPEND_COMMENTS: True})
        result = analyzer.analyze()
        assert result.success
        assert KEY_COMMENT in result.data
        assert 'ReplayGain Track:' in result.data[KEY_COMMENT]


# --------------------------------------------------------------- album grouping


class TestAlbumAggregation:

    def test_groups_by_album_and_albumartist(self):
        t1 = _make_stub_task('a/1.flac', block_ms=_rand_block_ms(seed=1),
                             album_key=('album one', 'artist x'))
        t2 = _make_stub_task('a/2.flac', block_ms=_rand_block_ms(seed=2),
                             album_key=('album one', 'artist x'))
        t3 = _make_stub_task('b/1.flac', block_ms=_rand_block_ms(seed=3),
                             album_key=('album two', 'artist y'))

        updates = ReplayGainAnalyzer.aggregate_results(
            [t1, t2, t3], {OPT_COMPUTE_ALBUM: True},
        )

        assert set(updates.keys()) == {'a/1.flac', 'a/2.flac', 'b/1.flac'}
        # Tracks in the same album get the same album tags.
        assert updates['a/1.flac'][KEY_REPLAYGAIN_ALBUM_GAIN] == \
               updates['a/2.flac'][KEY_REPLAYGAIN_ALBUM_GAIN]
        # Distinct albums get (usually) distinct gains.
        assert updates['a/1.flac'][KEY_REPLAYGAIN_ALBUM_GAIN] != \
               updates['b/1.flac'][KEY_REPLAYGAIN_ALBUM_GAIN]

    def test_compilation_album_groups_by_albumartist_not_artist(self):
        # A compilation: same album + same "Various Artists" but different
        # per-track artists. Our grouping is album_key = (album, album_artist),
        # which ignores the per-track artist.
        compilation_key = ('greatest hits', 'various artists')
        t1 = _make_stub_task('c/1.flac', block_ms=_rand_block_ms(seed=1),
                             album_key=compilation_key)
        t2 = _make_stub_task('c/2.flac', block_ms=_rand_block_ms(seed=2),
                             album_key=compilation_key)

        updates = ReplayGainAnalyzer.aggregate_results(
            [t1, t2], {OPT_COMPUTE_ALBUM: True},
        )

        assert 'c/1.flac' in updates and 'c/2.flac' in updates
        assert updates['c/1.flac'][KEY_REPLAYGAIN_ALBUM_GAIN] == \
               updates['c/2.flac'][KEY_REPLAYGAIN_ALBUM_GAIN]

    def test_blank_album_excluded_from_aggregation(self):
        t1 = _make_stub_task('s/1.flac', block_ms=_rand_block_ms(seed=1),
                             album_key=None)
        t2 = _make_stub_task('s/2.flac', block_ms=_rand_block_ms(seed=2),
                             album_key=None)

        updates = ReplayGainAnalyzer.aggregate_results(
            [t1, t2], {OPT_COMPUTE_ALBUM: True},
        )
        assert updates == {}

    def test_silent_track_excluded(self):
        # A silent track reports -inf LUFS; aggregator must skip it.
        normal = _make_stub_task('n/1.flac', block_ms=_rand_block_ms(seed=1),
                                 track_lufs=-18.0)
        silent = _make_stub_task('n/2.flac', block_ms=np.zeros((2, 40)),
                                 track_lufs=float('-inf'))

        updates = ReplayGainAnalyzer.aggregate_results(
            [normal, silent], {OPT_COMPUTE_ALBUM: True},
        )
        assert 'n/1.flac' in updates
        assert 'n/2.flac' not in updates

    def test_compute_album_gain_off_returns_empty(self):
        t = _make_stub_task('x/1.flac', block_ms=_rand_block_ms())
        updates = ReplayGainAnalyzer.aggregate_results(
            [t], {OPT_COMPUTE_ALBUM: False},
        )
        assert updates == {}

    def test_album_peak_is_max_of_track_peaks(self):
        t1 = _make_stub_task('p/1.flac', block_ms=_rand_block_ms(seed=1),
                             track_peak=0.75)
        t2 = _make_stub_task('p/2.flac', block_ms=_rand_block_ms(seed=2),
                             track_peak=0.92)
        updates = ReplayGainAnalyzer.aggregate_results(
            [t1, t2], {OPT_COMPUTE_ALBUM: True},
        )
        for upd in updates.values():
            assert upd[KEY_REPLAYGAIN_ALBUM_PEAK] == "0.920000"

    def test_append_to_comments_includes_album_line(self):
        t = _make_stub_task('q/1.flac', block_ms=_rand_block_ms(seed=1))
        updates = ReplayGainAnalyzer.aggregate_results(
            [t], {OPT_COMPUTE_ALBUM: True, OPT_APPEND_COMMENTS: True},
        )
        assert KEY_COMMENT in updates['q/1.flac']
        assert 'ReplayGain Album:' in updates['q/1.flac'][KEY_COMMENT]

    def test_mixed_channel_count_falls_back_to_energy_weighted(self):
        # Same album, different channel counts — aggregator should fall back
        # to energy-weighted mean instead of raising.
        t1 = _make_stub_task('m/1.flac', block_ms=_rand_block_ms(channels=2, seed=1),
                             channels=2, track_lufs=-18.0)
        t2 = _make_stub_task('m/2.flac', block_ms=_rand_block_ms(channels=1, seed=2),
                             channels=1, track_lufs=-20.0)
        updates = ReplayGainAnalyzer.aggregate_results(
            [t1, t2], {OPT_COMPUTE_ALBUM: True},
        )
        # Both tracks get album tags; gain is finite.
        assert 'm/1.flac' in updates and 'm/2.flac' in updates
        gain_str = updates['m/1.flac'][KEY_REPLAYGAIN_ALBUM_GAIN]
        assert gain_str.endswith('dB')


# --------------------------------------------------------------- end-to-end write


class TestEndToEndWrite:
    """
    Exercise the full MediaFile.save() path with RG tags applied via generic
    keys. This validates that Phase 2 provider registration and the analyzer's
    formatted string outputs round-trip through mutagen.
    """

    def test_media_file_persists_analyzer_output(self, tmp_path):
        src = FIXTURE_DIR / "sample_dtmf_original.flac"
        if not src.exists():
            pytest.skip("fixture missing")
        dst = tmp_path / src.name
        shutil.copy(src, dst)

        mf = MediaFile(str(dst), enable_write=True)
        analyzer = ReplayGainAnalyzer(mf, {OPT_COMPUTE_TRACK: True,
                                           OPT_COMPUTE_ALBUM: False})
        result = analyzer.analyze()
        assert result.success, result.error

        mf.save({KEY_TAG_GENERIC: result.data})

        # Read back.
        mf2 = MediaFile(str(dst))
        assert mf2.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) == \
               result.data[KEY_REPLAYGAIN_TRACK_GAIN]
        assert mf2.get_tag_simple(KEY_REPLAYGAIN_TRACK_PEAK) == \
               result.data[KEY_REPLAYGAIN_TRACK_PEAK]
