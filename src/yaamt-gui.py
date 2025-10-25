#!/usr/bin/env python
import sys
import os
import argparse
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from windows.main_window import MainWindow
from util.const import IS_DEBUG_BUILD
from util.debug import set_debug_mode, is_debug_mode
from util.logging import create_logger, log, configure_logger


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

    # Set application metadata (important for macOS menu bar)
    app.setApplicationName("YAAMT")
    app.setApplicationDisplayName("YAAMT")
    app.setOrganizationName("YAAMT")

    # Set application icon (for taskbar/dock)
    icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "app-icon-gui.png")
    icon_path = os.path.normpath(icon_path)
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow(path=args.path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()