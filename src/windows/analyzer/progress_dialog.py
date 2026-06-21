"""
Analyzer Progress Dialog.

This dialog shows real-time progress during analysis operations, including
the current file being analyzed and overall progress.
"""

from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox, QListWidget, QHBoxLayout, QWidget
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QGuiApplication, QCloseEvent
import os

from workers.analyzer_dispatcher import AnalyzerDispatcher
from util.logging import log


class AnalyzerProgressDialog(QDialog):
    """
    Modal dialog showing real-time analysis progress.

    Displays:
    - Current analyzer name
    - Current file being analyzed
    - Progress bar (files completed / total files)
    - Cancel button with option to keep/discard partial results
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        dispatcher: Any | None = None,
        title: str = "Analyzing Files",
        cancel_button_text: str = "Cancel Analysis",
        supports_discard: bool = True,
        cancel_prompt_title: str = "Cancel Analysis",
        cancel_prompt_body: str = (
            "Do you want to keep the results from files already analyzed?"
        ),
    ) -> None:
        """
        Initialize the progress dialog.

        Args:
            parent: Parent widget
            dispatcher: Any object exposing task_started/task_completed/
                progress_updated/analysis_completed/active_tasks_updated
                signals plus cancel_all(). Defaults to AnalyzerDispatcher()
                for backward compatibility with existing analyzer call sites.
            title: Window title (e.g. "Analyzing Files" or "Renaming Files").
            cancel_button_text: Label for the cancel button.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.dispatcher = dispatcher if dispatcher is not None else AnalyzerDispatcher()
        self._cancel_button_text = cancel_button_text
        self._supports_discard = supports_discard
        self._cancel_prompt_title = cancel_prompt_title
        self._cancel_prompt_body = cancel_prompt_body
        self._is_cancelled = False
        self._completed_count = 0
        self._total_count = 0
        self._has_sized = False  # Track if we've done initial content-based sizing

        self._setup_ui()
        self._connect_signals()

        # Defer sizing until the dialog is shown
        QTimer.singleShot(0, self._initial_resize)

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout()

        # Analyzer name (at top)
        self.analyzer_label = QLabel("Analyzer: ")
        self.analyzer_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(self.analyzer_label)

        layout.addSpacing(10)

        # Active files list label
        active_files_title = QLabel("Processing files:")
        layout.addWidget(active_files_title)

        # Active files list - this should expand to fill available space
        self.active_files_list = QListWidget()
        self.active_files_list.setStyleSheet("QListWidget { color: #666; }")
        # Remove maximum height constraint to allow expansion
        layout.addWidget(self.active_files_list, stretch=1)  # stretch factor = 1

        layout.addSpacing(10)

        # Progress section (fixed at bottom)
        # Progress label
        self.progress_label = QLabel("Progress:")
        layout.addWidget(self.progress_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress text (e.g., "42/100")
        self.progress_text_label = QLabel("0/0")
        self.progress_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_text_label)

        layout.addSpacing(10)

        # Cancel button (fixed at bottom)
        self.cancel_button = QPushButton(self._cancel_button_text)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def _connect_signals(self) -> None:
        """Connect to dispatcher signals."""
        self.dispatcher.task_started.connect(self._on_task_started)
        self.dispatcher.task_completed.connect(self._on_task_completed)
        self.dispatcher.progress_updated.connect(self._on_progress_updated)
        self.dispatcher.analysis_completed.connect(self._on_analysis_completed)
        self.dispatcher.active_tasks_updated.connect(self._on_active_tasks_updated)

    @Slot(str, str)
    def _on_task_started(self, file_path: str, analyzer_name: str) -> None:
        """
        Handle task started signal.

        Args:
            file_path: Path to file being analyzed
            analyzer_name: Name of analyzer being used
        """
        self.analyzer_label.setText(f"Analyzer: {analyzer_name}")
        # Active files are now handled by active_tasks_updated signal

    def _initial_resize(self) -> None:
        """
        Perform initial window sizing based on screen size.

        Sets the dialog to a reasonable default size, with soft maximum
        based on screen dimensions.
        """
        # Get the screen geometry
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

            # Set soft maximum to 70% of screen height, 50% of screen width
            max_height = int(screen_height * 0.7)
            max_width = int(screen_width * 0.5)

            # Set reasonable defaults
            default_width = min(600, max_width)
            default_height = min(400, max_height)

            self.resize(default_width, default_height)
            self.setMaximumHeight(max_height)
            self.setMaximumWidth(max_width)

            # Center on parent or screen
            if self.parent():
                parent_geo = self.parent().geometry()
                self.move(
                    parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                    parent_geo.y() + (parent_geo.height() - self.height()) // 2
                )
            else:
                self.move(
                    screen_geometry.x() + (screen_width - self.width()) // 2,
                    screen_geometry.y() + (screen_height - self.height()) // 2
                )

    def _size_for_content(self) -> None:
        """
        Resize dialog to fit all list items on first display.

        Called once when tasks are first shown to optimally size the window.
        """
        if self._has_sized:
            return

        item_count = self.active_files_list.count()
        if item_count == 0:
            return

        # Get height of a single item
        item_height = self.active_files_list.sizeHintForRow(0)
        if item_height <= 0:
            item_height = 24  # Default fallback

        # Calculate needed height for all items
        needed_list_height = item_height * item_count

        # Add extra space for horizontal scrollbar (if present) and padding
        # QListWidget adds horizontal scrollbar if content is too wide
        # Standard scrollbar height is ~20px, add extra padding for safety
        scrollbar_and_padding = 40

        needed_list_height += scrollbar_and_padding

        # Calculate fixed elements height (everything except the list)
        fixed_height = 200  # Approximate height of fixed elements

        # Calculate ideal total height
        ideal_height = fixed_height + needed_list_height

        # Get current screen constraints
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_height = screen.availableGeometry().height()
            max_height = int(screen_height * 0.7)

            # Use ideal height but respect maximum
            new_height = min(ideal_height, max_height)

            # Only resize if we need more space
            current_height = self.height()
            if new_height > current_height:
                self.resize(self.width(), new_height)

        self._has_sized = True

    @Slot(list)
    def _on_active_tasks_updated(self, active_tasks: list) -> None:
        """
        Update the active files list.

        Args:
            active_tasks: List of (file_path, analyzer_name) tuples
        """
        self.active_files_list.clear()
        for file_path, analyzer_name in active_tasks:
            filename = os.path.basename(file_path)
            item_text = f"[{analyzer_name}] {filename}"
            self.active_files_list.addItem(item_text)

        # Size window to fit content on first update
        if not self._has_sized:
            # Defer slightly to ensure list items are rendered
            QTimer.singleShot(10, self._size_for_content)

    @Slot(str, object)
    def _on_task_completed(self, file_path: str, result: Any) -> None:
        """
        Handle task completed signal.

        Args:
            file_path: Path to completed file
            result: AnalyzerResult object
        """
        # Progress is updated via progress_updated signal
        pass

    @Slot(int, int)
    def _on_progress_updated(self, completed: int, total: int) -> None:
        """
        Handle progress update signal.

        Args:
            completed: Number of completed tasks
            total: Total number of tasks
        """
        self._completed_count = completed
        self._total_count = total

        if total > 0:
            percent = int((completed / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_text_label.setText(f"{completed}/{total}")

    @Slot()
    def _on_analysis_completed(self) -> None:
        """Handle analysis completion."""
        if not self._is_cancelled:
            # Analysis finished normally
            self.accept()

    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        progress_line = (
            f"\n\nProgress: {self._completed_count}/{self._total_count} files completed"
        )

        if self._supports_discard:
            # Analyzer flow: Yes = keep partial results, No = discard.
            reply = QMessageBox.question(
                self,
                self._cancel_prompt_title,
                self._cancel_prompt_body + progress_line,
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                log.info("User cancelled operation, keeping partial results")
                self.dispatcher.cancel_all()
                self._is_cancelled = True
                self.accept()
            else:
                log.info("User cancelled operation, discarding all results")
                self.dispatcher.cancel_all()
                self._is_cancelled = True
                self.reject()
        else:
            # Rename flow: already-applied filesystem operations can't be
            # discarded. Just confirm stop-the-queue with a plain Yes/No.
            reply = QMessageBox.question(
                self,
                self._cancel_prompt_title,
                self._cancel_prompt_body + progress_line,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                log.info("User cancelled remaining operations")
                self.dispatcher.cancel_all()
                self._is_cancelled = True
                self.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle dialog close event."""
        # Treat close button same as cancel
        if not self._is_cancelled and self.dispatcher._is_running:
            self._on_cancel_clicked()
            event.ignore()
        else:
            super().closeEvent(event)
