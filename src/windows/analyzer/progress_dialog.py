"""
Analyzer Progress Dialog.

This dialog shows real-time progress during analysis operations, including
the current file being analyzed and overall progress.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox, QListWidget
)
from PySide6.QtCore import Qt, Slot
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

    def __init__(self, parent=None):
        """
        Initialize the progress dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Analyzing Files")
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.dispatcher = AnalyzerDispatcher()
        self._is_cancelled = False
        self._completed_count = 0
        self._total_count = 0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()

        # Analyzer name
        self.analyzer_label = QLabel("Analyzer: ")
        self.analyzer_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(self.analyzer_label)

        layout.addSpacing(10)

        # Active files list
        active_files_title = QLabel("Processing files:")
        layout.addWidget(active_files_title)

        self.active_files_list = QListWidget()
        self.active_files_list.setMaximumHeight(200)
        self.active_files_list.setStyleSheet("QListWidget { color: #666; }")
        layout.addWidget(self.active_files_list)

        layout.addSpacing(10)

        # Progress bar
        self.progress_label = QLabel("Progress:")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress text (e.g., "42/100")
        self.progress_text_label = QLabel("0/0")
        self.progress_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_text_label)

        layout.addStretch()

        # Cancel button
        self.cancel_button = QPushButton("Cancel Analysis")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def _connect_signals(self):
        """Connect to dispatcher signals."""
        self.dispatcher.task_started.connect(self._on_task_started)
        self.dispatcher.task_completed.connect(self._on_task_completed)
        self.dispatcher.progress_updated.connect(self._on_progress_updated)
        self.dispatcher.analysis_completed.connect(self._on_analysis_completed)
        self.dispatcher.active_tasks_updated.connect(self._on_active_tasks_updated)

    @Slot(str, str)
    def _on_task_started(self, file_path: str, analyzer_name: str):
        """
        Handle task started signal.

        Args:
            file_path: Path to file being analyzed
            analyzer_name: Name of analyzer being used
        """
        self.analyzer_label.setText(f"Analyzer: {analyzer_name}")
        # Active files are now handled by active_tasks_updated signal

    @Slot(list)
    def _on_active_tasks_updated(self, active_tasks: list):
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

    @Slot(str, object)
    def _on_task_completed(self, file_path: str, result):
        """
        Handle task completed signal.

        Args:
            file_path: Path to completed file
            result: AnalyzerResult object
        """
        # Progress is updated via progress_updated signal
        pass

    @Slot(int, int)
    def _on_progress_updated(self, completed: int, total: int):
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
    def _on_analysis_completed(self):
        """Handle analysis completion."""
        if not self._is_cancelled:
            # Analysis finished normally
            self.accept()

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        # Prompt user about keeping partial results
        reply = QMessageBox.question(
            self,
            "Cancel Analysis",
            "Do you want to keep the results from files already analyzed?\n\n"
            f"Progress: {self._completed_count}/{self._total_count} files completed",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Cancel:
            # User cancelled the cancellation
            return
        elif reply == QMessageBox.StandardButton.Yes:
            # Keep partial results
            log.info("User cancelled analysis, keeping partial results")
            self.dispatcher.cancel_all()
            self._is_cancelled = True
            self.accept()
        else:  # No
            # Discard all results
            log.info("User cancelled analysis, discarding all results")
            self.dispatcher.cancel_all()
            self._is_cancelled = True
            self.reject()

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Treat close button same as cancel
        if not self._is_cancelled and self.dispatcher._is_running:
            self._on_cancel_clicked()
            event.ignore()
        else:
            super().closeEvent(event)
