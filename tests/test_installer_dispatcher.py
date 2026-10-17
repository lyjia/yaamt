"""
Unit tests for the installer dispatcher in build.py.

Covers:
  - the dispatcher routes to the right backend per platform
  - each backend fails loudly when its required tool is missing
  - _resolve_version_name prefers the explicit override and falls back
    to the git-derived version
"""

import importlib.util
import shutil
import subprocess
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


class TestArtifactNaming:
    def test_stem_format(self, build_module):
        assert build_module._artifact_stem("0.3.0", "linux", "x64") == "yaamt-0.3.0-linux-x64"

    def test_macos_backend_requires_app_bundle(self, build_module, fake_config):
        with patch.object(build_module.shutil, "which", return_value="/usr/local/bin/create-dmg"):
            with pytest.raises(RuntimeError, match="App bundle not found"):
                build_module._create_macos_installer(fake_config, "0.3.0")


class TestArchiver:
    """Archives must unpack into one top-level folder and land in the
    build output directory next to the installers."""

    @pytest.fixture
    def archiver(self, build_module, fake_config):
        fake_config.get_build_tool = lambda: "pyinstaller"
        bundle = fake_config.output_dir / "yaamt"
        (bundle / "_internal").mkdir(parents=True)
        (bundle / "yaamt").write_text("cli")
        (bundle / "_internal" / "lib.so").write_text("lib")
        return build_module.Archiver(fake_config)

    def test_tarball_has_single_root(self, archiver, fake_config):
        import tarfile
        path = archiver.create_archive(version_name="0.3.0")
        assert path == fake_config.output_dir / "yaamt-0.3.0-linux-x64.tar.gz"
        with tarfile.open(path) as tar:
            roots = {Path(name).parts[0] for name in tar.getnames()}
            assert "yaamt-0.3.0-linux-x64/_internal/lib.so" in tar.getnames()
        assert roots == {"yaamt-0.3.0-linux-x64"}

    def test_zip_has_single_root(self, archiver, fake_config):
        import zipfile
        fake_config.platform = "windows"
        path = archiver.create_archive(version_name="0.3.0")
        assert path == fake_config.output_dir / "yaamt-0.3.0-windows-x64.zip"
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert {Path(n).parts[0] for n in names} == {"yaamt-0.3.0-windows-x64"}
        assert "yaamt-0.3.0-windows-x64/yaamt" in names


@pytest.mark.skipif(shutil.which("nfpm") is None, reason="nfpm not installed")
class TestLinuxInstallerWithNfpm:
    """Runs the real nfpm backend against a stub bundle; guards the
    placeholder rendering (nfpm does not expand env vars in `contents`)."""

    @pytest.mark.parametrize("arch, deb_arch", [("x64", "amd64"), ("arm64", "arm64")])
    def test_builds_deb_and_rpm_containing_bundle(self, build_module, fake_config, arch, deb_arch):
        fake_config.arch = arch
        bundle = fake_config.output_dir / "yaamt"
        bundle.mkdir()
        (bundle / "yaamt").write_text("#!/bin/sh\n")

        build_module._create_linux_installer(fake_config, "0.3.0")

        deb = fake_config.output_dir / f"yaamt-0.3.0-linux-{arch}.deb"
        rpm = fake_config.output_dir / f"yaamt-0.3.0-linux-{arch}.rpm"
        assert deb.is_file() and rpm.is_file()
        if shutil.which("dpkg-deb"):
            package_arch = subprocess.run(["dpkg-deb", "-f", str(deb), "Architecture"],
                                          capture_output=True, text=True, check=True).stdout.strip()
            assert package_arch == deb_arch
            listing = subprocess.run(["dpkg-deb", "-c", str(deb)], capture_output=True,
                                     text=True, check=True).stdout
            assert "./usr/lib/yaamt/yaamt" in listing
            assert "./usr/bin/yaamt -> /usr/lib/yaamt/yaamt" in listing
