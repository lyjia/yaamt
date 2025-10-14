"""
Stub BPM analyzer for testing the analyzer system.

This is a simple test analyzer that doesn't actually analyze audio,
but demonstrates the analyzer interface and can be used for testing
the auto-discovery and dispatcher systems.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox, QFormLayout

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from util.logging import log


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
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if BPM already exists (unless overwrite is enabled)
            overwrite = self.options.get('overwrite_existing', False)
            existing_bpm = self.media_file.get_tag_simple('bpm')

            if existing_bpm and not overwrite:
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="BPM already set"
                )

            # Return a fixed BPM value with specified decimal places
            bpm_value = 120.25

            log.debug(f"Stub analyzer returning BPM={bpm_value} for {self.media_file.file_path}")
            return AnalyzerResult(
                success=True,
                data={'bpm': bpm_value}
            )

        except Exception as e:
            log.error(f"Stub analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(
                success=False,
                error=str(e)
            )

    @classmethod
    def get_settings_widget(cls) -> Optional[QWidget]:
        """
        Return a QWidget for configuring decimal places.

        Returns:
            QWidget with decimal places spin box
        """
        widget = QWidget()
        layout = QFormLayout()

        # Create spin box for decimal places
        decimal_spin = QSpinBox()
        decimal_spin.setMinimum(0)
        decimal_spin.setMaximum(2)
        decimal_spin.setValue(0)
        decimal_spin.setObjectName("decimal_places")  # Important: used to retrieve value
        decimal_spin.setToolTip("Number of decimal places to use for BPM value (0-2)")

        layout.addRow("Decimal Places:", decimal_spin)

        widget.setLayout(layout)
        return widget

register_analyzer(AnalyzerCategory.BPM, StubBPMAnalyzer)