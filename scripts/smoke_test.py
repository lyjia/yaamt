#!/usr/bin/env python3
"""
Smoke-test a frozen YAAMT build (PyInstaller output or installed copy).

Catches the failures unit tests cannot: missing hidden imports, missing
shared libraries or Qt plugins, and a wrong stamped version. Runs the
frozen CLI and GUI executables only - never the source tree.

Checks:
  1. `yaamt --version` prints the expected version (if --expect-version).
  2. `yaamt list analyzers` succeeds (imports every registered analyzer).
  3. A few analyzers run end-to-end on a copy of a test fixture
     (exercises numpy / scipy / librosa / numba / libebur128).
  4. The GUI starts under Qt's offscreen platform and stays up.

Stdlib-only so it runs on every CI runner without an install step.

Usage:
    python scripts/smoke_test.py <dir-containing-yaamt-executables> [--expect-version V]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "metadata" / "lyjia_house_beat_generic_128bpm.wav"
EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""
CLI_NAME = f"yaamt{EXE_SUFFIX}"
GUI_NAME = f"yaamt-gui{EXE_SUFFIX}"

# Analyzers that need no network or downloaded model files.
OFFLINE_ANALYZERS = [
    "LibrosaBeatTrackingBPMAnalyzer",
    "LibrosaChromagramKeyAnalyzer",
    "ReplayGainAnalyzer",
]

CLI_TIMEOUT_SECONDS = 300
GUI_STARTUP_SECONDS = 20


def _run_cli(cli: Path, *args: str) -> str:
    """Run the CLI; return its stdout. stderr is echoed for the CI log."""
    print(f"$ {cli.name} {' '.join(args)}", flush=True)
    result = subprocess.run([str(cli), *args], capture_output=True, text=True,
                            timeout=CLI_TIMEOUT_SECONDS)
    if result.stderr:
        print(result.stderr.strip()[-2000:])
    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError(f"{cli.name} {' '.join(args)} exited {result.returncode}")
    return result.stdout


def _check_gui(gui: Path) -> None:
    """Start the GUI headless; it must still be running after startup."""
    print(f"$ {gui.name} (offscreen, {GUI_STARTUP_SECONDS}s)", flush=True)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryFile() as log_file:
        proc = subprocess.Popen([str(gui)], env=env, stdout=log_file, stderr=subprocess.STDOUT)
        time.sleep(GUI_STARTUP_SECONDS)
        exit_code = proc.poll()
        if exit_code is None:
            proc.kill()
            proc.wait()
            return
        log_file.seek(0)
        print(log_file.read().decode(errors="replace"))
        raise RuntimeError(f"{gui.name} exited during startup with code {exit_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("bin_dir", type=Path, help="Directory containing the yaamt executables")
    parser.add_argument("--expect-version", help="Version `yaamt --version` must print")
    args = parser.parse_args()

    cli = args.bin_dir / CLI_NAME
    gui = args.bin_dir / GUI_NAME
    for exe in (cli, gui):
        if not exe.is_file():
            print(f"FAIL: executable not found: {exe}", file=sys.stderr)
            return 1

    try:
        version = _run_cli(cli, "--version").strip().splitlines()[-1]
        print(f"  version: {version}")
        if args.expect_version and version != args.expect_version:
            raise RuntimeError(f"expected version {args.expect_version!r}, got {version!r}")

        _run_cli(cli, "list", "analyzers")

        # Never touch the fixture itself; analyze a scratch copy.
        with tempfile.TemporaryDirectory() as scratch:
            sample = Path(scratch) / FIXTURE.name
            shutil.copy2(FIXTURE, sample)
            for analyzer in OFFLINE_ANALYZERS:
                print(_run_cli(cli, "analyze", analyzer, str(sample)).strip()[-400:])

        _check_gui(gui)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
