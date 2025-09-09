import types

import gui_narzedzia


def _setup_dummy_gui(monkeypatch, autocheck=False):
    monkeypatch.setattr(
        gui_narzedzia,
        "tools",
        types.SimpleNamespace(default_collection="C1", collections_enabled=["C1"]),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "LZ",
        types.SimpleNamespace(
            get_tool_types=lambda c, s=None: [{"id": "T1", "name": "Typ1"}] if c == "C1" else [],
            get_statuses=lambda c, tid, s=None: [{"id": "S1", "name": "St1"}] if tid == "T1" else [],
            get_tasks=lambda c, tid, sid, s=None: ["A", "B"] if sid == "S1" else [],
            should_autocheck=lambda c, tid, sid, s=None: autocheck,
        ),
    )

    class DummyVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, val):
            self.value = val

    class DummyWidget:
        def __init__(self, *args, **kwargs):
            self.values = kwargs.get("values", [])
            self.textvariable = kwargs.get("textvariable")

        def pack(self, *args, **kwargs):
            pass

        def config(self, **kwargs):
            if "values" in kwargs:
                self.values = kwargs["values"]

        configure = config

        def bind(self, *args, **kwargs):
            pass

        def set(self, val):
            if self.textvariable:
                self.textvariable.set(val)

    class DummyListbox(DummyWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.items = []

        def delete(self, *args, **kwargs):
            self.items = []

        def insert(self, index, item):
            self.items.append(item)

    dummy_tk = types.SimpleNamespace(StringVar=DummyVar, Listbox=DummyListbox, END="end")
    dummy_ttk = types.SimpleNamespace(Combobox=DummyWidget)
    monkeypatch.setattr(gui_narzedzia, "tk", dummy_tk)
    monkeypatch.setattr(gui_narzedzia, "ttk", dummy_ttk)

    parent = DummyWidget()
    widgets = gui_narzedzia.build_task_template(parent)

    widgets["cb_collection"].set("C1")
    widgets["on_collection_change"]()
    widgets["cb_type"].set("Typ1")
    widgets["on_type_change"]()
    widgets["cb_status"].set("St1")
    widgets["on_status_change"]()

    return widgets


def test_tasks_from_comboboxes(monkeypatch):
    widgets = _setup_dummy_gui(monkeypatch)
    assert widgets["listbox"].items == ["[ ] A", "[ ] B"]


def test_autocheck_marks_done(monkeypatch):
    widgets = _setup_dummy_gui(monkeypatch, autocheck=True)
    assert widgets["listbox"].items and widgets["listbox"].items[0].startswith("[x] A")
