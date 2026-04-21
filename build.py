#!/usr/bin/env python3
"""
Build script for YAAMT (Yet Another Audio Metadata Tool)

This script builds the application for the current platform using PyInstaller.
Extracted from GitHub Actions workflow to allow local builds.

Nuitka support is commented out — see the NuitkaBuilder class below. The
Nuitka path never produced a usable release and the maintenance burden of
keeping its --nofollow-import-to list in sync with analyzer dependencies was
not worth it. Uncomment the Nuitka code paths if you want to revisit.

Usage:
    python build.py [options]

Options:
    --platform <platform>   Override platform detection (windows, linux, macos)
    --arch <arch>          Override architecture detection (x64, arm64)
    --tool <tool>          Build tool to use: pyinstaller (only supported value)
    --output-dir <dir>     Output directory for build artifacts (default: build)
    --release              Build in release mode (default is debug mode)
    --archive              Create archive of build artifacts
    --help                 Show this help message
"""

import sys
import os
import platform
import subprocess
import argparse
import shutil
import tempfile
import re
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime

DEBIAN_LINUX_DEPS = ["ccache", "patchelf", "alien", "libegl1", "libxkbcommon-x11-0",
                     "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
                     "libxcb-render-util0", "libxcb-xinerama0", "libxcb-xfixes0", "xvfb",
                     "portaudio19-dev", "rpm"]

MACOS_HOMEBREW_DEPS = ["portaudio", "ccache"]

WINDOWS_CHOCO_DEPS = ["ccache"]

FILENAME_SRC_CLI = "src/yaamt.py"
FILENAME_SRC_GUI = "src/yaamt-gui.py"
FILENAME_SRC_EVAL = "src/yaamt-eval.py"


class BuildConfig:
    """Configuration for building YAAMT"""

    def __init__(self, platform_name=None, arch=None, output_dir=None, build_mode='debug', build_tool=None):
        self.platform = platform_name or self._detect_platform()
        self.arch = arch or self._detect_arch()
        self.build_mode = build_mode  # 'debug' or 'release'
        self._build_tool = build_tool  # None means use default (pyinstaller)
        self.project_root = Path(__file__).parent.resolve()

        # Create build-mode-specific output directory with timestamp
        base_output_dir = Path(output_dir or "build")
        # Make it absolute relative to project root if it's not already absolute
        if not base_output_dir.is_absolute():
            base_output_dir = self.project_root / base_output_dir

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_dir = base_output_dir / f"{build_mode}-{timestamp}"

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
        # If explicitly set, use that
        if self._build_tool:
            return self._build_tool
        # PyInstaller is the only supported backend (Nuitka is disabled).
        return "pyinstaller"

    # NuitkaBuilder disabled — see class comment below.
    # def get_nuitka_dist_dir(self):
    #     """Get the Nuitka distribution directory"""
    #     return self.output_dir



# ============================================================================
# Build Backends
# ============================================================================

