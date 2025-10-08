import sys
import os
import re
import subprocess
from cx_Freeze import setup, Executable

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from util.version import get_version_from_git

def patch_const_file(version_string):
    """
    Patches the const.py file to include the version string.
    """
    const_file_path = os.path.join("src", "util", "const.py")
    with open(const_file_path, 'r') as f:
        content = f.read()
    
    # Replace the VERSION_STRING = None line
    new_content = re.sub(
        r'VERSION_STRING = None',
        f'VERSION_STRING = "{version_string}"',
        content
    )
    
    with open(const_file_path, 'w') as f:
        f.write(new_content)

def revert_const_file():
    """
    Reverts the const.py file to its original state.
    """
    const_file_path = os.path.join("src", "util", "const.py")
    with open(const_file_path, 'r') as f:
        content = f.read()
    
    # Replace the VERSION_STRING line back to None
    new_content = re.sub(
        r'VERSION_STRING = ".*"',
        'VERSION_STRING = None',
        content
    )
    
    with open(const_file_path, 'w') as f:
        f.write(new_content)

# Get version from git
version = get_version_from_git()

# Patch the const.py file with the version
try:
    patch_const_file(version)

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
            "cffi",
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
            "xml",
            "xmlrpc",
            "PySide6.QtSql" #responsible for  error: [Errno 2] No such file or directory: '/usr/local/opt/libiodbc/lib/libiodbc.2.dylib' on macos builds
        ],
        "include_files": [
            ("resources", "resources"),
            ("src", "src")
        ],
        "optimize": 2,
        "include_msvcr": True
    }

    # GUI applications require a different base on Windows
    gui_base = "gui"
    if sys.platform == "win32":
        gui_base = "Win32GUI"

    # Define executables
    executables = [
        Executable(
            "src/gui.py",
            base=gui_base,
            target_name="YAAMT",
            icon="resources/icons/app_icon.png"
        ),
        Executable(
            "src/main.py",
            base=None,
            target_name="yaamt",
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
                "NSHighResolutionCapable": True,
                "CFBundleExecutable": "YAAMT"
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
        },

        # macOS disk image configuration
        bdist_dmg_options={
            "volume_label": "YAAMT",
            "applications_shortcut": True,
            "bundle_name": "YAAMT"
        }
    )

except Exception as e:
    print(f"Error building the application: {e}")
    raise e
finally:
    # Revert the const.py file to its original state
    revert_const_file()