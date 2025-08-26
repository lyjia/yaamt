import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QStyle,
    QHeaderView,
    QSizePolicy,
    QFormLayout,
    QLineEdit,
    QGroupBox,
)
from models.media_file import MediaFile
from models.edit_manager import EditManager
from util.const import (
    KEY_INTERNAL, KEY_STREAM_INFO, KEY_TAGS, KEY_TITLE, KEY_ARTIST, KEY_ALBUM,
    KEY_ALBUM_ARTIST, KEY_DATE, KEY_GENRE, KEY_COMMENT, KEY_COMPOSER,
    KEY_TRACK_NUMBER, KEY_DISC_NUMBER, KEY_BPM, KEY_MUSICAL_KEY,
    KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN
)
import windows.__resources_rc


class SaveWorker(QThread):
    finished = Signal()

    def __init__(self, media_files, changes=None):
        super().__init__()
        self.media_files = media_files
        self.changes = changes

    def run(self):
        for media_file in self.media_files:
            if media_file.file_path in self.changes:
                media_file.save(self.changes[media_file.file_path])
        self.finished.emit()


class PropertiesWindow(QMainWindow):
    def __init__(self, file_paths, parent=None):
        super().__init__(parent)

        if isinstance(file_paths, str):
            self.file_paths = [file_paths]
        else:
            self.file_paths = file_paths

        self.media_files = [MediaFile(file_path, enable_write=True) for file_path in self.file_paths]
        self.edit_manager = EditManager()
        if len(self.file_paths) == 1:
            self.setWindowTitle(f"Properties for {os.path.basename(self.file_paths)}")
        else:
            self.setWindowTitle(f"Properties for {len(self.file_paths)} files")
        self.resize(720, 480)
        self.setMinimumSize(400, 300)
        self.setWindowIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )

        # Central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create and set up tabs
        self.basic_info_tab = QWidget()
        self.details_tab = QWidget()
        self.advanced_tab = QWidget()

        self.tab_widget.addTab(self.basic_info_tab, "Simplified")
        self.tab_widget.addTab(self.details_tab, "Details")
        self.tab_widget.addTab(self.advanced_tab, "Advanced")

        self.setup_basic_info_tab(self.basic_info_tab)
        self.setup_details_tab(self.details_tab)
        self.setup_advanced_tab(self.advanced_tab)

        # Connect to EditManager signals
        self.edit_manager.staged_changes_exist.connect(self.on_staged_changes_changed)

        # Bottom button layout
        self.bottom_layout = QHBoxLayout()

        # Left-aligned button
        tools_button = QPushButton("Tools")
        self.bottom_layout.addWidget(tools_button)

        self.bottom_layout.addStretch()

        # Right-aligned buttons
        self.close_button = QPushButton("Close")
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.close_button.clicked.connect(self.close)

        self.bottom_layout.addWidget(self.ok_button)
        self.bottom_layout.addWidget(self.close_button)

        main_layout.addLayout(self.bottom_layout)

    def on_ok_clicked(self):
        self.central_widget.setEnabled(False)

        self.status_label = QLabel("Writing changes...")
        self.spinner = QLabel()
        movie = QMovie(":/icons/spinner.gif")
        self.spinner.setMovie(movie)
        movie.start()

        self.bottom_layout.insertWidget(2, self.spinner)
        self.bottom_layout.insertWidget(3, self.status_label)

        # Commit changes via EditManager
        self.edit_manager.commit_requested.connect(self.on_commit_requested)
        self.edit_manager.commit_changes()

    def on_commit_requested(self, commit_data):
        """Handle the commit request from EditManager"""
        self.worker = SaveWorker(self.media_files, commit_data)
        self.worker.finished.connect(self.on_save_finished)
        self.worker.start()

    def on_save_finished(self):
        self.spinner.hide()
        self.status_label.hide()
        # Emit signal to notify MainWindow that the file has been successfully updated
        self.edit_manager.emit_commit_successful(self.file_paths)
        self.close()

    def on_staged_changes_changed(self, has_changes):
        """Handle changes in staged changes state"""
        self.update_button_states()

    def update_button_states(self):
        if self.edit_manager.has_staged_changes():
            self.ok_button.setEnabled(True)
            self.close_button.setText("Cancel")
        else:
            self.ok_button.setEnabled(False)
            self.close_button.setText("Close")

    def setup_basic_info_tab(self, tab_widget):
        layout = QFormLayout(tab_widget)
        
        # Metadata fields
        self.title_edit = QLineEdit()
        self.artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.album_artist_edit = QLineEdit()
        self.date_edit = QLineEdit()
        self.genre_edit = QLineEdit()
        self.comment_edit = QLineEdit()
        self.composer_edit = QLineEdit()
        self.publisher_edit = QLineEdit()
        self.track_num_edit = QLineEdit()
        self.disc_num_edit = QLineEdit()
        self.bpm_edit = QLineEdit()
        self.key_edit = QLineEdit()

        layout.addRow("Title:", self.title_edit)
        layout.addRow("Artist:", self.artist_edit)
        layout.addRow("Album:", self.album_edit)
        layout.addRow("Album Artist:", self.album_artist_edit)
        layout.addRow("Date:", self.date_edit)
        layout.addRow("Genre:", self.genre_edit)
        layout.addRow("Comment:", self.comment_edit)
        layout.addRow("Composer:", self.composer_edit)
        layout.addRow("Publisher:", self.publisher_edit)
        layout.addRow("Track #:", self.track_num_edit)
        layout.addRow("Disc #:", self.disc_num_edit)
        layout.addRow("BPM:", self.bpm_edit)
        layout.addRow("Key:", self.key_edit)

        # ReplayGain GroupBox
        replaygain_group = QGroupBox("ReplayGain")
        replaygain_layout = QFormLayout()
        replaygain_group.setLayout(replaygain_layout)

        self.replaygain_track_edit = QLineEdit()
        self.replaygain_track_edit.setReadOnly(True)
        self.replaygain_album_edit = QLineEdit()
        self.replaygain_album_edit.setReadOnly(True)

        replaygain_layout.addRow("Track:", self.replaygain_track_edit)
        replaygain_layout.addRow("Album:", self.replaygain_album_edit)
        
        layout.addRow(replaygain_group)

        # Helper to populate fields and set style for "<< multiple values >>"
        def populate_field(line_edit, tag_name):
            value = self._get_display_value(tag_name)
            if value == "<< multiple values >>":
                line_edit.setText(value)
                line_edit.setStyleSheet("color: gray;")
            else:
                line_edit.setText(str(value or ''))
                line_edit.setStyleSheet("")

        # Populate fields
        populate_field(self.title_edit, KEY_TITLE)
        populate_field(self.artist_edit, KEY_ARTIST)
        populate_field(self.album_edit, KEY_ALBUM)
        populate_field(self.album_artist_edit, KEY_ALBUM_ARTIST)
        populate_field(self.date_edit, KEY_DATE)
        populate_field(self.genre_edit, KEY_GENRE)
        populate_field(self.comment_edit, KEY_COMMENT)
        populate_field(self.composer_edit, KEY_COMPOSER)
        populate_field(self.track_num_edit, KEY_TRACK_NUMBER)
        populate_field(self.disc_num_edit, KEY_DISC_NUMBER)
        populate_field(self.bpm_edit, KEY_BPM)
        populate_field(self.key_edit, KEY_MUSICAL_KEY)

        populate_field(self.replaygain_track_edit, KEY_REPLAYGAIN_TRACK_GAIN)
        populate_field(self.replaygain_album_edit, KEY_REPLAYGAIN_ALBUM_GAIN)

        # Connect signals
        self.title_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_TITLE, self.title_edit.text()))
        self.artist_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_ARTIST, self.artist_edit.text()))
        self.album_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_ALBUM, self.album_edit.text()))
        self.album_artist_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_ALBUM_ARTIST, self.album_artist_edit.text()))
        self.date_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_DATE, self.date_edit.text()))
        self.genre_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_GENRE, self.genre_edit.text()))
        self.comment_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_COMMENT, self.comment_edit.text()))
        self.composer_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_COMPOSER, self.composer_edit.text()))
        self.track_num_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_TRACK_NUMBER, self.track_num_edit.text()))
        self.disc_num_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_DISC_NUMBER, self.disc_num_edit.text()))
        self.bpm_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_BPM, self.bpm_edit.text()))
        self.key_edit.editingFinished.connect(lambda: self._on_simple_tab_edited(KEY_MUSICAL_KEY, self.key_edit.text()))

    def _on_simple_tab_edited(self, generic_tag_name, new_value):
        self.edit_manager.stage_change(self.file_paths, generic_tag_name, new_value)
        self._refresh_advanced_tab()

    def _get_display_value(self, tag_name, is_internal_tag=False):
        """
        Get the display value for a given tag.
        - If a value is staged, it is returned.
        - If values for all files are the same, that value is returned.
        - Otherwise, "<< multiple values >>" is returned.
        """
        # Check for a staged value first (only for the first file, as edits are applied to all)
        if self.file_paths:
            staged_value = self.edit_manager.get_staged_value(self.file_paths, tag_name, is_internal_tag=is_internal_tag)
            if staged_value is not None:
                return staged_value

        # Get committed values from all files
        values = {media_file.get_tag_simple(tag_name, is_internal_tag_key=is_internal_tag) for media_file in self.media_files}

        if len(values) == 1:
            return values.pop()
        else:
            return "<< multiple values >>"

    def _refresh_advanced_tab(self):
        self.setup_advanced_tab(self.advanced_tab)

    def setup_details_tab(self, tab_widget):
        layout = QVBoxLayout(tab_widget)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Property", "Value"])
        layout.addWidget(tree)

        # File section
        file_item = QTreeWidgetItem(tree, ["File"])
        font = file_item.font(0)
        font.setBold(True)
        file_item.setFont(0, font)

        if len(self.media_files) == 1:
            if self.media_files:
                metadata = self.media_files.metadata
                if KEY_INTERNAL in metadata:
                    for key, value in metadata[KEY_INTERNAL].items():
                        child = QTreeWidgetItem(file_item, [key, str(value)])
                        child.setFlags(child.flags() & ~Qt.ItemIsEditable)
        else:
            file_item.setText(0, f"{len(self.media_files)} files selected")

        # Stream section
        stream_item = QTreeWidgetItem(tree, ["Stream"])
        stream_item.setFont(0, font)

        if len(self.media_files) == 1:
            if self.media_files:
                if KEY_STREAM_INFO in self.media_files.metadata:
                    for key, value in self.media_files.metadata[KEY_STREAM_INFO].items():
                        child = QTreeWidgetItem(stream_item, [key, str(value["value"])])
                        child.setFlags(child.flags() & ~Qt.ItemIsEditable)
        else:
            stream_item.setFlags(stream_item.flags() | Qt.ItemIsHidden)

        tree.expandAll()
        for i in range(tree.columnCount()):
            tree.resizeColumnToContents(i)

    def setup_advanced_tab(self, tab_widget):
        if not hasattr(self, 'advanced_tree'):
            layout = QVBoxLayout(tab_widget)
            tree = QTreeWidget()
            tree.setColumnCount(3)
            tree.setHeaderLabels(["Tag", "Value", ""])
            layout.addWidget(tree)
            tree.itemChanged.connect(self.on_advanced_item_changed)
            self.advanced_tree = tree
        
        self.advanced_tree.clear()
        tree = self.advanced_tree

        all_providers_to_tags = {}
        for media_file in self.media_files:
            if KEY_TAGS in media_file.metadata:
                for tag_name, tag_info in media_file.metadata[KEY_TAGS].items():
                    provider_name = tag_info.get("provider", "Unknown")
                    if provider_name not in all_providers_to_tags:
                        all_providers_to_tags[provider_name] = {}
                    if tag_name not in all_providers_to_tags[provider_name]:
                        all_providers_to_tags[provider_name][tag_name] = set()
                    
                    value = tag_info.get("value")
                    if isinstance(value, list):
                        value = tuple(value)
                    try:
                        all_providers_to_tags[provider_name][tag_name].add(value)
                    except TypeError:  # unhashable type
                        all_providers_to_tags[provider_name][tag_name].add(str(value))

        for provider_name, tags in all_providers_to_tags.items():
            provider_item = QTreeWidgetItem(tree, [provider_name])
            font = provider_item.font(0)
            font.setBold(True)
            provider_item.setFont(0, font)
            provider_item.setFlags(provider_item.flags() & ~Qt.ItemIsEditable)

            for tag_name, values in sorted(tags.items()):
                is_binary = any(isinstance(v, bytes) for v in values)
                
                # Check for staged value first
                staged_value = self.edit_manager.get_staged_value(self.file_paths, tag_name, is_internal_tag=True)
                if staged_value is not None:
                    display_value = str(staged_value)
                    is_staged = True
                elif len(values) > 1:
                    display_value = "<< multiple values >>"
                    is_staged = False
                else:
                    value = values.pop()
                    if isinstance(value, list) or isinstance(value, tuple):
                        display_value = "; ".join(map(str, value))
                    elif isinstance(value, bytes):
                        display_value = "(binary data)"
                    else:
                        display_value = str(value)
                    is_staged = False

                child = QTreeWidgetItem(provider_item, [tag_name, display_value])
                child.setFlags(child.flags() | Qt.ItemIsEditable)

                if is_binary:
                    child.setFlags(child.flags() & ~Qt.ItemIsEditable)

                # Make staged values bold
                if is_staged:
                    font = child.font(1)
                    font.setBold(True)
                    child.setFont(1, font)

                    # Add revert button for staged changes
                    revert_button = QPushButton("Revert")
                    revert_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
                    revert_button.clicked.connect(
                        lambda: self.revert_change(child, tag_name)
                    )
                    self.advanced_tree.setItemWidget(child, 2, revert_button)

        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

    def on_advanced_item_changed(self, item, column):
        if column == 1 and item.parent():
            tag_name = item.text(0)
            new_value = item.text(1)

            # Find the provider for this internal tag
            provider = None
            for media_file in self.media_files:
                if KEY_TAGS in media_file.metadata:
                    if tag_name in media_file.metadata[KEY_TAGS]:
                         provider = media_file.metadata[KEY_TAGS][tag_name].get("provider")
                         if provider:
                            break

            if provider:
                self.edit_manager.stage_change(self.file_paths, tag_name, new_value, is_internal_tag=True, provider=provider)

                # Make font bold
                font = item.font(1)
                font.setBold(True)
                item.setFont(1, font)

                # Add revert button
                revert_button = QPushButton("Revert")
                revert_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
                revert_button.clicked.connect(
                    lambda: self.revert_change(item, tag_name)
                )
                self.advanced_tree.setItemWidget(item, 2, revert_button)

                self._refresh_simple_tab()

    def _refresh_simple_tab(self):
        self.title_edit.setText(str(self._get_display_value(KEY_TITLE) or ''))
        self.artist_edit.setText(str(self._get_display_value(KEY_ARTIST) or ''))
        self.album_edit.setText(str(self._get_display_value(KEY_ALBUM) or ''))
        self.album_artist_edit.setText(str(self._get_display_value(KEY_ALBUM_ARTIST) or ''))
        self.date_edit.setText(str(self._get_display_value(KEY_DATE) or ''))
        self.genre_edit.setText(str(self._get_display_value(KEY_GENRE) or ''))
        self.comment_edit.setText(str(self._get_display_value(KEY_COMMENT) or ''))
        self.composer_edit.setText(str(self._get_display_value(KEY_COMPOSER) or ''))
        self.track_num_edit.setText(str(self._get_display_value(KEY_TRACK_NUMBER) or ''))
        self.disc_num_edit.setText(str(self._get_display_value(KEY_DISC_NUMBER) or ''))
        self.bpm_edit.setText(str(self._get_display_value(KEY_BPM) or ''))
        self.key_edit.setText(str(self._get_display_value(KEY_MUSICAL_KEY) or ''))

    def revert_change(self, item, tag_name):
        self.advanced_tree.blockSignals(True)

        # Reverting a change for multiple files is complex if their original values differed.
        # As a simple solution, we revert the value to the one from the first selected file.
        # A more robust solution would require changes to EditManager.
        if not self.media_files:
            self.advanced_tree.blockSignals(False)
            return

        original_value = self.media_files.get_tag_simple(tag_name, is_internal_tag_key=True)

        provider = None
        if self.media_files:
            metadata = self.media_files.metadata
            if KEY_TAGS in metadata and tag_name in metadata[KEY_TAGS]:
                provider = metadata[KEY_TAGS][tag_name].get("provider")

        if provider:
            self.edit_manager.stage_change(self.file_paths, tag_name, original_value, is_internal_tag=True, provider=provider)

        self._refresh_advanced_tab()
        self._refresh_simple_tab()
        self.advanced_tree.blockSignals(False)
