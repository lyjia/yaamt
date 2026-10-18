# Releasing YAAMT: A Maintainer's How-To

This is the practical playbook for versioning and publishing YAAMT.
"Publishing" here means: build executables/installers for each supported
platform and host the files on GitHub Releases. Code signing,
notarization, and marketplace listings are out of scope (deferred; see
the epic).

Design background lives in `doc/designs/versioning.md`,
`doc/designs/ci.md`, and `doc/designs/installers.md`. This document is
the *workflow* view: what to actually do in each scenario.

---

## How Versions Work (30-second recap)

- The version is derived from git tags shaped `v<major>.<minor>.<patch>`.
  You bump the version **by tagging** - there is no file to edit.
- A build on the tag reports `0.3.0`. A build 5 commits past it reports
  `0.3.0+5.<hash>`. A dirty tree appends `.dirty`.
- **Rule of thumb: a `+` in the version means "not a release".**
  The upload script uses the same rule to mark GitHub prereleases.

---

## Scenario 1: Cutting a Normal Release

Use this when `master` (or `development`, pre-1.0) is in a state you
want to ship.

1. **Pre-flight.** Confirm CI is green on the commit you intend to ship.
   Optionally dry-run packaging first: GitHub -> Actions -> Release ->
   Run workflow, with the branch name as `ref` (builds and smoke-tests
   all platforms without publishing).
2. **Tag the commit.** Pick the next version per semver-ish judgment
   (new features -> bump minor; fixes only -> bump patch):

   ```bash
   git checkout master
   git pull origin master
   git tag v0.3.0
   git push origin v0.3.0
   ```

