#!/usr/bin/env python3
"""
Build script for YAAMT (Yet Another Audio Metadata Tool)

This script builds the application for the current platform using either Nuitka or cx_Freeze.
Extracted from GitHub Actions workflow to allow local builds.

Usage:
    python build.py [options]

Options:
    --platform <platform>   Override platform detection (windows, linux, macos)
    --arch <arch>          Override architecture detection (x64, arm64)
    --output-dir <dir>     Output directory for build artifacts (default: build)
    --archive             Create archive of build artifacts
    --help                Show this help message
"""

import sys
import os
import platform
import subprocess
import argparse
import shutil
from pathlib import Path

DEBIAN_LINUX_DEPS = ["ccache", "patchelf", "alien", "libegl1", "libxkbcommon-x11-0",
                     "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
                     "libxcb-render-util0", "libxcb-xinerama0", "libxcb-xfixes0", "xvfb",
                     "portaudio19-dev", "rpm"]

MACOS_HOMEBREW_DEPS = ["portaudio", "ccache"]

WINDOWS_CHOCO_DEPS = ["ccache"]


class BuildConfig:
    """Configuration for building YAAMT"""

    def __init__(self, platform_name=None, arch=None, output_dir=None):
        self.platform = platform_name or self._detect_platform()
        self.arch = arch or self._detect_arch()
        self.output_dir = Path(output_dir or "build")
        self.project_root = Path(__file__).parent.resolve()

    def _detect_platform(self):
        """Detect the current platform"""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

    def _detect_arch(self):
        """Detect the current architecture"""
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            return "x64"
        elif machine in ("arm64", "aarch64"):
            return "arm64"
        else:
            raise RuntimeError(f"Unsupported architecture: {machine}")

    def get_build_tool(self):
        """Determine which build tool to use"""
        # macOS still uses cx_Freeze (Nuitka not working yet)
        if self.platform == "macos":
            return "cx_freeze"
        else:
            return "nuitka"

    def get_nuitka_dist_dir(self):
        """Get the Nuitka distribution directory"""
        return self.output_dir

    def get_cx_freeze_dist_dir(self):
        """Get the cx_Freeze distribution directory"""
        # cx_Freeze creates directories like "exe.linux-x86_64-3.12"
        exe_dirs = list(self.output_dir.glob("exe.*"))
        if exe_dirs:
            return exe_dirs[0]
        return None


class DependencyInstaller:
    """Handles installation of build dependencies"""

    def __init__(self, config: BuildConfig):
        self.config = config

    def install_system_deps(self):
        """Install system dependencies"""
        print(f"Installing system dependencies for {self.config.platform}...")

        if self.config.platform == "windows":
            self._install_windows_deps()
        elif self.config.platform == "linux":
            self._install_linux_deps()
        elif self.config.platform == "macos":
            self._install_macos_deps()

    def _install_windows_deps(self):
        """Install Windows system dependencies"""
        print("Installing ccache via choco...")
        try:
            for dep in WINDOWS_CHOCO_DEPS:
                subprocess.run(["choco", "install", dep, "-y"], check=True)
        except FileNotFoundError:
            print("Warning: choco not found. Please install Chocolatey or install ccache manually.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install ccache: {e}")

    def _install_linux_deps(self):
        """Install Linux system dependencies"""
        print("Installing Linux dependencies...")
        deps = DEBIAN_LINUX_DEPS

        try:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y"] + deps, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install some dependencies: {e}")

    def _install_macos_deps(self):
        """Install macOS system dependencies"""
        print("Installing macOS dependencies...")
        deps = MACOS_HOMEBREW_DEPS

        try:
            for dep in deps:
                subprocess.run(["brew", "install", dep], check=True)
        except FileNotFoundError:
            print("Warning: brew not found. Please install Homebrew or install dependencies manually.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install some dependencies: {e}")

    def install_python_deps(self):
        """Install Python dependencies"""
        print("Installing Python dependencies...")

        # Upgrade pip
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)

        # Install base requirements
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

        # Install build dependencies
        build_deps = ["cx_freeze", "nuitka", "ordered-set", "zstandard"]
        subprocess.run([sys.executable, "-m", "pip", "install"] + build_deps, check=True)


