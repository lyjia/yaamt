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
    QMessageBox,
)
from models.edit_manager import EditManager
from windows.properties_tabs.main_tab import MainTab
from windows.properties_tabs.details_tab import DetailsTab
from windows.properties_tabs.advanced_tab import AdvancedTab
from windows.properties_tabs.artwork_tab import ArtworkTab
import windows.__resources_rc


class PropertiesWindow(QMainWindow):
    def __init__(self, media_files: list, edit_manager: EditManager, parent=None):
        super().__init__(parent)

        self.media_files = media_files
        self.edit_manager = edit_manager
        self.edit_manager.register_media_files(self.media_files)

        # Drop any per-MediaFile tag cache before the tabs are constructed so
        # the first read always reflects current on-disk state. The window's
        # MediaFiles can be passed in pre-populated by callers (e.g. the file
        # model) where the cache may hold stale values from a prior load.
        for mf in self.media_files:
            mf.invalidate_tag_cache()
        if len(self.media_files) == 1:
            self.setWindowTitle(f"Properties for {os.path.basename(self.media_files[0].file_path)}")
        else:
            self.setWindowTitle(f"Properties for {len(self.media_files)} files")

        # Default tall enough to show the Main tab's full form including the
        # ReplayGain group box. Deliberately NO setMinimumSize() call here:
        # with no explicit minimum, Qt imposes the layouts' computed minimum
        # on the window (currently ~549 px for the Main tab's 15 form rows),
        # so the user cannot resize the window small enough to clip the form.
        # An explicit minimum like the old setMinimumSize(400, 300) OVERRIDES
        # that layout-derived floor and is exactly what allowed the ReplayGain
        # group to be crushed out of view.
        self.resize(720, 600)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create and set up tabs
        self.main_tab = MainTab(self.media_files, self.edit_manager)
        self.artwork_tab = ArtworkTab(self.media_files)
        self.tab_widget.addTab(self.main_tab, "Main")
        self.tab_widget.addTab(self.artwork_tab, "Artwork")

        # Connect MainTab's return_pressed signal
        self.main_tab.return_pressed.connect(self.on_ok_clicked)

        if len(self.media_files) == 1:
            self.details_tab = DetailsTab(self.media_files)
            self.advanced_tab = AdvancedTab(self.media_files, self.edit_manager)
            self.tab_widget.addTab(self.details_tab, "Details")
            self.tab_widget.addTab(self.advanced_tab, "Advanced")

        # Connect to EditManager signals
        self.edit_manager.staged_changes_exist.connect(self.on_staged_changes_changed)
        self.edit_manager.commit_finished.connect(self.on_save_finished)
        self.edit_manager.commit_failed.connect(self.on_commit_failed)

        # Refresh the tabs whenever the analyzer dispatcher finishes a batch:
        # the analyzer writes through a different MediaFile instance, so this
        # window's cached tag values would otherwise stay stale.
        from workers.analyzer_dispatcher import AnalyzerDispatcher
        AnalyzerDispatcher().analysis_completed.connect(self.refresh_tabs)

        # Bottom button layout
        self.bottom_layout = QHBoxLayout()
        tools_button = QPushButton("Tools")
        self.bottom_layout.addWidget(tools_button)
        self.bottom_layout.addStretch()

        self.status_label = QLabel("Writing changes...")
        self.spinner = QLabel()
        movie = QMovie(":/icons/spinner.gif")
        self.spinner.setMovie(movie)
        movie.start()
        self.bottom_layout.addWidget(self.spinner)
        self.bottom_layout.addWidget(self.status_label)
        self.spinner.hide()
        self.status_label.hide()

        self.close_button = QPushButton("Close")
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.setDefault(True)

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.close_button.clicked.connect(self.close)

        self.bottom_layout.addWidget(self.ok_button)
        self.bottom_layout.addWidget(self.close_button)

        main_layout.addLayout(self.bottom_layout)
        
        self.update_button_states()

    def on_ok_clicked(self):
        # If autosave or another process has already committed the changes,
        # there might be nothing left to save. In this case, just close.
        if not self.edit_manager.has_staged_changes():
            self.close()
            return

        self.central_widget.setEnabled(False)

        self.ok_button.hide()
        self.close_button.hide()
        self.spinner.show()
        self.status_label.show()

        if not self.edit_manager.commit_changes():
            self.close()

    def on_save_finished(self, file_ids):
        self.close()

    def refresh_tabs(self) -> None:
        """
        Drop cached metadata on every open MediaFile and re-populate the
        tabs. Wired to the analyzer dispatcher's ``analysis_completed`` so
        the window picks up tags written by a background batch.
        """
        for mf in self.media_files:
            mf.invalidate_tag_cache()
        if hasattr(self, 'main_tab'):
            self.main_tab.refresh()
        if hasattr(self, 'advanced_tab'):
            self.advanced_tab.refresh()

    def on_staged_changes_changed(self, has_changes):
        self.update_button_states()

    def update_button_states(self):
        has_changes = self.edit_manager.has_staged_changes()
        self.ok_button.setEnabled(has_changes)
        self.close_button.setText("Cancel" if has_changes else "Close")

    def on_commit_failed(self, error_message):
        self.central_widget.setEnabled(True)
        self.spinner.hide()
        self.status_label.hide()
        self.ok_button.show()
        self.close_button.show()

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText("Failed to save changes:")
        msg_box.setInformativeText(error_message)
        msg_box.setWindowTitle("Commit Failed")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()