#!/usr/bin/env python
import sys
import os
import argparse
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from windows.main_window import MainWindow
from util.const import IS_DEBUG_BUILD, APP_ORGANIZATION_NAME, APP_APPLICATION_NAME
from util.debug import set_debug_mode, is_debug_mode
from util.logging import create_logger, log, configure_logger
import util.resources_rc  # Import compiled Qt resources


def run_gui():
    """Initializes and runs the GUI application."""
    parser = argparse.ArgumentParser(description="Audio Metadata Tool")
    parser.add_argument("path", nargs='?', default=None, help="The starting path for the file browser.")
    parser.add_argument('--debug', action='store_true', default=1, help=f'Enable debug mode (default)')
    args = parser.parse_args()

    # Handle debug mode
    # If --debug is not specified (None), use IS_DEBUG_BUILD default
    debug_mode = args.debug if args.debug is not None else IS_DEBUG_BUILD
    set_debug_mode(debug_mode)

    # Determine log level based on debug mode (extensible for future --log-level flag)
    log_level = 'debug' if is_debug_mode() else 'info'

    # Configure logging
    configure_logger(use_formatter=True, log_level=log_level)

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
    run_gui()