import os
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QSplitter, QLabel, QProgressBar,
    QPushButton, QStyle, QTreeView, QFileSystemModel, QMenu, QMessageBox,
    QLineEdit, QSizePolicy, QFileDialog, QAbstractItemView, QVBoxLayout, QWidget,
    QDialog, QToolButton
)
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtCore import (
    QDir, QThreadPool, Qt, QSortFilterProxyModel, QThread, Slot, Signal
)

import windows
from models.media_file import MediaFile
from models.qt.metadata_model import MetadataTableModel
from workers.gui.load_files_worker import LoadFilesWorker
from workers.gui.playback_worker import PlaybackWorker
from windows.playback_panel import PlaybackPanel
from windows.analyzer import AnalyzerSetupDialog, AnalyzerProgressDialog, AnalyzerSummaryDialog
from models.settings import settings, FileListSettings, ColumnSettings
from models.edit_manager import EditManager
from delegates.editable_metadata_delegate import EditableMetadataDelegate
from util.const import (
    KEY_IS_MEDIA, KEY_FILE_PATH,
    SETTINGS_DEBUG_PLAYBACK_ADAPTATION, SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE,
    SETTINGS_DEBUG_PLAYBACK_CHANNELS, SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH,
    SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT, SETTINGS_UI_SKIN,
    SETTINGS_GROUP_FAVORITES, SETTINGS_ARRAY_FAVORITES_LOCATIONS,
    SETTINGS_GROUP_FILE_LIST, SETTINGS_ARRAY_FILE_LIST_COLUMNS,
)
from util.debug import is_debug_mode
from util.file_browser import open_in_file_browser
from util.logging import log
from util.resource_manager import get_resource_manager
from providers import get_all_categories, ProviderType
from workers.analyzer_dispatcher import AnalyzerDispatcher


