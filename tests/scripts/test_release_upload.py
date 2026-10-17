"""
Unit tests for scripts/release_upload.py release-reuse logic.

Each platform uploads to the same versioned release independently, so
the script must tolerate a release created concurrently by another
platform and must replace (not duplicate) an asset on re-run. The
GitHub API is mocked at the script's single _request seam.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPO = "lyjia/yaamt"
TAG = "v0.3.0"
TOKEN = "test-token"
UPLOAD_URL = "https://uploads.github.com/repos/lyjia/yaamt/releases/1/assets{?name,label}"


@pytest.fixture(scope="module")
def upload_module():
    spec = importlib.util.spec_from_file_location(
        "yaamt_release_upload", PROJECT_ROOT / "scripts" / "release_upload.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["yaamt_release_upload"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def artifact(tmp_path):
    path = tmp_path / "yaamt-0.3.0-linux-x64.deb"
    path.write_bytes(b"deb")
    return path


def _release(assets=None):
    return {"id": 1, "upload_url": UPLOAD_URL, "html_url": "html", "assets": assets or []}


class FakeGitHub:
    """Records calls and answers GET /releases/tags/<tag> from a script."""

    def __init__(self, get_responses, create_error=None):
        self.get_responses = list(get_responses)
        self.create_error = create_error
        self.calls = []

    def __call__(self, method, url, token, *, data=None, content_type=None):
        self.calls.append((method, url))
        if method == "GET":
            response = self.get_responses.pop(0)
            if response is None:
                raise RuntimeError(f"GET {url} -> HTTP 404: Not Found")
            return response
        if method == "POST" and url.endswith("/releases"):
            if self.create_error:
                raise RuntimeError(self.create_error)
            return _release()
        return {}


def test_reuses_release_created_concurrently(upload_module, artifact):
    fake = FakeGitHub(get_responses=[None, _release()],
                      create_error="POST /releases -> HTTP 422: already_exists")
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    assert ("POST", f"{UPLOAD_URL.split('{')[0]}?name={artifact.name}") in fake.calls


def test_other_create_errors_propagate(upload_module, artifact):
    fake = FakeGitHub(get_responses=[None], create_error="POST /releases -> HTTP 500: boom")
    with patch.object(upload_module, "_request", fake):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            upload_module.upload(REPO, TAG, [artifact], TOKEN)


def test_existing_asset_is_replaced(upload_module, artifact):
    asset_url = "https://api.github.com/repos/lyjia/yaamt/releases/assets/9"
    existing = _release(assets=[{"name": artifact.name, "url": asset_url}])
    fake = FakeGitHub(get_responses=[existing])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    methods = [c for c in fake.calls if c[0] in ("DELETE", "POST")]
    assert methods[0] == ("DELETE", asset_url)
    assert methods[1][0] == "POST"
