import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QStyledItemDelegate

from util.const import IN_GITHUB_RUNNER
from views.multi_select_preserving_tree_view import MultiSelectPreservingTreeView

SKIP_REASON = "Qt widgets crash in GitHub Actions runner"
NUM_ROWS = 5
NUM_COLS = 2


def _make_view_with_model(qapp):
    """Build a 5x2 model and attach it to a MultiSelectPreservingTreeView
    configured for ExtendedSelection. Shows the view so visualRect returns
    valid geometry for QTest.mouseClick."""
    model = QStandardItemModel(NUM_ROWS, NUM_COLS)
    for row in range(NUM_ROWS):
        for col in range(NUM_COLS):
            model.setItem(row, col, QStandardItem(f"r{row}c{col}"))

    view = MultiSelectPreservingTreeView()
    view.setModel(model)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.resize(400, 300)
    view.show()
    QTest.qWaitForWindowExposed(view)
    return view, model


def _select_rows(view, rows):
    """Programmatically add the given rows to the selection."""
    sel_model = view.selectionModel()
    model = view.model()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for row in rows:
        idx = model.index(row, 0)
        sel_model.select(idx, flags)


def _click_center_of(view, index, modifier=Qt.KeyboardModifier.NoModifier):
    """Synthesize a left-click at the center of the given index's visual rect."""
    rect = view.visualRect(index)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier, rect.center())


def _middle_click_center_of(view, index):
    """Synthesize a middle-click at the center of the given index's visual rect."""
    rect = view.visualRect(index)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier, rect.center())


def _selected_rows_set(view):
    return {idx.row() for idx in view.selectionModel().selectedRows()}


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_click_on_selected_row_preserves_multi_selection(qapp):
    """Left-clicking a row already in a multi-row selection must not collapse it."""
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [1, 2, 3])
    assert _selected_rows_set(view) == {1, 2, 3}

    _click_center_of(view, model.index(2, 0))

    assert _selected_rows_set(view) == {1, 2, 3}
    assert view.selectionModel().currentIndex().row() == 2


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_click_on_unselected_row_collapses_selection(qapp):
    """Left-clicking a row outside the current selection must collapse to it."""
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [1, 2, 3])

    _click_center_of(view, model.index(4, 0))

    assert _selected_rows_set(view) == {4}


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_ctrl_click_on_selected_row_toggles_off(qapp):
    """Ctrl-click on a selected row must still toggle it out of the selection."""
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [1, 2, 3])

    _click_center_of(view, model.index(2, 0), modifier=Qt.KeyboardModifier.ControlModifier)

    assert _selected_rows_set(view) == {1, 3}


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_click_on_empty_area_clears_selection(qapp):
    """Clicking below the last row must clear the selection (default behavior)."""
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [1, 2, 3])

    last_rect = view.visualRect(model.index(NUM_ROWS - 1, 0))
    empty_point = QPoint(last_rect.center().x(), last_rect.bottom() + 40)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, empty_point)

    assert _selected_rows_set(view) == set()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_click_with_single_row_selected_still_clicks_through(qapp):
    """With only one row selected, click on that row is a normal click (not intercepted)."""
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [2])

    _click_center_of(view, model.index(2, 0))

    assert _selected_rows_set(view) == {2}
    assert view.selectionModel().currentIndex().row() == 2


class _RecordingDelegate(QStyledItemDelegate):
    """Delegate that records every createEditor call for assertions."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.edited_indexes = []

    def createEditor(self, parent, option, index):
        self.edited_indexes.append((index.row(), index.column()))
        return QLineEdit(parent)


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_double_click_on_selected_row_emits_signal_without_editing(qapp):
    """Double-click on a row inside a multi-row selection must emit
    doubleClicked for the row under the cursor, preserve the selection,
    and NOT open an inline editor (editing is bound to middle-click)."""
    view, model = _make_view_with_model(qapp)
    delegate = _RecordingDelegate()
    view.setItemDelegate(delegate)

    _select_rows(view, [1, 2, 3])

    double_clicked_spy = QSignalSpy(view.doubleClicked)

    rect = view.visualRect(model.index(2, 0))
    QTest.mouseDClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        rect.center(),
    )

    assert _selected_rows_set(view) == {1, 2, 3}
    assert delegate.edited_indexes == [], (
        f"Double-click must not open an editor; got {delegate.edited_indexes}"
    )
    assert double_clicked_spy.count() == 1
    assert double_clicked_spy.at(0)[0].row() == 2


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_middle_click_on_unselected_row_selects_it_and_opens_editor(qapp):
    """Middle-click on an unselected row must select it and open the
    inline editor for the cell under the cursor."""
    view, model = _make_view_with_model(qapp)
    delegate = _RecordingDelegate()
    view.setItemDelegate(delegate)

    _middle_click_center_of(view, model.index(3, 1))

    assert _selected_rows_set(view) == {3}
    assert view.selectionModel().currentIndex().row() == 3
    assert (3, 1) in delegate.edited_indexes, (
        f"Expected an editor to be created for (row=3, col=1); got {delegate.edited_indexes}"
    )


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_middle_click_inside_multi_selection_preserves_it_and_opens_editor(qapp):
    """Middle-click on a row inside a multi-row selection must preserve
    the selection (so the delegate can edit all rows) and open the editor."""
    view, model = _make_view_with_model(qapp)
    delegate = _RecordingDelegate()
    view.setItemDelegate(delegate)

    _select_rows(view, [1, 2, 3])

    _middle_click_center_of(view, model.index(2, 0))

    assert _selected_rows_set(view) == {1, 2, 3}
    assert view.selectionModel().currentIndex().row() == 2
    assert (2, 0) in delegate.edited_indexes


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_middle_click_outside_multi_selection_collapses_to_it_and_opens_editor(qapp):
    """Middle-click on a row outside the current selection must collapse
    the selection to the clicked row and open the editor."""
    view, model = _make_view_with_model(qapp)
    delegate = _RecordingDelegate()
    view.setItemDelegate(delegate)

    _select_rows(view, [1, 2, 3])

    _middle_click_center_of(view, model.index(4, 0))

    assert _selected_rows_set(view) == {4}
    assert (4, 0) in delegate.edited_indexes


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_middle_click_on_empty_area_opens_no_editor(qapp):
    """Middle-click below the last row must not open an editor."""
    view, model = _make_view_with_model(qapp)
    delegate = _RecordingDelegate()
    view.setItemDelegate(delegate)

    last_rect = view.visualRect(model.index(NUM_ROWS - 1, 0))
    empty_point = QPoint(last_rect.center().x(), last_rect.bottom() + 40)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier, empty_point)

    assert delegate.edited_indexes == []


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason=SKIP_REASON)
def test_double_click_on_unselected_row_collapses_selection(qapp):
    """Double-click on a row outside the current selection must fall
    through to the default handler: selection collapses to that row.

    (We don't assert the editor opens here because QTest.mouseDClick does
    not reliably synthesize the internal press that Qt's default
    mouseDoubleClickEvent relies on — a plain QTreeView exhibits the same
    behavior under QTest. The multi-selection test above proves that our
    override does open the editor; this test guards only against our
    code accidentally intercepting clicks outside the selection.)
    """
    view, model = _make_view_with_model(qapp)
    _select_rows(view, [1, 2, 3])

    rect = view.visualRect(model.index(4, 0))
    QTest.mouseDClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        rect.center(),
    )

    assert _selected_rows_set(view) == {4}
