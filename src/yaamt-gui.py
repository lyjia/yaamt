#!/usr/bin/env python
import sys
import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from windows.main_window import MainWindow
from util.const import APP_ORGANIZATION_NAME, APP_APPLICATION_NAME
from util.debug import add_debug_argument, initialize_debug_and_logging
from util.logging import log
import util.resources_rc  # Import compiled Qt resources


def run_gui():
    """Initializes and runs the GUI application."""
    parser = argparse.ArgumentParser(description="Audio Metadata Tool")
    parser.add_argument("path", nargs='?', default=None, help="The starting path for the file browser.")
    add_debug_argument(parser)
    args = parser.parse_args()

    initialize_debug_and_logging(args)

    log.info("Starting QT application...")
    app = QApplication(sys.argv)

    # Set application metadata (important for macOS menu bar and QSettings)
    app.setApplicationName(APP_APPLICATION_NAME)
    app.setApplicationDisplayName(APP_APPLICATION_NAME)
    app.setOrganizationName(APP_ORGANIZATION_NAME)

    # Set application icon from Qt resources (for taskbar/dock)
    app.setWindowIcon(QIcon(":/icons/app-icon-gui.png"))

    window = MainWindow(path=args.path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # Required for multiprocessing to work in PyInstaller frozen builds on Windows
    import multiprocessing
    multiprocessing.freeze_support()

    run_gui()