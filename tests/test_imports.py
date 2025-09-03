"""
This module tests that all major classes can be imported without issue.
"""

import pytest

def test_imports():
    """
    Tests that all major classes can be imported without issue.
    """
    from models.media_file import MediaFile
    from models.settings import settings
    from models.qt.metadata_model import MetadataTableModel
    from providers.metadata.mutagen_provider import MutagenProvider
    # from windows.main_window import MainWindow # removed as this crashes github runner with:  ImportError: libEGL.so.1: cannot open shared object file: No such file or directory
    from workers.gui.load_files_worker import LoadFilesWorker

    assert MediaFile is not None
    assert settings is not None
    assert MetadataTableModel is not None
    assert MutagenProvider is not None
    # assert MainWindow is not None
    assert LoadFilesWorker is not None