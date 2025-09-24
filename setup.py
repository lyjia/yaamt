import sys
import os
from cx_Freeze import setup, Executable
from src.util.version import generate_version_file

# Generate version file before proceeding with setup
version = generate_version_file()

# Add the src directory to the Python path for cx_Freeze
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": [
        "os",
        "sys",
        "subprocess",
        "json",
        "pathlib",
        "logging",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "mutagen",
        "pytest"
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "email",
        "http",
        "xml",
        "xmlrpc"
    ],
    "include_files": [
        ("resources", "resources"),
        (os.path.join("src", "VERSION"), "VERSION"),
        ("src", "src")
    ],
    "optimize": 2
}

# GUI applications require a different base on Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# Define executables
executables = [
    Executable(
        "src/main.py",
        base=None,
        target_name="yaamt",
        icon="resources/icons/app_icon.png"
    ),
    Executable(
        "src/gui.py",
        base=base,
        target_name="yaamt-gui",
        icon="resources/icons/app_icon.png"
    )
]

setup(
    name="YAAMT",
    version=version,
    description="Yet Another Audio Metadata Tool",
    options={"build_exe": build_exe_options},
    executables=executables,
    
    # Windows MSI installer configuration
    bdist_msi_options={
        "upgrade_code": "{6659888b-5b85-44a8-b1e1-9ff55aa3124a}",
        "add_to_path": True,
        "all_users": True,
        "install_icon": "resources/icons/app_icon.png",
        "product_name": "YAAMT - Yet Another Audio Metadata Tool",
        "summary": "A tool for managing audio file metadata",
        "initial_target_dir": r"[ProgramFilesFolder]\YAAMT"
    },
    
    # macOS app bundle configuration
    bdist_mac_options={
        "iconfile": "resources/icons/app_icon.icns",
        "bundle_name": "YAAMT",
        "plist_items": {
            "CFBundleDisplayName": "YAAMT - Yet Another Audio Metadata Tool",
            "CFBundleVersion": version,
            "CFBundleShortVersionString": version,
            "NSHighResolutionCapable": True
        }
    },
    
    # Debian package configuration
    bdist_deb_options={
        "maintainer": "Lyjia",
        "maintainer_email": "yaamt@lyjia.us",
        "depends": "python3, python3-pyside6, python3-mutagen",
        "section": "sound",
        "priority": "optional",
        "description": "A tool for managing audio file metadata\n"
                     "This application allows users to view, edit, and manage metadata\n"
                     "for audio files including MP3, FLAC, WAV, and other formats.\n"
                     "Features include:\n"
                     " - Batch editing of metadata\n"
                     " - Support for multiple audio formats\n"
                     " - GUI and command-line interfaces"
    }
)