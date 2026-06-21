"""
Cross-platform utility for opening files in the system's file browser.

This module provides functionality to reveal a file in the native file browser
(Explorer on Windows, Finder on macOS, various file managers on Linux) with
the specified file selected.
"""

import os
import platform
import subprocess
import shutil
from pathlib import Path

from util.logging import log


def open_in_file_browser(file_path: str | Path) -> bool:
    """
    Open the system's file browser and select the specified file.

    This function works cross-platform:
    - Windows: Opens Explorer with the file selected
    - macOS: Opens Finder with the file revealed
    - Linux: Attempts to use common file managers (nautilus, dolphin, nemo, thunar, pcmanfm),
             falling back to xdg-open for the parent directory

    Args:
        file_path: Path to the file to reveal in the file browser.
                   Can be a string or Path object.

    Returns:
        True if the operation was initiated successfully, False otherwise.
        Note: A True return does not guarantee the file browser opened correctly,
        only that the command was dispatched without raising an exception.
    """
    path = Path(file_path).resolve()

    if not path.exists():
        log.warning(f"Cannot open in file browser: path does not exist: {path}")
        return False

    system = platform.system()

    try:
        if system == "Windows":
            return _open_windows(path)
        elif system == "Darwin":
            return _open_macos(path)
        else:
            # Assume Linux or other Unix-like
            return _open_linux(path)
    except Exception as e:
        log.error(f"Failed to open file browser: {e}")
        return False


def _open_windows(path: Path) -> bool:
    """Open Windows Explorer with the file selected."""
    # explorer /select expects the path with backslashes
    # Using subprocess.run to avoid issues with shell=True
    subprocess.run(
        ["explorer", "/select,", str(path)],
        check=False  # explorer returns non-zero on success sometimes
    )
    log.debug(f"Opened Explorer for: {path}")
    return True


def _open_macos(path: Path) -> bool:
    """Open Finder with the file revealed."""
    subprocess.run(
        ["open", "-R", str(path)],
        check=True
    )
    log.debug(f"Opened Finder for: {path}")
    return True


def _open_linux(path: Path) -> bool:
    """
    Open a Linux file manager with the file selected.

    Tries various common file managers in order of preference:
    1. nautilus (GNOME)
    2. dolphin (KDE)
    3. nemo (Cinnamon)
    4. thunar (Xfce)
    5. pcmanfm (LXDE)
    6. Falls back to xdg-open on the parent directory
    """
    # File managers that support selecting a specific file
    file_managers = [
        ("nautilus", ["nautilus", "--select", str(path)]),
        ("dolphin", ["dolphin", "--select", str(path)]),
        ("nemo", ["nemo", str(path)]),  # nemo selects the file automatically
        ("thunar", ["thunar", str(path)]),  # thunar selects the file automatically
        ("pcmanfm", ["pcmanfm", str(path)]),  # pcmanfm opens the directory
    ]

    for name, command in file_managers:
        if shutil.which(command[0]):
            try:
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                log.debug(f"Opened {name} for: {path}")
                return True
            except Exception as e:
                log.debug(f"Failed to open {name}: {e}")
                continue

    # Fallback: use xdg-open on the parent directory
    parent_dir = path.parent
    if shutil.which("xdg-open"):
        subprocess.Popen(
            ["xdg-open", str(parent_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log.debug(f"Opened xdg-open for parent directory: {parent_dir}")
        return True

    log.warning("No suitable file manager found on Linux")
    return False
