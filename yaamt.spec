# -*- mode: python ; coding: utf-8 -*-
"""
Unified PyInstaller spec file for YAAMT (Yet Another Audio Metadata Tool).

Builds both CLI (yaamt) and GUI (yaamt-gui) executables into a single output
folder with shared dependencies.

Environment variables (set by build.py):
    BUILD_MODE      - 'debug' or 'release' (default: 'debug')
    TARGET_ARCH     - 'x86_64', 'arm64', or None (auto-detect)
    YAAMT_ICON_DIR  - Path to icon directory (default: 'resources/icons')
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Read build configuration from environment
build_mode = os.environ.get('BUILD_MODE', 'debug')
target_arch = os.environ.get('TARGET_ARCH', None)
icon_dir = Path(os.environ.get('YAAMT_ICON_DIR', 'resources/icons'))

# Detect platform
is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

# ---------------------------------------------------------------------------
# Hidden imports for scipy (adapted from OpenKeyScan reference project).
# PyInstaller's static analysis misses many scipy submodules due to lazy
# loading and dynamic imports.
# ---------------------------------------------------------------------------
scipy_hiddenimports = [
    'scipy._lib',
    'scipy._lib.messagestream',
    'scipy.special',
    'scipy.special._cdflib',
    'scipy.special._ufuncs',
    'scipy.special._ufuncs_cxx',
    'scipy.stats',
    'scipy.stats._distn_infrastructure',
    'scipy.stats.distributions',
    'scipy.stats._continuous_distns',
    'scipy.stats._discrete_distns',
    'scipy.stats._stats_py',
    'scipy.stats._stats',
    'scipy.signal',
    'scipy.signal.windows',
    'scipy.signal._peak_finding',
    'scipy.fft',
    'scipy.fftpack',
    'scipy.linalg',
    'scipy.linalg.blas',
    'scipy.linalg.lapack',
]

# ---------------------------------------------------------------------------
# Excludes: packages that should never be in a distributable build.
# Build-time tools, test frameworks, and known-unused transitive deps.
# ---------------------------------------------------------------------------
excludes = [
    'pytest',
    'pytest_cov',
    'cx_Freeze',
    'nuitka',
    'lief',
    'imageio',
    'PIL',
    'tkinter',
    'unittest',
    # yaamt-eval only (not shipped in GUI/CLI builds)
    'pandas',
    'mingus',
]

# ---------------------------------------------------------------------------
# Runtime hooks
# ---------------------------------------------------------------------------
runtime_hooks = ['scripts/runtime_hook_scipy.py']

# ---------------------------------------------------------------------------
# Platform-specific icon
# ---------------------------------------------------------------------------
icon_path = None
if is_windows:
    candidate = icon_dir / 'app-icon-gui.ico'
    if candidate.exists():
        icon_path = str(candidate)
elif is_macos:
    candidate = icon_dir / 'app-icon-gui.icns'
    if candidate.exists():
        icon_path = str(candidate)
else:
    candidate = icon_dir / 'app-icon-gui.png'
    if candidate.exists():
        icon_path = str(candidate)

# ---------------------------------------------------------------------------
# Analysis: shared between CLI and GUI builds
# ---------------------------------------------------------------------------

# We build the GUI first (it has the heavier dependency tree) and then
# merge the CLI executable into the same COLLECT.
gui_a = Analysis(
    ['src/yaamt-gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=scipy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

cli_a = Analysis(
    ['src/yaamt.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=scipy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Merge CLI analysis into GUI to share dependencies in a single output folder
MERGE(
    (gui_a, 'yaamt-gui', 'yaamt-gui'),
    (cli_a, 'yaamt', 'yaamt'),
)

# ---------------------------------------------------------------------------
# PYZ archives
# ---------------------------------------------------------------------------
gui_pyz = PYZ(gui_a.pure, cipher=block_cipher)
cli_pyz = PYZ(cli_a.pure, cipher=block_cipher)

# ---------------------------------------------------------------------------
# Executables
# ---------------------------------------------------------------------------

# GUI executable (windowed on Windows/macOS, console on Linux)
gui_console = True if is_linux else False
gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name='yaamt-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=gui_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# CLI executable (always console)
cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name='yaamt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# ---------------------------------------------------------------------------
# COLLECT: single output folder with both executables and shared dependencies
# ---------------------------------------------------------------------------
coll = COLLECT(
    gui_exe,
    gui_a.binaries,
    gui_a.datas,
    cli_exe,
    cli_a.binaries,
    cli_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yaamt',
)
