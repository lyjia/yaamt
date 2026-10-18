#!/usr/bin/env python3
"""
Upload build artifacts to a GitHub Release.

Used by CI to publish:
  - tag pushes (v<M>.<m>.<p>) -> a *draft* versioned release, which a
    maintainer tests and then publishes by hand (doc/RELEASING.md)
  - branch pushes to master/development -> a rolling 'nightly' release

For the rolling 'nightly' tag, the existing release (if any) is deleted
and recreated so the asset list always reflects the latest build. For
versioned tags, an existing release for the tag (draft or published) is
reused and assets are added or replaced; otherwise a draft is created.
With no FILE arguments the script only ensures the release exists, which
lets CI create the draft once before parallel platform uploads.

--checksums writes SHA256SUMS.txt (sha256sum format) to the release from
the SHA-256 digests GitHub records for every uploaded asset, so nothing
has to be downloaded or re-hashed. CI runs it once all uploads finish.

Stdlib-only: this script must run on Linux, Windows, and macOS agents
without an extra install step.

Usage:
    GITHUB_RELEASE_TOKEN=... \\
        python scripts/release_upload.py --repo OWNER/REPO --tag TAG [--checksums] [FILE ...]
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
RELEASES_PER_PAGE = 100
CHECKSUMS_FILENAME = "SHA256SUMS.txt"
DIGEST_PREFIX = "sha256:"


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


def _find_release(repo: str, tag: str, token: str) -> dict | None:
    """Find the release for a tag, including drafts.

    GET /releases/tags/<tag> never returns drafts, so page through the
    release list instead (drafts are listed to users with write access).
    """
    page = 1
    while True:
        url = f"{API_ROOT}/repos/{repo}/releases?per_page={RELEASES_PER_PAGE}&page={page}"
        releases = _request("GET", url, token) or []
        for release in releases:
            if release.get("tag_name") == tag:
                return release
        if len(releases) < RELEASES_PER_PAGE:
            return None
        page += 1


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


def _create_release(repo: str, tag: str, *, prerelease: bool, draft: bool, token: str) -> dict:
    url = f"{API_ROOT}/repos/{repo}/releases"
    payload = json.dumps({
        "tag_name": tag,
        "name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "generate_release_notes": False,
    }).encode("utf-8")
    return _request("POST", url, token, data=payload, content_type="application/json")


def _delete_existing_asset(release: dict, name: str, token: str) -> None:
    """Remove a same-named asset so a re-run replaces it instead of
    failing with HTTP 422 (GitHub rejects duplicate asset names)."""
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            print(f"Replacing existing asset {name}")
            _request("DELETE", asset["url"], token)


def _upload_bytes(upload_url_template: str, name: str, data: bytes, token: str) -> dict:
    # The API returns 'upload_url' as an RFC 6570 template:
    #   "...releases/123/assets{?name,label}"
    base = upload_url_template.split("{", 1)[0]
    url = f"{base}?name={urllib.parse.quote(name)}"
    mime, _ = mimetypes.guess_type(name)
    content_type = mime or "application/octet-stream"
    return _request("POST", url, token, data=data, content_type=content_type)


def _upload_asset(upload_url_template: str, path: Path, token: str) -> dict:
    return _upload_bytes(upload_url_template, path.name, path.read_bytes(), token)


def _checksums_text(release: dict) -> str:
    """sha256sum-format listing of the release's assets, from GitHub's digests."""
    lines = []
    for asset in sorted(release.get("assets", []), key=lambda a: a["name"]):
        if asset["name"] == CHECKSUMS_FILENAME:
            continue
        digest = asset.get("digest") or ""
        if not digest.startswith(DIGEST_PREFIX):
            raise RuntimeError(f"GitHub reported no SHA-256 digest for {asset['name']}")
        lines.append(f"{digest[len(DIGEST_PREFIX):]}  {asset['name']}")
    if not lines:
        raise RuntimeError("Release has no assets to checksum")
    return "\n".join(lines) + "\n"


def publish_checksums(repo: str, tag: str, token: str) -> None:
    release = _find_release(repo, tag, token)
    if release is None:
        raise RuntimeError(f"No release found for tag {tag}")
    text = _checksums_text(release)
    _delete_existing_asset(release, CHECKSUMS_FILENAME, token)
    print(f"Uploading {CHECKSUMS_FILENAME}:\n{text}")
    _upload_bytes(release["upload_url"], CHECKSUMS_FILENAME, text.encode("utf-8"), token)


def _is_prerelease_tag(tag: str) -> bool:
    """Nightly is always a prerelease. Tags carrying a PEP 440 local-version
    suffix (a `+` segment) are intermediate builds, not real releases."""
    return tag == NIGHTLY_TAG or "+" in tag


def upload(repo: str, tag: str, files: list[Path], token: str) -> None:
    prerelease = _is_prerelease_tag(tag)

    if tag == NIGHTLY_TAG:
        existing = _find_release(repo, tag, token)
        if existing:
            print(f"Deleting existing nightly release id={existing['id']}")
            _delete_release(repo, existing["id"], token)
            _delete_tag_ref(repo, tag, token)
        release = _create_release(repo, tag, prerelease=True, draft=False, token=token)
    else:
        release = _find_release(repo, tag, token)
        if release is None:
            # Draft: nothing is public until a maintainer has tested the
            # artifacts and clicks Publish (doc/RELEASING.md).
            print(f"Creating draft release for tag {tag}")
            release = _create_release(repo, tag, prerelease=prerelease, draft=True, token=token)
        else:
            print(f"Reusing existing release for tag {tag} (id={release['id']})")

    upload_url = release["upload_url"]
    for path in files:
        if not path.exists():
            print(f"WARNING: {path} not found, skipping", file=sys.stderr)
            continue
        _delete_existing_asset(release, path.name, token)
        print(f"Uploading {path.name} ({path.stat().st_size} bytes)")
        _upload_asset(upload_url, path, token)

    print(f"Done. Release: {release.get('html_url', '<unknown>')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--repo", required=True, help="GitHub repo as OWNER/REPO")
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v0.3.0 or 'nightly')")
    parser.add_argument("files", nargs="*", type=Path,
                        help="Artifact files to upload (none: just ensure the release exists)")
    parser.add_argument("--checksums", action="store_true",
                        help=f"Write {CHECKSUMS_FILENAME} for the release's assets (after any uploads)")
    args = parser.parse_args()

    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        print(f"ERROR: {TOKEN_ENV_VAR} environment variable is required", file=sys.stderr)
        return 2

    try:
        if args.files or not args.checksums:
            upload(args.repo, args.tag, args.files, token)
        if args.checksums:
            publish_checksums(args.repo, args.tag, token)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
