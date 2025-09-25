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


def _validate_date_ym(value: str) -> bool:
    if not value:
        return True
    return bool(_YM_RE.fullmatch(value.strip()))


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
    left.pack(side="left", fill="both", padx=(8, 6), pady=8)
    right = ttk.Frame(frame)
    right.pack(side="left", fill="both", expand=True, padx=(6, 8), pady=8)

    ttk.Label(left, text="Użytkownicy", font=("Segoe UI", 10, "bold")).pack(
        anchor="w", pady=(0, 6)
    )
    cols = [
        "login",
        "rola",
        "display_name",
        "zatrudniony_od",
        "avatar_path",
        "cover_image",
        "allow_pw",
    ]
    tree_container = ttk.Frame(left)
    tree_container.pack(fill="both", expand=True)
    users_tree = ttk.Treeview(
        tree_container,
        columns=cols,
        show="headings",
        selectmode="browse",
        height=16,
    )
    vsb = ttk.Scrollbar(tree_container, orient="vertical", command=users_tree.yview)
    users_tree.configure(yscrollcommand=vsb.set)
    users_tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    tree_container.grid_rowconfigure(0, weight=1)
    tree_container.grid_columnconfigure(0, weight=1)
    for col in cols:
        users_tree.heading(col, text=col)
        users_tree.column(col, anchor="w", width=120, stretch=True)

    buttons_frame = ttk.Frame(left)
    buttons_frame.pack(fill="x", pady=(6, 0))

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
        if ym_disp and not _validate_date_ym(ym_disp):
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
            _reload_users(select_login=lg)
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
    tree_users: dict[str, dict] = {}

    def _reload_users(select_login: str | None = None):
        nonlocal users_cache, tree_users
        users_cache = _load_all_users()
        tree_users = {}
        for item in users_tree.get_children():
            users_tree.delete(item)
        for idx, rec in enumerate(users_cache):
            iid = rec.get("login") or f"row-{idx}"
            if iid in tree_users:
                iid = f"{iid}-{idx}"
            tree_users[iid] = rec
            values: list[str] = []
            for col in cols:
                if col == "allow_pw":
                    values.append("tak" if rec.get(col, True) else "nie")
                elif col == "zatrudniony_od":
                    values.append(_iso_to_ym_display(rec.get(col, "")))
                else:
                    val = rec.get(col, "")
                    values.append("" if val is None else str(val))
            users_tree.insert("", "end", iid=iid, values=values)
        if select_login:
            _select_user(select_login)

    def _on_select(_event=None):
        sel = users_tree.selection()
        if not sel:
            _fill_form(None)
            return
        user = tree_users.get(sel[0])
        _fill_form(user)

    def _select_user(login_value: str):
        for iid, rec in tree_users.items():
            if rec.get("login") == login_value:
                users_tree.selection_set(iid)
                users_tree.focus(iid)
                users_tree.see(iid)
                _on_select()
                return

    def _edit_user(user: dict | None = None):
        data = dict(user or {})
        win = tk.Toplevel(frame)
        title_login = data.get("login") or "nowy"
        win.title(f"Edytuj {title_login}")
        win.transient(frame.winfo_toplevel())
        win.columnconfigure(1, weight=1)

        vars_map: dict[str, tk.Variable] = {}
        row = 0
        for col in cols:
            ttk.Label(win, text=col).grid(
                row=row, column=0, sticky="w", padx=8, pady=4
            )
            if col == "allow_pw":
                var = tk.BooleanVar(value=bool(data.get(col, True)))
                ttk.Checkbutton(
                    win,
                    text="Pozwól na PW",
                    variable=var,
                    onvalue=True,
                    offvalue=False,
                ).grid(row=row, column=1, sticky="w", padx=8, pady=4)
            else:
                default = data.get(col, "")
                if default is None:
                    default = ""
                if col == "zatrudniony_od":
                    default = _iso_to_ym_display(str(default))
                var = tk.StringVar(value=str(default))
                ttk.Entry(win, textvariable=var, width=32).grid(
                    row=row, column=1, sticky="we", padx=8, pady=4
                )
            vars_map[col] = var
            row += 1

        def _save_from_editor():
            login_value = vars_map["login"].get().strip()
            if not login_value:
                messagebox.showerror("Błąd", "Login jest wymagany.", parent=win)
                return
            rola_value = vars_map["rola"].get().strip() or "uzytkownik"
            ym_value = vars_map["zatrudniony_od"].get().strip()
            if ym_value and not _validate_date_ym(ym_value):
                messagebox.showerror(
                    "Błąd",
                    "Pole 'zatrudniony_od' musi mieć format YYYY-MM.",
                    parent=win,
                )
                return
            user_data = get_user(login_value) or {"login": login_value}
            user_data["rola"] = rola_value
            display_value = vars_map["display_name"].get().strip()
            if display_value:
                user_data["display_name"] = display_value
            else:
                user_data.pop("display_name", None)
            if ym_value:
                user_data["zatrudniony_od"] = ym_value
            else:
                user_data.pop("zatrudniony_od", None)
            avatar_value = vars_map["avatar_path"].get().strip()
            if avatar_value:
                user_data["avatar_path"] = avatar_value
            else:
                user_data.pop("avatar_path", None)
            cover_value = vars_map["cover_image"].get().strip()
            if cover_value:
                user_data["cover_image"] = cover_value
            else:
                user_data.pop("cover_image", None)
            user_data["allow_pw"] = bool(vars_map["allow_pw"].get())
            try:
                save_user(user_data)
            except Exception as exc:  # pragma: no cover - IO issues
                messagebox.showerror("Błąd zapisu", str(exc), parent=win)
                return
            win.destroy()
            _reload_users(select_login=login_value)
            _fill_form(user_data)

        def _open_profile_from_editor():
            login_value = vars_map["login"].get().strip()
            if not login_value:
                messagebox.showwarning(
                    "Profil",
                    "Najpierw uzupełnij login użytkownika.",
                    parent=win,
                )
                return
            _open_profile_in_main(root, login_value)

        actions = ttk.Frame(win)
        actions.grid(row=row, column=0, columnspan=2, sticky="e", padx=8, pady=(8, 8))
        ttk.Button(actions, text="Otwórz profil", command=_open_profile_from_editor).pack(
            side="left"
        )
        ttk.Button(actions, text="Zapisz", command=_save_from_editor).pack(
            side="right", padx=(6, 0)
        )

    def _edit_selected_user(_event=None):
        sel = users_tree.selection()
        if not sel:
            messagebox.showinfo("Edycja", "Najpierw wybierz użytkownika z listy.")
            return
        user = tree_users.get(sel[0])
        if not user:
            messagebox.showerror("Edycja", "Nie udało się wczytać użytkownika.")
            return
        _edit_user(user)

    ttk.Button(
        buttons_frame,
        text="Edytuj zaznaczonego",
        command=_edit_selected_user,
    ).pack(fill="x")
    ttk.Button(
        buttons_frame,
        text="Nowy użytkownik",
        command=lambda: _edit_user({"allow_pw": True, "rola": "uzytkownik"}),
    ).pack(fill="x", pady=(4, 0))

    users_tree.bind("<<TreeviewSelect>>", _on_select)
    users_tree.bind("<Double-1>", _edit_selected_user)
    _reload_users()
    if users_cache:
        first = next(iter(users_tree.get_children()), None)
        if first:
            users_tree.selection_set(first)
            users_tree.focus(first)
            _on_select()

    for col in range(4):
        right.grid_columnconfigure(col, weight=1)


def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
