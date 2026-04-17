"""Resources preferences pane for managing external resources."""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QProgressDialog
)
from PySide6.QtGui import QIcon, QColor
from PySide6.QtCore import Qt, QThread, Signal

from models.settings import get_qsettings
from util.const import SETTINGS_RESOURCES_CACHE_ROOT
from windows.preferences.base import PreferencePaneBase
from util.resource_manager import get_resource_manager, ResourceMetadata


class ResourcesPane(PreferencePaneBase):
    """
    Preference pane for managing external resources.

    Displays a table of all registered resources with:
    - Resource name and description
    - Status indicator (OK/Not found)
    - Download/Locate actions
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_qsettings()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Description
        desc_label = QLabel(
            "External resources such as machine learning models can be managed here. "
            "Some analyzers require these resources to function."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Resources table
        self.resources_table = QTableWidget()
        self.resources_table.setColumnCount(4)
        self.resources_table.setHorizontalHeaderLabels([
            "Resource", "Required By", "Status", "Actions"
        ])

        # Configure table
        header = self.resources_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.resources_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.resources_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        layout.addWidget(self.resources_table)

        # Cache location section
        cache_group = QGroupBox("Cache Location")
        cache_layout = QVBoxLayout()

        # Cache path display row
        cache_path_row = QHBoxLayout()

        self.cache_path_label = QLabel()
        self.cache_path_label.setWordWrap(True)
        cache_path_row.addWidget(self.cache_path_label, 1)

        change_cache_btn = QPushButton("Change...")
        change_cache_btn.clicked.connect(self._on_change_cache_location)
        cache_path_row.addWidget(change_cache_btn)

        reset_cache_btn = QPushButton("Reset to Default")
        reset_cache_btn.clicked.connect(self._on_reset_cache_location)
        cache_path_row.addWidget(reset_cache_btn)

        cache_layout.addLayout(cache_path_row)

        # Info label
        cache_info_label = QLabel(
            "Note: Changing the cache location will not move existing downloads. "
            "You may need to re-download resources or use 'Locate...' to specify their paths."
        )
        cache_info_label.setWordWrap(True)
        cache_info_label.setStyleSheet("color: gray; font-size: 10px;")
        cache_layout.addWidget(cache_info_label)

        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)

        # Update cache path display
        self._update_cache_path_display()

    def _update_cache_path_display(self) -> None:
        """Update the cache path label with current location."""
        rm = get_resource_manager()
        self.cache_path_label.setText(f"Current: {rm.get_cache_root()}")

    def _on_change_cache_location(self) -> None:
        """Handle change cache location button click."""
        rm = get_resource_manager()
        current_path = str(rm.get_cache_root())

        new_path = QFileDialog.getExistingDirectory(
            self,
            "Select Cache Directory",
            current_path,
            QFileDialog.Option.ShowDirsOnly
        )

        if new_path and new_path != current_path:
            # Warn user about existing downloads
            result = QMessageBox.warning(
                self,
                "Change Cache Location",
                "Changing the cache location will not move existing downloads.\n\n"
                "Resources downloaded to the previous location will need to be "
                "re-downloaded or manually located using the 'Locate...' button.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if result == QMessageBox.StandardButton.Yes:
                rm.set_cache_root(Path(new_path))
                # Persist the setting
                self.settings.setValue(SETTINGS_RESOURCES_CACHE_ROOT, new_path)
                self._update_cache_path_display()
                self._populate_table()

    def _on_reset_cache_location(self) -> None:
        """Handle reset cache location button click."""
        result = QMessageBox.question(
            self,
            "Reset Cache Location",
            "Reset the cache location to the default system location?\n\n"
            "This will not move any existing downloads.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if result == QMessageBox.StandardButton.Yes:
            rm = get_resource_manager()
            # Clear the custom setting and reset to default
            self.settings.remove(SETTINGS_RESOURCES_CACHE_ROOT)
            rm.reset_cache_root()
            self._update_cache_path_display()
            self._populate_table()

    def _populate_table(self) -> None:
        """Populate the resources table with current data."""
        rm = get_resource_manager()
        resources = rm.get_all_registered_resources()

        self.resources_table.setRowCount(len(resources))

        for row, (resource_id, metadata) in enumerate(resources.items()):
            # Resource name/description
            name_item = QTableWidgetItem(metadata.display_name or resource_id)
            name_item.setData(Qt.ItemDataRole.UserRole, resource_id)
            if metadata.description:
                name_item.setToolTip(metadata.description)
            self.resources_table.setItem(row, 0, name_item)

            # Required by
            required_item = QTableWidgetItem(metadata.required_by or "")
            self.resources_table.setItem(row, 1, required_item)

            # Status
            is_available = rm.is_resource_loadable(resource_id)
            status_item = QTableWidgetItem("OK!" if is_available else "Not found")
            if is_available:
                status_item.setForeground(QColor("green"))
            else:
                status_item.setForeground(QColor("red"))
            self.resources_table.setItem(row, 2, status_item)

            # Actions widget
            actions_widget = self._create_actions_widget(
                resource_id, metadata, is_available
            )
            self.resources_table.setCellWidget(row, 3, actions_widget)

    def _create_actions_widget(
        self,
        resource_id: str,
        metadata: ResourceMetadata,
        is_available: bool
    ) -> QWidget:
        """Create the actions widget for a resource row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)

        # Download button
        download_btn = QPushButton("Download")
        download_btn.setEnabled(not is_available and bool(metadata.url))
        download_btn.clicked.connect(
            lambda checked, rid=resource_id, meta=metadata: self._on_download(
                rid, meta
            )
        )
        layout.addWidget(download_btn)

        # Locate button
        locate_btn = QPushButton("Locate...")
        locate_btn.clicked.connect(
            lambda checked, rid=resource_id, meta=metadata: self._on_locate(
                rid, meta
            )
        )
        layout.addWidget(locate_btn)

        return widget

    def _on_download(self, resource_id: str, metadata: ResourceMetadata) -> None:
        """Handle download button click."""
        if metadata.download_type == "browser":
            import webbrowser
            webbrowser.open(metadata.url)
            QMessageBox.information(
                self,
                "Download in Browser",
                f"The download page has been opened in your browser.\n\n"
                f"After downloading, use 'Locate...' to specify the file location."
            )
        else:
            self._start_download(resource_id, metadata)

    def _start_download(self, resource_id: str, metadata: ResourceMetadata) -> None:
        """Start a direct download with progress dialog."""
        rm = get_resource_manager()

        # Create progress dialog
        progress = QProgressDialog(
            f"Downloading {metadata.display_name or resource_id}...",
            "Cancel",
            0, 100,
            self
        )
        progress.setWindowTitle("Downloading Resource")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        # Create download worker thread
        class DownloadWorker(QThread):
            finished = Signal(bool, str)
            progress_update = Signal(int)

            def __init__(self, res_id, res_manager):
                super().__init__()
                self._resource_id = res_id
                self._resource_manager = res_manager

            def run(self):
                try:
                    # Create a progress reporter that emits signals
                    class QtProgressReporter:
                        def __init__(self, signal):
                            self._signal = signal

                        def start(self, resource_name: str, total_size: int):
                            pass

                        def update(self, bytes_downloaded: int, total_size: int):
                            if total_size > 0:
                                percent = int((bytes_downloaded / total_size) * 100)
                                self._signal.emit(percent)

                        def complete(self):
                            self._signal.emit(100)

                        def error(self, message: str):
                            pass

                    reporter = QtProgressReporter(self.progress_update)
                    self._resource_manager.ensure_resource(
                        self._resource_id,
                        progress_reporter=reporter
                    )
                    self.finished.emit(True, "")
                except Exception as e:
                    self.finished.emit(False, str(e))

        worker = DownloadWorker(resource_id, rm)

        def on_progress(value):
            progress.setValue(value)

        def on_finished(success, error):
            progress.close()
            if success:
                self._populate_table()
                QMessageBox.information(
                    self,
                    "Download Complete",
                    f"{metadata.display_name or resource_id} downloaded successfully."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Download Failed",
                    f"Failed to download resource:\n{error}"
                )

        def on_cancelled():
            worker.terminate()
            progress.close()

        worker.progress_update.connect(on_progress)
        worker.finished.connect(on_finished)
        progress.canceled.connect(on_cancelled)

        # Store worker reference to prevent garbage collection
        self._download_worker = worker
        worker.start()

    def _on_locate(self, resource_id: str, metadata: ResourceMetadata) -> None:
        """Handle locate button click."""
        file_filter = "All Files (*.*)"
        if metadata.filename.endswith('.pt') or metadata.filename.endswith('.pth'):
            file_filter = "PyTorch Models (*.pt *.pth);;All Files (*.*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Locate {metadata.display_name or resource_id}",
            "",
            file_filter
        )

        if file_path:
            rm = get_resource_manager()
            if rm.set_custom_location(resource_id, Path(file_path)):
                self._populate_table()
            else:
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "The selected file could not be found."
                )

    # PreferencePaneBase implementation

    def get_name(self) -> str:
        return "Resources"

    def get_icon(self) -> QIcon:
        from PySide6.QtWidgets import QApplication, QStyle
        return QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_DriveNetIcon
        )

    def load_from_settings(self) -> None:
        """Load resources table."""
        self._populate_table()

    def save_to_settings(self) -> None:
        """No settings to save - custom locations are saved immediately."""
        pass

    def validate(self) -> tuple[bool, str]:
        """No validation needed."""
        return True, ""

    def load_defaults(self) -> None:
        """Clear all custom locations."""
        rm = get_resource_manager()
        for resource_id in rm.get_all_registered_resources():
            rm.clear_custom_location(resource_id)
        self._populate_table()
