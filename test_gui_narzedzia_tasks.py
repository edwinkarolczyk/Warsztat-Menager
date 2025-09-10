import types

import gui_narzedzia


def test_tasks_from_comboboxes(monkeypatch):
    monkeypatch.setattr(
        gui_narzedzia,
        "LZ",
        types.SimpleNamespace(
            invalidate_cache=lambda: None,
            get_collections=lambda settings: [{"id": "C1", "name": "Coll1"}],
            get_default_collection=lambda settings: "C1",
            get_tool_types=lambda collection_id, settings: (
                [{"id": "T1", "name": "Typ1"}] if collection_id == "C1" else []
            ),
            get_statuses=lambda collection_id, type_id, settings: (
                [
                    {"id": "S1", "name": "St1", "auto_check_on_entry": True}
                ]
                if collection_id == "C1" and type_id == "T1"
                else []
            ),
            get_tasks=lambda collection_id, type_id, status_id, settings: (
                ["A", "B"]
                if collection_id == "C1" and type_id == "T1" and status_id == "S1"
                else []
            ),
            should_autocheck=lambda collection_id, status_id, settings: True,
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

    class DummyCfg:
        def __init__(self):
            self.merged = {
                "tools": {
                    "collections_enabled": ["C1"],
                    "default_collection": "C1",
                }
            }

    monkeypatch.setattr(gui_narzedzia, "ConfigManager", DummyCfg)

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
