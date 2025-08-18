import os
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QSplitter, QLabel, QProgressBar,
    QPushButton, QStyle, QTreeView, QFileSystemModel, QMenu, QMessageBox,
    QLineEdit, QSizePolicy, QFileDialog
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QDir, QThreadPool, Qt, QSortFilterProxyModel
from models.qt.metadata_model import MetadataTableModel
from workers.gui.metadata_loader import MetadataLoader
from models.settings import settings
from util.const import KEY_IS_MEDIA, KEY_FILE_PATH
from windows.properties_window import PropertiesWindow


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("YAAMT")
        self.resize(800, 600)
        self.thread_pool = QThreadPool()
        self._current_path = ""
        self.metadata_results = []
        self.column_menu = QMenu("Columns", self)

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
        self.file_model = MetadataTableModel()

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole)

        self.files_view.setModel(self.proxy_model)
        self.files_view.setSortingEnabled(True)
        self.files_view.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.header().customContextMenuRequested.connect(self.on_header_context_menu)
        self.files_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.customContextMenuRequested.connect(self.on_files_view_customContextMenuRequested)
        splitter.addWidget(self.files_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Connect the panes
        self.directory_tree.selectionModel().currentChanged.connect(self.on_directory_changed)
        self.files_view.selectionModel().selectionChanged.connect(self.update_file_actions)

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
        QMessageBox.about(
            self,
            "About Audio Metadata Tool",
            "<p>A simple tool for editing audio metadata.</p>"
            "<p>Version 0.1</p>"
        )

    def open_properties_window(self):
        selected_indexes = self.files_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        first_index = selected_indexes[0]
        source_index = self.proxy_model.mapToSource(first_index)
        
        # Get the dictionary for the selected row
        row_data = self.file_model._data[source_index.row()]
        file_path = row_data.get(KEY_FILE_PATH)

        if file_path:
            self.properties_window = PropertiesWindow(file_path, self)
            self.properties_window.show()

    def update_file_actions(self):
        selected_indexes = self.files_view.selectionModel().selectedIndexes()
        selected_rows = {index.row() for index in selected_indexes}

        is_media_file = False
        if len(selected_rows) == 1:
            first_index = selected_indexes[0]
            source_index = self.proxy_model.mapToSource(first_index)
            is_media_file = self.file_model.data(source_index, KEY_IS_MEDIA)

        self.action_properties.setEnabled(len(selected_rows) == 1 and is_media_file)