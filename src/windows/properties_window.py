import os
from PySide6.QtCore import Qt
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


class PropertiesWindow(QMainWindow):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)

        self.changes = {}
        self.original_values = {}

        self.file_path = file_path
        self.media_file = MediaFile(file_path)
        self.setWindowTitle(f"Properties for {os.path.basename(file_path)}")
        self.resize(720, 480)
        self.setMinimumSize(400, 300)
        self.setWindowIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Create and set up tabs
        self.basic_info_tab = QWidget()
        self.details_tab = QWidget()
        self.advanced_tab = QWidget()

        tab_widget.addTab(self.basic_info_tab, "Basic Info")
        tab_widget.addTab(self.details_tab, "Details")
        tab_widget.addTab(self.advanced_tab, "Advanced")

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
        self.setEnabled(False)

        status_label = QLabel("Writing changes...")
        self.bottom_layout.insertWidget(1, status_label)

        for provider_name, tags in self.changes.items():
            for tag_name, new_value in tags.items():
                print(
                    f"Provider: {provider_name}, Tag: {tag_name}, New Value: {new_value}"
                )
        self.close()

    def update_button_states(self):
        if self.changes:
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
        layout = QVBoxLayout(tab_widget)
        tree = QTreeWidget()
        tree.setColumnCount(3)
        tree.setHeaderLabels(["Tag", "Value", ""])
        layout.addWidget(tree)
        tree.itemChanged.connect(self.on_advanced_item_changed)

        self.advanced_tree = tree

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
            provider_name = item.parent().text(0)
            tag_name = item.text(0)
            new_value = item.text(1)

            # Store original value if it's the first change
            if provider_name not in self.original_values or tag_name not in self.original_values.get(provider_name, {}):
                original_value = self.media_file.metadata.get(KEY_TAGS, {}).get(tag_name, {}).get("value")
                display_value = ""
                if isinstance(original_value, list):
                    display_value = "; ".join(map(str, original_value))
                elif isinstance(original_value, bytes):
                    display_value = "(binary data)"
                else:
                    display_value = str(original_value)

                if provider_name not in self.original_values:
                    self.original_values[provider_name] = {}
                self.original_values[provider_name][tag_name] = display_value

            if provider_name not in self.changes:
                self.changes[provider_name] = {}
            self.changes[provider_name][tag_name] = new_value

            # Make font bold
            font = item.font(1)
            font.setBold(True)
            item.setFont(1, font)

            # Add revert button
            revert_button = QPushButton("Revert")
            revert_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            revert_button.clicked.connect(
                lambda: self.revert_change(item, provider_name, tag_name)
            )
            self.advanced_tree.setItemWidget(item, 2, revert_button)

            self.update_button_states()

    def revert_change(self, item, provider_name, tag_name):
        self.advanced_tree.blockSignals(True) # we do this because it stops the value from being bolded after reverting the change. TODO: is this the best way to handle this? It seems to address the underlying issue in an unnecessarily oblique fashion
        original_value = self.original_values[provider_name][tag_name]

        # Update item in QTreeWidget
        item.setText(1, original_value)

        # Reset font
        font = item.font(1)
        font.setBold(False)
        item.setFont(1, font)

        # Remove from changes
        if provider_name in self.changes and tag_name in self.changes[provider_name]:
            del self.changes[provider_name][tag_name]
            if not self.changes[provider_name]:
                del self.changes[provider_name]

        # Remove from original_values
        if provider_name in self.original_values and tag_name in self.original_values[provider_name]:
            del self.original_values[provider_name][tag_name]
            if not self.original_values[provider_name]:
                del self.original_values[provider_name]

        # Remove revert button
        self.advanced_tree.setItemWidget(item, 2, None)
        self.advanced_tree.blockSignals(False) # see comment where we set this to true

        self.update_button_states()