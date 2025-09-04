import types

import gui_narzedzia


def test_enter_triggers_actions(monkeypatch):
    buttons = []
    dialogs = []

    class DummyVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, val):
            self.value = val

        def trace_add(self, *_):
            pass

    class DummyWidget:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def pack(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

        def grid_remove(self, *args, **kwargs):
            pass

        def bind(self, *args, **kwargs):
            pass

        def config(self, *args, **kwargs):
            self.kwargs.update(kwargs)

        configure = config

        def delete(self, *args, **kwargs):
            pass

        def get_children(self):
            return []

        def heading(self, *args, **kwargs):
            pass

        def column(self, *args, **kwargs):
            pass

        def insert(self, *args, **kwargs):
            pass

        def tag_configure(self, *args, **kwargs):
            pass

        def state(self, *args, **kwargs):
            pass

        def current(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def focus(self):
            return ""

        def item(self, *args, **kwargs):
            return {"values": ()}

        def columnconfigure(self, *args, **kwargs):
            pass

        def rowconfigure(self, *args, **kwargs):
            pass

        def add(self, *args, **kwargs):
            pass

        def yview(self, *args, **kwargs):
            pass

    class DummyButton(DummyWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            buttons.append(self)

    class DummyToplevel(DummyWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.bindings = {}
            dialogs.append(self)

        def bind(self, event, func):
            self.bindings[event] = func

        def destroy(self):
            pass

        def title(self, *args, **kwargs):
            pass

    class DummyTk:
        Toplevel = staticmethod(DummyToplevel)
        StringVar = DummyVar
        BooleanVar = DummyVar

    class DummyTtk:
        Frame = Label = Entry = Treeview = Scrollbar = Combobox = (
            Checkbutton
        ) = Notebook = Radiobutton = DummyWidget
        Button = DummyButton

    monkeypatch.setattr(gui_narzedzia, "tk", DummyTk)
    monkeypatch.setattr(gui_narzedzia, "ttk", DummyTtk)
    monkeypatch.setattr(gui_narzedzia, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "clear_frame", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "_load_all_tools", lambda: [])
    monkeypatch.setattr(gui_narzedzia, "_statusy_for_mode", lambda mode: ["s"])
    monkeypatch.setattr(gui_narzedzia, "_next_free_in_range", lambda lo, hi: "001")
    monkeypatch.setattr(gui_narzedzia, "_resolve_tools_dir", lambda: ".")
    monkeypatch.setattr(gui_narzedzia, "_types_from_config", lambda: [])
    monkeypatch.setattr(gui_narzedzia, "_append_type_to_config", lambda v: True)
    monkeypatch.setattr(gui_narzedzia, "_tasks_for_type", lambda *a, **k: [])
    monkeypatch.setattr(gui_narzedzia, "_task_templates_from_config", lambda: [])
    monkeypatch.setattr(gui_narzedzia, "_phase_for_status", lambda *a, **k: None)
    monkeypatch.setattr(gui_narzedzia, "_is_taken", lambda n: False)
    monkeypatch.setattr(gui_narzedzia, "_read_tool", lambda n: {})
    monkeypatch.setattr(gui_narzedzia, "_save_tool", lambda d: None)
    monkeypatch.setattr(gui_narzedzia, "_generate_dxf_preview", lambda p: None)
    monkeypatch.setattr(
        gui_narzedzia,
        "ui_hover",
        types.SimpleNamespace(bind_treeview_row_hover=lambda *a, **k: None),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "messagebox",
        types.SimpleNamespace(
            showinfo=lambda *a, **k: None,
            showwarning=lambda *a, **k: None,
            askyesno=lambda *a, **k: False,
        ),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "filedialog",
        types.SimpleNamespace(askopenfilename=lambda *a, **k: ""),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "error_dialogs",
        types.SimpleNamespace(show_error_dialog=lambda *a, **k: None),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "LZ",
        types.SimpleNamespace(consume_for_task=lambda *a, **k: []),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "os",
        types.SimpleNamespace(
            path=types.SimpleNamespace(
                join=lambda *a: "",
                exists=lambda p: False,
                isabs=lambda p: True,
                relpath=lambda p, b: p,
                basename=lambda p: p,
                splitext=lambda p: (p, ""),
            ),
            makedirs=lambda *a, **k: None,
        ),
    )
    monkeypatch.setattr(
        gui_narzedzia,
        "shutil",
        types.SimpleNamespace(copy2=lambda *a, **k: None),
    )

    root = DummyWidget()
    frame = DummyWidget()
    gui_narzedzia.panel_narzedzia(root, frame)

    choose_cmd = buttons[0].kwargs["command"]
    choose_cmd()
    dlg_choose = dialogs[0]
    proceed_btn = next(b for b in buttons if b.kwargs.get("text") == "Dalej")
    assert dlg_choose.bindings["<Return>"] is proceed_btn.kwargs["command"]

    proceed_btn.kwargs["command"]()
    dlg_edit = dialogs[1]
    save_btn = next(b for b in buttons if b.kwargs.get("text") == "Zapisz")
    assert dlg_edit.bindings["<Return>"] is save_btn.kwargs["command"]

