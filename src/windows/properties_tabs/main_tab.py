from PySide6.QtWidgets import (
    QWidget, QFormLayout, QHBoxLayout, QLineEdit, QLabel, QGroupBox,
)
from PySide6.QtCore import Signal
from delegates.editable_metadata_delegate import PLACEHOLDER_MULTIPLE_VALUES
from models.edit_manager import EditManager
from util.const import (
    KEY_TITLE, KEY_ARTIST, KEY_ALBUM, KEY_ALBUM_ARTIST, KEY_DATE, KEY_GENRE,
    KEY_COMMENT, KEY_COMPOSER, KEY_TRACK_NUMBER, KEY_DISC_NUMBER, KEY_BPM,
    KEY_INITIAL_KEY, KEY_REPLAYGAIN_TRACK_GAIN, KEY_REPLAYGAIN_ALBUM_GAIN,
)


# Layout description for the editable metadata fields on this tab.
# Each entry is (display_label, attribute_name, generic_tag_key). The tab's
# __init__ iterates this list to create widgets, add them to the layout, wire
# up signals, and populate their values -- replacing what used to be six
# parallel blocks of copy-pasted boilerplate per field.
_EDITABLE_FIELDS: list[tuple[str, str, str]] = [
    ("Title:",        "title_edit",        KEY_TITLE),
    ("Artist:",       "artist_edit",       KEY_ARTIST),
    ("Album:",        "album_edit",        KEY_ALBUM),
    ("Album Artist:", "album_artist_edit", KEY_ALBUM_ARTIST),
    ("Date:",         "date_edit",         KEY_DATE),
    ("Genre:",        "genre_edit",        KEY_GENRE),
    ("Comment:",      "comment_edit",      KEY_COMMENT),
    ("Composer:",     "composer_edit",     KEY_COMPOSER),
    ("Track #:",      "track_num_edit",    KEY_TRACK_NUMBER),
    ("Disc #:",       "disc_num_edit",     KEY_DISC_NUMBER),
    ("BPM:",          "bpm_edit",          KEY_BPM),
    ("Key:",          "key_edit",          KEY_INITIAL_KEY),
]

# Read-only ReplayGain fields shown on a single line inside their own group box.
_READONLY_REPLAYGAIN_FIELDS: list[tuple[str, str, str]] = [
    ("Track:", "replaygain_track_label", KEY_REPLAYGAIN_TRACK_GAIN),
    ("Album:", "replaygain_album_label", KEY_REPLAYGAIN_ALBUM_GAIN),
]


class MainTab(QWidget):
    return_pressed = Signal()

    def __init__(self, media_files, edit_manager, parent=None):
        super().__init__(parent)
        self.media_files = media_files
        self.edit_manager = edit_manager

        layout = QFormLayout(self)

        # Build editable metadata fields from the declarative config.
        for label, attr_name, tag_key in _EDITABLE_FIELDS:
            line_edit = QLineEdit()
            setattr(self, attr_name, line_edit)
            layout.addRow(label, line_edit)
            self._wire_editable_field(line_edit, tag_key)

        # Publisher is shown in the layout but not wired to a tag today.
        # Preserved as-is pending a proper implementation of publisher editing.
        self.publisher_edit = QLineEdit()
        # Insert right after Composer to match the previous visual order.
        composer_index = next(
            i for i, (_, attr, _) in enumerate(_EDITABLE_FIELDS) if attr == "composer_edit"
        )
        layout.insertRow(composer_index + 1, "Publisher:", self.publisher_edit)

        # ReplayGain GroupBox: caption/value QLabel pairs on a single line,
        # each pair given equal stretch so they distribute evenly across the box.
        replaygain_group = QGroupBox("ReplayGain")
        replaygain_layout = QHBoxLayout()
        replaygain_group.setLayout(replaygain_layout)
        for label, attr_name, _tag_key in _READONLY_REPLAYGAIN_FIELDS:
            pair_layout = QHBoxLayout()
            pair_layout.addWidget(QLabel(label))
            value_label = QLabel()
            setattr(self, attr_name, value_label)
            pair_layout.addWidget(value_label)
            pair_layout.addStretch(1)
            replaygain_layout.addLayout(pair_layout, 1)
        layout.addRow(replaygain_group)

        self.refresh()

    def _wire_editable_field(self, line_edit: QLineEdit, tag_key: str) -> None:
        """Attach focus / textChanged / returnPressed handlers to an editable field."""
        line_edit.focusInEvent = lambda event, w=line_edit: self._clear_placeholder_on_focus(event, w)
        line_edit.textChanged.connect(lambda text, key=tag_key: self._on_edited(key, text))
        line_edit.returnPressed.connect(self._on_return_pressed)

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
        if line_edit.placeholderText() == PLACEHOLDER_MULTIPLE_VALUES:
            line_edit.setPlaceholderText("")
            line_edit.setStyleSheet("")
        QLineEdit.focusInEvent(line_edit, event)

    def _populate_field(self, line_edit, tag_name):
        value = self._get_display_value(tag_name)
        if value is None: # Multiple values
            line_edit.setText("")
            line_edit.setPlaceholderText(PLACEHOLDER_MULTIPLE_VALUES)
            line_edit.setStyleSheet("color: gray;")
        else: # Single value or empty
            line_edit.setText(str(value))
            line_edit.setPlaceholderText("")
            line_edit.setStyleSheet("")

    def _populate_readonly_label(self, label: QLabel, tag_name: str) -> None:
        """Populate a read-only value QLabel; labels have no placeholder text."""
        value = self._get_display_value(tag_name)
        if value is None: # Multiple values
            label.setText(PLACEHOLDER_MULTIPLE_VALUES)
            label.setStyleSheet("color: gray;")
        else: # Single value or empty
            label.setText(str(value))
            label.setStyleSheet("")

    def refresh(self):
        for _label, attr_name, tag_key in _EDITABLE_FIELDS:
            self._populate_field(getattr(self, attr_name), tag_key)
        for _label, attr_name, tag_key in _READONLY_REPLAYGAIN_FIELDS:
            self._populate_readonly_label(getattr(self, attr_name), tag_key)