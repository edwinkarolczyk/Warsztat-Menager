import types

import gui_narzedzia


def test_tasks_from_comboboxes(monkeypatch):
    monkeypatch.setattr(
        gui_narzedzia,
        "LZ",
        types.SimpleNamespace(
            get_tool_types_list=lambda: [{"id": "T1", "name": "Typ1"}],
            get_statuses_for_type=lambda tid: [{"id": "S1", "name": "St1"}] if tid == "T1" else [],
            get_tasks_for=lambda tid, sid: ["A", "B"] if tid == "T1" and sid == "S1" else [],
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

    widgets["cb_type"].set("Typ1")
    widgets["on_type_change"]()
    widgets["cb_status"].set("St1")
    widgets["on_status_change"]()

    assert widgets["listbox"].items == ["[ ] A", "[ ] B"]
