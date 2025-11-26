"""Resources preferences pane for managing external resources."""
from typing import Tuple
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QProgressDialog
)
from PySide6.QtGui import QIcon, QColor
from PySide6.QtCore import QSettings, Qt, QThread, Signal

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
        self.settings = QSettings("Lyjia", "Audio Metadata Tool")
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

        # Cache location info
        cache_group = QGroupBox("Cache Location")
        cache_layout = QVBoxLayout()

        rm = get_resource_manager()
        cache_path_label = QLabel(f"Resources are cached in: {rm.get_cache_root()}")
        cache_path_label.setWordWrap(True)
        cache_path_label.setStyleSheet("color: gray; font-size: 10px;")
        cache_layout.addWidget(cache_path_label)

        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)

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

    def validate(self) -> Tuple[bool, str]:
        """No validation needed."""
        return True, ""

    def load_defaults(self) -> None:
        """Clear all custom locations."""
        rm = get_resource_manager()
        for resource_id in rm.get_all_registered_resources():
            rm.clear_custom_location(resource_id)
        self._populate_table()
