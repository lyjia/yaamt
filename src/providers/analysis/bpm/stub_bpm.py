"""
Stub BPM analyzer for testing the analyzer system.

This is a simple test analyzer that doesn't actually analyze audio,
but demonstrates the analyzer interface and can be used for testing
the auto-discovery and dispatcher systems.
"""

from typing import Optional, List

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox, QFormLayout

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import analyzer
from util.analyzer_options import AnalyzerOption
from util.bpm import BpmCandidate
from util.logging import log


@analyzer(AnalyzerCategory.BPM, debug_only=True)
class StubBPMAnalyzer(AnalyzerBase):
    """
    A stub analyzer for testing purposes.

    This analyzer doesn't perform real analysis - it just returns
    a fixed BPM value for testing the analyzer system.

    Analyzer-specific options:
        - 'decimal_places' (int): Number of decimal places for BPM (0-2, default: 0)
    """

    name = "Stub BPM Analyzer"
    description = "Test analyzer that returns a fixed BPM value"
    category = "bpm"
    version = "0.1.0"

    def analyze(self) -> AnalyzerResult:
        """
        Perform stub analysis.

        Returns:
            AnalyzerResult with a fixed BPM value
        """
        try:
            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled

            skipped = self._check_skip_if_exists('bpm', "BPM already set")
            if skipped is not None:
                return skipped

            # Return a fixed BPM value as a candidate
            bpm_value = 120.25

            log.debug(f"Stub analyzer returning BPM={bpm_value} for {self.media_file.file_path}")
            return AnalyzerResult(
                success=True,
                data={'bpm_candidates': [BpmCandidate(bpm=bpm_value, certainty=0.0)]}
            )

        except Exception as e:
            log.error(f"Stub analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(
                success=False,
                error=str(e)
            )

    @classmethod
    def get_options_metadata(cls) -> List[AnalyzerOption]:
        """
        Return option metadata for this analyzer.

        StubBPMAnalyzer has no configurable options - it returns a fixed value.

        Returns:
            Empty list (no options)
        """
        return []

    # Note: get_settings_widget() is inherited from AnalyzerBase
    # and will auto-generate from get_options_metadata() (returns None since no options)