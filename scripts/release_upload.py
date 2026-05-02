#!/usr/bin/env python3
"""
Upload build artifacts to a GitHub Release.

Used by the Woodpecker build pipelines to publish:
  - tag pushes (v<M>.<m>.<p>) -> a versioned release
  - branch pushes to master/development -> a rolling 'nightly' release

For the rolling 'nightly' tag, the existing release (if any) is deleted
and recreated so the asset list always reflects the latest build. For
versioned tags, the release is created on first upload and assets are
appended on subsequent uploads.

Stdlib-only: this script must run on Linux, Windows, and macOS agents
without an extra install step.

Usage:
    GITHUB_RELEASE_TOKEN=... \\
        python scripts/release_upload.py --repo OWNER/REPO --tag TAG FILE [FILE ...]
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_ROOT = "https://api.github.com"
UPLOAD_ROOT = "https://uploads.github.com"
NIGHTLY_TAG = "nightly"
TOKEN_ENV_VAR = "GITHUB_RELEASE_TOKEN"


def _request(method: str, url: str, token: str, *, data: bytes | None = None,
             content_type: str | None = None) -> dict | bytes | None:
    """Issue an authenticated request. Returns parsed JSON, raw bytes, or None."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "yaamt-release-upload",
    }
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            if not body:
                return None
            ctype = resp.headers.get("Content-Type", "")
            if ctype.startswith("application/json"):
                return json.loads(body)
            return body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {body}") from e


def _get_release(repo: str, tag: str, token: str) -> dict | None:
    url = f"{API_ROOT}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}"
    try:
        return _request("GET", url, token)
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return None
        raise


def _delete_release(repo: str, release_id: int, token: str) -> None:
    url = f"{API_ROOT}/repos/{repo}/releases/{release_id}"
    _request("DELETE", url, token)


def _delete_tag_ref(repo: str, tag: str, token: str) -> None:
    """Best-effort: GitHub keeps the underlying git tag after release deletion;
    we remove it so the next create_release call places the tag at HEAD."""
    url = f"{API_ROOT}/repos/{repo}/git/refs/tags/{urllib.parse.quote(tag)}"
    try:
        _request("DELETE", url, token)
    except RuntimeError as e:
        # Tag may not exist yet (first nightly run); ignore 404/422.
        if "HTTP 404" not in str(e) and "HTTP 422" not in str(e):
            raise


def _create_release(repo: str, tag: str, *, prerelease: bool, token: str) -> dict:
    url = f"{API_ROOT}/repos/{repo}/releases"
    payload = json.dumps({
        "tag_name": tag,
        "name": tag,
        "prerelease": prerelease,
        "generate_release_notes": False,
    }).encode("utf-8")
    return _request("POST", url, token, data=payload, content_type="application/json")


def _upload_asset(upload_url_template: str, path: Path, token: str) -> dict:
    # The API returns 'upload_url' as an RFC 6570 template:
    #   "...releases/123/assets{?name,label}"
    base = upload_url_template.split("{", 1)[0]
    url = f"{base}?name={urllib.parse.quote(path.name)}"
    mime, _ = mimetypes.guess_type(path.name)
    content_type = mime or "application/octet-stream"
    data = path.read_bytes()
    return _request("POST", url, token, data=data, content_type=content_type)


def _is_prerelease_tag(tag: str) -> bool:
    """Nightly is always a prerelease. Tags carrying a PEP 440 local-version
    suffix (a `+` segment) are intermediate builds, not real releases."""
    return tag == NIGHTLY_TAG or "+" in tag


def upload(repo: str, tag: str, files: list[Path], token: str) -> None:
    prerelease = _is_prerelease_tag(tag)

    if tag == NIGHTLY_TAG:
        existing = _get_release(repo, tag, token)
        if existing:
            print(f"Deleting existing nightly release id={existing['id']}")
            _delete_release(repo, existing["id"], token)
            _delete_tag_ref(repo, tag, token)
        release = _create_release(repo, tag, prerelease=True, token=token)
    else:
        release = _get_release(repo, tag, token)
        if release is None:
            print(f"Creating release for tag {tag}")
            release = _create_release(repo, tag, prerelease=prerelease, token=token)
        else:
            print(f"Reusing existing release for tag {tag} (id={release['id']})")

    upload_url = release["upload_url"]
    for path in files:
        if not path.exists():
            print(f"WARNING: {path} not found, skipping", file=sys.stderr)
            continue
        print(f"Uploading {path.name} ({path.stat().st_size} bytes)")
        _upload_asset(upload_url, path, token)

    print(f"Done. Release: {release.get('html_url', '<unknown>')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--repo", required=True, help="GitHub repo as OWNER/REPO")
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v0.3.0 or 'nightly')")
    parser.add_argument("files", nargs="+", type=Path, help="Artifact files to upload")
    args = parser.parse_args()

    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        print(f"ERROR: {TOKEN_ENV_VAR} environment variable is required", file=sys.stderr)
        return 2

    try:
        upload(args.repo, args.tag, args.files, token)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
