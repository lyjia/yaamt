import os
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QSplitter, QLabel, QProgressBar,
    QPushButton, QStyle, QTreeView, QFileSystemModel, QMenu
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QDir, QThreadPool, Qt
from .metadata_model import MetadataTableModel
from .worker import MetadataWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Metadata Tool")
        self.resize(800, 600)
        self.thread_pool = QThreadPool()
        self.metadata_results = []

        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        action_refresh = QAction(refresh_icon, "Refresh", self)
        toolbar.addAction(action_refresh)

        # View Menu
        self.view_menu = self.menuBar().addMenu("View")

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        cancel_button = QPushButton("Cancel")
        self.status_bar.addPermanentWidget(cancel_button)

        # Central Widget
        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # Left Pane (Directory Tree)
        self.directory_tree = QTreeView()
        self.dir_model = QFileSystemModel()
        self.dir_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)
        self.dir_model.setRootPath(QDir.homePath())
        self.directory_tree.setModel(self.dir_model)
        self.directory_tree.setRootIndex(self.dir_model.index(QDir.homePath()))
        splitter.addWidget(self.directory_tree)

        # Right Pane (File List)
        self.file_list = QTreeView()
        self.file_model = MetadataTableModel()
        self.file_list.setModel(self.file_model)
        self.file_list.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.header().customContextMenuRequested.connect(self.on_header_context_menu)
        splitter.addWidget(self.file_list)

        # Connect the panes
        self.directory_tree.selectionModel().currentChanged.connect(self.on_directory_changed)

    def on_directory_changed(self, current, previous):
        self.metadata_results = []
        path = self.dir_model.filePath(current)
        files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        
        worker = MetadataWorker(files)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.result.connect(self.on_worker_result)
        
        self.thread_pool.start(worker)
        self.status_label.setText(f"Loading files in {path}...")
        self.progress_bar.show()

    def update_progress(self, percent):
        self.progress_bar.setValue(percent)

    def on_worker_finished(self):
        self.progress_bar.hide()
        self.status_label.setText("Finished loading.")
        self.file_model.set_data(self.metadata_results)
        self.setup_view_menu()

    def on_worker_result(self, result_data):
        self.metadata_results.append(result_data)

    def on_header_context_menu(self, pos):
        menu = QMenu(self)
        for i, header in enumerate(self.file_model._headers):
            action = QAction(header, self, checkable=True)
            action.setChecked(not self.file_list.isColumnHidden(i))
            action.setData(i)
            action.toggled.connect(self.toggle_column)
            menu.addAction(action)
        menu.exec_(self.file_list.header().mapToGlobal(pos))

    def toggle_column(self, checked):
        column_index = self.sender().data()
        self.file_list.setColumnHidden(column_index, not checked)

    def setup_view_menu(self):
        self.view_menu.clear()
        for i, header in enumerate(self.file_model._headers):
            action = QAction(header, self, checkable=True)
            action.setChecked(not self.file_list.isColumnHidden(i))
            action.setData(i)
            action.toggled.connect(self.toggle_column)
            self.view_menu.addAction(action)