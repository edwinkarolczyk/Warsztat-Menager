# version: 1.1
import tkinter as tk
from tkinter import ttk

import settings_users_runtime as settings_runtime
import ustawienia_uzytkownicy as users_settings


def _texts(notebook):
    return [str(notebook.tab(tab_id, "text")) for tab_id in notebook.tabs()]


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_profile_settings_use_single_users_profile_roles_level(monkeypatch):
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
        panel.var_profile_editable_fields = tk.StringVar(
            master=root,
            value="imie, staz, email, im",
        )

        old_nb = ttk.Notebook(panel._users_container)
        old_nb.pack(fill="both", expand=True)
        panel._users_notebook = old_nb
        old_nb.add(ttk.Frame(old_nb), text="Lista i edycja")
        old_nb.add(ttk.Frame(old_nb), text="Profil użytkownika")

        registrations = {}

        def register(name, _top, nb, tab_widget):
            registrations[name] = (nb, tab_widget)

        panel._register_nested_tab = register

        admin = settings_runtime._rebuild_profile_admin(panel)
        root.update_idletasks()

        assert admin is not None
        assert panel._users_notebook is admin.nb
        assert _texts(admin.nb) == ["Użytkownicy", "Profile", "Rangi"]
        assert set(registrations) >= {"Użytkownicy", "Profile", "Profil", "Rangi"}

        # Legacy staz jest mapowany na realne pole, a śmieć "im" znika.
        assert panel.var_profile_editable_fields.get() == "imie, zatrudniony_od, email"

        # Zakładka Użytkownicy nie ma już kolejnego Notebooka Użytkownicy/Rangi.
        nested_notebooks = [
            widget
            for widget in _descendants(admin.users_tab)
            if isinstance(widget, ttk.Notebook)
        ]
        assert nested_notebooks == []

        phone = next(
            widget
            for widget in _descendants(admin.profile_tab)
            if isinstance(widget, ttk.Checkbutton)
            and str(widget.cget("text")) == "Telefon"
        )
        phone.invoke()
        assert "telefon" in panel.var_profile_editable_fields.get()
        assert panel._dirty is True

        labels = [
            str(widget.cget("text"))
            for widget in _descendants(admin.profile_tab)
            if isinstance(widget, ttk.Label)
        ]
        assert not any("Pozostałe zapisane pola" in text for text in labels)
    finally:
        root.destroy()
