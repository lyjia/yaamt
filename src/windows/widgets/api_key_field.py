"""
Reusable API-key entry widget with focus-out verification.

``ApiKeyField`` wraps a password-masked QLineEdit alongside a small status
indicator that reflects the result of an asynchronous verification call.
The widget triggers verification when the user finishes editing the field
(focus loss / Enter), and emits ``validity_changed(bool)`` whenever its
"acceptable to save" state changes.

The field is considered VALID when:
    - it is empty (no key entered yet), or
    - the entered key has been successfully verified by the supplied
      verifier callable.

The field is considered INVALID when:
    - the user typed a key that hasn't been verified yet, or
    - verification is in flight, or
    - verification returned an error.

A pane that uses this widget should connect ``validity_changed`` to its
own validity signal so the preferences window can disable Save while any
key is in an unverified state.

The widget is generic; supply a callable ``verifier(key) -> (ok, error)``
specific to whichever service you're validating. Verification runs on a
QThread so the UI stays responsive.
"""

from typing import Callable

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from util.logging import log


# Verifier contract: synchronous call returning (is_valid, error_or_none).
# The widget runs the verifier on a background QThread so blocking network
# calls are fine.
Verifier = Callable[[str], tuple[bool, "str | None"]]


# UI states the indicator can show. Values are stable strings used in tests.
STATE_IDLE = "idle"           # empty field — nothing to verify, no marker
STATE_UNVERIFIED = "unverified"  # user typed something not yet verified
STATE_CHECKING = "checking"      # verification in flight
STATE_OK = "ok"                  # verified successfully
STATE_FAIL = "fail"              # verification rejected the key

# HTML snippets for each state. Kept short so the indicator fits beside the
# QLineEdit on a single row.
_OK_GLYPH = '<span style="color:#2a7;">&#x2713;</span>'
_FAIL_GLYPH = '<span style="color:#c33;">&#x2717;</span>'
_CHECK_GLYPH = '<span style="color:#888;">&#x22ef;</span>'


class _VerifyWorker(QObject):
    """Tiny QObject that runs the verifier and emits the result.

    Lives on a QThread; the QThread owns it. We don't subclass QThread so
    we can keep the worker pure-Python and easily testable.
    """

    finished = Signal(str, bool, object)  # key, ok, error_or_none

    def __init__(self, verifier: Verifier, key: str):
        super().__init__()
        self._verifier = verifier
        self._key = key

    def run(self) -> None:
        try:
            ok, error = self._verifier(self._key)
        except Exception as e:  # pragma: no cover - defensive
            ok, error = False, str(e)
        self.finished.emit(self._key, ok, error)


