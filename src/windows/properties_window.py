import os
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QStyle,
)
from models.edit_manager import EditManager
from windows.properties_tabs.main_tab import MainTab
from windows.properties_tabs.details_tab import DetailsTab
from windows.properties_tabs.advanced_tab import AdvancedTab
from windows.properties_tabs.artwork_tab import ArtworkTab
import windows.__resources_rc


class SaveWorker(QThread):
    finished = Signal(list)

    def __init__(self, media_files, changes=None):
        super().__init__()
        self.media_files = media_files
        self.changes = changes

    def run(self):
        file_paths = [mf.file_path for mf in self.media_files]
        for media_file in self.media_files:
            if media_file.file_path in self.changes:
                media_file.save(self.changes[media_file.file_path])
        self.finished.emit(file_paths)


class PropertiesWindow(QMainWindow):
    def __init__(self, media_files, parent=None):
        super().__init__(parent)

        self.media_files = media_files
        self.edit_manager = EditManager()

        if len(self.media_files) == 1:
            self.setWindowTitle(f"Properties for {os.path.basename(self.media_files[0].file_path)}")
        else:
            self.setWindowTitle(f"Properties for {len(self.media_files)} files")

        self.resize(720, 480)
        self.setMinimumSize(400, 300)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create and set up tabs
        self.main_tab = MainTab(self.media_files)
        self.artwork_tab = ArtworkTab(self.media_files)
        self.tab_widget.addTab(self.main_tab, "Main")
        self.tab_widget.addTab(self.artwork_tab, "Artwork")

        if len(self.media_files) == 1:
            self.details_tab = DetailsTab(self.media_files)
            self.advanced_tab = AdvancedTab(self.media_files)
            self.tab_widget.addTab(self.details_tab, "Details")
            self.tab_widget.addTab(self.advanced_tab, "Advanced")

        # Connect to EditManager signals
        self.edit_manager.staged_changes_exist.connect(self.on_staged_changes_changed)

        # Bottom button layout
        self.bottom_layout = QHBoxLayout()
        tools_button = QPushButton("Tools")
        self.bottom_layout.addWidget(tools_button)
        self.bottom_layout.addStretch()

        self.close_button = QPushButton("Close")
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.close_button.clicked.connect(self.close)

        self.bottom_layout.addWidget(self.ok_button)
        self.bottom_layout.addWidget(self.close_button)

        main_layout.addLayout(self.bottom_layout)
        
        self.update_button_states()

    def on_ok_clicked(self):
        self.central_widget.setEnabled(False)

        self.status_label = QLabel("Writing changes...")
        self.spinner = QLabel()
        movie = QMovie(":/icons/spinner.gif")
        self.spinner.setMovie(movie)
        movie.start()

        self.bottom_layout.insertWidget(2, self.spinner)
        self.bottom_layout.insertWidget(3, self.status_label)

        self.edit_manager.commit_changes()

    def on_save_finished(self, file_paths):
        self.spinner.hide()
        self.status_label.hide()
        self.edit_manager.emit_commit_successful(file_paths)
        self.close()

    def on_staged_changes_changed(self, has_changes):
        self.update_button_states()

    def update_button_states(self):
        has_changes = self.edit_manager.has_staged_changes()
        self.ok_button.setEnabled(has_changes)
        self.close_button.setText("Cancel" if has_changes else "Close")
