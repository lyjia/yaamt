from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHeaderView, QSizePolicy
)
from models.edit_manager import EditManager
from util.const import KEY_TAGS

class AdvancedTab(QWidget):
    def __init__(self, media_files, edit_manager, parent=None):
        super().__init__(parent)
        self.media_files = media_files
        self.edit_manager = edit_manager

        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Tag", "Value", ""])
        layout.addWidget(self.tree)

        self.tree.itemChanged.connect(self.on_item_changed)

        self.refresh()

    def refresh(self):
        self.tree.clear()

        if not self.media_files or len(self.media_files) > 1:
            return

        media_file = self.media_files[0]
        metadata = media_file.metadata

        if KEY_TAGS not in metadata:
            return

        # Group tags by provider
        providers_to_tags = {}
        for tag_name, tag_info in metadata[KEY_TAGS].items():
            provider_name = tag_info.get("provider", "Unknown")
            if provider_name not in providers_to_tags:
                providers_to_tags[provider_name] = []
            providers_to_tags[provider_name].append((tag_name, tag_info))

        for provider_name, tags in sorted(providers_to_tags.items()):
            provider_item = QTreeWidgetItem(self.tree, [provider_name])
            font = provider_item.font(0)
            font.setBold(True)
            provider_item.setFont(0, font)
            provider_item.setFlags(provider_item.flags() & ~provider_item.flags().ItemIsEditable)

            for tag_name, tag_info in sorted(tags):
                value = tag_info.get("value")
                is_binary = isinstance(value, bytes)

                staged_value = self.edit_manager.get_staged_value_for_file(self.media_files[0], tag_name, is_internal_tag=True)
                is_staged = staged_value is not None

                display_value = str(staged_value) if is_staged else self._format_value(value)

                child = QTreeWidgetItem(provider_item, [tag_name, display_value])
                child.setFlags(child.flags() | child.flags().ItemIsEditable)

                if is_binary:
                    child.setFlags(child.flags() & ~child.flags().ItemIsEditable)

                if is_staged:
                    font = child.font(1)
                    font.setBold(True)
                    child.setFont(1, font)
                    self._add_revert_button(child, tag_name)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

    def _format_value(self, value):
        if isinstance(value, list) or isinstance(value, tuple):
            return "; ".join(map(str, value))
        elif isinstance(value, bytes):
            return "(binary data)"
        return str(value)

    def on_item_changed(self, item, column):
        if column == 1 and item.parent():
            tag_name = item.text(0)
            new_value = item.text(1)

            provider = self._get_provider_for_tag(tag_name)
            if provider:
                self.edit_manager.stage_change(self.media_files, tag_name, new_value, is_internal_tag=True, provider=provider)
                font = item.font(1)
                font.setBold(True)
                item.setFont(1, font)
                self._add_revert_button(item, tag_name)

    def _get_provider_for_tag(self, tag_name):
        if self.media_files:
            metadata = self.media_files[0].metadata
            if KEY_TAGS in metadata and tag_name in metadata[KEY_TAGS]:
                provider_class_name = metadata[KEY_TAGS][tag_name].get("provider")
                # Find the provider instance in the media_file's providers
                for provider in self.media_files[0]._providers:
                    if provider.__class__.__name__ == provider_class_name:
                        return provider
        return None

    def _add_revert_button(self, item, tag_name):
        revert_button = QPushButton("Revert")
        revert_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        revert_button.clicked.connect(lambda: self.revert_change(tag_name))
        self.tree.setItemWidget(item, 2, revert_button)

    def revert_change(self, tag_name):
        self.tree.blockSignals(True)
        original_value = self.media_files[0].get_tag_simple(tag_name, is_internal_tag_key=True)
        provider = self._get_provider_for_tag(tag_name)
        if provider:
            self.edit_manager.stage_change(self.media_files, tag_name, original_value, is_internal_tag=True, provider=provider)
        self.refresh()
        self.tree.blockSignals(False)