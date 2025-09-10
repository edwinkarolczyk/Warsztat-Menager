import types

import gui_narzedzia


def test_tasks_from_comboboxes(monkeypatch):
    monkeypatch.setattr(
        gui_narzedzia,
        "LZ",
        types.SimpleNamespace(
            invalidate_cache=lambda: None,
            get_collections=lambda settings=None: [{"id": "C1", "name": "Coll1"}],
            get_default_collection=lambda settings=None: "C1",
            get_tool_types=lambda collection=None: (
                [{"id": "T1", "name": "Typ1"}] if collection == "C1" else []
            ),
            get_statuses=lambda tid, collection=None: (
                [{"id": "S1", "name": "St1"}] if tid == "T1" and collection == "C1" else []
            ),
            get_tasks=lambda tid, sid, collection=None: (
                ["A", "B"]
                if tid == "T1" and sid == "S1" and collection == "C1"
                else []
            ),
            should_autocheck=lambda sid, collection_id: True,
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

    widgets["cb_collection"].set("Coll1")
    widgets["on_collection_change"]()
    widgets["cb_type"].set("Typ1")
    widgets["on_type_change"]()
    widgets["cb_status"].set("St1")
    widgets["on_status_change"]()

    assert widgets["listbox"].items == ["[x] A", "[x] B"]
    assert all(t["done"] for t in widgets["tasks_state"])
