import os
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont
from models.settings import ColumnSettings
from models.media_file import MediaFile
from models.edit_manager import EditManager

from util.const import (
    KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_SIZE_HUMAN, KEY_FILE_MTIME_HUMAN,
    KEY_FILE_CTIME, KEY_FILE_ATIME, KEY_FILE_TYPE, KEY_FILE_TYPE_HUMAN, KEY_IS_MEDIA,
    COL_MAIN_FILENAME, COL_MAIN_SIZE, COL_MAIN_TYPE, COL_MAIN_DATE_MODIFIED, KEY_FORMAT, KEY_TITLE, KEY_ARTIST,
    KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY, KEY_FILE_ID
)
from util.display import human_readable_size, human_readable_timestamp
from util.logging import log


class MetadataTableModel(QAbstractTableModel):
    def __init__(self, columns: list[ColumnSettings], edit_manager: EditManager, parent=None):
        super().__init__(parent)
        self._data = []
        self._columns = columns
        self.edit_manager = edit_manager

        if self.edit_manager is None:
            raise ValueError("edit_manager cannot be None!")

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None

        row_data = self._data[index.row()]
        file_id = row_data.get(KEY_FILE_ID)
        column = self._columns[index.column()]

        if role == KEY_IS_MEDIA:
            return row_data.get(KEY_IS_MEDIA) is True

        # Helper to get staged value, assuming generic tags for columns handled by this model
        staged_value = None
        if file_id and column.id:
            staged_value = self.edit_manager.get_staged_value(file_id, column.id)

        if role == Qt.ItemDataRole.DisplayRole:
            if staged_value is not None:
                return staged_value

            if column.id == COL_MAIN_FILENAME:
                return os.path.basename(row_data.get(KEY_FILE_PATH, ""))

            elif column.id == COL_MAIN_SIZE:
                fsize = row_data.get(KEY_FILE_SIZE, 0)
                return human_readable_size(fsize)

            elif column.id == COL_MAIN_TYPE:
                return row_data.get(KEY_FILE_TYPE_HUMAN)

            elif column.id == COL_MAIN_DATE_MODIFIED:
                fmtime = row_data.get(KEY_FILE_MTIME)
                return human_readable_timestamp(fmtime)

            elif column.id == "date_created":
                fctime = row_data.get(KEY_FILE_CTIME)
                return human_readable_timestamp(fctime)

            # elif header == "Last Accessed":
            #     fatime = row_data.get(KEY_FILE_ATIME)
            #     return human_readable_timestamp(fatime)

            else:
                return row_data.get(column.id, "")
        
        elif role == Qt.ItemDataRole.FontRole:
            if staged_value is not None:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.ItemDataRole.UserRole or role == Qt.ItemDataRole.EditRole:
            # For EditRole, return the current value from row_data, which should be consistent
            # with staged changes due to setData's behavior.
            if column.id == COL_MAIN_FILENAME:
                return os.path.basename(row_data.get(KEY_FILE_PATH, ""))

            elif column.id == COL_MAIN_SIZE:
                return row_data.get(KEY_FILE_SIZE, 0)

            elif column.id == COL_MAIN_TYPE:
                return row_data.get(KEY_FILE_TYPE)

            elif column.id == COL_MAIN_DATE_MODIFIED:
                return row_data.get(KEY_FILE_MTIME)

            elif column.id == "date_created":
                return row_data.get(KEY_FILE_CTIME)

            # elif header == "Last Accessed":
            #     return row_data.get(KEY_FILE_ATIME)

            else:
                return row_data.get(column.id, "")
                
        return None

    def flags(self, index):
        """
        Return the item flags for the given index.
        This determines whether a cell is editable and selectable.

        Args:
            index: The model index

        Returns:
            Qt.ItemFlags: The flags for the item
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        # Check if this column is writable
        column_settings = self._columns[index.column()]
        if column_settings.is_writable:
            flags |= Qt.ItemFlag.ItemIsEditable

        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """
        Set the data for the item at the given index.

        Args:
            index: The model index
            value: The new value to set
            role: The role for which to set data

        Returns:
            bool: True if the data was set successfully
        """
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            log.error(f"Invalid index or role for setData(): {index.isValid()}, {role}. Save aborted!")
            return False

        column_settings = self._columns[index.column()]
        if not column_settings.is_writable:
            log.error(f"Column {column_settings.id} is not writable! Save aborted!")
            return False

        row_data = self._data[index.row()]
        file_path = row_data.get(KEY_FILE_PATH)

        # Get the MediaFile object for this row
        media_file = MediaFile(file_path, enable_write=True)
        self.edit_manager.register_media_files([ media_file ])

        if media_file is None:
            log.error(f"media_file is None for row {index.row()}! Save aborted!")
            return False

        # Stage the change with the EditManager
        self.edit_manager.stage_change([media_file], column_settings.id, value)

        # Update the internal data immediately for UI responsiveness
        row_data[column_settings.id] = value
        self._data[index.row()] = row_data

        # Emit data changed signal
        self.dataChanged.emit(index, index, [role])

        return True

    def finished_with_edits(self):
        log.debug("Finished with edits. Saving changes...")
        self.edit_manager.commit_changes()

    def get_media_file_for_row(self, row):
        """
        Get the MediaFile object for a given row index.

        Args:
            row: The row index

        Returns:
            MediaFile or None: The MediaFile object if found
        """
        if row < 0 or row >= len(self._data):
            log.error(f"Invalid row index: {row} (of {len(self._data)})!")
            return None

        row_data = self._data[row]
        file_id = row_data.get(KEY_FILE_ID)
        if file_id:
            # We need to access the EditManager's media files
            # This will be set external to this model when it's created
            return self.edit_manager.get_media_file(file_id)
        else:
            log.error(f"Row {row} does not have a file ID!")

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._columns[section].label
        return None

    def get_data_for_row(self, row):
        return self._data[row]

    def set_entire_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        column_settings = self._columns[column]
        self._data.sort(key=lambda x: x.get(column_settings.id, ""), reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()

    @staticmethod
    def get_metadata_from_media_file(media_file: MediaFile) -> dict:
        """
        Given a MediaFile object, return a dictionary of its metadata.

        Args:
            media_file: The MediaFile object to get metadata from.

        Returns:
            A dictionary of metadata.
        """
        return {
            # fs attributes
            KEY_FILE_PATH: media_file.file_path,
            KEY_FILE_SIZE: media_file.get_internal_data(KEY_FILE_SIZE),
            KEY_FILE_MTIME: media_file.get_internal_data(KEY_FILE_MTIME),
            KEY_FILE_CTIME: media_file.get_internal_data(KEY_FILE_CTIME),
            KEY_FILE_TYPE: media_file.get_internal_data(KEY_FILE_TYPE),
            KEY_FILE_TYPE_HUMAN: media_file.get_stream_info_value(KEY_FORMAT),

            # tag attributes
            KEY_TITLE: media_file.get_tag_simple(KEY_TITLE),
            KEY_ARTIST: media_file.get_tag_simple(KEY_ARTIST),
            KEY_ALBUM: media_file.get_tag_simple(KEY_ALBUM),
            KEY_GENRE: media_file.get_tag_simple(KEY_GENRE),
            KEY_BPM: media_file.get_tag_simple(KEY_BPM),
            KEY_MUSICAL_KEY: media_file.get_tag_simple(KEY_MUSICAL_KEY),

            # internal
            KEY_IS_MEDIA: media_file.get_internal_data(KEY_IS_MEDIA),
            KEY_FILE_ID: media_file.file_id
        }

    def refresh_files(self, file_ids: list[str], edit_manager: EditManager):
        """
        Refresh the metadata for specific files in the model.

        Args:
            file_ids: List of file ids to refresh
            edit_manager: The EditManager instance
        """
        log.debug(f"Refreshing metadata for files: {file_ids}...")
        updated_rows = []
        #TODO: this iterates through every file in a folder just to find the file ids to redraw,
        # because we do not index file ID in self._data.
        # We should figure out some way to easily reference a row in self._data by file ID without having to
        # enumerate the whole thing. This logic is also mostly the same as the logic in MetadataLoader.run(), we should
        # consolidate that.
        for row_index, row_data in enumerate(self._data):
            file_id = row_data.get(KEY_FILE_ID)
            if file_id in file_ids:
                media_file = edit_manager.get_media_file(file_id)
                if not media_file:
                    continue

                # Re-fetch metadata from the MediaFile object
                new_metadata = self.get_metadata_from_media_file(media_file)
                # Update the row data with new metadata
                self._data[row_index] = new_metadata
                updated_rows.append(row_index)

        # Emit signals for the updated rows
        if updated_rows:
            for row in updated_rows:
                start_index = self.createIndex(row, 0)
                end_index = self.createIndex(row, self.columnCount() - 1)
                self.dataChanged.emit(start_index, end_index, [])