from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

class ArtworkTab(QWidget):
    def __init__(self, media_files, parent=None):
        super().__init__(parent)
        self.media_files = media_files

        layout = QVBoxLayout(self)
        label = QLabel("Artwork editing will be available here.")
        layout.addWidget(label)