import os
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from models.settings import ColumnSettings
from models.media_file import MediaFile

from util.const import (
    KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_SIZE_HUMAN, KEY_FILE_MTIME_HUMAN,
    KEY_FILE_CTIME, KEY_FILE_ATIME, KEY_FILE_TYPE, KEY_FILE_TYPE_HUMAN, KEY_IS_MEDIA,
    COL_MAIN_FILENAME, COL_MAIN_SIZE, COL_MAIN_TYPE, COL_MAIN_DATE_MODIFIED, KEY_FORMAT, KEY_TITLE, KEY_ARTIST,
    KEY_ALBUM, KEY_GENRE, KEY_BPM, KEY_MUSICAL_KEY
)
from util.display import human_readable_size, human_readable_timestamp


class MetadataTableModel(QAbstractTableModel):
    def __init__(self, columns: list[ColumnSettings], parent=None):
        super().__init__(parent)
        self._data = []
        self._columns = columns

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None

        row_data = self._data[index.row()]

        if role == KEY_IS_MEDIA:
            return row_data.get(KEY_IS_MEDIA) is True

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.UserRole:
            column = self._columns[index.column()]

            if column.id == COL_MAIN_FILENAME:
                return os.path.basename(row_data.get(KEY_FILE_PATH, ""))

            elif column.id == COL_MAIN_SIZE:
                fsize = row_data.get(KEY_FILE_SIZE, 0)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_size( fsize )
                else:
                    return fsize

            elif column.id == COL_MAIN_TYPE:
                if role == Qt.ItemDataRole.DisplayRole:
                    return row_data.get(KEY_FILE_TYPE_HUMAN)
                else:
                    return row_data.get(KEY_FILE_TYPE)

            elif column.id == COL_MAIN_DATE_MODIFIED:
                fmtime = row_data.get(KEY_FILE_MTIME)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_timestamp( fmtime )
                else:
                    return fmtime

            elif column.id == "date_created":
                fctime = row_data.get(KEY_FILE_CTIME)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_timestamp( fctime )
                else:
                    return fctime

            # elif header == "Last Accessed":
            #     fatime = row_data.get(KEY_FILE_ATIME)
            #
            #     if role == Qt.ItemDataRole.DisplayRole:
            #         return human_readable_timestamp( fatime )
            #     else:
            #         return fatime

            else:
                return row_data.get(column.id, "")
                
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._columns[section].label
        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        column_settings = self._columns[column]
        self._data.sort(key=lambda x: x.get(column_settings.id, ""), reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()

    def refresh_files(self, file_paths):
        """
        Refresh the metadata for specific files in the model.

        Args:
            file_paths: List of file paths to refresh
        """
        updated_rows = []
        for row_index, row_data in enumerate(self._data):
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path in file_paths:
                # Reload metadata for this file using the same structure as MetadataLoader
                media_file = MediaFile(file_path)
                mf_size = media_file.get_internal_data(KEY_FILE_SIZE)
                mf_ctime = media_file.get_internal_data(KEY_FILE_CTIME)
                mf_mtime = media_file.get_internal_data(KEY_FILE_MTIME)
                mf_type = media_file.get_internal_data(KEY_FILE_TYPE)

                new_metadata = {
                    # fs attributes
                    KEY_FILE_PATH: file_path,
                    KEY_FILE_SIZE: mf_size,
                    KEY_FILE_MTIME: mf_mtime,
                    KEY_FILE_CTIME: mf_ctime,
                    KEY_FILE_TYPE: mf_type,
                    KEY_FILE_TYPE_HUMAN: media_file.get_stream_info_value(KEY_FORMAT),

                    # tag attributes
                    KEY_TITLE: media_file.get_tag_simple(KEY_TITLE),
                    KEY_ARTIST: media_file.get_tag_simple(KEY_ARTIST),
                    KEY_ALBUM: media_file.get_tag_simple(KEY_ALBUM),
                    KEY_GENRE: media_file.get_tag_simple(KEY_GENRE),
                    KEY_BPM: media_file.get_tag_simple(KEY_BPM),
                    KEY_MUSICAL_KEY: media_file.get_tag_simple(KEY_MUSICAL_KEY),

                    # internal
                    KEY_IS_MEDIA: media_file.get_internal_data(KEY_IS_MEDIA)
                }
                # Update the row data with new metadata
                self._data[row_index] = new_metadata
                updated_rows.append(row_index)

        # Emit signals for the updated rows
        if updated_rows:
            for row in updated_rows:
                index = self.createIndex(row, 0)
                self.dataChanged.emit(index, index, [])