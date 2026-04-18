"""Tests for the Resources preferences pane — specifically the smart
Locate... preselection added for tools that can be discovered on PATH."""

import pytest

from util.const import IN_GITHUB_RUNNER


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


@pytest.fixture
def pane(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from models import settings as settings_mod
    from windows.preferences import resources_pane as rp_mod

    isolated = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(settings_mod, "get_qsettings", lambda: isolated)
    monkeypatch.setattr(rp_mod, "get_qsettings", lambda: isolated)

    return rp_mod.ResourcesPane()


def test_suggested_path_uses_discovery_executable(pane, tmp_path, monkeypatch):
    from windows.preferences import resources_pane as rp_mod
    from util.resource_manager import ResourceMetadata

    fake_fpcalc = tmp_path / "bin" / "fpcalc"
    fake_fpcalc.parent.mkdir(parents=True)
    fake_fpcalc.write_text("")

    monkeypatch.setattr(
        rp_mod.shutil, "which",
        lambda name: str(fake_fpcalc) if name == "fpcalc" else None,
    )

    metadata = ResourceMetadata(
        resource_id="chromaprint_fpcalc",
        url="https://acoustid.org/chromaprint",
        filename="fpcalc",
        expected_size=0,
        download_type="browser",
        discovery_executable="fpcalc",
    )
    assert pane._suggested_locate_path(metadata) == str(fake_fpcalc)


def test_suggested_path_blank_when_not_on_path(pane, monkeypatch):
    from windows.preferences import resources_pane as rp_mod
    from util.resource_manager import ResourceMetadata

    monkeypatch.setattr(rp_mod.shutil, "which", lambda _name: None)
    metadata = ResourceMetadata(
        resource_id="chromaprint_fpcalc",
        url="https://acoustid.org/chromaprint",
        filename="fpcalc",
        expected_size=0,
        download_type="browser",
        discovery_executable="fpcalc",
    )
    assert pane._suggested_locate_path(metadata) == ""


def test_suggested_path_blank_without_discovery_executable(pane, monkeypatch):
    from windows.preferences import resources_pane as rp_mod
    from util.resource_manager import ResourceMetadata

    # shutil.which should not be consulted when the metadata doesn't declare
    # a discovery_executable. A ValueError trips the test if it is called.
    def _explode(_name):
        raise AssertionError("shutil.which should not be called")
    monkeypatch.setattr(rp_mod.shutil, "which", _explode)

    metadata = ResourceMetadata(
        resource_id="keynet_model",
        url="https://example.com/keynet.pt",
        filename="keynet.pt",
        expected_size=100,
    )
    assert pane._suggested_locate_path(metadata) == ""
