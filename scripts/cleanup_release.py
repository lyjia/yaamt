#!/usr/bin/env python3
"""
Post-build cleanup for YAAMT PyInstaller distributions.

Removes unused Qt modules, build-time dependencies that leaked into the
output, and other unnecessary files to reduce distribution size.

Modeled on OpenKeyScan's cleanup_video_deps.py pattern.

Usage:
    python scripts/cleanup_release.py <dist_path>
    python scripts/cleanup_release.py <dist_path> --dry-run

Examples:
    python scripts/cleanup_release.py build/release-20260401/yaamt
    python scripts/cleanup_release.py build/release-20260401/yaamt --dry-run
"""

import sys
import argparse
import shutil
from pathlib import Path


def get_dir_size(path: Path) -> int:
    """Get total size of a directory in bytes."""
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())


def get_file_size(path: Path) -> int:
    """Get file size in bytes, 0 if not found."""
    try:
        return path.stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


# -----------------------------------------------------------------------
# Removal targets
# -----------------------------------------------------------------------

# PySide6 DLLs/dylibs that YAAMT does not use.
# YAAMT only needs: QtCore, QtGui, QtWidgets, QtNetwork, QtSvg, shiboken6
UNUSED_QT_DLLS = [
    'opengl32sw',        # Software OpenGL renderer (~20MB on Windows)
    'Qt6Quick',          # QML Quick framework
    'Qt6Pdf',            # PDF rendering
    'Qt6Qml',            # QML engine
    'Qt6QmlModels',      # QML model classes
    'Qt6QmlMeta',        # QML meta types
    'Qt6QmlWorkerScript', # QML worker scripts
    'Qt6VirtualKeyboard', # Virtual keyboard
    'Qt6OpenGL',         # OpenGL bindings
]

# PySide6 directories that can be removed
UNUSED_QT_DIRS = [
    'translations',      # Qt translation files (~6MB)
]

# Top-level package directories that should not be in a distributable build.
# These are build-time or eval-only dependencies.
UNUSED_PACKAGES = [
    'lief',              # PyInstaller build-time dep (~10MB)
    'pandas',            # Only for yaamt-eval (~17MB)
    'PIL',               # Not imported by YAAMT source (~13MB)
    'imageio',           # Not imported by YAAMT source
    'mingus',            # Only for yaamt-eval
]


def remove_item(path: Path, dry_run: bool) -> tuple[int, bool]:
    """Remove a file or directory. Returns (bytes_freed, was_removed)."""
    if not path.exists():
        return 0, False

    if path.is_dir():
        size = get_dir_size(path)
        label = f"{path.name}/"
    else:
        size = get_file_size(path)
        label = path.name

    if dry_run:
        print(f"  [DRY RUN] Would remove: {label} ({format_size(size)})")
    else:
        print(f"  Removing: {label} ({format_size(size)})")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    return size, True


def cleanup(dist_path: Path, dry_run: bool = False) -> int:
    """
    Remove unnecessary files from a PyInstaller distribution.

    Args:
        dist_path: Path to the distribution folder (e.g., build/.../yaamt/)
        dry_run: If True, only print what would be removed.

    Returns:
        Total bytes removed.
    """
    internal = dist_path / '_internal'
    if not internal.exists():
        print(f"Error: _internal directory not found in {dist_path}")
        return 0

    pyside_dir = internal / 'PySide6'

    print("=" * 70)
    print(f"YAAMT post-build cleanup: {dist_path}")
    if dry_run:
        print("DRY RUN MODE - no files will be removed")
    print("=" * 70)

    total_removed = 0
    total_items = 0

    # 1. Unused PySide6 DLLs
    if pyside_dir.exists():
        print("\nRemoving unused PySide6 modules...")
        for dll_base in UNUSED_QT_DLLS:
            # Try common patterns: .dll (Windows), .dylib (macOS),
            # .so (Linux), .pyd (Windows Python ext)
            for ext in ('.dll', '.dylib', '.so', '.pyd'):
                candidate = pyside_dir / f"{dll_base}{ext}"
                size, removed = remove_item(candidate, dry_run)
                if removed:
                    total_removed += size
                    total_items += 1

        # Also check for versioned .so files on Linux (e.g., .so.6)
        for dll_base in UNUSED_QT_DLLS:
            for candidate in pyside_dir.glob(f"{dll_base}.so*"):
                size, removed = remove_item(candidate, dry_run)
                if removed:
                    total_removed += size
                    total_items += 1

    # 2. Unused PySide6 directories
    if pyside_dir.exists():
        print("\nRemoving unused PySide6 directories...")
        for dirname in UNUSED_QT_DIRS:
            size, removed = remove_item(pyside_dir / dirname, dry_run)
            if removed:
                total_removed += size
                total_items += 1

    # 3. Unused top-level packages
    print("\nRemoving unused packages...")
    for pkg in UNUSED_PACKAGES:
        size, removed = remove_item(internal / pkg, dry_run)
        if removed:
            total_removed += size
            total_items += 1

    # 4. Test directories inside scipy/numpy (if present)
    print("\nRemoving test directories...")
    for pkg in ('numpy', 'scipy'):
        pkg_dir = internal / pkg
        if pkg_dir.exists():
            for test_dir in pkg_dir.rglob('tests'):
                if test_dir.is_dir():
                    size, removed = remove_item(test_dir, dry_run)
                    if removed:
                        total_removed += size
                        total_items += 1

    # Summary
    print("\n" + "=" * 70)
    if dry_run:
        print("DRY RUN SUMMARY")
    else:
        print("CLEANUP COMPLETE")
    print(f"Items removed: {total_items}")
    print(f"Space saved: {format_size(total_removed)}")
    print("=" * 70)

    return total_removed


def main():
    parser = argparse.ArgumentParser(
        description='Post-build cleanup for YAAMT PyInstaller distributions',
    )
    parser.add_argument(
        'dist_path',
        help='Path to the distribution directory (e.g., build/.../yaamt/)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be removed without actually removing files',
    )
    args = parser.parse_args()

    dist = Path(args.dist_path)
    if not dist.exists():
        print(f"Error: path does not exist: {dist}", file=sys.stderr)
        return 1

    bytes_removed = cleanup(dist, dry_run=args.dry_run)

    if args.dry_run and bytes_removed > 0:
        print(f"\nRun without --dry-run to actually remove files.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
