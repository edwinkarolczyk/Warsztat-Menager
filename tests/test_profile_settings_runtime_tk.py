# version: 1.0
import tkinter as tk
from tkinter import ttk

import settings_users_runtime as settings_runtime
import ustawienia_uzytkownicy as users_settings


def _texts(notebook):
    return [str(notebook.tab(tab_id, "text")) for tab_id in notebook.tabs()]


def test_profile_settings_are_grouped_and_duplicate_profile_tab_is_removed(monkeypatch):
    monkeypatch.setattr(users_settings, "_load_users", lambda: [])

    root = tk.Tk()
    try:
        panel = ttk.Frame(root)
        panel.pack(fill="both", expand=True)
        panel._users_container = ttk.Frame(panel)
        panel._users_container.pack(fill="both", expand=True)
        panel.tab_users = panel._users_container
        panel._dirty = False
        panel._unsaved = False
        panel._mark_dirty = lambda: setattr(panel, "_dirty", True)

        panel.var_profile_enabled = tk.BooleanVar(master=root, value=True)
        panel.var_profile_header = tk.BooleanVar(master=root, value=True)
        panel.var_profile_avatar = tk.BooleanVar(master=root, value=False)
        panel.var_profile_pin_change = tk.BooleanVar(master=root, value=False)
        panel.var_profile_editable_fields = tk.StringVar(master=root, value="imie, email")

        outer_nb = ttk.Notebook(panel._users_container)
        outer_nb.pack(fill="both", expand=True)
        panel._users_notebook = outer_nb
        users_frame = ttk.Frame(outer_nb)
        profile_frame = ttk.Frame(outer_nb)
        outer_nb.add(users_frame, text="Lista i edycja")
        outer_nb.add(profile_frame, text="Profil użytkownika")

        registrations = {}

        def register(name, _top, nb, tab_widget):
            registrations[name] = (nb, tab_widget)

        panel._register_nested_tab = register

        manager = users_settings.SettingsProfilesTab(users_frame)
        manager.pack(fill="both", expand=True)

        settings_box = ttk.LabelFrame(profile_frame, text="Ustawienia profilu użytkownika")
        settings_box.pack(fill="x")
        ttk.Checkbutton(settings_box, text="Włącz kartę profilu").grid(row=0, column=0)
        ttk.Checkbutton(settings_box, text="Pokazuj imię w nagłówku").grid(row=1, column=0)
        ttk.Checkbutton(settings_box, text="Włącz avatar").grid(row=2, column=0)
        ttk.Checkbutton(settings_box, text="Zezwól na zmianę PIN").grid(row=3, column=0)
        ttk.Label(settings_box, text="Pola edytowane przez użytkownika (CSV):").grid(row=4, column=0)
        ttk.Entry(settings_box, textvariable=panel.var_profile_editable_fields).grid(row=4, column=1)
        ttk.Label(settings_box, text="Np.: imie, nazwisko, telefon, email").grid(row=5, column=0)

        settings_runtime._rename_tabs(panel)
        settings_runtime._cleanup_embedded_profile_manager(panel)
        settings_runtime._rebuild_profile_settings(panel)
        root.update_idletasks()

        assert _texts(outer_nb) == ["Użytkownicy", "Profile"]
        assert "Profile" in registrations
        assert "Profil" in registrations
        assert _texts(manager.nb) == ["Użytkownicy", "Rangi"]

        assert str(settings_box.cget("text")) == "Profile — ustawienia"
        group_titles = {
            str(widget.cget("text"))
            for widget in settings_box.winfo_children()
            if isinstance(widget, ttk.LabelFrame)
        }
        assert "Widoczność profilu" in group_titles
        assert "Edycja własnego profilu" in group_titles

        edit_group = next(
            widget
            for widget in settings_box.winfo_children()
            if isinstance(widget, ttk.LabelFrame)
            and str(widget.cget("text")) == "Edycja własnego profilu"
        )
        field_checks = []
        for child in edit_group.winfo_children():
            if isinstance(child, ttk.Frame):
                field_checks.extend(
                    grandchild
                    for grandchild in child.winfo_children()
                    if isinstance(grandchild, ttk.Checkbutton)
                )
        phone = next(w for w in field_checks if str(w.cget("text")) == "Telefon")
        phone.invoke()
        assert "telefon" in panel.var_profile_editable_fields.get()
        assert panel._dirty is True
    finally:
        root.destroy()
