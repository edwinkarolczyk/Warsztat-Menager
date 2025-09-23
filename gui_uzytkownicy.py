import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

try:
    from services.profile_service import get_user, save_user
except Exception:  # pragma: no cover - fallback gdy serwis nie jest dostępny
    def get_user(login: str):
        """Odczytuje profil użytkownika z ``data/uzytkownicy.json``."""
        path = os.path.join("data", "uzytkownicy.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            iterator = data.values()
        else:
            iterator = data
        for record in iterator:
            if isinstance(record, dict) and record.get("login") == login:
                return record
        return None

    def save_user(user: dict):
        """Zapisuje lub aktualizuje profil w ``data/uzytkownicy.json``."""
        path = os.path.join("data", "uzytkownicy.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = []
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    payload = list(data.values())
                elif isinstance(data, list):
                    payload = data
            except Exception:
                payload = []
        login = user.get("login")
        updated: list[dict] = []
        found = False
        for record in payload:
            if isinstance(record, dict) and record.get("login") == login:
                updated.append(user)
                found = True
            else:
                updated.append(record)
        if not found:
            updated.append(user)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(updated, handle, ensure_ascii=False, indent=2)

try:
    from gui_profile import ProfileView
except Exception:  # pragma: no cover - brak nowego widoku profilu
    ProfileView = None

_YM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _load_all_users() -> list[dict]:
    """Zwraca listę użytkowników z pliku ``data/uzytkownicy.json``."""
    path = os.path.join("data", "uzytkownicy.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return [value for value in data.values() if isinstance(value, dict)]
        if isinstance(data, list):
            return [value for value in data if isinstance(value, dict)]
    except Exception:
        return []
    return []


def _ym_to_iso_first_day(value: str) -> str | None:
    """Zamienia wartość ``YYYY-MM`` na ``YYYY-MM-01`` (pierwszy dzień miesiąca)."""
    if not value:
        return None
    value = value.strip()
    if _YM_RE.match(value):
        return f"{value}-01"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
    return f"{dt.year:04d}-{dt.month:02d}-01"


def _iso_to_ym_display(value: str) -> str:
    """Formatuje datę ISO (``YYYY-MM-DD``) do postaci ``YYYY-MM``."""
    if not value:
        return ""
    value = str(value).strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return f"{dt.year:04d}-{dt.month:02d}"
    except ValueError:
        if _YM_RE.match(value):
            return value
        return value


def _open_profile_in_main(root: tk.Tk, login: str) -> None:
    """Wstawia ``ProfileView`` do centralnego kontenera panelu głównego."""
    if ProfileView is None:
        messagebox.showwarning("Profil", "Nowy widok profilu (ProfileView) jest niedostępny.")
        return
    container = None
    for attr in ("content", "main_content", "content_frame", "body"):
        if hasattr(root, attr):
            container = getattr(root, attr)
            if container is not None:
                break
    if container is None:
        messagebox.showwarning("Profil", "Nie znaleziono kontenera głównego (content).")
        return
    for widget in list(container.winfo_children()):
        try:
            widget.destroy()
        except Exception:
            continue
    for attr in ("active_login", "current_user", "username"):
        try:
            setattr(root, attr, login)
        except Exception:
            pass
    view = ProfileView(container, login=login)
    try:
        if hasattr(root, "_show"):
            root._show(view)  # type: ignore[attr-defined]
        else:
            view.pack(fill="both", expand=True)
    except Exception:
        view.pack(fill="both", expand=True)


def panel_uzytkownicy(root, frame, login=None, rola=None):
    """Panel ustawień użytkowników z edycją rozszerzonego profilu."""
    for widget in list(frame.winfo_children()):
        try:
            widget.destroy()
        except Exception:
            continue

    left = ttk.Frame(frame)
    left.pack(side="left", fill="y", padx=(8, 6), pady=8)
    ttk.Label(left, text="Użytkownicy", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

    users_listbox = tk.Listbox(left, height=18, width=28)
    users_listbox.pack(fill="y", padx=(0, 6))

    right = ttk.Frame(frame)
    right.pack(side="left", fill="both", expand=True, padx=(6, 8), pady=8)

    ttk.Label(right, text="Edycja profilu", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
    )

    row_index = 1
    ttk.Label(right, text="Login*:").grid(row=row_index, column=0, sticky="w")
    login_var = tk.StringVar()
    login_entry = ttk.Entry(right, textvariable=login_var, width=26)
    login_entry.grid(row=row_index, column=1, sticky="w", padx=(6, 18))
    ttk.Label(right, text="Rola*:").grid(row=row_index, column=2, sticky="w")
    role_var = tk.StringVar()
    role_entry = ttk.Entry(right, textvariable=role_var, width=20)
    role_entry.grid(row=row_index, column=3, sticky="w", padx=(6, 0))
    row_index += 1

    ttk.Label(right, text="Display name:").grid(row=row_index, column=0, sticky="w")
    display_name_var = tk.StringVar()
    ttk.Entry(right, textvariable=display_name_var, width=26).grid(
        row=row_index, column=1, sticky="w", padx=(6, 18)
    )
    ttk.Label(right, text="Zatrudniony od (YYYY-MM):").grid(row=row_index, column=2, sticky="w")
    employment_var = tk.StringVar()
    ttk.Entry(right, textvariable=employment_var, width=20).grid(
        row=row_index, column=3, sticky="w", padx=(6, 0)
    )
    row_index += 1

    ttk.Label(right, text="Avatar path:").grid(row=row_index, column=0, sticky="w")
    avatar_var = tk.StringVar()
    ttk.Entry(right, textvariable=avatar_var, width=26).grid(
        row=row_index, column=1, sticky="w", padx=(6, 18)
    )
    ttk.Label(right, text="Cover image:").grid(row=row_index, column=2, sticky="w")
    cover_var = tk.StringVar()
    ttk.Entry(right, textvariable=cover_var, width=20).grid(
        row=row_index, column=3, sticky="w", padx=(6, 0)
    )
    row_index += 1

    allow_var = tk.IntVar(value=1)
    ttk.Checkbutton(
        right,
        text="Pozwól na PW (allow_pw)",
        variable=allow_var,
    ).grid(row=row_index, column=0, columnspan=2, sticky="w", pady=(6, 6))
    row_index += 1

    buttons = ttk.Frame(right)
    buttons.grid(row=row_index, column=0, columnspan=4, sticky="e", pady=(8, 0))

    def _save() -> None:
        login_value = login_var.get().strip()
        if not login_value:
            messagebox.showerror("Błąd", "Login jest wymagany.")
            return
        role_value = (role_var.get() or "").strip() or "uzytkownik"
        employment_value = (employment_var.get() or "").strip()
        if employment_value:
            if not _YM_RE.match(employment_value):
                messagebox.showwarning(
                    "Walidacja",
                    "Pole 'Zatrudniony od' musi być w formacie YYYY-MM (np. 2023-04).",
                )
                return
            _ym_to_iso_first_day(employment_value)
        user = get_user(login_value) or {"login": login_value}
        user["rola"] = role_value
        display_value = display_name_var.get().strip()
        if display_value:
            user["display_name"] = display_value
        else:
            user.pop("display_name", None)
        if employment_value:
            user["zatrudniony_od"] = employment_value
        else:
            user.pop("zatrudniony_od", None)
        avatar_value = avatar_var.get().strip()
        if avatar_value:
            user["avatar_path"] = avatar_value
        else:
            user.pop("avatar_path", None)
        cover_value = cover_var.get().strip()
        if cover_value:
            user["cover_image"] = cover_value
        else:
            user.pop("cover_image", None)
        user["allow_pw"] = bool(allow_var.get())
        try:
            save_user(user)
        except Exception as exc:  # pragma: no cover - obsługa błędu IO
            messagebox.showerror("Błąd zapisu", str(exc))
            return
        messagebox.showinfo("Zapisano", f"Profil '{login_value}' zapisany.")
        _reload_users()

    def _open_profile() -> None:
        login_value = login_var.get().strip()
        if not login_value:
            messagebox.showwarning("Profil", "Najpierw wybierz użytkownika.")
            return
        _open_profile_in_main(root, login_value)

    ttk.Button(buttons, text="Zapisz", command=_save).pack(side="right", padx=(6, 0))
    ttk.Button(buttons, text="Otwórz profil", command=_open_profile).pack(side="right", padx=(6, 0))

    def _fill_form(user: dict | None) -> None:
        if not user:
            login_var.set("")
            role_var.set("")
            display_name_var.set("")
            employment_var.set("")
            avatar_var.set("")
            cover_var.set("")
            allow_var.set(1)
            return
        login_var.set(user.get("login", ""))
        role_var.set(user.get("rola", "uzytkownik"))
        display_name_var.set(user.get("display_name", ""))
        employment_var.set(_iso_to_ym_display(user.get("zatrudniony_od", "")))
        avatar_var.set(user.get("avatar_path", ""))
        cover_var.set(user.get("cover_image", ""))
        allow_var.set(1 if user.get("allow_pw", True) else 0)

    users_cache: list[dict] = []

    def _reload_users() -> None:
        nonlocal users_cache
        users_cache = _load_all_users()
        users_listbox.delete(0, "end")
        for record in users_cache:
            label = f"{record.get('login', '?')}  ({record.get('rola', '?')})"
            users_listbox.insert("end", label)

    def _on_select(_event=None) -> None:
        selection = users_listbox.curselection()
        if not selection:
            _fill_form(None)
            return
        index = selection[0]
        user = users_cache[index] if 0 <= index < len(users_cache) else None
        _fill_form(user)

    users_listbox.bind("<<ListboxSelect>>", _on_select)
    _reload_users()
    if users_cache:
        users_listbox.selection_set(0)
        _on_select()

    for column in range(4):
        right.grid_columnconfigure(column, weight=1)


def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
