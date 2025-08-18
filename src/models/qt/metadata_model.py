import os
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from util.const import KEY_FILE_PATH, KEY_FILE_SIZE, KEY_FILE_MTIME, KEY_FILE_SIZE_HUMAN, KEY_FILE_MTIME_HUMAN, \
    KEY_FILE_CTIME, KEY_FILE_ATIME, KEY_FILE_TYPE, KEY_FILE_TYPE_HUMAN
from util.display import human_readable_size, human_readable_timestamp


class MetadataTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._headers = ["Name", "Size", "Type", "Date Modified", "Title", "Artist", "Album", "Genre", "BPM", "Key"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.UserRole:
            row_data = self._data[index.row()]
            header = self._headers[index.column()]

            if header == "Name":
                return os.path.basename(row_data.get(KEY_FILE_PATH, ""))

            elif header == "Size":
                fsize = row_data.get(KEY_FILE_SIZE, 0)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_size( fsize )
                else:
                    return fsize

            elif header == "Type":
                if role == Qt.ItemDataRole.DisplayRole:
                    return row_data.get(KEY_FILE_TYPE_HUMAN)
                else:
                    return row_data.get(KEY_FILE_TYPE)

            elif header == "Date Modified":
                fmtime = row_data.get(KEY_FILE_MTIME)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_timestamp( fmtime )
                else:
                    return fmtime

            elif header == "Date Created":
                fctime = row_data.get(KEY_FILE_CTIME)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_timestamp( fctime )
                else:
                    return fctime

            elif header == "Last Accessed":
                fatime = row_data.get(KEY_FILE_ATIME)

                if role == Qt.ItemDataRole.DisplayRole:
                    return human_readable_timestamp( fatime )
                else:
                    return fatime

            else:
                return row_data.get(header.lower(), "")
                
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        header = self._headers[column]
        self._data.sort(key=lambda x: x.get(header.lower(), ""), reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()