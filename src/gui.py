import sys
import argparse
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

def run_gui():
    """Initializes and runs the GUI application."""
    parser = argparse.ArgumentParser(description="Audio Metadata Tool")
    parser.add_argument("path", nargs='?', default=None, help="The starting path for the file browser.")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(path=args.path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()