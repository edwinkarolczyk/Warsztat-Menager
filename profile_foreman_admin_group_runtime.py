# version: 1.1
"""Grupuje rzadziej używane zakładki Brygadzisty w jedną Administrację.

Na głównym poziomie pozostają tylko codzienne widoki: Pulpit, Ruch WM,
Obecność i Urlopy. Użytkownicy, Opinie i Statystyki są dostępne wewnątrz
Administracji, bez zmiany źródeł danych ani logiki tych ekranów.
"""
from __future__ import annotations

from tkinter import ttk

from ui_context_help import add_help_button

_INSTALLED = False
_ADMIN_NAMES = ("Użytkownicy", "Opinie", "Statystyki")


def _group_admin_tabs(panel) -> None:
    if getattr(panel, "_wm_admin_group_built", False):
        return

    notebook = getattr(panel, "notebook", None)
    tabs = getattr(panel, "_tabs", None)
    if notebook is None or not isinstance(tabs, dict):
        return

    old_tabs = {name: tabs.get(name) for name in _ADMIN_NAMES}

    admin = ttk.Frame(notebook, style="WM.Container.TFrame")
    notebook.add(admin, text="Administracja")
    tabs["Administracja"] = admin

    header = ttk.Frame(admin, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(header, text="Administracja profili", style="WM.Muted.TLabel").pack(side="left")
    add_help_button(
        header,
        "Tutaj są ustawienia kont, Opinie i Statystyki. Codzienna praca brygadzisty pozostaje w Pulpit, Ruch WM, Obecność i Urlopy.",
    ).pack(side="left", padx=(6, 0))

    inner = ttk.Notebook(admin)
    inner.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    for name in _ADMIN_NAMES:
        frame = ttk.Frame(inner, style="WM.Container.TFrame")
        inner.add(frame, text=name)
        tabs[name] = frame

    # Nie tylko ukrywamy stare karty, ale usuwamy ich zawartość. Dzięki temu
    # nie istnieją dwa równoległe panele Użytkowników ani zbędne bindingi GUI.
    for old in old_tabs.values():
        if old is None:
            continue
        for child in list(old.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        try:
            notebook.hide(old)
        except Exception:
            pass

    try:
        from profile_foreman_flat_users_runtime import _flatten_users_tab
        _flatten_users_tab(panel)
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] admin users rebuild failed: {exc!r}")

    for index, key in enumerate(("Pulpit", "Zespół", "Obecność", "Urlopy", "Administracja")):
        tab = tabs.get(key)
        if tab is None:
            continue
        try:
            notebook.insert(index, tab)
        except Exception:
            pass

    panel._wm_admin_notebook = inner
    panel._wm_admin_group_built = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        import gui_profile_foreman as foreman
        cls = foreman.ForemanProfilePanel
    except Exception:
        return

    if getattr(cls, "_wm_admin_group_runtime", False):
        _INSTALLED = True
        return

    original_build = cls._build

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        _group_admin_tabs(self)
        return result

    cls._build = build
    cls._wm_admin_group_runtime = True
    _INSTALLED = True


__all__ = ["install"]
