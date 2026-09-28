from __future__ import annotations

import subprocess
import sys

import gui_zlecenia as GZ
import gui_planista_panel as GPP
from machine_ui_repair_runtime import _fit_editor


def test_single_instance_blocks_second_process_and_releases_after_exit():
    from core import wm_single_instance as guard

    guard.release_single_instance()
    assert guard.acquire_single_instance(wait_seconds=0) is True
    code = (
        "from core.wm_single_instance import acquire_single_instance; "
        "print('1' if acquire_single_instance(wait_seconds=0) else '0')"
    )
    blocked = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert blocked.stdout.strip().endswith("0")
    guard.release_single_instance()

    free = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert free.stdout.strip().endswith("1")


class _Root:
    def __init__(self):
        self.calls = []

    def _wm_open_module(self, key, object_id):
        self.calls.append((key, object_id))
        return True


def _source_view(row):
    view = object.__new__(GZ.ZleceniaView)
    root = _Root()
    view._selected_row = lambda: dict(row)
    view.winfo_toplevel = lambda: root
    return view, root


def test_disposition_source_navigation_switches_main_modules_without_toplevel():
    cases = [
        ({"typ_dyspozycji": "zlecenie_wykonania", "obiekt_id": "zlecenie:000012"}, ("planowanie", "000012")),
        ({"typ_dyspozycji": "maszyna", "obiekt_id": "75"}, ("maszyny", "75")),
        ({"typ_dyspozycji": "narzedzie", "obiekt_id": "507"}, ("narzedzia", "507")),
        ({"typ_dyspozycji": "magazyn", "obiekt_id": "SR-01"}, ("magazyn", "SR-01")),
        (
            {
                "typ_dyspozycji": "magazyn",
                "obiekt_id": "zlecenie:000012:surowiec:SR-02",
                "meta": {"surowiec": "SR-02"},
            },
            ("magazyn", "SR-02"),
        ),
    ]
    for row, expected in cases:
        view, root = _source_view(row)
        view._on_open_source()
        assert root.calls == [expected]


class _Tree:
    def __init__(self):
        self.selected = None
        self.focused = None
        self.seen = None

    def selection_set(self, value):
        self.selected = value

    def focus(self, value):
        self.focused = value

    def see(self, value):
        self.seen = value

    def focus_set(self):
        return None


class _Notebook:
    def __init__(self):
        self.selected = None

    def select(self, value):
        self.selected = value


def test_planista_focus_object_selects_existing_order_in_same_panel():
    panel = object.__new__(GPP.PlanistaPanel)
    panel._orders = {"000012": {"id": "000012"}}
    panel.tree = _Tree()
    panel.nb = _Notebook()
    panel.orders_tab = object()
    panel._refresh_approval_button = lambda: None
    panel.refresh = lambda: None

    assert panel.focus_object("000012") is True
    assert panel.tree.selected == "000012"
    assert panel.tree.focused == "000012"
    assert panel.tree.seen == "000012"
    assert panel.nb.selected is panel.orders_tab


class _EditorWindow:
    def __init__(self):
        self.geometry_value = ""
        self.minsize_value = None
        self.resizable_value = None

    def update_idletasks(self):
        return None

    def winfo_screenwidth(self):
        return 1536

    def winfo_screenheight(self):
        return 864

    def winfo_reqwidth(self):
        return 1100

    def winfo_reqheight(self):
        return 720

    def geometry(self, value):
        self.geometry_value = value

    def minsize(self, width, height):
        self.minsize_value = (width, height)

    def resizable(self, width, height):
        self.resizable_value = (width, height)


def test_machine_editor_opens_larger_than_old_1100x720_default():
    window = _EditorWindow()
    _fit_editor(window)
    size = window.geometry_value.split("+", 1)[0]
    width, height = (int(value) for value in size.split("x"))
    assert width > 1100
    assert height > 720
    assert width <= 1536
    assert height <= 864
    assert window.resizable_value == (True, True)
