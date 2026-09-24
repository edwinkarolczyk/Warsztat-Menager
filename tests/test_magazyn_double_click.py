from types import SimpleNamespace

from gui_magazyn import MagazynFrame


def test_double_click_edits_the_row_under_cursor():
    calls = []

    class Tree:
        def identify_row(self, y):
            assert y == 42
            return "row-b"

        def selection_set(self, row):
            calls.append(("select", row))

        def focus(self, row):
            calls.append(("focus", row))

    frame = SimpleNamespace(
        tree=Tree(),
        _edit_selected_item=lambda: calls.append(("edit",)),
    )
    MagazynFrame._on_double_click(frame, SimpleNamespace(y=42))

    assert calls == [("select", "row-b"), ("focus", "row-b"), ("edit",)]


def test_double_click_on_empty_space_does_not_edit_old_selection():
    frame = SimpleNamespace(
        tree=SimpleNamespace(identify_row=lambda _y: ""),
        _edit_selected_item=lambda: (_ for _ in ()).throw(
            AssertionError("An old selection must not be edited")
        ),
    )
    MagazynFrame._on_double_click(frame, SimpleNamespace(y=999))
