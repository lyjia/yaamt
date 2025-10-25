import os
import sys
import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Get the absolute path to the project root directory
project_root = Path(__file__).parent.parent

# Add the src directory to the Python path
sys.path.insert(0, str(project_root / "src"))

# Enable debug mode for all tests to ensure debug-only analyzers are available
from util.debug import set_debug_mode
set_debug_mode(True)

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])