from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QGroupBox
from PySide6.QtCore import QEvent, Signal
from models.edit_manager import EditManager
from util.const import (
    KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_ALBUM_ARTIST, KEY_DATE, KEY_GENRE,
    KEY_COMMENT, KEY_COMPOSER, KEY_TRACK_NUMBER, KEY_DISC_NUMBER, KEY_BPM,
    KEY_MUSICAL_KEY, KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN
)

class MainTab(QWidget):
    return_pressed = Signal()

    def __init__(self, media_files, edit_manager, parent=None):
        super().__init__(parent)
        self.media_files = media_files
        self.edit_manager = edit_manager

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

        # Connect focus events for clearing placeholders
        self.title_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.title_edit)
        self.artist_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.artist_edit)
        self.album_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.album_edit)
        self.album_artist_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.album_artist_edit)
        self.date_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.date_edit)
        self.genre_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.genre_edit)
        self.comment_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.comment_edit)
        self.composer_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.composer_edit)
        self.track_num_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.track_num_edit)
        self.disc_num_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.disc_num_edit)
        self.bpm_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.bpm_edit)
        self.key_edit.focusInEvent = lambda event: self._clear_placeholder_on_focus(event, self.key_edit)

        self.refresh()

        # Connect signals for text changes
        self.title_edit.textChanged.connect(lambda text: self._on_edited(KEY_TITLE, text))
        self.artist_edit.textChanged.connect(lambda text: self._on_edited(KEY_ARTIST, text))
        self.album_edit.textChanged.connect(lambda text: self._on_edited(KEY_ALBUM, text))
        self.album_artist_edit.textChanged.connect(lambda text: self._on_edited(KEY_ALBUM_ARTIST, text))
        self.date_edit.textChanged.connect(lambda text: self._on_edited(KEY_DATE, text))
        self.genre_edit.textChanged.connect(lambda text: self._on_edited(KEY_GENRE, text))
        self.comment_edit.textChanged.connect(lambda text: self._on_edited(KEY_COMMENT, text))
        self.composer_edit.textChanged.connect(lambda text: self._on_edited(KEY_COMPOSER, text))
        self.track_num_edit.textChanged.connect(lambda text: self._on_edited(KEY_TRACK_NUMBER, text))
        self.disc_num_edit.textChanged.connect(lambda text: self._on_edited(KEY_DISC_NUMBER, text))
        self.bpm_edit.textChanged.connect(lambda text: self._on_edited(KEY_BPM, text))
        self.key_edit.textChanged.connect(lambda text: self._on_edited(KEY_MUSICAL_KEY, text))

        # Connect returnPressed signals
        self.title_edit.returnPressed.connect(self._on_return_pressed)
        self.artist_edit.returnPressed.connect(self._on_return_pressed)
        self.album_edit.returnPressed.connect(self._on_return_pressed)
        self.album_artist_edit.returnPressed.connect(self._on_return_pressed)
        self.date_edit.returnPressed.connect(self._on_return_pressed)
        self.genre_edit.returnPressed.connect(self._on_return_pressed)
        self.comment_edit.returnPressed.connect(self._on_return_pressed)
        self.composer_edit.returnPressed.connect(self._on_return_pressed)
        self.track_num_edit.returnPressed.connect(self._on_return_pressed)
        self.disc_num_edit.returnPressed.connect(self._on_return_pressed)
        self.bpm_edit.returnPressed.connect(self._on_return_pressed)
        self.key_edit.returnPressed.connect(self._on_return_pressed)

    def _on_edited(self, generic_tag_name, new_value):
        self.edit_manager.stage_change(self.media_files, generic_tag_name, new_value)

    def _on_return_pressed(self):
        self.return_pressed.emit()

    def _get_display_value(self, tag_name):
        if not self.media_files:
            return ""

        # Check for staged changes first. If any file has a staged change, that takes precedence.
        # For simplicity, we'll check the first file. A more complex scenario might involve
        # checking if all staged changes are the same.
        staged_value = self.edit_manager.get_staged_value_for_file(self.media_files[0], tag_name)
        if staged_value is not None:
            # If a value is staged for the first file, we assume it's representative for all in this context.
            # The edit manager handles applying it to all.
            return staged_value

        values = set()
        for mf in self.media_files:
            val = mf.get_tag_simple(tag_name)
            values.add(val)

        if len(values) == 1:
            popped = values.pop()
            return popped if popped is not None else ""

        return None # Indicates multiple values

    def _clear_placeholder_on_focus(self, event, line_edit):
        if line_edit.placeholderText() == "<< multiple values >>":
            line_edit.setPlaceholderText("")
            line_edit.setStyleSheet("")
        QLineEdit.focusInEvent(line_edit, event)

    def _populate_field(self, line_edit, tag_name):
        value = self._get_display_value(tag_name)
        if value is None: # Multiple values
            line_edit.setText("")
            line_edit.setPlaceholderText("<< multiple values >>")
            line_edit.setStyleSheet("color: gray;")
        else: # Single value or empty
            line_edit.setText(str(value))
            line_edit.setPlaceholderText("")
            line_edit.setStyleSheet("")

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