import os
import sys
import pytest
from pathlib import Path

from PySide6.QtCore import QSettings
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


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path_factory, monkeypatch):
    """
    Route every test through an isolated, INI-backed QSettings store.

    Without this, code paths that read application preferences (BPM decimal
    places, musical-key notation, analyzer range hints, playback debug knobs,
    ...) inherit whatever values the developer has configured on their real
    user-scope QSettings. That makes expected-output assertions non-
    deterministic across machines - the exact failure mode that prompted this
    fixture being written. Tests that need a specific preference value should
    receive this fixture as a parameter and call ``setValue()`` on it
    explicitly; everything else sees a fresh, empty settings store each test.

    The fixture also rebinds any module-level aliases that captured the
    original ``models.settings.settings`` or ``models.settings.get_qsettings``
    at import time (e.g. ``from models.settings import settings`` in
    ``workers.gui.playback_worker``), so those call sites also land on the
    isolated store rather than polluting the real user registry.
    """
    import models.settings as settings_mod

    original_settings = settings_mod.settings
    original_get = settings_mod.get_qsettings

    settings_path = tmp_path_factory.mktemp("qsettings") / "test.ini"
    isolated = QSettings(str(settings_path), QSettings.Format.IniFormat)

    def _isolated_factory() -> QSettings:
        return isolated

    # Primary patch: the source-of-truth module attributes.
    monkeypatch.setattr(settings_mod, "settings", isolated)
    monkeypatch.setattr(settings_mod, "get_qsettings", _isolated_factory)

    # Rebind already-imported aliases. Any module that did
    # ``from models.settings import settings`` or ``... import get_qsettings``
    # is holding a reference identity-equal to the originals captured above.
    # Walking sys.modules and rebinding by identity is safe: we only touch
    # attributes whose value IS one of the originals.
    for mod in list(sys.modules.values()):
        if mod is None or mod is settings_mod:
            continue
        mod_dict = getattr(mod, "__dict__", None)
        if mod_dict is None:
            continue
        for attr_name, current in list(mod_dict.items()):
            if current is original_settings:
                monkeypatch.setattr(mod, attr_name, isolated)
            elif current is original_get:
                monkeypatch.setattr(mod, attr_name, _isolated_factory)

    yield isolated
    isolated.clear()