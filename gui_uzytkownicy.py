import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

try:
    from services.profile_service import get_user, save_user
except Exception:  # pragma: no cover - fallback gdy serwis nie jest dostępny
    def get_user(login: str):
        p = os.path.join("data", "uzytkownicy.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        seq = data.values() if isinstance(data, dict) else data
        for rec in seq:
            if isinstance(rec, dict) and rec.get("login") == login:
                return rec
        return None

    def save_user(user: dict):
        p = os.path.join("data", "uzytkownicy.json")
        arr = []
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
                arr = list(data.values()) if isinstance(data, dict) else data
            except Exception:
                arr = []
        out, found = [], False
        for rec in arr:
            if isinstance(rec, dict) and rec.get("login") == user.get("login"):
                out.append(user)
                found = True
            else:
                out.append(rec)
        if not found:
            out.append(user)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)

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


def _iso_to_ym_display(raw: str) -> str:
    if not raw:
        return ""
    raw = str(raw).strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return f"{dt.year:04d}-{dt.month:02d}"
    except Exception:
        return raw


def _open_profile_in_main(root: tk.Tk, login: str):
    if ProfileView is None:
        messagebox.showwarning("Profil", "ProfileView niedostępny.")
        return
    container = None
    for attr in ("content", "main_content", "content_frame", "body"):
        if hasattr(root, attr):
            container = getattr(root, attr)
            if container is not None:
                break
    if container is None:
        messagebox.showwarning("Profil", "Nie znaleziono kontenera głównego.")
        return
    for widget in list(container.winfo_children()):
        try:
            widget.destroy()
        except Exception:
            pass
    try:
        setattr(root, "active_login", login)
        setattr(root, "current_user", login)
        setattr(root, "username", login)
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
    for widget in list(frame.winfo_children()):
        try:
            widget.destroy()
        except Exception:
            pass

    left = ttk.Frame(frame)
    left.pack(side="left", fill="y", padx=(8, 6), pady=8)
    right = ttk.Frame(frame)
    right.pack(side="left", fill="both", expand=True, padx=(6, 8), pady=8)

    ttk.Label(left, text="Użytkownicy", font=("Segoe UI", 10, "bold")).pack(
        anchor="w", pady=(0, 6)
    )
    users_listbox = tk.Listbox(left, height=20, width=28)
    users_listbox.pack(fill="y")

    ttk.Label(right, text="Edycja profilu", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
    )

    row_idx = 1
    ttk.Label(right, text="Login*:").grid(row=row_idx, column=0, sticky="w")
    login_var = tk.StringVar()
    ttk.Entry(right, textvariable=login_var, width=26).grid(
        row=row_idx, column=1, sticky="w", padx=(6, 18)
    )
    ttk.Label(right, text="Rola*:").grid(row=row_idx, column=2, sticky="w")
    rola_var = tk.StringVar()
    ttk.Entry(right, textvariable=rola_var, width=20).grid(
        row=row_idx, column=3, sticky="w", padx=(6, 0)
    )
    row_idx += 1

    ttk.Label(right, text="Display name:").grid(row=row_idx, column=0, sticky="w")
    dn_var = tk.StringVar()
    ttk.Entry(right, textvariable=dn_var, width=26).grid(
        row=row_idx, column=1, sticky="w", padx=(6, 18)
    )
    ttk.Label(right, text="Zatrudniony od (YYYY-MM):").grid(
        row=row_idx, column=2, sticky="w"
    )
    ym_var = tk.StringVar()
    ttk.Entry(right, textvariable=ym_var, width=20).grid(
        row=row_idx, column=3, sticky="w", padx=(6, 0)
    )
    row_idx += 1

    ttk.Label(right, text="Avatar path:").grid(row=row_idx, column=0, sticky="w")
    av_var = tk.StringVar()
    ttk.Entry(right, textvariable=av_var, width=26).grid(
        row=row_idx, column=1, sticky="w", padx=(6, 18)
    )
    ttk.Label(right, text="Cover image:").grid(row=row_idx, column=2, sticky="w")
    cv_var = tk.StringVar()
    ttk.Entry(right, textvariable=cv_var, width=20).grid(
        row=row_idx, column=3, sticky="w", padx=(6, 0)
    )
    row_idx += 1

    allow_var = tk.IntVar(value=1)
    ttk.Checkbutton(
        right,
        text="Pozwól na PW (allow_pw)",
        variable=allow_var,
    ).grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(6, 6))
    row_idx += 1

    btns = ttk.Frame(right)
    btns.grid(row=row_idx, column=0, columnspan=4, sticky="e", pady=(8, 0))

    def _save():
        lg = (login_var.get() or "").strip()
        if not lg:
            messagebox.showerror("Błąd", "Login jest wymagany.")
            return
        rl = (rola_var.get() or "").strip() or "uzytkownik"

        ym_disp = (ym_var.get() or "").strip()
        if ym_disp and not _YM_RE.match(ym_disp):
            messagebox.showwarning(
                "Walidacja",
                "Pole 'Zatrudniony od' musi być w formacie YYYY-MM (np. 2024-09).",
            )
            return

        user = get_user(lg) or {"login": lg}
        user["rola"] = rl
        if dn_var.get().strip():
            user["display_name"] = dn_var.get().strip()
        else:
            user.pop("display_name", None)
        if ym_disp:
            user["zatrudniony_od"] = ym_disp
        else:
            user.pop("zatrudniony_od", None)
        if av_var.get().strip():
            user["avatar_path"] = av_var.get().strip()
        else:
            user.pop("avatar_path", None)
        if cv_var.get().strip():
            user["cover_image"] = cv_var.get().strip()
        else:
            user.pop("cover_image", None)
        user["allow_pw"] = bool(allow_var.get())

        try:
            save_user(user)
            messagebox.showinfo("Zapisano", f"Profil '{lg}' zapisany.")
            _reload_users()
        except Exception as exc:  # pragma: no cover - IO issues
            messagebox.showerror("Błąd zapisu", str(exc))

    def _open_profile():
        lg = (login_var.get() or "").strip()
        if not lg:
            messagebox.showwarning("Profil", "Najpierw wybierz użytkownika.")
            return
        _open_profile_in_main(root, lg)

    def _migrate_fill_missing_dates():
        users = _load_all_users()
        if not users:
            messagebox.showinfo("Migracja", "Brak użytkowników do migracji.")
            return
        ym_now = datetime.now().strftime("%Y-%m")
        changed = 0
        for rec in users:
            if not isinstance(rec, dict):
                continue
            if not rec.get("login"):
                continue
            if not rec.get("zatrudniony_od"):
                rec["zatrudniony_od"] = ym_now
                changed += 1
        if changed == 0:
            messagebox.showinfo(
                "Migracja",
                "Wszyscy użytkownicy mają już ustawione 'zatrudniony_od'.",
            )
            return
        path = os.path.join("data", "uzytkownicy.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(users, fh, ensure_ascii=False, indent=2)
        messagebox.showinfo(
            "Migracja",
            f"Uzupełniono 'zatrudniony_od' dla {changed} użytkowników.",
        )
        _reload_users()

    ttk.Button(btns, text="Zapisz", command=_save).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Otwórz profil", command=_open_profile).pack(
        side="right", padx=(6, 0)
    )
    ttk.Button(
        btns,
        text="Uzupełnij 'zatrudniony_od' (MIGRACJA)",
        command=_migrate_fill_missing_dates,
    ).pack(side="left")

    def _fill_form(user: dict | None):
        if not user:
            login_var.set("")
            rola_var.set("")
            dn_var.set("")
            ym_var.set("")
            av_var.set("")
            cv_var.set("")
            allow_var.set(1)
            return
        login_var.set(user.get("login", ""))
        rola_var.set(user.get("rola", "uzytkownik"))
        dn_var.set(user.get("display_name", ""))
        ym_var.set(_iso_to_ym_display(user.get("zatrudniony_od", "")))
        av_var.set(user.get("avatar_path", ""))
        cv_var.set(user.get("cover_image", ""))
        allow_var.set(1 if user.get("allow_pw", True) else 0)

    users_cache: list[dict] = []

    def _reload_users():
        nonlocal users_cache
        users_cache = _load_all_users()
        users_listbox.delete(0, "end")
        for rec in users_cache:
            label = f"{rec.get('login', '?')}  ({rec.get('rola', '?')})"
            users_listbox.insert("end", label)

    def _on_select(_event=None):
        sel = users_listbox.curselection()
        if not sel:
            _fill_form(None)
            return
        idx = sel[0]
        user = users_cache[idx] if 0 <= idx < len(users_cache) else None
        _fill_form(user)

    users_listbox.bind("<<ListboxSelect>>", _on_select)
    _reload_users()
    if users_cache:
        users_listbox.selection_set(0)
        _on_select()

    for col in range(4):
        right.grid_columnconfigure(col, weight=1)


def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