class ApiKeyField(QWidget):
    """A QLineEdit + status indicator with focus-out verification.

    See module docstring for the validity contract. The widget exposes a
    ``text()`` getter and ``setText()`` setter that mirror QLineEdit's
    interface so calling code reads/writes plain strings.
    """

    # Emitted when the field's "ready to save" state changes. Initial
    # state is True (an empty field is acceptable to save).
    validity_changed = Signal(bool)

    def __init__(
        self,
        verifier: Verifier,
        placeholder: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._verifier = verifier
        self._verified_key: str | None = None
        self._state = STATE_IDLE
        self._last_error: str | None = None
        self._thread: QThread | None = None
        self._worker: _VerifyWorker | None = None
        self._last_emitted_validity = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._line_edit = QLineEdit()
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        if placeholder:
            self._line_edit.setPlaceholderText(placeholder)
        layout.addWidget(self._line_edit, 1)

        self._status_label = QLabel()
        self._status_label.setTextFormat(Qt.TextFormat.RichText)
        self._status_label.setMinimumWidth(20)
        layout.addWidget(self._status_label)

        self._line_edit.editingFinished.connect(self._on_editing_finished)
        self._line_edit.textEdited.connect(self._on_text_edited)

        self._refresh_status()

    # ----- public API --------------------------------------------------

    def text(self) -> str:
        """Return the current entered text, whitespace-trimmed."""
        return self._line_edit.text().strip()

    def setText(self, text: str) -> None:
        """Replace the field's text.

        Setting non-empty text leaves the field in the UNVERIFIED state
        until the user blurs out (or some other code calls
        :meth:`mark_verified`). Setting empty text returns to IDLE.
        """
        text = text or ""
        self._line_edit.setText(text)
        if text.strip():
            self._verified_key = None
            self._set_state(STATE_UNVERIFIED)
        else:
            self._verified_key = None
            self._set_state(STATE_IDLE)

    def is_valid(self) -> bool:
        """Return True if the field is in a savable state.

        Empty is always savable. A non-empty value is savable only after
        successful verification of that exact value.
        """
        text = self.text()
        if text == "":
            return True
        return text == self._verified_key

    def mark_verified(self, key: str) -> None:
        """Programmatically record that ``key`` is known to be valid.

        Useful when loading a saved key from settings and treating it as
        verified without re-hitting the network on every preferences open.
        """
        if self._line_edit.text().strip() == key.strip():
            self._verified_key = key.strip()
            self._set_state(STATE_OK if key.strip() else STATE_IDLE)

    def status_state(self) -> str:
        """Return the current UI state string (one of the STATE_* constants)."""
        return self._state

    @property
    def line_edit(self) -> QLineEdit:
        """Expose the inner QLineEdit for tests and special wiring."""
        return self._line_edit

    # ----- event handlers ----------------------------------------------

    def _on_text_edited(self, _new_text: str) -> None:
        # Any user edit invalidates a previously-verified key.
        text = self.text()
        if text == "":
            self._verified_key = None
            self._set_state(STATE_IDLE)
            return
        if text != self._verified_key:
            self._verified_key = None
            self._set_state(STATE_UNVERIFIED)

    def _on_editing_finished(self) -> None:
        text = self.text()
        if text == "":
            self._set_state(STATE_IDLE)
            return
        if text == self._verified_key:
            return  # nothing changed since last successful verify
        self._start_verification(text)

    # ----- verification --------------------------------------------------

    def _start_verification(self, key: str) -> None:
        log.debug(f"ApiKeyField: starting verification for key suffix ...{key[-4:] if len(key) >= 4 else '***'}")
        self._cancel_in_flight()

        thread = QThread(self)
        worker = _VerifyWorker(self._verifier, key)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_verification_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._set_state(STATE_CHECKING)
        thread.start()

    def _cancel_in_flight(self) -> None:
        # Two ways the in-flight handles get stale:
        #   1. A previous verification finished cleanly — _on_verification_done
        #      cleared the references. self._thread is None, nothing to do.
        #   2. A previous verification finished and Qt's deleteLater already
        #      collected the underlying C++ object, but our Python wrapper
        #      still exists. Touching it raises RuntimeError; the cheapest
        #      defence is to swallow it. We don't have a kill switch into
        #      the verifier callable anyway; stale results are filtered in
        #      _on_verification_done by comparing the returned key against
        #      the current text.
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
        except RuntimeError:
            pass

    def _on_verification_done(self, key: str, ok: bool, error: object) -> None:
        # The thread/worker are about to be torn down by the deleteLater
        # signals connected in _start_verification — drop our references
        # now so a subsequent _cancel_in_flight doesn't try to call into
        # a wrapper whose C++ object has already been collected.
        self._thread = None
        self._worker = None

        # If the user kept typing while we were checking, the result is
        # stale; ignore it. The state is already STATE_UNVERIFIED.
        if self.text() != key:
            log.debug(
                f"ApiKeyField: discarding stale verification result for "
                f"...{key[-4:] if len(key) >= 4 else '***'}"
            )
            return
        if ok:
            log.info(
                f"ApiKeyField: verification succeeded for key suffix "
                f"...{key[-4:] if len(key) >= 4 else '***'}"
            )
            self._verified_key = key
            self._last_error = None
            self._set_state(STATE_OK)
        else:
            log.info(
                f"ApiKeyField: verification failed for key suffix "
                f"...{key[-4:] if len(key) >= 4 else '***'}: {error}"
            )
            self._verified_key = None
            self._last_error = str(error) if error else None
            self._set_state(STATE_FAIL)

    # ----- view ----------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state
        self._refresh_status()
        validity = self.is_valid()
        if validity != self._last_emitted_validity:
            self._last_emitted_validity = validity
            self.validity_changed.emit(validity)

    def _refresh_status(self) -> None:
        if self._state == STATE_IDLE:
            self._status_label.setText("")
            self._status_label.setToolTip("")
        elif self._state == STATE_UNVERIFIED:
            # No marker — the field is just "edited but not yet verified".
            self._status_label.setText("")
            self._status_label.setToolTip("Press Tab or Enter to verify")
        elif self._state == STATE_CHECKING:
            self._status_label.setText(_CHECK_GLYPH)
            self._status_label.setToolTip("Verifying API key…")
        elif self._state == STATE_OK:
            self._status_label.setText(_OK_GLYPH)
            self._status_label.setToolTip("API key verified")
        elif self._state == STATE_FAIL:
            self._status_label.setText(_FAIL_GLYPH)
            tip = "API key rejected"
            if self._last_error:
                tip = f"{tip}: {self._last_error}"
            self._status_label.setToolTip(tip)