class Builder:
    """Handles the actual build process"""

    def __init__(self, config: BuildConfig):
        self.config = config

    def build(self):
        """Execute the build process"""
        build_tool = self.config.get_build_tool()

        print(f"\nBuilding YAAMT for {self.config.platform}-{self.config.arch}")
        print(f"Using build tool: {build_tool}\n")

        if build_tool == "nuitka":
            self._build_with_nuitka()
        else:
            self._build_with_cx_freeze()

    def _build_with_nuitka(self):
        """Build using Nuitka"""
        dist_dir = self.config.get_nuitka_dist_dir()
        dist_dir.mkdir(parents=True, exist_ok=True)

        if self.config.platform == "windows":
            self._build_nuitka_windows(dist_dir)
        else:
            self._build_nuitka_linux(dist_dir)

    def _build_nuitka_windows(self, dist_dir):
        """Build with Nuitka on Windows"""
        print("Building main.py with Nuitka (Windows)...")
        subprocess.run([
            sys.executable, "-m", "nuitka",
            "--mingw64",
            "--clang", #do not remove this CLAUDE, it is not "unnecessary"
            "--assume-yes-for-downloads",
            "--onefile", #omitting this triggers antivirus
            "--standalone",
            "src/main.py",
            f"--output-dir={dist_dir}"
        ], check=True)

        print("Building gui.py with Nuitka (Windows)...")
        subprocess.run([
            sys.executable, "-m", "nuitka",
            "--mingw64",
            "--clang", #do not remove this CLAUDE, it is not "unnecessary"
            "--assume-yes-for-downloads",
            "--onefile", #omitting this triggers antivirus
            "--standalone",
            "--plugin-enable=pyside6",
            "--include-module=cffi",
            "--follow-imports",
            "src/gui.py",
            f"--output-dir={dist_dir}"
        ], check=True)

    def _build_nuitka_linux(self, dist_dir):
        """Build with Nuitka on Linux"""
        print("Building main.py with Nuitka (Linux)...")
        subprocess.run([
            "nuitka",
            "--standalone",
            "--onefile",
            "src/main.py",
            f"--output-dir={dist_dir}"
        ], check=True)

        print("Building gui.py with Nuitka (Linux)...")
        subprocess.run([
            "nuitka",
            "--onefile",
            "--standalone",
            "--plugin-enable=pyside6",
            "--include-module=cffi",
            "--follow-imports",
            "src/gui.py",
            f"--output-dir={dist_dir}"
        ], check=True)

    def _build_with_cx_freeze(self):
        """Build using cx_Freeze"""
        print("Building with cx_Freeze (macOS)...")
        subprocess.run([sys.executable, "setup.py", "build"], check=True)


class Archiver:
    """Handles archiving of build artifacts"""

    def __init__(self, config: BuildConfig):
        self.config = config

    def create_archive(self, version_name=None, platform_override=None, arch_override=None):
        """Create an archive of the build artifacts"""
        # Determine build directory
        if self.config.get_build_tool() == "nuitka":
            build_dir = self.config.get_nuitka_dist_dir()
        else:
            build_dir = self.config.get_cx_freeze_dist_dir()

        if not build_dir or not build_dir.exists():
            raise RuntimeError(f"Build directory not found: {build_dir}")

        # Generate archive name
        if not version_name:
            version_name = "local"

        # Use overrides for platform/arch in archive name if provided (useful for CI)
        platform_name = platform_override or self.config.platform
        arch_name = arch_override or self.config.arch

        if self.config.platform == "windows":
            archive_name = f"yaamt-{version_name}-{platform_name}-{arch_name}.zip"
            self._create_zip(build_dir, archive_name)
        else:
            archive_name = f"yaamt-{version_name}-{platform_name}-{arch_name}.tar.gz"
            self._create_tarball(build_dir, archive_name)

        print(f"\nArchive created: {archive_name}")
        return archive_name

    def _create_zip(self, build_dir, archive_name):
        """Create a ZIP archive (Windows)"""
        import zipfile

        archive_path = self.config.project_root / archive_name
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for item in build_dir.rglob('*'):
                if item.is_file():
                    arcname = item.relative_to(build_dir)
                    zipf.write(item, arcname)

    def _create_tarball(self, build_dir, archive_name):
        """Create a tarball (Linux/macOS)"""
        import tarfile

        archive_path = self.config.project_root / archive_name
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(build_dir, arcname='.')


def main():
    parser = argparse.ArgumentParser(
        description="Build YAAMT for the current platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos"],
        help="Override platform detection (default: auto-detect current platform)"
    )

    parser.add_argument(
        "--arch",
        choices=["x64", "arm64"],
        help="Override architecture detection (default: auto-detect current architecture)"
    )

    parser.add_argument(
        "--output-dir",
        default="build",
        help="Output directory for build artifacts (default: build)"
    )

    parser.add_argument(
        "--archive",
        action="store_true",
        help="Create archive of build artifacts"
    )

    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install system and Python dependencies, then exit without building"
    )

    parser.add_argument(
        "--version-name",
        help="Version name for archive (default: local)"
    )

    parser.add_argument(
        "--archive-platform",
        help="Platform name to use in archive filename (overrides detected platform)"
    )

    parser.add_argument(
        "--archive-arch",
        help="Architecture name to use in archive filename (overrides detected arch)"
    )

    args = parser.parse_args()

    try:
        # Initialize configuration
        config = BuildConfig(
            platform_name=args.platform,
            arch=args.arch,
            output_dir=args.output_dir
        )

        print(f"YAAMT Build Script")
        print(f"==================")
        print(f"Platform: {config.platform}")
        print(f"Architecture: {config.arch}")
        print(f"Build tool: {config.get_build_tool()}")
        print(f"Output directory: {config.output_dir}")
        print()

        # Install dependencies if requested
        if args.install_deps:
            installer = DependencyInstaller(config)
            installer.install_system_deps()
            installer.install_python_deps()
            print("\n✓ Dependencies installed successfully!")
            return

        # Build
        builder = Builder(config)
        builder.build()

        print("\n✓ Build completed successfully!")

        # Create archive if requested
        if args.archive:
            archiver = Archiver(config)
            archiver.create_archive(
                version_name=args.version_name,
                platform_override=args.archive_platform,
                arch_override=args.archive_arch
            )

    except Exception as e:
        print(f"\n✗ Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