3. **CI takes over.** The tag push triggers the GitHub Actions
   `Release` workflow (`.github/workflows/release.yml`). It creates a
   **draft** GitHub Release for the tag, builds on Linux (x64 and
   arm64), Windows, and macOS, smoke-tests each bundle and installed
   package, and uploads the artifacts to the draft via
   `scripts/release_upload.py`. If one platform fails, fix it and
   re-run that job (or dispatch the workflow with the tag); re-uploads
   replace same-named assets.

   A draft is visible only to repo collaborators, and the in-app update
   check ignores it (GitHub's `releases/latest` skips drafts), so
   nothing is public yet.
4. **Test the real binaries.** Open the draft (Releases page, marked
   "Draft"), check that all expected assets are present and carry the
   bare version (no `+`):
   - `yaamt-0.3.0-windows-x64.zip`, `yaamt-0.3.0-windows-x64-setup.exe`
   - `yaamt-0.3.0-linux-x64.tar.gz`, `.deb`, `.rpm` (and the same for `linux-arm64`)
   - `yaamt-0.3.0-macos-arm64.dmg`
   - `SHA256SUMS.txt` (written last, from GitHub's digests of the files above)

   Install them on your own machines. Confirm `yaamt --version` and the
   About window show the tag's version, and exercise whatever the
   release changed. These are the exact files users will get.

   If something is broken: delete the draft and the tag (Scenario 5),
   fix, and re-tag the same version. Nobody outside has downloaded it,
   so re-using the version number is safe at this stage.
5. **Write the release notes and publish.** Edit the draft, summarize
   the changes, and paste in the install instructions from the
   [Release Notes Template](#release-notes-template) below (replace
   `<version>`). Leave "Set as a pre-release" unticked (pre-releases are
   invisible to the update checker), and click **Publish release**.
   After publishing, About -> "Check for updates" on an older build
   reports the new version.

That's it. No branch ceremony is required for a normal release.

---

## Scenario 2: Testing Builds Before Tagging

There are no automatic nightly builds. To check that packaging still
works on an untagged commit, run the `Release` workflow by hand
(GitHub -> Actions -> Release -> Run workflow) with a branch name as
`ref`: it builds and smoke-tests every platform but publishes nothing,
and the binaries are discarded when the run ends.

To test the *exact* binaries users will get, use the draft from
Scenario 1 instead.

---

## Scenario 3: Hotfix to a Shipped Release

Use this when `master` has moved on with unreleased work but a shipped
version needs an urgent fix.

1. Branch from the release tag:

   ```bash
   git checkout -b hotfix/0.3.1 v0.3.0
   ```

2. Apply the fix (cherry-pick from `master`/`development` if it's
   already fixed there), run `pytest`, and commit.
3. Tag the hotfix branch tip and push both:

   ```bash
   git tag v0.3.1
   git push origin hotfix/0.3.1 v0.3.1
   ```

4. CI builds and publishes `v0.3.1` exactly as in Scenario 1.
5. Merge the hotfix branch back to `master`/`development` so the fix is
   not lost, then delete the branch.

If `master` has *not* moved on, skip the branch: just commit the fix to
`master`, tag, and push (Scenario 1 with a patch bump).

---

## Scenario 4: Manual / Offline Publishing

Use this when GitHub Actions is unavailable or a platform's job cannot
build there, and you need that platform's artifact anyway.

The shape is identical on every platform: create the tag once, then on
each build machine check that tag out, build, and upload. The exact
per-platform sequences follow. They use `v0.1.0` as the example tag -
substitute the version you are shipping.

### Step 0: Create and push the tag (once)

Do this a single time, from any clone. Every build machine then fetches
the same tag, so all artifacts stamp the identical version.

```bash
git checkout master            # or development, pre-1.0
git pull
git tag v0.1.0
git push origin v0.1.0
```

### Prerequisites per platform

| Platform | Build host must have                                                              |
|----------|----------------------------------------------------------------------------------|
| Windows  | Python 3.12, Git, Inno Setup 6 (`iscc` on PATH)                                   |
| macOS    | Python 3.12, Xcode Command Line Tools, Homebrew                                   |
| Linux    | Python 3.12, Git, apt (Debian/Ubuntu)                                             |

`python build.py --install-deps` installs the installer tool for each
platform (Inno Setup via choco, `create-dmg` via brew, a pinned `nfpm`).

### Windows (PowerShell) -> `*-setup.exe`

```powershell
git fetch --tags
git checkout v0.1.0
cd src; python -m util.version; cd ..   # expect bare "0.1.0" (no '+' or '.dirty')
python build.py --install-deps          # first time on this machine only
python build.py --release --archive --installer
# Artifacts land at: build\release-<timestamp>\yaamt-0.1.0-windows-x64{.zip,-setup.exe}
```

### macOS (bash) -> `.dmg`

```bash
git fetch --tags
git checkout v0.1.0
(cd src && python3 -m util.version)     # expect bare "0.1.0" (no '+' or '.dirty')
python3 build.py --install-deps         # first time on this machine only
python3 build.py --release --installer
# Installer lands at: build/release-<timestamp>/yaamt-0.1.0-macos-<arch>.dmg
```

### Linux (bash) -> `.deb` + `.rpm`

```bash
git fetch --tags
git checkout v0.1.0
(cd src && python -m util.version)      # expect bare "0.1.0" (no '+' or '.dirty')
python build.py --install-deps          # first time on this machine only
python build.py --release --archive --installer
# Packages land at: build/release-<timestamp>/yaamt-0.1.0-linux-x64.{tar.gz,deb,rpm}
```

### Uploading the artifacts

From each build host, choose one:

- **By hand (recommended for a release candidate):** in the GitHub UI,
  create the release for the tag *first* and tick "Set as a pre-release"
  (or save it as a draft), then drag each platform's artifact onto it.
  Promote it to a full release once you have validated the build. This
  is the supported way to get release-candidate behavior, since the
  version scheme has no `-rcN` tag form.
- **By script** (same path CI uses; needs a GitHub token with
  `contents: write` on the repo):

  ```bash
  # bash (macOS / Linux)
  export GITHUB_RELEASE_TOKEN=<token>
  python scripts/release_upload.py --repo lyjia/yaamt --tag v0.1.0 build/release-*/*.dmg
  ```

  ```powershell
  # PowerShell (Windows)
  $env:GITHUB_RELEASE_TOKEN = "<token>"
  python scripts/release_upload.py --repo lyjia/yaamt --tag v0.1.0 (Get-ChildItem build\release-*\*-setup.exe).FullName
  ```

After uploading, run the script once more with `--checksums` (and no
files) to write `SHA256SUMS.txt`. The upload script creates a draft
release if none exists yet for the tag, and otherwise reuses the existing one (draft or published), so the
fully-manual flow (no CI at all) is: build on each platform, upload from
each, then test and publish the draft as in Scenario 1. If you
pre-created the release in the UI, the script reuses it and keeps your
settings (see `scripts/release_upload.py`).

Checking out the tag matters: building from a later commit would stamp
`0.1.0+N.<hash>` into the binary, and the artifact would advertise
itself as a non-release build. The `python -m util.version` check in
each sequence above catches this before you spend time on a build.

---

## Scenario 5: Recovering from a Botched Release

Tagged the wrong commit, or the artifacts are broken:

1. Delete the GitHub Release (GitHub UI -> release -> delete).
2. Delete the tag locally and remotely:

   ```bash
   git tag -d v0.3.0
   git push origin :refs/tags/v0.3.0
   ```

3. Fix whatever was wrong, then redo Scenario 1.

Caveat: if users may have already downloaded the bad artifacts, prefer
shipping a `v0.3.1` hotfix over silently re-tagging `v0.3.0` - the
update checker can announce a new version, but it cannot tell anyone a
version they already installed was re-issued.

---

## Scenario 6: Verifying What a Build Will Report

Before tagging or shipping, you can always check what version string a
checkout would produce:

```bash
cd src && python -m util.version
```

- Bare `M.m.p` -> you are exactly on a release tag with a clean tree.
- `+N.<hash>` -> N commits past the last tag.
- `.dirty` -> uncommitted changes present; commit or stash before
  building anything you intend to publish.

---

## Release Notes Template

Paste this below the change summary in each release's notes and
replace `<version>` (e.g. `0.3.0`). It covers the first-launch
warnings caused by the builds not being code-signed yet, and how to
verify downloads against `SHA256SUMS.txt`.

````markdown
## Installing

YAAMT is not yet code-signed with a paid Microsoft or Apple certificate, so Windows and macOS will warn the first time you run it. You only need to get past this once per download.

### Windows

**Installer (`yaamt-<version>-windows-x64-setup.exe`)**

1. Your browser may say the file "isn't commonly downloaded". Choose **Keep** (in Edge: **…** → **Keep** → **Show more** → **Keep anyway**).
2. Run the installer. If you see **"Windows protected your PC"**, click **More info**, then **Run anyway**.

**Portable zip (`yaamt-<version>-windows-x64.zip`)**

1. Before extracting, right-click the zip, choose **Properties**, tick **Unblock** at the bottom of the General tab, and click **OK**. Otherwise Windows warns about every program inside.
2. Extract it and run `yaamt-gui.exe`. The command-line tool is `yaamt.exe`.

If **Smart App Control** is turned on (Windows 11), unsigned apps are blocked with no "Run anyway" option. It is under Windows Security → App & browser control → Smart App Control. Turning it off cannot be undone without reinstalling Windows.

### macOS (Apple Silicon)

1. Open `yaamt-<version>-macos-arm64.dmg` and drag **YAAMT** into **Applications**.
2. Open YAAMT from Applications. macOS will say it cannot verify the developer; click **Done** (or **Cancel**).
3. Open **System Settings → Privacy & Security**, scroll down to the message about YAAMT being blocked, click **Open Anyway**, and confirm with your password or Touch ID.
4. Open YAAMT again and click **Open** when asked.

On macOS 14 (Sonoma) or earlier you can skip steps 2–3: Control-click YAAMT in Applications, choose **Open**, then click **Open** again.

Alternatively, in Terminal, remove the download quarantine flag from just this app:

```
xattr -dr com.apple.quarantine /Applications/YAAMT.app
```

Please do not disable Gatekeeper system-wide (`spctl --master-disable`); that lowers protection for every app.

The command-line tool is inside the app bundle: `/Applications/YAAMT.app/Contents/MacOS/yaamt`. This build is for Apple Silicon Macs (M1 and later); Intel Macs are not supported in this release.

### Linux

No signing step is needed.

- Debian/Ubuntu: `sudo apt install ./yaamt-<version>-linux-<arch>.deb`
- Fedora/RHEL: `sudo dnf install ./yaamt-<version>-linux-<arch>.rpm`
- Any distribution: extract the `.tar.gz` and run `yaamt-gui`

The `arm64` builds need glibc 2.39 or newer (Ubuntu 24.04, Debian 13, Fedora 40, or later).

### Verifying your download

`SHA256SUMS.txt` lists the SHA-256 hash of every file in this release. Compare it with the hash of the file you downloaded:

- Windows (PowerShell): `Get-FileHash .\yaamt-<version>-windows-x64-setup.exe -Algorithm SHA256`
- macOS: `shasum -a 256 yaamt-<version>-macos-arm64.dmg`
- Linux: `sha256sum -c SHA256SUMS.txt --ignore-missing` (run in the download folder)
````

---

## Quick Reference

| I want to...                       | Do this                                          |
|------------------------------------|--------------------------------------------------|
| Ship a new version                 | `git tag v0.X.Y && git push origin v0.X.Y`, test the draft, Publish |
| Fix a shipped release              | Branch from tag, fix, tag `v0.X.(Y+1)`, push     |
| Build one platform by hand         | Checkout the tag, `build.py --release --archive --installer` |
| Test packaging without releasing   | Actions -> Release -> Run workflow on a branch   |
| Undo a bad tag                     | Delete release + tag, fix, re-tag (or hotfix)    |
| See what version a build would get | `cd src && python -m util.version`               |
