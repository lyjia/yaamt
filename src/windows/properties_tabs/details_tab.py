from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from util.const import KEY_INTERNAL, KEY_STREAM_INFO

class DetailsTab(QWidget):
    def __init__(self, media_files, parent=None):
        super().__init__(parent)
        self.media_files = media_files

        layout = QVBoxLayout(self)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Property", "Value"])
        layout.addWidget(tree)

        if not self.media_files or len(self.media_files) > 1:
            return

        media_file = self.media_files[0]
        metadata = media_file.metadata

        # File section
        file_item = QTreeWidgetItem(tree, ["File"])
        font = file_item.font(0)
        font.setBold(True)
        file_item.setFont(0, font)

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