class BuildBackend(ABC):
    """Abstract base class for build backends"""

    def __init__(self, config: BuildConfig):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return backend name for logging"""
        pass

    @abstractmethod
    def build(self, dist_dir: Path) -> None:
        """Build CLI and GUI executables into dist_dir"""
        pass


class PyInstallerBuilder(BuildBackend):
    """Build backend using PyInstaller"""

    @property
    def name(self) -> str:
        return "pyinstaller"

    def build(self, dist_dir: Path) -> None:
        """Build both CLI and GUI executables using the unified .spec file."""
        dist_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variables read by yaamt.spec
        env = os.environ.copy()
        env['BUILD_MODE'] = self.config.build_mode
        env['YAAMT_ICON_DIR'] = str(Path('resources/icons'))
        if self.config.arch == "arm64":
            env['TARGET_ARCH'] = 'arm64'
        elif self.config.arch == "x64":
            env['TARGET_ARCH'] = 'x86_64'

        print("=== Building with PyInstaller (unified spec)... ===")
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "yaamt.spec",
            f"--distpath={dist_dir}",
            "--noconfirm",
        ]
        subprocess.run(cmd, env=env, check=True)

        # Run post-build cleanup
        yaamt_dir = dist_dir / "yaamt"
        if yaamt_dir.exists():
            print("\n=== Running post-build cleanup... ===")
            cleanup_cmd = [
                sys.executable,
                str(Path('scripts/cleanup_release.py')),
                str(yaamt_dir),
            ]
            subprocess.run(cleanup_cmd, check=True)

        print(f"=== PyInstaller build complete. Output in {yaamt_dir} ===")


# Nuitka build backend disabled — the Nuitka path never produced a usable
# release (C extensions in analyzer dependencies can't be compiled, and
# maintaining the --nofollow-import-to exclusion list in sync with the
# providers layer was not worth the effort). PyInstaller is the only
# supported backend. Uncomment this class plus the factory / archive /
# argparse / install hooks marked "NuitkaBuilder disabled" below to revisit.
#
# class NuitkaBuilder(BuildBackend):
#     """Build backend using Nuitka"""
#
#     # Nuitka options shared across all platforms
#     UNIVERSAL_OPTS = [
#         "--assume-yes-for-downloads",
#         "--onefile",
#         "--standalone",
#         "--lto=no",
#
#         # Explicitly allowed dependencies to include
#         "--nofollow-imports",
#         "--follow-import-to=models",
#         "--follow-import-to=providers",
#         "--follow-import-to=util",
#         "--follow-import-to=workers",
#
#         # Explicitly disabled dependencies (skip compilation, save as bytecode)
#         "--nofollow-import-to=aubio",
#         "--nofollow-import-to=audioread",
#         "--nofollow-import-to=charset_normalizer",
#         "--nofollow-import-to=jinja2",
#         "--nofollow-import-to=joblib",
#         "--nofollow-import-to=librosa",
#         "--nofollow-import-to=numba",
#         "--nofollow-import-to=numpy",
#         "--nofollow-import-to=pyebur128",
#         "--nofollow-import-to=scipy",
#         "--nofollow-import-to=soundfile",
#         "--nofollow-import-to=torch",
#         "--nofollow-import-to=torchaudio",
#
#         # Anti-bloat settings
#         "--noinclude-pytest-mode=nofollow",
#         "--noinclude-setuptools-mode=nofollow",
#         "--noinclude-custom-mode=torch:nofollow",
#
#         # Suppress warnings
#         "--module-parameter=numba-disable-jit=yes",
#         "--enable-plugin=pyside6"
#     ]
#
#     GUI_OPTS = [
#         "--follow-import-to=windows",
#     ]
#
#     @property
#     def name(self) -> str:
#         return "nuitka"
#
#     def build(self, dist_dir: Path) -> None:
#         """Build both CLI and GUI executables using Nuitka"""
#         dist_dir.mkdir(parents=True, exist_ok=True)
#
#         if self.config.platform == "windows":
#             self._build_windows(dist_dir)
#         else:
#             self._build_linux(dist_dir)
#
#     def _build_windows(self, dist_dir: Path) -> None:
#         """Build with Nuitka on Windows"""
#         windows_opts = [
#             "--mingw64",
#             "--clang",
#             "--nofollow-import-to=cffi",
#             f"--output-dir={dist_dir}"
#         ]
#
#         # Add icon if available
#         icon_path = Path("resources/icons/app-icon-gui.ico")
#         if icon_path.exists():
#             windows_opts.append(f"--windows-icon-from-ico={icon_path}")
#         else:
#             print("Warning: No .ico icon file found. Windows executable will use default icon.")
#
#         print("=== Building CLI with Nuitka (Windows)... ===")
#         cmd_args = [sys.executable, "-m", "nuitka"] + self.UNIVERSAL_OPTS + windows_opts + [FILENAME_SRC_CLI]
#         subprocess.run(cmd_args, check=True)
#
#         print("=== Building GUI with Nuitka (Windows)... ===")
#         gui_opts = self.GUI_OPTS + ["--windows-console-mode=attach", FILENAME_SRC_GUI]
#         gui_args = [sys.executable, "-m", "nuitka"] + self.UNIVERSAL_OPTS + windows_opts + gui_opts
#         subprocess.run(gui_args, check=True)
#
#     def _build_linux(self, dist_dir: Path) -> None:
#         """Build with Nuitka on Linux"""
#         linux_opts = [f"--output-dir={dist_dir}"]
#
#         # Add icon if available
#         icon_path = Path("resources/icons/app-icon-gui.png")
#         if icon_path.exists():
#             linux_opts.append(f"--linux-icon={icon_path}")
#         else:
#             print("Warning: Icon file not found at resources/icons/app-icon-gui.png")
#
#         print("=== Building CLI with Nuitka (Linux)... ===")
#         cmd_args = ["nuitka"] + self.UNIVERSAL_OPTS + linux_opts + [FILENAME_SRC_CLI]
#         subprocess.run(cmd_args, check=True)
#
#         print("=== Building GUI with Nuitka (Linux)... ===")
#         gui_args = ["nuitka"] + self.UNIVERSAL_OPTS + linux_opts + self.GUI_OPTS + [FILENAME_SRC_GUI]
#         subprocess.run(gui_args, check=True)




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

        # Install build dependencies.
        # "nuitka" removed from this list — Nuitka backend is disabled.
        build_deps = ["ordered-set", "zstandard"]
        subprocess.run([sys.executable, "-m", "pip", "install"] + build_deps, check=True)


# ============================================================================
# Build Workspace Management
# ============================================================================

def create_build_workspace(build_mode: str, project_root: Path) -> Path:
    """
    Create a temporary build workspace by copying only the necessary files.

    Only copies:
    - src/ directory (source code)
    - resources/ directory (for GUI assets)

    Args:
        build_mode: 'debug' or 'release'
        project_root: Path to the project root directory

    Returns:
        Path to the temporary workspace directory
    """
    # Create temp directory with descriptive prefix
    temp_dir = tempfile.mkdtemp(prefix=f'yaamt_build_{build_mode}_')
    temp_path = Path(temp_dir)

    print(f"Creating build workspace at: {temp_path}")

    # Copy only what's needed for builds
    try:
        workspace_root = temp_path / 'yaamt'
        workspace_root.mkdir(parents=True, exist_ok=True)

        # Copy src/ directory
        src_dest = workspace_root / 'src'
        shutil.copytree(
            project_root / 'src',
            src_dest,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo')
        )
        print(f"  Copied src/")

        # Copy resources/ directory
        resources_dest = workspace_root / 'resources'
        if (project_root / 'resources').exists():
            shutil.copytree(project_root / 'resources', resources_dest)
            print(f"  Copied resources/")

        # Copy PyInstaller spec file
        spec_file = project_root / 'yaamt.spec'
        if spec_file.exists():
            shutil.copy2(spec_file, workspace_root / 'yaamt.spec')
            print(f"  Copied yaamt.spec")

        # Copy scripts/ directory (contains runtime hooks and cleanup script)
        scripts_src = project_root / 'scripts'
        if scripts_src.exists():
            shutil.copytree(
                scripts_src,
                workspace_root / 'scripts',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo')
            )
            print(f"  Copied scripts/")

        print(f"Build workspace created")
        return workspace_root
    except Exception as e:
        # Clean up temp dir if copy fails
        shutil.rmtree(temp_path, ignore_errors=True)
        raise RuntimeError(f"Failed to create build workspace: {e}")


def prepare_source_for_build(temp_src_path: Path, build_mode: str, version_string: str) -> None:
    """
    Prepare the copied source for building by patching constants and
    removing debug-only code for release builds.

    Args:
        temp_src_path: Path to the temporary source directory
        build_mode: 'debug' or 'release'
        version_string: Version string to embed in the build
    """
    print(f"Preparing source for {build_mode} build...")

    const_file = temp_src_path / 'src' / 'util' / 'const.py'

    # Read const.py
    with open(const_file, 'r') as f:
        content = f.read()

    # Patch IS_DEBUG_BUILD constant
    is_debug_value = 'True' if build_mode == 'debug' else 'False'
    content = re.sub(
        r'IS_DEBUG_BUILD\s*=\s*(True|False)',
        f'IS_DEBUG_BUILD = {is_debug_value}',
        content
    )

    # Patch VERSION_STRING
    content = re.sub(
        r'VERSION_STRING\s*=\s*None',
        f'VERSION_STRING = "{version_string}"',
        content
    )

    # Write patched const.py
    with open(const_file, 'w') as f:
        f.write(content)

    print(f"  Patched IS_DEBUG_BUILD = {is_debug_value}")
    print(f"  Patched VERSION_STRING = {version_string}")


def cleanup_build_workspace(temp_path: Path) -> None:
    """
    Clean up the temporary build workspace.

    Args:
        temp_path: Path to the temporary workspace directory
    """
    if temp_path.exists():
        print(f"Cleaning up build workspace: {temp_path}")
        shutil.rmtree(temp_path, ignore_errors=True)


def cleanup_build_directories(output_dir: str = "build") -> None:
    """
    Clean up all timestamped build directories.

    Removes all directories matching the pattern:
    - build/debug-YYYYMMDD-HHMMSS/
    - build/release-YYYYMMDD-HHMMSS/

    Args:
        output_dir: Base output directory (default: "build")
    """
    build_path = Path(output_dir)

    if not build_path.exists():
        print(f"Build directory does not exist: {build_path}")
        return

    # Pattern to match timestamped build directories
    # Format: debug-YYYYMMDD-HHMMSS or release-YYYYMMDD-HHMMSS
    import glob

    patterns = [
        str(build_path / "debug-*"),
        str(build_path / "release-*")
    ]

    directories_found = []
    for pattern in patterns:
        directories_found.extend(glob.glob(pattern))

    if not directories_found:
        print(f"No timestamped build directories found in {build_path}")
        return

    print(f"Found {len(directories_found)} build director{'y' if len(directories_found) == 1 else 'ies'} to clean:")
    for directory in directories_found:
        print(f"  - {directory}")

    # Confirm deletion
    confirm = input("\nDelete these directories? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Cleanup cancelled.")
        return

    # Delete directories
    deleted = 0
    failed = 0
    for directory in directories_found:
        try:
            shutil.rmtree(directory)
            print(f"  [OK] Deleted: {directory}")
            deleted += 1
        except Exception as e:
            print(f"  [FAILED] Failed to delete {directory}: {e}")
            failed += 1

    print(f"\nCleanup complete: {deleted} deleted, {failed} failed")


class Builder:
    """Handles the actual build process"""

    def __init__(self, config: BuildConfig):
        self.config = config

    def _get_backend(self) -> BuildBackend:
        """Factory method to create the appropriate build backend"""
        tool = self.config.get_build_tool()
        if tool == "pyinstaller":
            return PyInstallerBuilder(self.config)
        # NuitkaBuilder disabled — see class comment in this file.
        # elif tool == "nuitka":
        #     return NuitkaBuilder(self.config)
        else:
            raise ValueError(f"Unknown build tool: {tool}")

    def build(self):
        """Execute the build process using temporary workspace"""
        backend = self._get_backend()

        print(f"\nBuilding YAAMT for {self.config.platform}-{self.config.arch}")
        print(f"Build mode: {self.config.build_mode}")
        print(f"Using build tool: {backend.name}\n")

        # Get version string from git in original repo (before copying)
        try:
            version_result = subprocess.run(
                ['git', 'describe', '--tags', '--always', '--dirty'],
                cwd=self.config.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            version_string = version_result.stdout.strip()
        except subprocess.CalledProcessError:
            version_string = "unknown"

        print(f"Version: {version_string}\n")

        # Create temporary build workspace
        temp_workspace = create_build_workspace(self.config.build_mode, self.config.project_root)

        try:
            # Prepare source for build (patch constants, remove debug-only code)
            prepare_source_for_build(temp_workspace, self.config.build_mode, version_string)

            # Save original working directory
            original_cwd = os.getcwd()

            try:
                # Change to temp workspace for build
                os.chdir(temp_workspace)

                # Get relative dist dir for building in temp workspace
                dist_dir_relative = self.config.output_dir.relative_to(self.config.project_root)

                # Delegate to the backend
                backend.build(dist_dir_relative)

            finally:
                # Restore original working directory
                os.chdir(original_cwd)

            # Copy build artifacts from temp workspace to project root
            temp_build_dir = temp_workspace / self.config.output_dir.relative_to(self.config.project_root)
            final_build_dir = self.config.output_dir

            print(f"\nCopying build artifacts...")
            print(f"  From: {temp_build_dir}")
            print(f"  To:   {final_build_dir}")

            if temp_build_dir.exists():
                # Create parent directory if needed
                final_build_dir.parent.mkdir(parents=True, exist_ok=True)

                # Copy the entire build directory
                shutil.copytree(temp_build_dir, final_build_dir, dirs_exist_ok=True)
                print(f"  [OK] Build artifacts copied successfully")
            else:
                raise RuntimeError(f"Build artifacts not found at {temp_build_dir}")

            # Build succeeded - cleanup temp workspace
            cleanup_build_workspace(temp_workspace)

        except Exception as e:
            # Build failed - preserve workspace for debugging
            print(f"\n[FAILED] Build failed: {e}")
            print(f"\nTemp workspace preserved at: {temp_workspace}")
            print(f"To clean up manually: rm -rf {temp_workspace}")
            raise


class Archiver:
    """Handles archiving of build artifacts"""

    def __init__(self, config: BuildConfig):
        self.config = config

    def create_archive(self, version_name=None, platform_override=None, arch_override=None):
        """Create an archive of the build artifacts"""
        # Determine build directory based on tool
        tool = self.config.get_build_tool()
        if tool == "pyinstaller":
            # PyInstaller outputs to dist_dir/yaamt/ (contains both executables)
            build_dir = self.config.output_dir / "yaamt"
        # NuitkaBuilder disabled — see class comment in this file.
        # elif tool == "nuitka":
        #     build_dir = self.config.get_nuitka_dist_dir()
        else:
            build_dir = self.config.output_dir

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


def _create_installer(config: BuildConfig, version_name: str | None = None):
    """Create a platform-native installer from the build output."""
    if config.platform != "windows":
        print(f"Installer generation not yet implemented for {config.platform}")
        return

    # Check for Inno Setup compiler
    iscc = shutil.which("iscc")
    if not iscc:
        # Try common install locations
        for candidate in [
            Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
            Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        ]:
            if candidate.exists():
                iscc = str(candidate)
                break

    if not iscc:
        print("Warning: Inno Setup (ISCC.exe) not found. Skipping installer creation.")
        print("Install from: https://jrsoftware.org/isdl.php")
        return

    # Determine source directory (where PyInstaller output lives)
    source_dir = config.output_dir / "yaamt"
    if not source_dir.exists():
        raise RuntimeError(f"Build output not found at {source_dir}")

    version = version_name or "local"
    iss_file = config.project_root / "installer" / "yaamt.iss"

    if not iss_file.exists():
        raise RuntimeError(f"Inno Setup script not found: {iss_file}")

    print(f"\n=== Creating Windows installer with Inno Setup... ===")
    cmd = [
        iscc,
        str(iss_file),
        f"/DAppVersion={version}",
        f"/DSourceDir={source_dir}",
        f"/DOutputDir={config.output_dir}",
        f"/DArch={config.arch}",
    ]
    subprocess.run(cmd, check=True)
    print(f"=== Installer created in {config.output_dir} ===")


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
        "--release",
        action="store_true",
        help="Build in release mode (default is debug mode)"
    )

    parser.add_argument(
        "--tool",
        # Nuitka disabled — see NuitkaBuilder class comment in this file.
        choices=["pyinstaller"],
        default=None,
        help="Build tool to use (default: pyinstaller)"
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
        "--clean",
        action="store_true",
        help="Clean up all timestamped build directories, then exit"
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

    parser.add_argument(
        "--installer",
        action="store_true",
        help="Create a platform-native installer (Windows: Inno Setup)"
    )

    args = parser.parse_args()

    try:
        # Handle cleanup request (doesn't require config)
        if args.clean:
            cleanup_build_directories(args.output_dir)
            return

        # Determine build mode
        build_mode = 'release' if args.release else 'debug'

        # Initialize configuration
        config = BuildConfig(
            platform_name=args.platform,
            arch=args.arch,
            output_dir=args.output_dir,
            build_mode=build_mode,
            build_tool=args.tool
        )

        print(f"YAAMT Build Script")
        print(f"==================")
        print(f"Platform: {config.platform}")
        print(f"Architecture: {config.arch}")
        print(f"Build mode: {config.build_mode}")
        print(f"Build tool: {config.get_build_tool()}")
        print(f"Output directory: {config.output_dir}")
        print()

        # Install dependencies if requested
        if args.install_deps:
            installer = DependencyInstaller(config)
            installer.install_system_deps()
            installer.install_python_deps()
            print("\n[OK] Dependencies installed successfully!")
            return

        # Build
        builder = Builder(config)
        builder.build()

        print("\n[OK] Build completed successfully!")

        # Create archive if requested
        if args.archive:
            archiver = Archiver(config)
            archiver.create_archive(
                version_name=args.version_name,
                platform_override=args.archive_platform,
                arch_override=args.archive_arch
            )

        # Create installer if requested
        if args.installer:
            _create_installer(config, args.version_name)

    except Exception as e:
        print(f"\n[FAILED] Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
