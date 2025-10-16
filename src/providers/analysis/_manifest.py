"""
Explicit manifest of all analyzer modules for static discovery.

This file exists to support compilation with Nuitka and other bundlers that
don't support runtime module discovery via pkgutil. Each analyzer module
is explicitly imported here, which triggers their self-registration via
the register_analyzer() calls.

When adding a new analyzer, add its import to this file.
"""

# BPM analyzers
from providers.analysis.bpm import stub_bpm
from providers.analysis.bpm import aubio_bpm

# Key analyzers
# (none yet)

# Fingerprint analyzers
# (none yet)

# Loudness analyzers
from providers.analysis.loudness import peak_meter
