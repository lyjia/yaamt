"""Tests for the Resources preferences pane — specifically the
Locate... default-path priority chain (custom location > discovery_executable
> resource cache path > OS default)."""

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


@pytest.fixture
def isolated_resource_manager(tmp_path, monkeypatch):
    """A throwaway ResourceManager with a tmp cache root, returned in place
    of the global singleton for the duration of one test."""
    from util import resource_manager as rm_mod
    rm = rm_mod.ResourceManager(cache_root=tmp_path / "cache")
    monkeypatch.setattr(rm_mod, "get_resource_manager", lambda: rm)
    # Ensure callers that re-import via the resources pane see the same RM.
    from windows.preferences import resources_pane as rp_mod
    monkeypatch.setattr(rp_mod, "get_resource_manager", lambda: rm)
    return rm


def _fpcalc_metadata():
    from util.resource_manager import ResourceMetadata
    return ResourceMetadata(
        resource_id="chromaprint_fpcalc",
        url="https://acoustid.org/chromaprint",
        filename="fpcalc",
        expected_size=0,
        category="tools",
        subdirectory="chromaprint",
        download_type="browser",
        discovery_executable="fpcalc",
    )


def _keynet_metadata():
    from util.resource_manager import ResourceMetadata
    return ResourceMetadata(
        resource_id="keynet_model",
        url="https://example.com/keynet.pt",
        filename="keynet.pt",
        expected_size=100,
        category="models",
        subdirectory="keynet",
    )


def test_custom_location_wins_over_everything(
    pane, tmp_path, monkeypatch, isolated_resource_manager
):
    from windows.preferences import resources_pane as rp_mod

    metadata = _fpcalc_metadata()
    isolated_resource_manager.register_resource(metadata)

    # Stage a real custom location so set_custom_location accepts it.
    custom = tmp_path / "user_chosen" / "fpcalc"
    custom.parent.mkdir(parents=True)
    custom.write_text("")
    isolated_resource_manager.set_custom_location(metadata.resource_id, custom)

    # Set up a competing PATH hit and a competing cache file — neither
    # should be chosen because the user's custom location takes priority.
    monkeypatch.setattr(
        rp_mod.shutil, "which",
        lambda name: "/elsewhere/fpcalc" if name == "fpcalc" else None,
    )

    assert pane._suggested_locate_path(metadata) == str(custom)


def test_discovery_executable_beats_cache_path(
    pane, tmp_path, monkeypatch, isolated_resource_manager
):
    """A real installed binary (PATH hit) wins over the empty cache subdir
    so the user lands on something useful instead of an empty folder."""
    from windows.preferences import resources_pane as rp_mod

    metadata = _fpcalc_metadata()
    isolated_resource_manager.register_resource(metadata)

    fake_fpcalc = tmp_path / "bin" / "fpcalc"
    fake_fpcalc.parent.mkdir(parents=True)
    fake_fpcalc.write_text("")

    monkeypatch.setattr(
        rp_mod.shutil, "which",
        lambda name: str(fake_fpcalc) if name == "fpcalc" else None,
    )
    assert pane._suggested_locate_path(metadata) == str(fake_fpcalc)


def test_falls_through_to_resource_cache_path(
    pane, monkeypatch, isolated_resource_manager
):
    """When neither a custom location nor a PATH hit is available, the
    dialog should land on the resource's standard cache subdirectory so
    the user is in 'the folder for that resource' to begin with."""
    from windows.preferences import resources_pane as rp_mod

    metadata = _keynet_metadata()
    isolated_resource_manager.register_resource(metadata)

    monkeypatch.setattr(rp_mod.shutil, "which", lambda _name: None)

    suggested = pane._suggested_locate_path(metadata)
    expected = isolated_resource_manager.get_resource_path(metadata.resource_id)
    assert suggested == str(expected)


def test_blank_for_unregistered_resource_with_no_other_hints(
    pane, monkeypatch, isolated_resource_manager
):
    """Truly orphaned metadata (not registered, no executable, nothing on
    PATH) falls back to the platform default."""
    from windows.preferences import resources_pane as rp_mod

    monkeypatch.setattr(rp_mod.shutil, "which", lambda _name: None)
    metadata = _keynet_metadata()  # not registered with the isolated RM
    assert pane._suggested_locate_path(metadata) == ""
