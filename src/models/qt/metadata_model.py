import os
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


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
        if role == Qt.ItemDataRole.DisplayRole:
            row_data = self._data[index.row()]
            header = self._headers[index.column()]
            if header == "Name":
                return os.path.basename(row_data.get("file_path", ""))
            elif header == "Size":
                size_in_bytes = row_data.get('size', 0)
                return f"{size_in_bytes / 1024:.2f} KB" if size_in_bytes else "N/A"
            elif header == "Type":
                return os.path.splitext(row_data.get("file_path", ""))
            elif header == "Date Modified":
                return str(row_data.get("date_modified", "N/A"))
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