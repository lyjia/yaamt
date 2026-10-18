"""
Explicit manifest of all analyzer modules for static discovery.

This file exists to support compilation with Nuitka and other bundlers that
don't support runtime module discovery via pkgutil. Each analyzer module
is explicitly imported here, which triggers their self-registration via
the @analyzer() decorator.

When adding a new analyzer, add its import to this file.

Debug-only analyzers:
Analyzers decorated with @analyzer(..., debug_only=True) are automatically
excluded from release builds by the build system. No additional markers needed.
"""

# Within each category, import order is UI display order (best to worst);
# the first analyzer listed is the default.

# BPM analyzers
from providers.analysis.bpm import re3_bpm
from providers.analysis.bpm import librosa_bpm
from providers.analysis.bpm import aubio_bpm
from providers.analysis.bpm import stub_bpm

# Key analyzers
from providers.analysis.key import musical_cnn_key
from providers.analysis.key import re3_key
from providers.analysis.key import librosa_key

# Fingerprint analyzers
from providers.analysis.fingerprint import musicbrainz_acoustid

# Loudness analyzers (ReplayGain listed first so the setup dialog defaults to
# it in the Loudness category combo).
from providers.analysis.loudness import replaygain
from providers.analysis.loudness import peak_meter
