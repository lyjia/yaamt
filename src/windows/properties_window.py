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
from util.const import (
    KEY_INTERNAL, KEY_STREAM_INFO, KEY_TAGS, KEY_TITLE, KEY_ARTIST, KEY_ALBUM,
    KEY_ALBUM_ARTIST, KEY_DATE, KEY_GENRE, KEY_COMMENT, KEY_COMPOSER,
    KEY_TRACK_NUMBER, KEY_DISC_NUMBER, KEY_BPM, KEY_MUSICAL_KEY,
    KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN
)
import windows.__resources_rc


class SaveWorker(QThread):
    finished = Signal()

    def __init__(self, media_file):
        super().__init__()
        self.media_file = media_file

    def run(self):
        self.media_file.save()
        self.finished.emit()


class PropertiesWindow(QMainWindow):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)

        self.file_path = file_path
        self.media_file = MediaFile(file_path, enable_write=True)
        self.setWindowTitle(f"Properties for {os.path.basename(file_path)}")
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

        self.worker = SaveWorker(self.media_file)
        self.worker.finished.connect(self.on_save_finished)
        self.worker.start()

    def on_save_finished(self):
        self.spinner.hide()
        self.status_label.hide()
        self.close()

    def update_button_states(self):
        if self.media_file.has_pending_changes():
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

        # Populate fields
        self.title_edit.setText(str(self.media_file.get_tag_simple(KEY_TITLE) or ''))
        self.artist_edit.setText(str(self.media_file.get_tag_simple(KEY_ARTIST) or ''))
        self.album_edit.setText(str(self.media_file.get_tag_simple(KEY_ALBUM) or ''))
        self.album_artist_edit.setText(str(self.media_file.get_tag_simple(KEY_ALBUM_ARTIST) or ''))
        self.date_edit.setText(str(self.media_file.get_tag_simple(KEY_DATE) or ''))
        self.genre_edit.setText(str(self.media_file.get_tag_simple(KEY_GENRE) or ''))
        self.comment_edit.setText(str(self.media_file.get_tag_simple(KEY_COMMENT) or ''))
        self.composer_edit.setText(str(self.media_file.get_tag_simple(KEY_COMPOSER) or ''))
        self.track_num_edit.setText(str(self.media_file.get_tag_simple(KEY_TRACK_NUMBER) or ''))
        self.disc_num_edit.setText(str(self.media_file.get_tag_simple(KEY_DISC_NUMBER) or ''))
        self.bpm_edit.setText(str(self.media_file.get_tag_simple(KEY_BPM) or ''))
        self.key_edit.setText(str(self.media_file.get_tag_simple(KEY_MUSICAL_KEY) or ''))

        self.replaygain_track_edit.setText(str(self.media_file.get_tag_simple(KEY_REPLAYGAIN_TRACK_GAIN) or ''))
        self.replaygain_album_edit.setText(str(self.media_file.get_tag_simple(KEY_REPLAYGAIN_ALBUM_GAIN) or ''))

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
        self.media_file.set_tag(generic_tag_name, new_value)
        self._refresh_advanced_tab()
        self.update_button_states()

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

        metadata = self.media_file.metadata
        if KEY_INTERNAL in metadata:
            for key, value in metadata[KEY_INTERNAL].items():
                child = QTreeWidgetItem(file_item, [key, str(value)])
                child.setFlags(child.flags() & ~Qt.ItemIsEditable)

        # Stream section
        stream_item = QTreeWidgetItem(tree, ["Stream"])
        stream_item.setFont(0, font)

        if KEY_STREAM_INFO in metadata:
            for key, value in metadata[KEY_STREAM_INFO].items():
                child = QTreeWidgetItem(stream_item, [key, str(value["value"])])
                child.setFlags(child.flags() & ~Qt.ItemIsEditable)

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

        metadata = self.media_file.metadata
        providers_to_tags = {}

        if KEY_TAGS in metadata:
            for tag_name, tag_info in metadata[KEY_TAGS].items():
                provider_name = tag_info.get("provider", "Unknown")
                if provider_name not in providers_to_tags:
                    providers_to_tags[provider_name] = []
                providers_to_tags[provider_name].append((tag_name, tag_info.get("value")))

        for provider_name, tags in providers_to_tags.items():
            provider_item = QTreeWidgetItem(tree, [provider_name])
            font = provider_item.font(0)
            font.setBold(True)
            provider_item.setFont(0, font)
            provider_item.setFlags(provider_item.flags() & ~Qt.ItemIsEditable)

            for tag_name, tag_value in sorted(tags):
                display_value = ""
                if isinstance(tag_value, list):
                    display_value = "; ".join(map(str, tag_value))
                elif isinstance(tag_value, bytes):
                    display_value = "(binary data)"
                else:
                    display_value = str(tag_value)

                child = QTreeWidgetItem(provider_item, [tag_name, display_value])
                child.setFlags(child.flags() | Qt.ItemIsEditable)

                if isinstance(tag_value, bytes):
                    child.setFlags(child.flags() & ~Qt.ItemIsEditable)

        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

    def on_advanced_item_changed(self, item, column):
        if column == 1 and item.parent():
            tag_name = item.text(0)
            new_value = item.text(1)

            self.media_file.set_tag(tag_name, new_value, is_internal_tag_key=True)

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

            self.update_button_states()
            self._refresh_simple_tab()

    def _refresh_simple_tab(self):
        self.title_edit.setText(str(self.media_file.get_tag_simple(KEY_TITLE) or ''))
        self.artist_edit.setText(str(self.media_file.get_tag_simple(KEY_ARTIST) or ''))
        self.album_edit.setText(str(self.media_file.get_tag_simple(KEY_ALBUM) or ''))
        self.album_artist_edit.setText(str(self.media_file.get_tag_simple(KEY_ALBUM_ARTIST) or ''))
        self.date_edit.setText(str(self.media_file.get_tag_simple(KEY_DATE) or ''))
        self.genre_edit.setText(str(self.media_file.get_tag_simple(KEY_GENRE) or ''))
        self.comment_edit.setText(str(self.media_file.get_tag_simple(KEY_COMMENT) or ''))
        self.composer_edit.setText(str(self.media_file.get_tag_simple(KEY_COMPOSER) or ''))
        self.track_num_edit.setText(str(self.media_file.get_tag_simple(KEY_TRACK_NUMBER) or ''))
        self.disc_num_edit.setText(str(self.media_file.get_tag_simple(KEY_DISC_NUMBER) or ''))
        self.bpm_edit.setText(str(self.media_file.get_tag_simple(KEY_BPM) or ''))
        self.key_edit.setText(str(self.media_file.get_tag_simple(KEY_MUSICAL_KEY) or ''))

    def revert_change(self, item, tag_name):
        self.advanced_tree.blockSignals(True)
        self.media_file.revert_tag_change(tag_name, is_internal_tag_key=True)

        original_value = self.media_file.get_tag_simple(tag_name, is_internal_tag_key=True)
        display_value = ""
        if isinstance(original_value, list):
            display_value = "; ".join(map(str, original_value))
        elif isinstance(original_value, bytes):
            display_value = "(binary data)"
        else:
            display_value = str(original_value)

        item.setText(1, display_value)

        # Reset font
        font = item.font(1)
        font.setBold(False)
        item.setFont(1, font)

        # Remove revert button
        self.advanced_tree.setItemWidget(item, 2, None)
        self.advanced_tree.blockSignals(False)

        self.update_button_states()
        self._refresh_simple_tab()