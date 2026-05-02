"""
Unit tests for the installer dispatcher in build.py.

Covers:
  - the dispatcher routes to the right backend per platform
  - each backend fails loudly when its required tool is missing
  - _resolve_version_name prefers the explicit override and falls back
    to the git-derived version
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def build_module():
    """Import build.py as a module without executing main()."""
    spec = importlib.util.spec_from_file_location(
        "yaamt_build", PROJECT_ROOT / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["yaamt_build"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_config(tmp_path):
    """Minimal config-like object with the attributes the backends touch."""
    class _Cfg:
        platform = "linux"
        arch = "x64"
        project_root = PROJECT_ROOT
        output_dir = tmp_path
    return _Cfg()


class TestResolveVersionName:
    def test_override_takes_precedence(self, build_module, fake_config):
        result = build_module._resolve_version_name(fake_config, "custom-tag")
        assert result == "custom-tag"

    def test_falls_back_to_git_version(self, build_module, fake_config):
        with patch.object(build_module, "get_version_from_git", return_value="0.3.0"):
            result = build_module._resolve_version_name(fake_config, None)
        assert result == "0.3.0"


class TestRequirePyinstallerOutput:
    def test_raises_when_output_missing(self, build_module, fake_config):
        with pytest.raises(RuntimeError, match="Build output not found"):
            build_module._require_pyinstaller_output(fake_config)

    def test_returns_path_when_present(self, build_module, fake_config):
        (fake_config.output_dir / "yaamt").mkdir()
        result = build_module._require_pyinstaller_output(fake_config)
        assert result == fake_config.output_dir / "yaamt"


class TestDispatcher:
    def test_unknown_platform_raises(self, build_module, fake_config):
        fake_config.platform = "haiku"
        with pytest.raises(RuntimeError, match="No installer backend"):
            build_module._create_installer(fake_config, "0.3.0")

    def test_dispatch_routes_to_registered_backend(self, build_module, fake_config):
        called = {}

        def fake_backend(config, version):
            called["config"] = config
            called["version"] = version

        with patch.dict(build_module._INSTALLER_BACKENDS, {"linux": fake_backend}):
            build_module._create_installer(fake_config, "0.3.0")

        assert called["version"] == "0.3.0"
        assert called["config"] is fake_config

    def test_dispatch_resolves_version_when_none(self, build_module, fake_config):
        seen = {}

        def fake_backend(config, version):
            seen["version"] = version

        with patch.dict(build_module._INSTALLER_BACKENDS, {"linux": fake_backend}), \
                patch.object(build_module, "get_version_from_git", return_value="0.0.0+1.deadbee"):
            build_module._create_installer(fake_config, None)

        assert seen["version"] == "0.0.0+1.deadbee"


class TestBackendsFailLoudWhenToolMissing:
    """Each backend must raise (not silently skip) when its tool is absent.

    Silent skips would let the upload step run with no artifact and
    publish an empty release. Loud failures are the right behavior.
    """

    def test_linux_backend_raises_without_nfpm(self, build_module, fake_config):
        with patch.object(build_module.shutil, "which", return_value=None):
            with pytest.raises(RuntimeError, match="nfpm not found"):
                build_module._create_linux_installer(fake_config, "0.3.0")

    def test_macos_backend_raises_without_create_dmg(self, build_module, fake_config):
        with patch.object(build_module.shutil, "which", return_value=None):
            with pytest.raises(RuntimeError, match="create-dmg not found"):
                build_module._create_macos_installer(fake_config, "0.3.0")

    def test_windows_backend_raises_without_iscc(self, build_module, fake_config):
        with patch.object(build_module.shutil, "which", return_value=None), \
                patch.object(build_module.Path, "exists", return_value=False):
            with pytest.raises(RuntimeError, match="Inno Setup"):
                build_module._create_windows_installer(fake_config, "0.3.0")
