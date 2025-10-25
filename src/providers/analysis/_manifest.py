"""
Explicit manifest of all analyzer modules for static discovery.

This file exists to support compilation with Nuitka and other bundlers that
don't support runtime module discovery via pkgutil. Each analyzer module
is explicitly imported here, which triggers their self-registration via
the register_analyzer() calls.

When adding a new analyzer, add its import to this file.

DEBUG_ONLY marker:
Lines marked with # DEBUG_ONLY are removed from release builds by the build system.
This allows excluding analyzers with heavy dependencies (like scipy) from release builds.
"""

# BPM analyzers
from providers.analysis.bpm import stub_bpm
from providers.analysis.bpm import aubio_bpm
from providers.analysis.bpm import re3_bpm   # DEBUG_ONLY
from providers.analysis.bpm import librosa_bpm # DEBUG_ONLY

# Key analyzers
from providers.analysis.key import re3_key   # DEBUG_ONLY
from providers.analysis.key import librosa_key # DEBUG_ONLY

# Fingerprint analyzers
# (none yet)

# Loudness analyzers
from providers.analysis.loudness import peak_meter
