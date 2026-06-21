"""
Loudness analysis module.

This module contains analyzers for measuring audio loudness and dynamics.
Import order matters: whichever analyzer is registered first appears as the
default selection in the Loudness setup dialog combo.
"""
from .replaygain import ReplayGainAnalyzer
from .peak_meter import PeakMeterAnalyzer