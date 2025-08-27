import os
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QSplitter, QLabel, QProgressBar,
    QPushButton, QStyle, QTreeView, QFileSystemModel, QMenu, QMessageBox,
    QLineEdit, QSizePolicy, QFileDialog
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QDir, QThreadPool, Qt, QSortFilterProxyModel, QThread

import windows
from models.media_file import MediaFile
from models.qt.metadata_model import MetadataTableModel
from workers.gui.metadata_loader import MetadataLoader
from workers.gui.commit_worker import CommitWorker
from models.settings import settings, FileListSettings, ColumnSettings
from models.edit_manager import EditManager
from util.const import KEY_IS_MEDIA, KEY_FILE_PATH


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("YAAMT")
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)
        self.setWindowIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self.thread_pool = QThreadPool()
        self._current_path = ""
        self.metadata_results = []
        self.column_menu = QMenu("Columns", self)

        self.file_list_settings = FileListSettings()
        self._logical_column_ids = [c.id for c in FileListSettings().columns]

        # Menus
        self._create_menus()

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        open_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        action_open = QAction(open_icon, "Open Folder", self)
        action_open.triggered.connect(self.open_folder)
        self.toolbar.addAction(action_open)

        refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        action_refresh = QAction(refresh_icon, "Refresh", self)
        self.toolbar.addAction(action_refresh)

        self.path_textbox = QLineEdit()
        self.path_textbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(self.path_textbox)
        self.path_textbox.editingFinished.connect(self.on_path_editing_finished)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.cancel_button = QPushButton("Cancel")
        self.status_bar.addPermanentWidget(self.cancel_button)

        # Central Widget
        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # Left Pane (Directory Tree)
        self.directory_tree = QTreeView()
        self.dir_model = QFileSystemModel()
        self.dir_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)
        self.dir_model.setRootPath("")
        self.directory_tree.setModel(self.dir_model)
        self.directory_tree.setRootIndex(self.dir_model.index(""))
        for i in range(1, self.dir_model.columnCount()):
            self.directory_tree.hideColumn(i)
        splitter.addWidget(self.directory_tree)

        # Right Pane (File List)
        self.files_view = QTreeView()
        self.file_model = MetadataTableModel(self.file_list_settings.columns)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole)

        self.files_view.setModel(self.proxy_model)
        self.files_view.setSortingEnabled(True)
        self.files_view.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.header().customContextMenuRequested.connect(self.on_header_context_menu)
        self.files_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.customContextMenuRequested.connect(self.on_files_view_customContextMenuRequested)

        # Connect to EditManager signals
        self.edit_manager = EditManager()
        self.edit_manager.commit_successful.connect(self.on_commit_successful)

        # Setup commit worker
        self.commit_thread = QThread()
        self.commit_worker = CommitWorker(self.edit_manager)
        self.commit_worker.moveToThread(self.commit_thread)
        self.edit_manager.commit_requested.connect(self.commit_worker.commit_changes)
        self.commit_worker.signals.commit_finished.connect(self.on_commit_finished)
        self.commit_thread.start()

        splitter.addWidget(self.files_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Connect the panes
        self.directory_tree.selectionModel().currentChanged.connect(self.on_directory_changed)
        self.files_view.selectionModel().selectionChanged.connect(self.update_file_actions)

        # Connect header signals
        header = self.files_view.header()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.sectionResized.connect(self.on_column_resized)
        header.sectionMoved.connect(self.on_column_moved)
        header.sortIndicatorChanged.connect(self.on_sort_indicator_changed)

        self.setup_view_menu()

        # Set initial path
        if path and os.path.isdir(path):
            initial_path = path
        else:
            stored_path = settings.value("last_path")
            if stored_path and os.path.isdir(stored_path):
                initial_path = stored_path
            else:
                initial_path = QDir.homePath()
        self.set_path(initial_path)
        self.update_file_actions()
        self._load_column_settings()

    def closeEvent(self, event):
        self._save_column_settings()
        self.commit_thread.quit()
        self.commit_thread.wait()
        super().closeEvent(event)

    def set_path(self, path):
        self._current_path = path
        self.path_textbox.setText(path)
        index = self.dir_model.index(path)
        self.directory_tree.setCurrentIndex(index)
        settings.setValue("last_path", path)

    def on_directory_changed(self, current, previous):
        self.metadata_results = []
        path = self.dir_model.filePath(current)
        self.set_path(path)
        files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        
        worker = MetadataLoader(files)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.result.connect(self.on_worker_result)
        
        self.thread_pool.start(worker)
        self.status_label.setText(f"Loading files in {path}...")
        self.progress_bar.show()
        self.cancel_button.show()

    def update_progress(self, percent):
        self.progress_bar.setValue(percent)

    def on_worker_finished(self):
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.status_label.setText("Finished loading.")
        self.file_model.set_data(self.metadata_results)

    def on_worker_result(self, result_data):
        self.metadata_results.append(result_data)

    def on_header_context_menu(self, pos):
        self.column_menu.exec_(self.files_view.header().mapToGlobal(pos))

    def on_files_view_customContextMenuRequested(self, pos):
        menu = QMenu()
        menu.addAction(self.action_properties)
        menu.exec_(self.files_view.mapToGlobal(pos))

    def toggle_column(self, index, checked):
        self.files_view.setColumnHidden(index, not checked)
        # The main settings are now saved directly from the header in _save_column_settings.
        # However, we still need to update the is_visible flag for the context menu to work correctly.
        col_settings = self._get_column_settings_by_logical_index(index)
        if col_settings:
            col_settings.is_visible = checked

    def setup_view_menu(self):
        self.column_menu.clear()
        for i in range(self.file_model.columnCount()):
            action = QAction(self.file_model.headerData(i, Qt.Horizontal), self)
            action.setCheckable(True)
            action.setChecked(not self.files_view.isColumnHidden(i))
            action.setData(i)
            action.toggled.connect(lambda checked, index=i: self.toggle_column(index, checked))
            self.column_menu.addAction(action)
        self.view_menu.clear()
        self.view_menu.addMenu(self.column_menu)
        self.view_menu.addSeparator()
        action_reset_columns = QAction("Reset Columns", self)
        action_reset_columns.triggered.connect(self._reset_column_settings)
        self.view_menu.addAction(action_reset_columns)

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", self._current_path)
        if folder_path:
            self.set_path(folder_path)

    def on_path_editing_finished(self):
        path = self.path_textbox.text()
        if path != self._current_path:
            self._validate_path(path)

    def _validate_path(self, path):
        if os.path.isdir(path):
            self.set_path(path)
            return True
        else:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"The path '{path}' is not a valid directory.")
            msg_box.setWindowTitle("Invalid Path")
            msg_box.setStandardButtons(QMessageBox.Retry | QMessageBox.Cancel)
            response = msg_box.exec()

            if response == QMessageBox.Retry:
                self.path_textbox.setFocus()
                self.path_textbox.selectAll()
            else:
                self.path_textbox.setText(self._current_path)
            return False

    def _create_menus(self):
        # File Menu
        file_menu = self.menuBar().addMenu("&File")

        self.action_properties = QAction("Properties...", self)
        self.action_properties.setEnabled(False)
        self.action_properties.triggered.connect(self.open_properties_window)
        file_menu.addAction(self.action_properties)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View Menu
        self.view_menu = self.menuBar().addMenu("&View")

        # Help Menu
        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _show_about_dialog(self):
        about_window = windows.AboutWindow(self)
        about_window.exec()

    def open_properties_window(self):
        selected_indexes = self.files_view.selectionModel().selectedRows()
        if not selected_indexes:
            return

        media_files = []
        for index in selected_indexes:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.file_model._data[source_index.row()]
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path and row_data.get(KEY_IS_MEDIA):
                media_files.append(MediaFile(file_path, enable_write=True))

        if media_files:
            self.properties_window = windows.PropertiesWindow(media_files, self)
            self.properties_window.show()

    def on_column_resized(self, logical_index, old_size, new_size):
        # This is now handled by _save_column_settings, which reads the visual layout
        pass

    def on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        # This is now handled by _save_column_settings, which reads the visual layout
        pass

    def on_sort_indicator_changed(self, logical_index, order):
        self.file_list_settings.sort_column = logical_index
        self.file_list_settings.sort_order = order

    def update_file_actions(self):
        selected_indexes = self.files_view.selectionModel().selectedIndexes()
        selected_rows = {self.proxy_model.mapToSource(index).row() for index in selected_indexes}

        is_media_file = False
        if selected_rows:
            # Check if all selected items are media files
            all_media = True
            for row in selected_rows:
                index = self.file_model.index(row, 0) # Check first column
                if not self.file_model.data(index, KEY_IS_MEDIA):
                    all_media = False
                    break
            is_media_file = all_media

        self.action_properties.setEnabled(len(selected_rows) > 0 and is_media_file)

    def on_commit_successful(self, file_ids):
        """
        Slot called when commit is successful. Refreshes the model for the updated files.

        Args:
            file_ids: List of file ids that were successfully updated
        """
        self.file_model.refresh_files(file_ids, self.edit_manager)

    def on_commit_finished(self, saved_files, errors):
        if errors:
            self.edit_manager.commit_failed.emit(errors)
        else:
            self.edit_manager.emit_commit_successful(saved_files)

    def _reset_column_settings(self):
        self.file_list_settings = FileListSettings()
        self.file_model = MetadataTableModel(self.file_list_settings.columns)
        self.proxy_model.setSourceModel(self.file_model)
        self._apply_column_settings()
        self.setup_view_menu()

    def _get_column_settings_by_logical_index(self, logical_index):
        if logical_index < 0 or logical_index >= len(self._logical_column_ids):
            return None
        
        column_id = self._logical_column_ids[logical_index]
        for col in self.file_list_settings.columns:
            if col.id == column_id:
                return col
        return None

    def _load_column_settings(self):
        settings.beginGroup("file_list")
        
        # Load column settings
        num_columns = settings.beginReadArray("columns")
        if num_columns > 0:
            self.file_list_settings.columns = []
            for i in range(num_columns):
                settings.setArrayIndex(i)
                col_settings = ColumnSettings(
                    id=settings.value("id"),
                    label=settings.value("label"),
                    group=settings.value("group"),
                    width=int(settings.value("width")),
                    is_visible=settings.value("is_visible", type=bool)
                )
                self.file_list_settings.columns.append(col_settings)
        settings.endArray()

        # Load sort settings
        self.file_list_settings.sort_column = settings.value("sort_column", 0, type=int)
        self.file_list_settings.sort_order = settings.value("sort_order", Qt.SortOrder.AscendingOrder, type=int)
        
        settings.endGroup()

        self._apply_column_settings()

    def _apply_column_settings(self):
        header = self.files_view.header()
        model_columns_by_id = {id: i for i, id in enumerate(self._logical_column_ids)}

        # Set properties for columns based on settings
        for col_settings in self.file_list_settings.columns:
            if col_settings.id in model_columns_by_id:
                logical_index = model_columns_by_id[col_settings.id]
                header.resizeSection(logical_index, col_settings.width)
                header.setSectionHidden(logical_index, not col_settings.is_visible)

        # Set visual order of columns
        for visual_index, col_settings in enumerate(self.file_list_settings.columns):
            if col_settings.id in model_columns_by_id:
                logical_index = model_columns_by_id[col_settings.id]
                current_visual_index = header.visualIndex(logical_index)
                if current_visual_index != visual_index:
                    header.moveSection(current_visual_index, visual_index)

        self.files_view.sortByColumn(
            self.file_list_settings.sort_column,
            Qt.SortOrder(self.file_list_settings.sort_order)
        )

    def _save_column_settings(self):
        settings.beginGroup("file_list")
        header = self.files_view.header()
        
        # Get current visual layout
        columns_to_save = []
        for visual_index in range(header.count()):
            logical_index = header.logicalIndex(visual_index)
            col_id = self._logical_column_ids[logical_index]
            
            # Find original column settings to get label
            original_col = next((c for c in FileListSettings().columns if c.id == col_id), None)
            if original_col:
                columns_to_save.append(ColumnSettings(
                    id=col_id,
                    label=original_col.label,
                    group=original_col.group,
                    width=header.sectionSize(logical_index),
                    is_visible=not header.isSectionHidden(logical_index)
                ))

        # Save column settings
        settings.beginWriteArray("columns", len(columns_to_save))
        for i, col in enumerate(columns_to_save):
            settings.setArrayIndex(i)
            settings.setValue("id", col.id)
            settings.setValue("label", col.label)
            settings.setValue("width", col.width)
            settings.setValue("is_visible", col.is_visible)
        settings.endArray()

        # Save sort settings
        settings.setValue("sort_column", self.file_list_settings.sort_column)
        settings.setValue("sort_order", self.file_list_settings.sort_order)

        settings.endGroup()