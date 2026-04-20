"""
Analyzer Summary Dialog.

This dialog displays the results summary after analysis completes, including
success/failure/skip counts and detailed error information.
"""


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from workers.analyzer_dispatcher import AnalyzerDispatcher
from util.logging import log


class AnalyzerSummaryDialog(QDialog):
    """
    Dialog displaying analysis results summary.

    Shows:
    - Count of successful/failed/skipped files
    - List of failed files with error messages
    - List of skipped files with reasons
    - Button to select failed/skipped files in MainWindow for retry
    """

    # Signal emitted when user wants to select failed/skipped files
    select_files_requested = Signal(list)  # List of file paths

    def __init__(
        self,
        parent=None,
        summary: dict | None = None,
        title: str = "Analysis Complete",
        success_verb: str = "analyzed",
    ):
        """
        Initialize the summary dialog.

        Args:
            parent: Parent widget
            summary: Pre-built summary dict matching
                AnalyzerDispatcher.get_summary()'s shape. If None, falls back
                to the analyzer singleton for backward compatibility.
            title: Window title (e.g. "Analysis Complete", "Rename Complete").
            success_verb: Past-tense verb used in the header label
                (e.g. "analyzed" or "renamed").
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)

        if summary is None:
            # Legacy analyzer call site - fetch summary from the singleton.
            summary = AnalyzerDispatcher().get_summary()
        self.summary = summary
        self._success_verb = success_verb

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()

        # Summary header
        total = self.summary['total']
        successful = self.summary['successful']
        failed_count = len(self.summary['failed'])
        skipped_count = len(self.summary['skipped'])

        summary_text = f"Successfully {self._success_verb}: {successful} / {total} files"
        summary_label = QLabel(summary_text)
        summary_label.setStyleSheet("QLabel { font-size: 14pt; font-weight: bold; }")
        layout.addWidget(summary_label)

        layout.addSpacing(10)

        # Failed files section
        if failed_count > 0:
            failed_group = QGroupBox(f"Failed ({failed_count})")
            failed_layout = QVBoxLayout()

            failed_text = QTextEdit()
            failed_text.setReadOnly(True)
            failed_text.setMaximumHeight(150)

            failed_lines = []
            for file_path, error in self.summary['failed']:
                failed_lines.append(f"• {file_path}")
                failed_lines.append(f"  Error: {error}")

            failed_text.setPlainText("\n".join(failed_lines))
            failed_layout.addWidget(failed_text)

            failed_group.setLayout(failed_layout)
            layout.addWidget(failed_group)

        # Skipped files section
        if skipped_count > 0:
            skipped_group = QGroupBox(f"Skipped ({skipped_count})")
            skipped_layout = QVBoxLayout()

            skipped_text = QTextEdit()
            skipped_text.setReadOnly(True)
            skipped_text.setMaximumHeight(150)

            skipped_lines = []
            for file_path, reason in self.summary['skipped']:
                skipped_lines.append(f"• {file_path}")
                skipped_lines.append(f"  Reason: {reason}")

            skipped_text.setPlainText("\n".join(skipped_lines))
            skipped_layout.addWidget(skipped_text)

            skipped_group.setLayout(skipped_layout)
            layout.addWidget(skipped_group)

        # If all successful, show a success message
        if failed_count == 0 and skipped_count == 0 and total > 0:
            success_label = QLabel(f"All files {self._success_verb} successfully!")
            success_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(success_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        # Select failed/skipped files button (only if there are failures/skips)
        if failed_count > 0 or skipped_count > 0:
            self.select_files_button = QPushButton("Select Failed/Skipped Files")
            self.select_files_button.clicked.connect(self._on_select_files_clicked)
            button_layout.addWidget(self.select_files_button)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _on_select_files_clicked(self):
        """Handle select files button click."""
        # Collect all failed and skipped file paths
        file_paths = []

        for file_path, _ in self.summary['failed']:
            file_paths.append(file_path)

        for file_path, _ in self.summary['skipped']:
            file_paths.append(file_path)

        if file_paths:
            log.info(f"Requesting selection of {len(file_paths)} failed/skipped files")
            self.select_files_requested.emit(file_paths)

        # Close the dialog
        self.accept()
