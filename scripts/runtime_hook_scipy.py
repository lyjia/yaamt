"""
PyInstaller runtime hook for scipy initialization.

Fixes scipy.stats lazy loading issues that cause 'obj is not defined' errors
in PyInstaller-bundled executables. This hook runs before the application
starts and ensures scipy modules are properly initialized.

Adapted from OpenKeyScan (references/openkeyscan-analyzer/runtime_hook_scipy.py).
"""

import sys
import warnings

# Suppress warnings during initialization
warnings.filterwarnings('ignore')


def _create_minimal_scipy_stats():
    """
    Create a minimal scipy.stats module with functions needed by scipy.signal.

    This is a workaround for the scipy.stats lazy loading issue in PyInstaller.
    scipy.signal._peak_finding requires scipy.stats.scoreatpercentile, which
    may fail to load due to PyInstaller's frozen module system.
    """
    print("[scipy hook] Creating minimal scipy.stats module", file=sys.stderr)

    import types
    import numpy as np

    stats_module = types.ModuleType('scipy.stats')

    def scoreatpercentile(a, per, limit=(), interpolation_method='fraction'):
        """Minimal implementation using numpy percentile."""
        return np.percentile(a, per)

    stats_module.scoreatpercentile = scoreatpercentile

    # Stub out common attributes that other modules may check for
    stats_module.norm = type('norm', (), {
        'cdf': lambda x: 0.5,
        'pdf': lambda x: 0.4,
        'ppf': lambda x: 0.0,
    })()

    sys.modules['scipy.stats'] = stats_module

    # Add sub-modules that might be imported
    for submod in ('_distn_infrastructure', 'distributions',
                   '_continuous_distns', '_discrete_distns'):
        sys.modules[f'scipy.stats.{submod}'] = types.ModuleType(
            f'scipy.stats.{submod}')

    print("[scipy hook] Minimal scipy.stats module created", file=sys.stderr)
    return stats_module


def _initialize_scipy():
    """Initialize scipy modules required by YAAMT."""
    try:
        import scipy
        import scipy._lib
        import scipy.special

        # Try normal scipy.stats import first
        try:
            import scipy.stats
            if hasattr(scipy.stats, 'scoreatpercentile'):
                print("[scipy hook] scipy.stats loaded normally",
                      file=sys.stderr)
            else:
                # Module loaded but missing expected function
                _create_minimal_scipy_stats()
        except Exception as e:
            if "'obj' is not defined" in str(e):
                print(f"[scipy hook] scipy.stats has PyInstaller issue: {e}",
                      file=sys.stderr)
            else:
                print(f"[scipy hook] scipy.stats import error: {e}",
                      file=sys.stderr)
            _create_minimal_scipy_stats()

        # Pre-import the scipy modules YAAMT actually uses
        import scipy.signal
        import scipy.fft
        import scipy.linalg

        print("[scipy hook] Core scipy modules loaded", file=sys.stderr)
        return True

    except Exception as e:
        print(f"[scipy hook] Error initializing scipy: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


# Run initialization
print("[scipy hook] Starting scipy initialization", file=sys.stderr)
success = _initialize_scipy()

# Pre-import numpy modules
try:
    import numpy
    import numpy.fft
    import numpy.linalg
    print("[scipy hook] Numpy modules initialized", file=sys.stderr)
except Exception as e:
    print(f"[scipy hook] Warning: Numpy initialization issue: {e}",
          file=sys.stderr)

if success:
    print("[scipy hook] Scipy hook completed successfully", file=sys.stderr)
else:
    print("[scipy hook] Scipy hook completed with warnings", file=sys.stderr)

# Restore warnings
warnings.filterwarnings('default')
