from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QTreeView


class MultiSelectPreservingTreeView(QTreeView):
    """
    QTreeView that preserves an existing multi-row selection when the user
    left-clicks on a row already in that selection.

    Qt's default QAbstractItemView.mousePressEvent collapses the selection
    to the single clicked row on the first press of a double-click sequence.
    That defeats inline-editing delegates that apply the edit to every row
    in the current selection. This subclass short-circuits that collapse
    only when:
      * the button is LeftButton,
      * no keyboard modifiers are held,
      * the press hits a valid index, and
      * the clicked row is one of at least two currently selected rows.

    In that case we update the current index (so the editor knows which
    cell it targets) without touching the selection, and accept the event.
    All other presses fall through to the default behavior, so right-click
    context menus, Ctrl/Shift selection edits, empty-area deselect, and
    single-row click-to-select continue to work as before.

    Caveat: because we consume the press on an already-selected row, an
    item drag initiated from such a row will not start. The view this class
    is used with today does not enable item drag, so this is a non-issue.

    A second override on mouseDoubleClickEvent is required for a subtle
    reason: QAbstractItemView.mouseDoubleClickEvent checks an internal
    pressedIndex that only gets assigned inside the default mousePressEvent.
    Because our mousePressEvent short-circuits super() in the multi-select
    case, that pressedIndex stays stale and the default double-click
    handler bails out without opening the editor. Our override starts the
    editor explicitly for the multi-select case.
    """

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._is_click_inside_multi_selection(event):
            index = self.indexAt(event.position().toPoint())
            self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._is_click_inside_multi_selection(event):
            index = self.indexAt(event.position().toPoint())
            self.doubleClicked.emit(index)
            self.edit(index)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _is_click_inside_multi_selection(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            return False
        selected_rows = self.selectionModel().selectedRows()
        if len(selected_rows) < 2:
            return False
        return any(r.row() == index.row() for r in selected_rows)
