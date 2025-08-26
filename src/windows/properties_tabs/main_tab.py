from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QGroupBox
from models.edit_manager import EditManager
from util.const import (
    KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_ALBUM_ARTIST, KEY_DATE, KEY_GENRE,
    KEY_COMMENT, KEY_COMPOSER, KEY_TRACK_NUMBER, KEY_DISC_NUMBER, KEY_BPM,
    KEY_MUSICAL_KEY, KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN
)

class MainTab(QWidget):
    def __init__(self, media_files, parent=None):
        super().__init__(parent)
        self.media_files = media_files
        self.edit_manager = EditManager()
        self.file_paths = [mf.file_path for mf in self.media_files]

        layout = QFormLayout(self)

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

        self.refresh()

        # Connect signals
        self.title_edit.editingFinished.connect(lambda: self._on_edited(KEY_TITLE, self.title_edit.text()))
        self.artist_edit.editingFinished.connect(lambda: self._on_edited(KEY_ARTIST, self.artist_edit.text()))
        self.album_edit.editingFinished.connect(lambda: self._on_edited(KEY_ALBUM, self.album_edit.text()))
        self.album_artist_edit.editingFinished.connect(lambda: self._on_edited(KEY_ALBUM_ARTIST, self.album_artist_edit.text()))
        self.date_edit.editingFinished.connect(lambda: self._on_edited(KEY_DATE, self.date_edit.text()))
        self.genre_edit.editingFinished.connect(lambda: self._on_edited(KEY_GENRE, self.genre_edit.text()))
        self.comment_edit.editingFinished.connect(lambda: self._on_edited(KEY_COMMENT, self.comment_edit.text()))
        self.composer_edit.editingFinished.connect(lambda: self._on_edited(KEY_COMPOSER, self.composer_edit.text()))
        self.track_num_edit.editingFinished.connect(lambda: self._on_edited(KEY_TRACK_NUMBER, self.track_num_edit.text()))
        self.disc_num_edit.editingFinished.connect(lambda: self._on_edited(KEY_DISC_NUMBER, self.disc_num_edit.text()))
        self.bpm_edit.editingFinished.connect(lambda: self._on_edited(KEY_BPM, self.bpm_edit.text()))
        self.key_edit.editingFinished.connect(lambda: self._on_edited(KEY_MUSICAL_KEY, self.key_edit.text()))

    def _on_edited(self, generic_tag_name, new_value):
        self.edit_manager.stage_change(self.file_paths, generic_tag_name, new_value)

    def _get_display_value(self, tag_name):
        staged_value = self.edit_manager.get_staged_value(self.file_paths, tag_name)
        if staged_value is not None:
            return staged_value

        values = {mf.get_tag_simple(tag_name) for mf in self.media_files}
        if len(values) == 1:
            return values.pop()
        return "<< multiple values >>"

    def _populate_field(self, line_edit, tag_name):
        value = self._get_display_value(tag_name)
        if value == "<< multiple values >>":
            line_edit.setText(value)
            line_edit.setStyleSheet("color: gray;")
            line_edit.setPlaceholderText("Enter a new value for all files")
        else:
            line_edit.setText(str(value or ''))
            line_edit.setStyleSheet("")
            line_edit.setPlaceholderText("")

    def refresh(self):
        self._populate_field(self.title_edit, KEY_TITLE)
        self._populate_field(self.artist_edit, KEY_ARTIST)
        self._populate_field(self.album_edit, KEY_ALBUM)
        self._populate_field(self.album_artist_edit, KEY_ALBUM_ARTIST)
        self._populate_field(self.date_edit, KEY_DATE)
        self._populate_field(self.genre_edit, KEY_GENRE)
        self._populate_field(self.comment_edit, KEY_COMMENT)
        self._populate_field(self.composer_edit, KEY_COMPOSER)
        self._populate_field(self.track_num_edit, KEY_TRACK_NUMBER)
        self._populate_field(self.disc_num_edit, KEY_DISC_NUMBER)
        self._populate_field(self.bpm_edit, KEY_BPM)
        self._populate_field(self.key_edit, KEY_MUSICAL_KEY)
        self._populate_field(self.replaygain_track_edit, KEY_REPLAYGAIN_TRACK_GAIN)
        self._populate_field(self.replaygain_album_edit, KEY_REPLAYGAIN_ALBUM_GAIN)