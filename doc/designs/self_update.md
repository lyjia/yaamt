# Self-Update Notification Design

From the Public Release Readiness epic.

## Goal

Tell the user when a newer release is available. Never download or apply
the update; just point them at the GitHub release page. Must be
opt-in - the application must not make any network call on startup
unless the user has explicitly enabled the check.

## Hard Requirement: Opt-In

This is the single most important constraint in this design. Reasons:

- Users may be on metered or offline connections.
- Users may consider any unsolicited network call from a desktop app
  to be a privacy violation.
- The "iTunes problem" (silently doing things to user data) is in the
  project's stated values - we don't surprise users.

Implementation rules:

- A new `General/CheckForUpdatesOnStartup` boolean in QSettings,
  default **false**.
- The startup-time check runs only if the setting is true.
- The "Check Now" button in the About dialog is always available
  regardless of the setting (explicit user action).
- The CLI flag `--check-update` is always available (explicit user
  action).
- Wire the toggle into the existing General preference pane so users
  can turn it on or off without leaving the app.

## Format Comparison

`util.version.is_newer(candidate, baseline) -> bool` returns True when
`candidate`'s `Major.Minor.Patch` is strictly greater than
`baseline`'s. Local-version suffixes (`+5.abc1234`, `.dirty`) are
ignored for comparison: a user running `0.3.0+5.abc1234` is "past"
0.3.0 and should not be notified that 0.3.0 is available. They will
be notified when 0.3.1 or 0.4.0 ships.

## Worker

`src/workers/update_checker.py` implements `UpdateChecker(QRunnable)`:

1. GETs `https://api.github.com/repos/lyjia/yaamt/releases/latest`
   using stdlib `urllib.request` (no new dependencies; works under
   nuitka).
2. Parses `tag_name` (`v0.3.0` -> `0.3.0`).
3. Compares against the bundled `VERSION_STRING` via `is_newer`.
4. Emits one of three signals on its `signals` companion:
   - `update_available(latest_version: str, html_url: str)`
   - `no_update()`
   - `failed(error_message: str)`

Network failures are logged via `util.logging.log` at WARNING and
emitted as `failed`. The GUI swallows `failed` for the startup check
(silent log only) but surfaces it as a status-bar message for the
explicit "Check Now" path.

## Caching

`General/LastUpdateCheckTimestamp` (Unix epoch int) and
`General/LastKnownLatestVersion` (string) are persisted after each
successful check. The startup-path checker skips the network call
entirely if the cached timestamp is less than `UPDATE_CHECK_INTERVAL_SECONDS`
old (default 24h) and surfaces the cached result instead. The "Check
Now" path bypasses the cache.

## GUI Integration

- `MainWindow.__init__` schedules `_maybe_check_for_updates()` after
  the window shows. That method short-circuits when the preference is
  off; otherwise it instantiates an `UpdateChecker`, wires its signals
  to `_on_update_available` / `_on_update_no_update` /
  `_on_update_failed`, and submits it to the existing `QThreadPool`.
- `_on_update_available` adds a status-bar message with a clickable
  link via `QStatusBar.showMessage`. (We avoid a modal dialog or a
  toast; a passive status-bar nudge is the least intrusive.)
- `AboutWindow` gets a "Check Now" button that runs the same flow
  with the cache bypassed.

## CLI Integration

`yaamt.py` adds `--check-update` (mutually exclusive with subcommands).
When set, it runs the check synchronously (no Qt threading), prints
the result in plain text, and exits. Cache is bypassed.

## Files

- `src/util/version.py` - add `is_newer`
- `src/util/const.py` - add settings keys and the GitHub API URL
- `src/workers/update_checker.py` (new) - the worker
- `src/windows/preferences/general_pane.py` - add the checkbox
- `src/windows/main_window.py` - wire startup check + status handler
- `src/windows/about_window.py` - add "Check Now" button
- `src/yaamt.py` - add `--check-update` flag
- `tests/util/test_is_newer.py` (new) - comparator coverage
- `tests/workers/test_update_checker.py` (new) - worker logic
  with mocked HTTP

## Out of Scope

- Downloading the release asset
- Applying the update / replacing the binary
- Differential updates
- Verifying signatures (depends on code signing, deferred)

## Verification

- `pytest tests/util/test_is_newer.py tests/workers/test_update_checker.py`
  passes.
- Manual: `python src/yaamt.py --check-update` against a checkout
  whose VERSION_STRING is older than the latest release prints
  "Update available: ..." and exits 0.
- Manual: launch the GUI with the toggle off - no network traffic on
  startup (verify with a network-blocking proxy or `tcpdump`).
- Manual: enable the toggle, restart, observe the status-bar nudge
  when an update is available.
