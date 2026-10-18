"""
Unit tests for scripts/release_upload.py release lookup and creation.

Versioned tags are published as drafts that a maintainer tests and then
publishes by hand, so lookup must find draft releases (GitHub's by-tag
endpoint does not return them) and creation must produce a draft. Re-runs
must replace, not duplicate, same-named assets. The GitHub API is mocked
at the script's single _request seam.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPO = "lyjia/yaamt"
TAG = "v0.3.0"
TOKEN = "test-token"
UPLOAD_URL = "https://uploads.github.com/repos/lyjia/yaamt/releases/1/assets{?name,label}"
RELEASES_URL = "https://api.github.com/repos/lyjia/yaamt/releases"


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


def _release(tag=TAG, assets=None, draft=True):
    return {"id": 1, "tag_name": tag, "draft": draft, "upload_url": UPLOAD_URL,
            "html_url": "html", "assets": assets or []}


class FakeGitHub:
    """Records calls; serves release-list pages and accepts creates."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []
        self.created = []

    def __call__(self, method, url, token, *, data=None, content_type=None):
        self.calls.append((method, url))
        if method == "GET":
            return self.pages.pop(0) if self.pages else []
        if method == "POST" and url == RELEASES_URL:
            payload = json.loads(data)
            self.created.append(payload)
            return _release(tag=payload["tag_name"], draft=payload["draft"])
        return {}

    def uploads(self):
        return [url for method, url in self.calls if method == "POST" and url != RELEASES_URL]


def test_creates_draft_when_no_release_exists(upload_module, artifact):
    fake = FakeGitHub(pages=[[]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    assert len(fake.created) == 1
    assert fake.created[0]["draft"] is True
    assert fake.created[0]["prerelease"] is False
    assert len(fake.uploads()) == 1


def test_reuses_existing_draft(upload_module, artifact):
    fake = FakeGitHub(pages=[[_release(tag="v0.2.0"), _release()]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    assert fake.created == []
    assert len(fake.uploads()) == 1


def test_finds_release_on_later_page(upload_module, artifact):
    full_page = [_release(tag=f"v0.0.{i}") for i in range(upload_module.RELEASES_PER_PAGE)]
    fake = FakeGitHub(pages=[full_page, [_release()]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    assert fake.created == []


def test_no_files_only_ensures_release(upload_module):
    fake = FakeGitHub(pages=[[]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [], TOKEN)
    assert len(fake.created) == 1
    assert fake.uploads() == []


def test_existing_asset_is_replaced(upload_module, artifact):
    asset_url = "https://api.github.com/repos/lyjia/yaamt/releases/assets/9"
    existing = _release(assets=[{"name": artifact.name, "url": asset_url}])
    fake = FakeGitHub(pages=[[existing]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, TAG, [artifact], TOKEN)
    writes = [c for c in fake.calls if c[0] in ("DELETE", "POST")]
    assert writes[0] == ("DELETE", asset_url)
    assert writes[1][0] == "POST"


def test_nightly_is_published_prerelease(upload_module, artifact):
    fake = FakeGitHub(pages=[[]])
    with patch.object(upload_module, "_request", fake):
        upload_module.upload(REPO, upload_module.NIGHTLY_TAG, [artifact], TOKEN)
    assert fake.created[0]["draft"] is False
    assert fake.created[0]["prerelease"] is True


def _asset(name, digest="sha256:" + "ab" * 32, asset_id=1):
    return {"name": name, "digest": digest,
            "url": f"https://api.github.com/repos/lyjia/yaamt/releases/assets/{asset_id}"}


def test_checksums_listing_uses_github_digests(upload_module):
    release = _release(assets=[
        _asset("yaamt-0.3.0-windows-x64.zip", "sha256:" + "22" * 32),
        _asset("yaamt-0.3.0-linux-x64.deb", "sha256:" + "11" * 32),
        _asset(upload_module.CHECKSUMS_FILENAME),
    ])
    text = upload_module._checksums_text(release)
    assert text == (f"{'11' * 32}  yaamt-0.3.0-linux-x64.deb\n"
                    f"{'22' * 32}  yaamt-0.3.0-windows-x64.zip\n")


def test_checksums_fail_when_digest_missing(upload_module):
    release = _release(assets=[_asset("yaamt-0.3.0-linux-x64.deb", digest=None)])
    with pytest.raises(RuntimeError, match="no SHA-256 digest"):
        upload_module._checksums_text(release)


def test_publish_checksums_replaces_existing_file(upload_module):
    old_sums = _asset(upload_module.CHECKSUMS_FILENAME, asset_id=9)
    release = _release(assets=[_asset("yaamt-0.3.0-linux-x64.deb"), old_sums])
    fake = FakeGitHub(pages=[[release]])
    with patch.object(upload_module, "_request", fake):
        upload_module.publish_checksums(REPO, TAG, TOKEN)
    writes = [c for c in fake.calls if c[0] in ("DELETE", "POST")]
    assert writes[0] == ("DELETE", old_sums["url"])
    assert writes[1][1].endswith(f"?name={upload_module.CHECKSUMS_FILENAME}")
