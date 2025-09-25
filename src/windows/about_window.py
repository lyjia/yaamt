from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from util.version import get_version


class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About YAAMT")

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap(":/logo.png")
        logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Text
        version = get_version()
        text_label = QLabel(
            f"""
            <p>A simple tool for editing audio metadata.</p>
            <p>Version: {version}</p>
            """
        )
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(logo_label)
        layout.addWidget(text_label)
        self.setLayout(layout)