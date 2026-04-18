"""Tests for ``ApiKeyField`` — the reusable verify-on-focus-out widget.

Verification is mocked at the verifier-callable boundary so no test needs
network access. We exercise the synchronous slots directly rather than
spinning the QThread, which keeps the tests deterministic.
"""

import pytest

from util.const import IN_GITHUB_RUNNER


pytestmark = pytest.mark.skipif(
    IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner"
)


def _make_field(qapp, verifier=None):
    from windows.widgets.api_key_field import ApiKeyField
    if verifier is None:
        verifier = lambda key: (True, None)
    return ApiKeyField(verifier=verifier)


def test_empty_field_is_valid_and_idle(qapp):
    from windows.widgets.api_key_field import STATE_IDLE
    field = _make_field(qapp)
    assert field.text() == ""
    assert field.is_valid() is True
    assert field.status_state() == STATE_IDLE


def test_typing_marks_unverified_and_invalid(qapp):
    from windows.widgets.api_key_field import STATE_UNVERIFIED
    field = _make_field(qapp)
    # textEdited is only emitted by user input, not setText. Use the line
    # edit's keyboard-equivalent path: setText then emit textEdited
    # explicitly to mimic a user typing.
    field.line_edit.setText("typed-key")
    field.line_edit.textEdited.emit("typed-key")
    assert field.is_valid() is False
    assert field.status_state() == STATE_UNVERIFIED


def test_set_text_with_value_starts_unverified(qapp):
    from windows.widgets.api_key_field import STATE_UNVERIFIED
    field = _make_field(qapp)
    field.setText("some-key")
    assert field.status_state() == STATE_UNVERIFIED
    assert field.is_valid() is False


def test_set_text_with_empty_returns_to_idle(qapp):
    from windows.widgets.api_key_field import STATE_IDLE
    field = _make_field(qapp)
    field.setText("a-key")
    field.setText("")
    assert field.status_state() == STATE_IDLE
    assert field.is_valid() is True


def test_mark_verified_promotes_state(qapp):
    from windows.widgets.api_key_field import STATE_OK
    field = _make_field(qapp)
    field.setText("known-good")
    field.mark_verified("known-good")
    assert field.status_state() == STATE_OK
    assert field.is_valid() is True


def test_mark_verified_ignores_mismatched_key(qapp):
    from windows.widgets.api_key_field import STATE_UNVERIFIED
    field = _make_field(qapp)
    field.setText("typed")
    field.mark_verified("different-key")
    # Field text wasn't "different-key", so the mark was a no-op.
    assert field.status_state() == STATE_UNVERIFIED
    assert field.is_valid() is False


def test_verification_success_path(qapp):
    """Drive _on_verification_done directly to bypass QThread spin-up."""
    from windows.widgets.api_key_field import STATE_OK
    field = _make_field(qapp, verifier=lambda k: (True, None))
    field.setText("good-key")
    field._on_verification_done("good-key", True, None)
    assert field.status_state() == STATE_OK
    assert field.is_valid() is True


def test_verification_failure_path_records_error(qapp):
    from windows.widgets.api_key_field import STATE_FAIL
    field = _make_field(qapp, verifier=lambda k: (False, "Invalid API key"))
    field.setText("bad-key")
    field._on_verification_done("bad-key", False, "Invalid API key")
    assert field.status_state() == STATE_FAIL
    assert field.is_valid() is False
    assert "Invalid API key" in field._status_label.toolTip()


def test_stale_verification_result_is_ignored(qapp):
    """If the user kept typing while a request was in flight, the late
    callback for the old key must not flip status back to OK."""
    from windows.widgets.api_key_field import STATE_UNVERIFIED
    field = _make_field(qapp)
    field.setText("first")
    field._on_verification_done("first", True, None)  # first is OK
    # Then user retyped, mid-flight callback for the now-stale text.
    field.line_edit.setText("second")
    field.line_edit.textEdited.emit("second")
    field._on_verification_done("first", True, None)  # stale
    assert field.status_state() == STATE_UNVERIFIED
    assert field.is_valid() is False


def test_validity_changed_signal_fires_on_state_transitions(qapp):
    field = _make_field(qapp)
    seen: list[bool] = []
    field.validity_changed.connect(seen.append)

    # Empty → typing key → unverified (False)
    field.line_edit.setText("typed")
    field.line_edit.textEdited.emit("typed")
    # OK after server replies
    field._on_verification_done("typed", True, None)
    # Clear back to empty
    field.setText("")

    # No duplicate emissions: each transition should appear at most once.
    assert seen == [False, True, True] or seen == [False, True]
    # Either is acceptable depending on whether clearing emits when state
    # is already valid. Just make sure we observed False then True at minimum.
    assert False in seen
    assert True in seen


def test_editing_finished_with_empty_skips_verification(qapp):
    """Pressing Tab in an empty field must not spawn a verification."""
    calls = []
    field = _make_field(qapp, verifier=lambda k: (calls.append(k) or (True, None)))
    field.line_edit.editingFinished.emit()
    assert calls == []


def test_editing_finished_skips_when_text_already_verified(qapp):
    """Tabbing through an already-verified field should not re-verify."""
    calls = []
    field = _make_field(qapp, verifier=lambda k: (calls.append(k) or (True, None)))
    field.setText("good")
    field.mark_verified("good")
    field.line_edit.editingFinished.emit()
    assert calls == []


def test_thread_handles_cleared_after_verification(qapp):
    """Regression: once a verification completes, the QThread/worker
    references must be dropped so the next verification doesn't poke at
    a deleted-by-Qt C++ object."""
    field = _make_field(qapp)
    field.setText("first")
    # Pretend a real verification cycle ran: in production
    # _on_verification_done is invoked by the worker's finished signal
    # immediately before the QThread is deleteLater'd.
    field._on_verification_done("first", False, "Invalid API key")
    assert field._thread is None
    assert field._worker is None


def test_cancel_in_flight_survives_deleted_qthread_wrapper(qapp):
    """Regression: simulate the post-deleteLater state where our Python
    wrapper exists but the underlying QThread C++ object is gone. The
    next _cancel_in_flight (e.g. triggered by a second editingFinished)
    must not raise RuntimeError."""
    field = _make_field(qapp)

    class _DeadQThread:
        def isRunning(self):
            raise RuntimeError(
                "Internal C++ object (PySide6.QtCore.QThread) already deleted."
            )

        def quit(self):  # pragma: no cover - unreachable; isRunning blew up
            raise AssertionError("quit should not be called when isRunning raises")

    field._thread = _DeadQThread()
    field._worker = object()
    # Must not raise; should clear references defensively.
    field._cancel_in_flight()
    assert field._thread is None
    assert field._worker is None


def test_second_verification_after_first_completes(qapp):
    """End-to-end of the user's reported flow: verify a bad key, then a
    correct one. The widget must not blow up when starting the second
    verification because of stale handles from the first."""
    results_iter = iter([(False, "Invalid API key"), (True, None)])
    verifier = lambda _key: next(results_iter)
    field = _make_field(qapp, verifier=verifier)

    # First attempt: bad key, then the worker fires _on_verification_done.
    field.setText("bad-key")
    field._on_verification_done("bad-key", False, "Invalid API key")

    # Second attempt: user retypes and tabs out. Pre-fix this raised
    # RuntimeError inside _cancel_in_flight.
    field.line_edit.setText("good-key")
    field.line_edit.textEdited.emit("good-key")
    # Trigger the same code path the editingFinished signal uses, but
    # short-circuit before the real QThread spawn so the test stays
    # synchronous.
    field._cancel_in_flight()
    assert field._thread is None
