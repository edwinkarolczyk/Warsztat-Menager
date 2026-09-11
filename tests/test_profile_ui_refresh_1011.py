# version: 1.0
from datetime import date

import profile_shift_mode_sync_runtime as shift_ui
import profile_tree_autofit_runtime as tree_ui


def test_shift_anchor_calendar_uses_monday(monkeypatch):
    created_buttons = []
    picker_calls = []

    class FakeEntry:
        def __init__(self):
            self.state = "normal"
            self.bindings = {}

        def grid_info(self):
            return {"row": 1, "column": 1}

        def cget(self, key):
            if key == "textvariable":
                return "anchor_var"
            return ""

        def configure(self, **kwargs):
            self.state = kwargs.get("state", self.state)

        def bind(self, sequence, callback, add=None):
            self.bindings[sequence] = callback

    class FakeButton:
        def __init__(self, _parent, *, text, width, command):
            self.text = text
            self.width = width
            self.command = command
            created_buttons.append(self)

        def grid(self, **_kwargs):
            return None

    class FakeSchedule:
        def __init__(self, entry):
            self.entry = entry

        def winfo_children(self):
            return [self.entry]

    class FakeWindow:
        def __init__(self):
            self.vars = {"anchor_var": "2026-09-09"}

        def getvar(self, name):
            return self.vars[name]

        def setvar(self, name, value):
            self.vars[name] = value

    def fake_picker(owner, *, initial, on_select, title):
        picker_calls.append((owner, initial, title))
        on_select(date(2026, 9, 10))
        return object()

    monkeypatch.setattr(shift_ui.ttk, "Entry", FakeEntry)
    monkeypatch.setattr(shift_ui.ttk, "Button", FakeButton)
    monkeypatch.setattr(shift_ui, "open_date_picker", fake_picker)

    entry = FakeEntry()
    schedule = FakeSchedule(entry)
    win = FakeWindow()

    shift_ui._install_anchor_calendar(schedule, win)

    assert entry.state == "readonly"
    assert "<Button-1>" in entry.bindings
    assert len(created_buttons) == 1
    assert created_buttons[0].text == "📅"

    created_buttons[0].command()

    assert picker_calls[0][1] == date(2026, 9, 9)
    assert picker_calls[0][2] == "Tydzień bazowy — tydzień 1"
    assert win.vars["anchor_var"] == "2026-09-07"
    assert shift_ui._anchor_monday_iso("2026-09-13") == "2026-09-07"


def test_foreman_tree_autofit_runs_again_when_tab_becomes_visible(monkeypatch):
    calls = []

    class FakeTree:
        def __init__(self):
            self.bindings = {}
            self.idle_updates = 0

        def bind(self, sequence, callback, add=None):
            self.bindings[sequence] = callback

        def after_idle(self, callback):
            callback()

        def after(self, _delay_ms, callback):
            callback()

        def winfo_exists(self):
            return True

        def update_idletasks(self):
            self.idle_updates += 1

    tree = FakeTree()
    monkeypatch.setattr(tree_ui, "_autofit_tree", lambda current: calls.append(current))

    tree_ui._bind_visible_autofit(tree)

    assert "<Map>" in tree.bindings
    tree.bindings["<Map>"]()

    assert calls == [tree, tree]
    assert tree.idle_updates == 2
    assert tree._wm_autofit_visible_v1 is True
