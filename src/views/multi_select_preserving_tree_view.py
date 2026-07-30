from PySide6.QtCore import Qt, QItemSelectionModel, QModelIndex
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QTreeView


class MultiSelectPreservingTreeView(QTreeView):
    """
    QTreeView with custom mouse bindings for the file list:

      * Left-click on a row already in a multi-row selection preserves that
        selection instead of collapsing it to the clicked row.
      * Middle-click opens the inline editor for the cell under the cursor.
      * Double-click only emits doubleClicked (the owning window binds it to
        playback); it no longer starts inline editing.

    Qt's default QAbstractItemView.mousePressEvent collapses the selection
    to the single clicked row on the first press of a double-click sequence.
    That defeats inline-editing delegates that apply the edit to every row
    in the current selection. mousePressEvent short-circuits that collapse
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

    Middle-click mirrors the same selection semantics: inside a multi-row
    selection it preserves the selection (so the delegate applies the edit
    to all selected rows); otherwise it selects the clicked row first. The
    editor is started with the unconditional edit() slot, so the view does
    not need a DoubleClicked/SelectedClicked edit trigger.

    Caveat: because we consume the press on an already-selected row, an
    item drag initiated from such a row will not start. The view this class
    is used with today does not enable item drag, so this is a non-issue.

    The mouseDoubleClickEvent override is required for a subtle reason:
    QAbstractItemView.mouseDoubleClickEvent checks an internal pressedIndex
    that only gets assigned inside the default mousePressEvent. Because our
    mousePressEvent short-circuits super() in the multi-select case, that
    pressedIndex stays stale and the default handler would not emit
    doubleClicked, so the override emits it explicitly.
    """

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._is_middle_click_on_index(event):
            index = self.indexAt(event.position().toPoint())
            if self._is_index_in_multi_selection(index):
                # Preserve the multi-selection so the delegate applies the
                # edit to every selected row.
                self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                self.selectionModel().setCurrentIndex(
                    index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
            self.edit(index)
            event.accept()
            return
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
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _is_middle_click_on_index(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.MiddleButton:
            return False
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        return self.indexAt(event.position().toPoint()).isValid()

    def _is_click_inside_multi_selection(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        return self._is_index_in_multi_selection(self.indexAt(event.position().toPoint()))

    def _is_index_in_multi_selection(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        selected_rows = self.selectionModel().selectedRows()
        if len(selected_rows) < 2:
            return False
        return any(r.row() == index.row() for r in selected_rows)
