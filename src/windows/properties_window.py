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
)
from models.media_file import MediaFile
from util.const import KEY_INTERNAL, KEY_STREAM_INFO, KEY_TAGS


class PropertiesWindow(QMainWindow):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)

        self.file_path = file_path
        self.media_file = MediaFile(file_path)
        self.setWindowTitle(f"Properties for {os.path.basename(file_path)}")
        self.changes = {}

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tab widget
        tab_widget = QTabWidget()
        tab_widget.addTab(QWidget(), "Details")
        tab_widget.addTab(QWidget(), "Advanced")
        main_layout.addWidget(tab_widget)

        self.setup_details_tab(tab_widget.widget(0))
        self.setup_advanced_tab(tab_widget.widget(1))

        # Bottom button layout
        bottom_layout = QHBoxLayout()

        # Left-aligned button
        tools_button = QPushButton("Tools")
        bottom_layout.addWidget(tools_button)

        bottom_layout.addStretch()

        # Right-aligned buttons
        self.close_button = QPushButton("Close")
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.close_button.clicked.connect(self.close)

        bottom_layout.addWidget(self.ok_button)
        bottom_layout.addWidget(self.close_button)

        main_layout.addLayout(bottom_layout)

    def on_ok_clicked(self):
        print(self.changes)
        self.close()

    def update_button_states(self):
        if self.changes:
            self.ok_button.setEnabled(True)
            self.close_button.setText("Cancel")
        else:
            self.ok_button.setEnabled(False)
            self.close_button.setText("Close")

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
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Tag", "Value"])
        layout.addWidget(tree)
        tree.itemChanged.connect(self.on_advanced_item_changed)

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

        for i in range(tree.columnCount()):
            tree.resizeColumnToContents(i)

    def on_advanced_item_changed(self, item, column):
        if column == 1 and item.parent():
            provider_name = item.parent().text(0)
            tag_name = item.text(0)
            new_value = item.text(1)
            if provider_name not in self.changes:
                self.changes[provider_name] = {}
            self.changes[provider_name][tag_name] = new_value
            self.update_button_states()