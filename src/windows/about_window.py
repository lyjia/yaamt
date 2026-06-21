from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from util.const import UPDATE_CHECK_REPO
from util.version import get_version


class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About YAAMT")

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap(":/logo.png")
        logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Text
        version = get_version()
        text_label = QLabel(
            f"""
            <p>A simple tool for editing audio metadata.</p>
            <p>Version: {version}</p>
            """
        )
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Update check controls. The "Check Now" path is always available
        # (explicit user action) and bypasses both the opt-in setting and
        # the cache.
        self.update_status_label = QLabel("")
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label.setOpenExternalLinks(True)

        self.check_now_button = QPushButton("Check for updates")
        self.check_now_button.clicked.connect(self._on_check_now_clicked)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.check_now_button)
        button_row.addStretch()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(logo_label)
        layout.addWidget(text_label)
        layout.addWidget(self.update_status_label)
        layout.addLayout(button_row)
        self.setLayout(layout)

    def _on_check_now_clicked(self):
        from workers.update_checker import UpdateChecker

        self.check_now_button.setEnabled(False)
        self.update_status_label.setText("Checking...")
        checker = UpdateChecker(current_version=get_version(), use_cache=False)
        checker.signals.update_available.connect(self._on_update_available)
        checker.signals.no_update.connect(self._on_no_update)
        checker.signals.failed.connect(self._on_failed)
        QThreadPool.globalInstance().start(checker)

    @Slot(str, str)
    def _on_update_available(self, latest_version: str, html_url: str):
        url = html_url or f"https://github.com/{UPDATE_CHECK_REPO}/releases"
        self.update_status_label.setText(
            f'<p>Version {latest_version} is available. '
            f'<a href="{url}">Download</a></p>'
        )
        self.check_now_button.setEnabled(True)

    @Slot()
    def _on_no_update(self):
        self.update_status_label.setText("<p>You are on the latest release.</p>")
        self.check_now_button.setEnabled(True)

    @Slot(str)
    def _on_failed(self, error_message: str):
        self.update_status_label.setText(
            f"<p>Update check failed: {error_message}</p>"
        )
        self.check_now_button.setEnabled(True)
