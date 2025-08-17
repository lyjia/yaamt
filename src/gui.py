import sys
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

def run_gui():
    """Initializes and runs the GUI application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()