class MainWindow(QMainWindow):
    start_playback_signal = Signal(object)  # Emits MediaFile instance

    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("YAAMT")
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)

        self.thread_pool = QThreadPool()
        self._current_path = ""
        self.column_menu = QMenu("Columns", self)
        self._current_load_worker = None
        self._current_worker_id = 0
        self._saved_sort_column = None
        self._saved_sort_order = None

        # Playback components
        self.playback_panel = PlaybackPanel()
        self.playback_panel.hide() # Hidden by default
        self.playback_worker = PlaybackWorker()
        self.playback_thread = QThread()
        self.playback_worker.moveToThread(self.playback_thread)
        self.playback_thread.start()

        self.file_list_settings = FileListSettings()
        self._logical_column_ids = [c.id for c in FileListSettings().columns]

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

        # Add Favorites toolbar button
        self.favorites_button = QToolButton()
        favorites_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirLinkIcon)
        self.favorites_button.setIcon(favorites_icon)
        self.favorites_button.setToolTip("Favorites")
        self.favorites_button.setPopupMode(QToolButton.MenuButtonPopup)
        # Menu will be created and shared with menu bar in _create_menus()
        self.favorites_button.clicked.connect(self._on_favorites_button_clicked)
        self.toolbar.addWidget(self.favorites_button)

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
        self.cancel_button.clicked.connect(self.on_load_cancelled)
        self.status_bar.addPermanentWidget(self.cancel_button)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter(self)
        main_layout.addWidget(splitter, 1)
        main_layout.addWidget(self.playback_panel, 0)

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

        # Connect to EditManager signals
        self.edit_manager = EditManager()
        self.edit_manager.commit_started.connect(self.on_commit_started)
        self.edit_manager.commit_progress.connect(self.update_progress)
        self.edit_manager.commit_finished.connect(self.on_commit_finished)
        self.edit_manager.commit_failed.connect(self.on_commit_failed)
        self.edit_manager.autosave_changed.connect(self.on_autosave_changed)

        # Coordinate playback pause/resume around file writes
        from workers.gui.playback_coordinator import PlaybackCoordinator
        self.playback_coordinator = PlaybackCoordinator(self.playback_worker)
        self.edit_manager.set_playback_coordinator(self.playback_coordinator)

        # Right Pane (File List)
        self.files_view = QTreeView()
        self.file_model = MetadataTableModel(self.file_list_settings.columns, self.edit_manager)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole)

        self.files_view.setModel(self.proxy_model)

        # Set up the editable delegate for edit-in-place functionality
        self.editable_delegate = EditableMetadataDelegate()
        self.files_view.setItemDelegate(self.editable_delegate)
        self.files_view.setSortingEnabled(True)
        self.files_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files_view.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.header().customContextMenuRequested.connect(self.on_header_context_menu)
        self.files_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_view.customContextMenuRequested.connect(self.on_files_view_customContextMenuRequested)
        self.files_view.doubleClicked.connect(self.on_files_view_double_clicked)

        # TODO: Viewport-aware priority loading during scrolling (currently disabled)
        # The priority range calculation works correctly, but the worker's priority list
        # is built once at the start of Stage 2 enrichment and never rebuilt. This means
        # scrolling during loading updates the priority range but doesn't actually change
        # the processing order. To make this work properly, we need to:
        # 1. Implement a dynamic priority queue in LoadFilesWorker that can be reordered
        # 2. Add debouncing (500ms) to prevent flooding the worker with priority updates
        # 3. Rebuild the processing order when priority range changes significantly
        # For now, only the INITIAL viewport when enrichment starts is prioritized.
        #
        # self.files_view.verticalScrollBar().valueChanged.connect(self._on_viewport_changed_debounced)
        # self.files_view.resizeEvent = self._create_resize_event_wrapper(self.files_view.resizeEvent)

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


        # Actions
        self.create_file_menu_actions()

        # Menus
        self._create_menus()

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

        # Connect playback signals and slots
        self.playback_panel.play_requested.connect(self.playback_worker.resume)
        self.playback_panel.pause_requested.connect(self.playback_worker.pause)
        self.playback_panel.stop_requested.connect(self.playback_worker.stop)
        self.playback_panel.seek_requested.connect(self.playback_worker.seek)

        self.playback_worker.playback_started.connect(self.on_playback_started)
        self.playback_worker.position_changed.connect(self.playback_panel.update_playback_position)
        self.playback_worker.playback_finished.connect(self.on_playback_finished)
        self.playback_worker.playback_stopped.connect(self.on_playback_stopped)
        self.playback_worker.playback_paused.connect(self.on_playback_paused)
        self.playback_worker.playback_resumed.connect(self.on_playback_resumed)
        self.playback_worker.error_occurred.connect(self.on_playback_error)

        # Connect the signal to start playback in the worker thread
        self.start_playback_signal.connect(self.playback_worker.start_playback)

    def closeEvent(self, event):
        log.info("MainWindow close event received!") # Commenting-out or removing this line causes playback to freeze for some reason https://github.com/lyjia/yaamt/issues/49

        # Stop playback and clean up the playback thread
        self._cleanup_playback()  # Commenting-out or removing this line fixes the playback bug mentioned above, but then the program won't exit cleanly https://github.com/lyjia/yaamt/issues/49

        # Cancel any running file loading worker
        if self._current_load_worker is not None:
            log.debug("Cancelling file loading worker on window close")
            self._current_load_worker.cancel()
            self._current_load_worker = None

        if self.edit_manager.has_staged_changes():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before quitting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                # Save changes and then close
                self.edit_manager.commit_changes(autosave_override=True)
                # We don't have a direct signal to know when the override save is done,
                # so we'll assume for now that if commit_changes is called, it will handle its state.
                # A more robust solution might involve connecting to commit_finished/failed
                # and then closing, but that adds complexity.
                # For now, we proceed with closing after initiating the save.
                self._save_column_settings()
                super().closeEvent(event)
            elif reply == QMessageBox.Discard:
                # Discard changes and close
                self._save_column_settings()
                super().closeEvent(event)
            else: # Cancel
                event.ignore()
        else:
            self._save_column_settings()
            super().closeEvent(event)

    def set_path(self, path):
        self._current_path = path
        self.path_textbox.setText(path)
        index = self.dir_model.index(path)
        self.directory_tree.setCurrentIndex(index)
        settings.setValue("last_path", path)

    def on_directory_changed(self, current, previous):
        # Cancel any existing load operation
        if self._current_load_worker is not None:
            log.debug("Cancelling previous load worker due to directory change")
            self._current_load_worker.cancel()

        path = self.dir_model.filePath(current)
        self.set_path(path)

        # Clear the model for the new directory
        self.file_model.set_entire_data([])

        # Save current sort order and switch to filename ascending for loading
        header = self.files_view.header()
        self._saved_sort_column = header.sortIndicatorSection()
        self._saved_sort_order = header.sortIndicatorOrder()

        # Find the filename column index
        from util.const import COL_MAIN_FILENAME
        filename_column = None
        for i, col_id in enumerate(self._logical_column_ids):
            if col_id == COL_MAIN_FILENAME:
                filename_column = i
                break

        # Disable sorting during load and force to filename ascending
        self.files_view.setSortingEnabled(False)
        if filename_column is not None:
            # Only sort the proxy model - source model stays in insertion order
            # This keeps row indices stable for the worker's file_updated signals
            self.proxy_model.sort(filename_column, Qt.SortOrder.AscendingOrder)
            header.setSortIndicator(filename_column, Qt.SortOrder.AscendingOrder)

        # Increment worker ID to track this specific load operation
        self._current_worker_id += 1
        worker_id = self._current_worker_id

        # Create worker with directory path
        worker = LoadFilesWorker(path)
        self._current_load_worker = worker

        # Connect to new two-stage signals
        worker.signals.files_discovered.connect(lambda files: self.on_files_discovered(files, worker_id))
        worker.signals.discovery_finished.connect(lambda count: self.on_discovery_finished(count, worker_id))
        worker.signals.file_updated.connect(lambda index, metadata: self.on_file_updated(index, metadata, worker_id))
        worker.signals.enrichment_progress.connect(lambda current, total: self.on_enrichment_progress(current, total, worker_id))
        worker.signals.finished.connect(lambda: self.on_worker_finished(worker_id))

        self.thread_pool.start(worker)
        self.status_label.setText(f"Scanning files in {path}...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode during discovery
        self.progress_bar.show()
        self.cancel_button.show()

    def update_progress(self, percent):
        self.progress_bar.setValue(percent)

    def on_files_discovered(self, files: list, worker_id: int):
        """
        Handle files discovered during Stage 1.

        Args:
            files: List of basic file data dictionaries
            worker_id: ID of the worker that emitted this signal
        """
        if worker_id != self._current_worker_id:
            log.debug(f"Ignoring discovery from old worker {worker_id} (current: {self._current_worker_id})")
            return

        # Add discovered files to the model
        self.file_model.add_rows(files)

        # Update status with current count
        current_count = self.file_model.rowCount()
        self.status_label.setText(f"Scanning files... ({current_count} found)")

    def on_discovery_finished(self, total_count: int, worker_id: int):
        """
        Handle completion of Stage 1 discovery.

        Args:
            total_count: Total number of files discovered
            worker_id: ID of the worker that emitted this signal
        """
        if worker_id != self._current_worker_id:
            log.debug(f"Ignoring discovery finish from old worker {worker_id} (current: {self._current_worker_id})")
            return

        log.info(f"Discovery finished: {total_count} files found")
        self.status_label.setText(f"Loading metadata... (0/{total_count})")
        self.progress_bar.setMaximum(100)  # Switch to determinate mode
        self.progress_bar.setValue(0)

        # Send initial viewport range to worker
        self._update_viewport_priority()

    def on_file_updated(self, index: int, metadata: dict, worker_id: int):
        """
        Handle a single file being updated during Stage 2.

        Args:
            index: Row index to update
            metadata: Full metadata dictionary
            worker_id: ID of the worker that emitted this signal
        """
        if worker_id != self._current_worker_id:
            log.debug(f"Ignoring file update from old worker {worker_id} (current: {self._current_worker_id})")
            return

        # Update the row with enriched metadata
        self.file_model.update_row(index, metadata)

    def on_enrichment_progress(self, current: int, total: int, worker_id: int):
        """
        Handle progress updates during Stage 2.

        Args:
            current: Number of files processed
            total: Total number of files
            worker_id: ID of the worker that emitted this signal
        """
        if worker_id != self._current_worker_id:
            log.debug(f"Ignoring enrichment progress from old worker {worker_id} (current: {self._current_worker_id})")
            return

        # Update status and progress bar
        self.status_label.setText(f"Loading metadata... ({current}/{total})")
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)

    def on_worker_finished(self, worker_id):
        """
        Handle worker completion.

        Args:
            worker_id: ID of the worker that finished
        """
        if worker_id != self._current_worker_id:
            log.debug(f"Ignoring finished signal from old worker {worker_id} (current: {self._current_worker_id})")
            return

        # Restore the saved sort order
        if self._saved_sort_column is not None and self._saved_sort_order is not None:
            header = self.files_view.header()
            header.setSortIndicator(self._saved_sort_column, self._saved_sort_order)
            # Only sort the proxy model - source model stays in insertion order
            self.proxy_model.sort(self._saved_sort_column, self._saved_sort_order)

        # Re-enable sorting
        self.files_view.setSortingEnabled(True)

        self.progress_bar.hide()
        self.cancel_button.hide()
        file_count = self.file_model.rowCount()
        self.status_label.setText(f"Ready. {file_count} files loaded.")
        self._current_load_worker = None

    def on_load_cancelled(self):
        """Handle the cancel button being clicked during file loading."""
        if self._current_load_worker is not None:
            log.info("User cancelled file loading")
            self._current_load_worker.cancel()

            # Restore the saved sort order
            if self._saved_sort_column is not None and self._saved_sort_order is not None:
                header = self.files_view.header()
                header.setSortIndicator(self._saved_sort_column, self._saved_sort_order)
                # Only sort the proxy model - source model stays in insertion order
                self.proxy_model.sort(self._saved_sort_column, self._saved_sort_order)

            # Re-enable sorting
            self.files_view.setSortingEnabled(True)

            self.status_label.setText("Loading cancelled.")
            self.progress_bar.hide()
            self.cancel_button.hide()
            self._current_load_worker = None

    # TODO: Re-enable these methods when dynamic priority queue is implemented
    # def _on_viewport_changed(self):
    #     """Called when the viewport scrolls or changes."""
    #     self._update_viewport_priority()
    #
    # def _create_resize_event_wrapper(self, original_resize_event):
    #     """
    #     Create a wrapper for the resize event that also updates viewport priority.
    #
    #     Args:
    #         original_resize_event: The original resizeEvent method
    #
    #     Returns:
    #         Wrapped resize event handler
    #     """
    #     def wrapped_resize_event(event):
    #         original_resize_event(event)
    #         self._update_viewport_priority()
    #
    #     return wrapped_resize_event

    def _update_viewport_priority(self):
        """
        Calculate the visible row range and send it to the worker for priority loading.

        Note: Since the proxy model can be sorted, visible VIEW rows may map to
        scattered SOURCE rows. We collect all source rows for visible view rows,
        then find the min/max range to send to the worker.
        """
        if self._current_load_worker is None:
            return

        # Get visible row range in the VIEW
        viewport = self.files_view.viewport()
        top_index = self.files_view.indexAt(viewport.rect().topLeft())
        bottom_index = self.files_view.indexAt(viewport.rect().bottomLeft())

        if top_index.isValid() and bottom_index.isValid():
            # Collect source row indices for all visible view rows
            view_start_row = top_index.row()
            view_end_row = bottom_index.row() + 1

            source_rows = []
            for view_row in range(view_start_row, view_end_row):
                view_index = self.proxy_model.index(view_row, 0)
                source_index = self.proxy_model.mapToSource(view_index)
                if source_index.isValid():
                    source_rows.append(source_index.row())

            if source_rows:
                # Find min and max source rows that correspond to visible view rows
                # Note: This may include some non-visible rows if the sort is scrambled,
                # but it ensures we cover all visible rows
                start_row = min(source_rows)
                end_row = max(source_rows) + 1

                # Add buffer rows for smoother scrolling
                buffer = 50
                start_row = max(0, start_row - buffer)
                end_row = min(self.file_model.rowCount(), end_row + buffer)

                # Send priority range to worker
                self._current_load_worker.set_priority_range(start_row, end_row)
            else:
                # Fallback to default range
                self._current_load_worker.set_priority_range(0, 100)
        else:
            # No valid indices, set default range
            self._current_load_worker.set_priority_range(0, 100)

    def on_header_context_menu(self, pos):
        self.column_menu.exec_(self.files_view.header().mapToGlobal(pos))

    def on_files_view_customContextMenuRequested(self, pos):
        menu = QMenu()
        menu.addAction(self.action_play_file)
        menu.addAction(self.action_properties)
        menu.addAction(self.action_open_in_file_browser)
        menu.addSeparator()

        # Add Analyze submenu
        analyze_menu = self._build_analyze_menu()
        menu.addMenu(analyze_menu)

        menu.exec_(self.files_view.mapToGlobal(pos))

    def toggle_column(self, index, checked):
        self.files_view.setColumnHidden(index, not checked)
        # The main settings are now saved directly from the header in _save_column_settings.
        # However, we still need to update the is_visible flag for the context menu to work correctly.
        col_settings = self._get_column_settings_by_logical_index(index)
        if col_settings:
            col_settings.is_visible = checked

    def setup_columns_in_view_menu(self, view_menu):
        self.column_menu.clear()
        for i in range(self.file_model.columnCount()):
            action = QAction(self.file_model.headerData(i, Qt.Horizontal), self)
            action.setCheckable(True)
            action.setChecked(not self.files_view.isColumnHidden(i))
            action.setData(i)
            action.toggled.connect(lambda checked, index=i: self.toggle_column(index, checked))
            self.column_menu.addAction(action)
        view_menu.clear()
        view_menu.addMenu(self.column_menu)
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

    def create_file_menu_actions(self):
        """Creates actions for the File menu."""
        self.action_autosave = QAction("Autosave", self)
        self.action_autosave.setCheckable(True)
        self.action_autosave.setChecked(self.edit_manager.autosave) # Initial state from EditManager
        self.action_autosave.toggled.connect(self.edit_manager.set_autosave)

        self.action_save = QAction("Save Changes", self)
        self.action_save.setEnabled(not self.edit_manager.autosave) # Enabled if autosave is off
        self.action_save.triggered.connect(lambda: self.edit_manager.commit_changes(autosave_override=True))

        self.action_reset = QAction("Reset Changes", self)
        self.action_reset.setEnabled(not self.edit_manager.autosave) # Enabled if autosave is off
        self.action_reset.triggered.connect(self.edit_manager.reset_changes)

        self.action_properties = QAction("Properties...", self)
        self.action_properties.setEnabled(False)
        self.action_properties.triggered.connect(self.open_properties_window)

        # Playback actions
        self.action_play_file = QAction("Play this file", self)
        self.action_play_file.setEnabled(False)
        self.action_play_file.triggered.connect(self.on_play_file_requested)

        self.action_show_playback_panel = QAction("Show Playback Panel", self)
        self.action_show_playback_panel.setCheckable(True)
        self.action_show_playback_panel.setChecked(self.playback_panel.isVisible())
        self.action_show_playback_panel.triggered.connect(self.on_show_playback_panel_requested)

        # File browser action
        self.action_open_in_file_browser = QAction("Open in File Browser", self)
        self.action_open_in_file_browser.setEnabled(False)
        self.action_open_in_file_browser.triggered.connect(self.on_open_in_file_browser)

    def _create_menus(self):
        # File Menu
        file_menu = self.menuBar().addMenu("&File")

        file_menu.addAction(self.action_autosave)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_reset)
        file_menu.addSeparator()

        # Add Analyze submenu
        analyze_menu = self._build_analyze_menu()
        file_menu.addMenu(analyze_menu)
        file_menu.addSeparator()

        file_menu.addAction(self.action_properties)
        file_menu.addAction(self.action_play_file)
        file_menu.addAction(self.action_open_in_file_browser)
        file_menu.addSeparator()

        # Preferences action
        preferences_action = QAction("Preferences", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self._show_preferences)
        file_menu.addAction(preferences_action)
        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View Menu
        self.view_menu = self.menuBar().addMenu("&View")
        self.setup_columns_in_view_menu(self.view_menu)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.action_show_playback_panel)

        # Favorites Menu - shared between menu bar and toolbar
        self.favorites_menu = self._create_favorites_menu()
        self.menuBar().addMenu(self.favorites_menu)
        self.favorites_button.setMenu(self.favorites_menu)
        # Refresh menu dynamically when shown
        self.favorites_menu.aboutToShow.connect(lambda: self._refresh_favorites_menu(self.favorites_menu))

        # Debug Menu (only shown if debug mode is enabled)
        if is_debug_mode():
            debug_menu = self.menuBar().addMenu("&Debug")
            self._create_debug_menu(debug_menu)

        # Help Menu
        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _create_debug_menu(self, debug_menu: QMenu):
        """
        Create the Debug menu with audio format adaptation settings.

        Args:
            debug_menu: The QMenu to populate with debug actions
        """
        # Enable/disable format adaptation
        self.debug_enable_adaptation = QAction("Enable Playback Format Adaptation", self)
        self.debug_enable_adaptation.setCheckable(True)
        self.debug_enable_adaptation.setChecked(
            settings.value(SETTINGS_DEBUG_PLAYBACK_ADAPTATION, False, type=bool)
        )
        self.debug_enable_adaptation.toggled.connect(self._on_debug_adaptation_toggled)
        debug_menu.addAction(self.debug_enable_adaptation)
        debug_menu.addSeparator()

        # Sample Rate submenu
        sample_rate_menu = QMenu("Sample Rate", self)
        self.debug_sample_rate_group = QActionGroup(self)
        self.debug_sample_rate_group.setExclusive(True)

        sample_rates = [
            ("Native (no conversion)", 0),
            ("22050 Hz", 22050),
            ("44100 Hz", 44100),
            ("48000 Hz", 48000),
            ("96000 Hz", 96000),
        ]

        current_sample_rate = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE, 0, type=int)
        for label, value in sample_rates:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            if value == current_sample_rate:
                action.setChecked(True)
            action.triggered.connect(lambda checked, v=value: self._on_debug_sample_rate_changed(v))
            self.debug_sample_rate_group.addAction(action)
            sample_rate_menu.addAction(action)

        debug_menu.addMenu(sample_rate_menu)
        self.debug_sample_rate_menu = sample_rate_menu

        # Channels submenu
        channels_menu = QMenu("Channels", self)
        self.debug_channels_group = QActionGroup(self)
        self.debug_channels_group.setExclusive(True)

        channels_options = [
            ("Native (no conversion)", 0),
            ("Mono (1 channel)", 1),
            ("Stereo (2 channels)", 2),
        ]

        current_channels = settings.value(SETTINGS_DEBUG_PLAYBACK_CHANNELS, 0, type=int)
        for label, value in channels_options:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            if value == current_channels:
                action.setChecked(True)
            action.triggered.connect(lambda checked, v=value: self._on_debug_channels_changed(v))
            self.debug_channels_group.addAction(action)
            channels_menu.addAction(action)

        debug_menu.addMenu(channels_menu)
        self.debug_channels_menu = channels_menu

        # Bit Depth submenu
        bit_depth_menu = QMenu("Bit Depth", self)
        self.debug_bit_depth_group = QActionGroup(self)
        self.debug_bit_depth_group.setExclusive(True)

        bit_depth_options = [
            ("Native (no conversion)", 0),
            ("16-bit (2 bytes)", 2),
            ("24-bit (3 bytes)", 3),
            ("32-bit (4 bytes)", 4),
        ]

        current_bit_depth = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH, 0, type=int)
        for label, value in bit_depth_options:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            if value == current_bit_depth:
                action.setChecked(True)
            action.triggered.connect(lambda checked, v=value: self._on_debug_bit_depth_changed(v))
            self.debug_bit_depth_group.addAction(action)
            bit_depth_menu.addAction(action)

        debug_menu.addMenu(bit_depth_menu)
        self.debug_bit_depth_menu = bit_depth_menu

        # Sample Format submenu
        sample_format_menu = QMenu("Sample Format", self)
        self.debug_sample_format_group = QActionGroup(self)
        self.debug_sample_format_group.setExclusive(True)

        sample_format_options = [
            ("Native (no conversion)", ""),
            ("Integer", "int"),
            ("Float", "float"),
        ]

        current_sample_format = settings.value(SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT, "", type=str)
        for label, value in sample_format_options:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            if value == current_sample_format:
                action.setChecked(True)
            action.triggered.connect(lambda checked, v=value: self._on_debug_sample_format_changed(v))
            self.debug_sample_format_group.addAction(action)
            sample_format_menu.addAction(action)

        debug_menu.addMenu(sample_format_menu)
        self.debug_sample_format_menu = sample_format_menu

        # Resource cache management
        debug_menu.addSeparator()
        clear_cache_action = QAction("Clear Downloaded Resource Cache", self)
        clear_cache_action.triggered.connect(self._on_clear_resource_cache)
        debug_menu.addAction(clear_cache_action)

        # Update submenu enabled state based on adaptation toggle
        self._update_debug_menu_state()

    def _on_debug_adaptation_toggled(self, enabled: bool):
        """Handle toggling of format adaptation."""
        settings.setValue(SETTINGS_DEBUG_PLAYBACK_ADAPTATION, enabled)
        self._update_debug_menu_state()
        log.info(f"Playback format adaptation {'enabled' if enabled else 'disabled'}")

    def _on_debug_sample_rate_changed(self, value: int):
        """Handle sample rate selection."""
        settings.setValue(SETTINGS_DEBUG_PLAYBACK_SAMPLE_RATE, value)
        log.info(f"Debug playback sample rate set to: {value if value else 'Native'}")

    def _on_debug_channels_changed(self, value: int):
        """Handle channels selection."""
        settings.setValue(SETTINGS_DEBUG_PLAYBACK_CHANNELS, value)
        log.info(f"Debug playback channels set to: {value if value else 'Native'}")

    def _on_debug_bit_depth_changed(self, value: int):
        """Handle bit depth selection."""
        settings.setValue(SETTINGS_DEBUG_PLAYBACK_SAMPLE_WIDTH, value)
        log.info(f"Debug playback bit depth set to: {value if value else 'Native'} bytes")

    def _on_debug_sample_format_changed(self, value: str):
        """Handle sample format selection."""
        settings.setValue(SETTINGS_DEBUG_PLAYBACK_SAMPLE_FORMAT, value)
        log.info(f"Debug playback sample format set to: {value if value else 'Native'}")

    def _on_clear_resource_cache(self):
        """Handle clearing the downloaded resource cache."""
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Clear Resource Cache",
            "This will delete all downloaded resources (models, data files, etc.).\n\n"
            "Resources will be re-downloaded when needed.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                resource_manager = get_resource_manager()
                cache_root = resource_manager.get_cache_root()

                # Get cached resources before clearing
                cached_resources = resource_manager.get_cached_resources()
                num_resources = len(cached_resources)

                # Clear the cache
                resource_manager.clear_cache()

                # Show success message
                QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Successfully cleared resource cache.\n\n"
                    f"Removed {num_resources} cached resource(s) from:\n{cache_root}"
                )

                log.info(f"Resource cache cleared: {num_resources} resources removed from {cache_root}")

            except Exception as e:
                log.error(f"Error clearing resource cache: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear resource cache:\n\n{str(e)}"
                )

    def _update_debug_menu_state(self):
        """Enable or disable debug submenus based on adaptation toggle."""
        enabled = self.debug_enable_adaptation.isChecked()
        self.debug_sample_rate_menu.setEnabled(enabled)
        self.debug_channels_menu.setEnabled(enabled)
        self.debug_bit_depth_menu.setEnabled(enabled)
        self.debug_sample_format_menu.setEnabled(enabled)

    def _show_about_dialog(self):
        about_window = windows.AboutWindow(self)
        about_window.exec()

    def _build_analyze_menu(self):
        """
        Build the Analyze submenu with categories.

        Returns:
            QMenu with analyzer categories
        """
        analyze_menu = QMenu("&Analyze", self)

        # Get all analyzer categories
        categories = get_all_categories(ProviderType.ANALYZER)

        if not categories:
            # No analyzers available
            no_analyzers_action = QAction("No analyzers available", self)
            no_analyzers_action.setEnabled(False)
            analyze_menu.addAction(no_analyzers_action)
        else:
            # Create menu item for each category
            for category in categories:
                # Capitalize category name for display
                display_name = category.value
                action = QAction(display_name, self)
                action.setData(category)
                action.triggered.connect(lambda checked, cat=category: self._on_analyze_category_selected(cat))
                analyze_menu.addAction(action)

        return analyze_menu

    def _on_analyze_category_selected(self, category: str):
        """
        Handle analyzer category selection from menu.

        Args:
            category: The selected analyzer category (e.g., 'bpm', 'key')
        """
        # Get selected media files
        selected_indexes = self.files_view.selectionModel().selectedRows()
        if not selected_indexes:
            log.debug("No files selected for analysis")
            return

        media_files = []
        for index in selected_indexes:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.file_model.get_data_for_row(row=source_index.row())
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path and row_data.get(KEY_IS_MEDIA):
                media_files.append(MediaFile(file_path, enable_write=True))

        if not media_files:
            log.debug("No valid media files selected for analysis")
            return

        log.info(f"Starting {category} analysis for {len(media_files)} files")

        # Show setup dialog
        setup_dialog = AnalyzerSetupDialog(category, media_files, self)
        if setup_dialog.exec() != QDialog.DialogCode.Accepted:
            log.debug("Analysis cancelled by user in setup dialog")
            return

        # Get selected analyzer and options
        analyzer_class = setup_dialog.get_analyzer_class()
        options = setup_dialog.get_options()

        if not analyzer_class:
            log.error("No analyzer class selected")
            return

        # Enqueue tasks to dispatcher
        dispatcher = AnalyzerDispatcher()
        dispatcher.reset()  # Clear any previous state
        dispatcher.enqueue(analyzer_class, media_files, options)

        # Show progress dialog
        progress_dialog = AnalyzerProgressDialog(self)

        # Start analysis
        dispatcher.start()

        # Show progress dialog (modal)
        result = progress_dialog.exec()

        # Show summary dialog after completion
        if result == QDialog.DialogCode.Accepted:
            summary_dialog = AnalyzerSummaryDialog(self)
            summary_dialog.select_files_requested.connect(self._on_select_analyzer_files)
            summary_dialog.exec()

            # Refresh the file list to show updated metadata
            # Get the file IDs that were analyzed
            file_ids = [mf.file_id for mf in media_files]

            # Clear any staged changes for these files (analyzer results are authoritative)
            self.edit_manager.clear_staged_changes_for_files(file_ids)

            # Force-replace MediaFile instances to ensure fresh data is used
            self.edit_manager.register_media_files(media_files, force_replace=True)

            # Refresh the display
            self.file_model.refresh_files(file_ids, self.edit_manager)

    @Slot(list)
    def _on_select_analyzer_files(self, file_paths: list):
        """
        Select files in the file list view.

        Args:
            file_paths: List of file paths to select
        """
        # Clear current selection
        self.files_view.clearSelection()

        # Select files matching the paths
        for row in range(self.file_model.rowCount()):
            row_data = self.file_model.get_data_for_row(row=row)
            if row_data.get(KEY_FILE_PATH) in file_paths:
                # Map source index to proxy index and select
                source_index = self.file_model.index(row, 0)
                proxy_index = self.proxy_model.mapFromSource(source_index)
                self.files_view.selectionModel().select(
                    proxy_index,
                    self.files_view.selectionModel().SelectionFlag.Select |
                    self.files_view.selectionModel().SelectionFlag.Rows
                )

        log.info(f"Selected {len(file_paths)} files for retry")

    def _create_favorites_menu(self) -> QMenu:
        """
        Create and populate the Favorites menu.

        Returns:
            QMenu with favorites locations and management actions
        """
        menu = QMenu("&Favorites", self)
        self._populate_favorites_menu(menu)
        return menu

    def _populate_favorites_menu(self, menu: QMenu):
        """
        Populate a menu with favorites content.

        Args:
            menu: The menu to populate
        """
        # Load favorites from settings
        favorites = self._load_favorites()

        # Sort favorites alphabetically by path
        sorted_favorites = sorted(favorites, key=lambda f: f.path)

        # Add favorite locations
        if sorted_favorites:
            for favorite in sorted_favorites:
                action = QAction(favorite.path, self)
                action.triggered.connect(lambda checked, path=favorite.path: self.set_path(path))
                menu.addAction(action)
            menu.addSeparator()

        # Add "Add Favorite..." action
        add_action = QAction("Add Favorite", self)
        add_action.triggered.connect(self._on_add_favorite)
        # Disable if current path is already in favorites
        current_path_is_favorite = any(f.path == self._current_path for f in favorites)
        add_action.setEnabled(not current_path_is_favorite)
        menu.addAction(add_action)

        # Add "Remove Favorite" submenu
        if sorted_favorites:
            remove_menu = QMenu("Remove Favorite", self)
            for favorite in sorted_favorites:
                action = QAction(favorite.path, self)
                action.triggered.connect(lambda checked, path=favorite.path: self._on_remove_favorite(path))
                remove_menu.addAction(action)
            menu.addAction(remove_menu.menuAction())

    def _on_add_favorite(self):
        """Add the current directory to favorites."""
        current_path = self._current_path

        if not current_path:
            QMessageBox.warning(
                self,
                "No Directory",
                "No directory is currently selected."
            )
            return

        # Load current favorites
        favorites = self._load_favorites()

        # Check if already in favorites
        if any(f.path == current_path for f in favorites):
            QMessageBox.information(
                self,
                "Already Favorited",
                f"The path '{current_path}' is already in your favorites."
            )
            return

        # Check maximum limit (25 as per design spec)
        MAX_FAVORITES = 25
        if len(favorites) >= MAX_FAVORITES:
            QMessageBox.warning(
                self,
                "Too Many Favorites",
                f"You have reached the maximum number of favorites ({MAX_FAVORITES}).\n"
                "Please remove some favorites before adding new ones."
            )
            return

        # Add to favorites
        from models.settings import Favorite
        favorites.append(Favorite(path=current_path))
        self._save_favorites(favorites)

        # Refresh menu to show the new favorite immediately
        self._refresh_favorites_menu(self.favorites_menu)

        log.info(f"Added favorite: {current_path}")

    def _on_remove_favorite(self, path: str):
        """
        Remove a favorite from the list.

        Args:
            path: The path to remove from favorites
        """
        reply = QMessageBox.question(
            self,
            "Remove Favorite",
            f"Are you sure you want to remove this favorite?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            favorites = self._load_favorites()
            favorites = [f for f in favorites if f.path != path]
            self._save_favorites(favorites)

            # Refresh menu to reflect the removal immediately
            self._refresh_favorites_menu(self.favorites_menu)

            log.info(f"Removed favorite: {path}")

    def _load_favorites(self) -> list:
        """
        Load favorites from QSettings.

        Returns:
            List of Favorite objects
        """
        from models.settings import Favorite

        settings.beginGroup(SETTINGS_GROUP_FAVORITES)
        favorites = []

        num_favorites = settings.beginReadArray(SETTINGS_ARRAY_FAVORITES_LOCATIONS)
        for i in range(num_favorites):
            settings.setArrayIndex(i)
            path = settings.value("path", type=str)
            if path:
                favorites.append(Favorite(path=path))
        settings.endArray()

        settings.endGroup()
        return favorites

    def _save_favorites(self, favorites: list):
        """
        Save favorites to QSettings.

        Args:
            favorites: List of Favorite objects to save
        """
        settings.beginGroup(SETTINGS_GROUP_FAVORITES)

        settings.beginWriteArray(SETTINGS_ARRAY_FAVORITES_LOCATIONS, len(favorites))
        for i, favorite in enumerate(favorites):
            settings.setArrayIndex(i)
            settings.setValue("path", favorite.path)
        settings.endArray()

        settings.endGroup()

    def _on_favorites_button_clicked(self):
        """Handle favorites toolbar button click by refreshing and showing the menu."""
        # Refresh the menu to reflect any changes
        self._refresh_favorites_menu(self.favorites_menu)
        self.favorites_button.showMenu()

    def _refresh_favorites_menu(self, menu: QMenu):
        """
        Refresh the favorites menu to reflect current state.

        Args:
            menu: The menu to refresh
        """
        menu.clear()
        self._populate_favorites_menu(menu)

    def open_properties_window(self):
        selected_indexes = self.files_view.selectionModel().selectedRows()
        log.debug(f"selectedIndexes from selectionModel: {selected_indexes} (type: {type(selected_indexes)})")

        if not selected_indexes:
            log.debug("No selected indexes, returning.")
            return

        media_files = []
        for index in selected_indexes:
            source_index = self.proxy_model.mapToSource(index)
            row_data = self.file_model.get_data_for_row( row=source_index.row() )
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path and row_data.get(KEY_IS_MEDIA):
                media_files.append(MediaFile(file_path, enable_write=True))

        if media_files:
            self.properties_window = windows.PropertiesWindow(media_files, self.edit_manager, self)
            self.properties_window.show()

    def on_files_view_double_clicked(self, index):
        log.debug(f"on_files_view_double_clicked called with index: {index}")
        selected_indexes = self.files_view.selectionModel().selectedRows()
        log.debug(f"Double-click: selected_indexes from selectionModel: {selected_indexes} (type: {type(selected_indexes)})")
        if len(selected_indexes) > 1:
            # this may not ever get called because the UI doesnt let you double-click multiple selected files
            log.debug("Multiple files selected, calling open_properties_window.")
            self.open_properties_window()
        else:
            log.debug("Single or no file selected by double-click, PropertiesWindow will not be opened by this handler.")
        # If a single row is selected, the default in-place editing will occur.

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
        self.action_play_file.setEnabled(len(selected_rows) == 1 and is_media_file)
        self.action_open_in_file_browser.setEnabled(len(selected_rows) >= 1)
        # Save and Reset actions are enabled/disabled by on_autosave_changed
        # but they also require staged changes to be meaningful.
        # We can further refine their state here if needed, e.g., disable if no staged changes.
        # For now, they are enabled/disabled solely by the autosave state.
        # if not self.edit_manager.autosave:
        #     self.action_save.setEnabled(self.edit_manager.has_staged_changes())
        #     self.action_reset.setEnabled(self.edit_manager.has_staged_changes())

    @Slot(bool)
    def on_autosave_changed(self, enabled: bool):
        """
        Handles the autosave_changed signal from EditManager.
        Enables or disables the Save and Reset actions based on the autosave state.
        """
        self.action_save.setEnabled(not enabled)
        self.action_reset.setEnabled(not enabled)
        # Also update the checked state of the autosave action itself in case it was changed programmatically
        if self.action_autosave.isChecked() != enabled:
            self.action_autosave.setChecked(enabled)

    def on_commit_started(self):
        self.status_label.setText("Saving changes...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

    def on_commit_finished(self, saved_file_ids):
        """
        Slot called when commit is successful. Refreshes the model for the updated files.

        Args:
            saved_file_ids: List of file ids that were successfully updated
        """
        self.status_label.setText(f"Saved {len(saved_file_ids)} files.")
        self.progress_bar.hide()

        if saved_file_ids:
            self.file_model.refresh_files(saved_file_ids, self.edit_manager)

    def on_commit_failed(self, errors):
        """
        Slot called when a commit fails.
        """
        self.progress_bar.hide()
        error_message = "\n".join(errors)
        self._show_error_message("Error Committing Changes", error_message)

    def _show_error_message(self, title, message):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(title)
        msg_box.setInformativeText(message)
        msg_box.setWindowTitle("Error")
        msg_box.exec()

    def _reset_column_settings(self):
        self.file_list_settings = FileListSettings()
        self.file_model = MetadataTableModel(self.file_list_settings.columns, self.edit_manager)
        self.proxy_model.setSourceModel(self.file_model)
        self._apply_column_settings()
        self.setup_columns_in_view_menu(self.view_menu)

    def _get_column_settings_by_logical_index(self, logical_index):
        if logical_index < 0 or logical_index >= len(self._logical_column_ids):
            return None
        
        column_id = self._logical_column_ids[logical_index]
        for col in self.file_list_settings.columns:
            if col.id == column_id:
                return col
        return None

    def _load_column_settings(self):
        settings.beginGroup(SETTINGS_GROUP_FILE_LIST)
        
        # Load column settings
        num_columns = settings.beginReadArray(SETTINGS_ARRAY_FILE_LIST_COLUMNS)
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
        settings.beginGroup(SETTINGS_GROUP_FILE_LIST)
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
        settings.beginWriteArray(SETTINGS_ARRAY_FILE_LIST_COLUMNS, len(columns_to_save))
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

    @Slot(str, float)
    def on_playback_started(self, filename: str, duration: float):
        """
        Handles the playback_started signal from PlaybackWorker.
        Shows the playback panel and ensures the "Show Playback Panel" menu action is checked.
        """
        self.playback_panel.update_ui('playing', filename, duration)
        self.playback_panel.show()
        self.action_show_playback_panel.setChecked(True)

    @Slot(str, float)
    def on_playback_resumed(self, filename: str, duration: float):
        """
        Handles the playback_resumed signal from PlaybackWorker.
        """
        self.playback_panel.update_ui('playing', filename, duration)

    @Slot(str, float)
    def on_playback_paused(self, filename: str, duration: float):
        """
        Handles the playback_paused signal from PlaybackWorker.
        """
        self.playback_panel.update_ui('paused', filename, duration)

    @Slot()
    def on_playback_finished(self):
        """
        Handles the playback_finished signal from PlaybackWorker.
        Updates the playback panel to the stopped state.
        """
        self.playback_panel.update_ui('stopped')

    @Slot()
    def on_playback_stopped(self):
        """
        Handles the playback_stopped signal from PlaybackWorker.
        Updates the playback panel to the stopped state.
        """
        self.playback_panel.update_ui('stopped')

    @Slot(str)
    def on_playback_error(self, error_message: str):
        """
        Handles the error_occurred signal from PlaybackWorker.
        """
        log.error(f"Playback error: {error_message}")
        self.playback_panel.update_ui('stopped')
        self._show_error_message("Playback Error", error_message)

    @Slot()
    def on_play_file_requested(self):
        """
        Handles the play_file_requested signal from menu actions.
        Starts playback of the selected file.
        """
        selected_indexes = self.files_view.selectionModel().selectedRows()
        if len(selected_indexes) == 1:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            row_data = self.file_model.get_data_for_row(row=source_index.row())
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path and row_data.get(KEY_IS_MEDIA):
                media_file = MediaFile(file_path)
                self.playback_panel.show()
                self.start_playback_signal.emit(media_file)

    def on_open_in_file_browser(self):
        """
        Opens the system file browser with the first selected file revealed.
        When multiple files are selected, the first one is used.
        """
        selected_indexes = self.files_view.selectionModel().selectedRows()
        if len(selected_indexes) >= 1:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            row_data = self.file_model.get_data_for_row(row=source_index.row())
            file_path = row_data.get(KEY_FILE_PATH)
            if file_path:
                if not open_in_file_browser(file_path):
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Could not open file browser for:\n{file_path}"
                    )

    @Slot(bool)
    def on_show_playback_panel_requested(self, checked: bool):
        """
        Handles the show_playback_panel_requested signal from the View menu.
        Toggles the visibility of the playback panel.
        """
        self.playback_panel.setVisible(checked)
        self.action_show_playback_panel.setChecked(checked)

    def _cleanup_playback(self):
        """
        Clean up playback resources before closing.
        Stops playback, disconnects signals, and terminates the thread.
        """
        log.debug("Cleaning up playback resources")

        # Stop any active playback
        if self.playback_worker.state != "stopped":
            self.playback_worker.stop()

        # Disconnect signals to prevent callbacks to destroyed objects
        try:
            self.playback_worker.position_changed.disconnect(self.playback_panel.update_playback_position)
        except RuntimeError:
            pass  # Signal was not connected

        # Stop the thread
        if self.playback_thread.isRunning():
            self.playback_thread.quit()
            if not self.playback_thread.wait(2000):  # Wait up to 2 seconds
                log.warning("Playback thread did not terminate gracefully, forcing termination")
                self.playback_thread.terminate()
                self.playback_thread.wait()

        log.debug("Playback cleanup complete")

    def _show_preferences(self):
        """Show the preferences window."""
        from windows.preferences_window import PreferencesWindow
        from PySide6.QtWidgets import QApplication, QStyleFactory

        dialog = PreferencesWindow(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply preference changes
            self._apply_preference_changes()

    def _apply_preference_changes(self):
        """Apply preference changes that take effect immediately."""
        # Apply UI skin
        from PySide6.QtWidgets import QApplication, QStyleFactory
        ui_skin = settings.value(SETTINGS_UI_SKIN, "")

        if ui_skin:
            # User selected a specific style
            style = QStyleFactory.create(ui_skin)
            if style:
                QApplication.setStyle(style)
        else:
            # User selected "System Default" - reset to platform default
            # Get the platform's default style name
            platform_style = QApplication.style().objectName()
            # On Windows this is typically "windows11" or "windowsvista"
            # We need to get the actual system default, not the current style
            # The best approach is to use the platform-appropriate default
            import sys
            if sys.platform == "win32":
                default_style = "windowsvista"  # Windows default
            elif sys.platform == "darwin":
                default_style = "macos"  # macOS default
            else:
                default_style = "fusion"  # Linux/other default

            style = QStyleFactory.create(default_style)
            if style:
                QApplication.setStyle(style)