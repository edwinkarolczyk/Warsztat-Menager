# version: 1.0
import json
import os
import re
import unicodedata
import tkinter as tk
from collections.abc import Callable
from datetime import datetime, timezone
from tkinter import ttk, messagebox

from profile_utils import ADMIN_ROLE_NAMES, SIDEBAR_MODULES

try:
    from ui_theme_guard import ensure_theme_applied
except Exception:  # pragma: no cover - brak strażnika motywów
    def ensure_theme_applied(_owner):
        return None

try:
    from wm_access import (
        get_disabled_modules_for,
        set_modules_visibility_map,
        load_profiles,
        save_profiles,
        normalize_role_name,
    )
except Exception:  # pragma: no cover - fallback, gdy moduł nie istnieje
    def get_disabled_modules_for(_login: str):
        return []

    def set_modules_visibility_map(_login: str, _show_map: dict):
        pass

    def normalize_role_name(role: str) -> str:
        return str(role or "").strip().lower()

    def load_profiles():
        return {}

    def save_profiles(_profiles_dict: dict):
        return None

try:
    from utils.moduly import zaladuj_manifest
except Exception:  # pragma: no cover - fallback na brak manifestu
    def zaladuj_manifest():
        return {}

try:
    from services.profile_service import get_user, save_user, get_all_users, write_users
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

    def write_users(users: list[dict]):
        p = os.path.join("data", "uzytkownicy.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(list(users), fh, ensure_ascii=False, indent=2)

    def get_all_users():
        p = os.path.join("data", "uzytkownicy.json")
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return []
        if isinstance(data, dict):
            if "users" in data and isinstance(data["users"], list):
                return [value for value in data["users"] if isinstance(value, dict)]
            return [value for value in data.values() if isinstance(value, dict)]
        if isinstance(data, list):
            return [value for value in data if isinstance(value, dict)]
        return []

try:
    from gui_profile import ProfileView
except Exception:  # pragma: no cover - brak nowego widoku profilu
    ProfileView = None

_YM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

SHIFT_MODE_CHOICES = {
    "Stała 1 zmiana (6:00–14:00)": "111",
    "Stała 2 zmiana (14:00–22:00)": "222",
    "Rotacja 1 → 2 → 1": "121",
    "Rotacja 2 → 1 → 2": "212",
}

ROLE_LABELS = [
    ("administrator", "Administrator"),
    ("kierownik", "Kierownik"),
    ("brygadzista", "Brygadzista"),
    ("operator", "Operator / Ślusarz"),
    ("student", "Student"),
    ("sezonowiec", "Sezonowiec"),
    ("guest", "Gość"),
]

ROLE_KEYS = [role_key for role_key, _label in ROLE_LABELS]
ROLE_LABELS_MAP = {role_key: label for role_key, label in ROLE_LABELS}

LEGACY_ROLE_ALIASES = {
    "admin": "administrator",
    "administrator": "administrator",
    "user": "operator",
    "uzytkownik": "operator",
    "użytkownik": "operator",
    "pracownik": "operator",
    "serwisant": "operator",
}


def _shift_mode_label_from_code(code: str | None) -> str:
    normalized = str(code or "").strip()
    for label, value in SHIFT_MODE_CHOICES.items():
        if value == normalized:
            return label
    return "Stała 1 zmiana (6:00–14:00)"


def _validate_date_ym(value: str) -> bool:
    if not value:
        return True
    return bool(_YM_RE.fullmatch(value.strip()))


def _get_from(obj, *keys, default=None):
    """Bezpieczne pobieranie zagnieżdżonych wartości (dict lub atrybuty)."""

    current = obj
    for key in keys:
        try:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                current = getattr(current, key)
        except Exception:  # pragma: no cover - defensywne odczyty
            return default
        if current is None:
            return default
    return current if current is not None else default


def _current_user_role_safe(owner=None) -> str:
    """Bezpieczne pobieranie roli aktualnego użytkownika."""

    profile = _get_from(owner, "active_profile", default={})
    if isinstance(profile, dict):
        role = profile.get("rola")
        if role:
            return role

    profile = _get_from(owner, "cfg_manager", "active_profile", default={})
    if isinstance(profile, dict):
        role = profile.get("rola")
        if role:
            return role

    role = _get_from(owner, "rola", default=None)
    if role:
        return role

    return "user"


def _current_user_login_safe(owner=None) -> str:
    """Bezpieczne pobieranie loginu aktualnego użytkownika."""

    profile = _get_from(owner, "active_profile", default={})
    if isinstance(profile, dict):
        login = profile.get("login")
        if login:
            return login

    profile = _get_from(owner, "cfg_manager", "active_profile", default={})
    if isinstance(profile, dict):
        login = profile.get("login")
        if login:
            return login

    login = _get_from(owner, "login", default="")
    return login or ""


def _load_manifest_modules_safe() -> list[tuple[str, str]]:
    """Zwraca listę modułów z manifestu (id, etykieta)."""

    try:
        manifest = zaladuj_manifest()
    except Exception:  # pragma: no cover - brak manifestu/zależności
        return []

    modules = manifest.get("moduly") if isinstance(manifest, dict) else None
    if not isinstance(modules, list):
        return []

    result: list[tuple[str, str]] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_id = module.get("id")
        if not isinstance(module_id, str) or not module_id.strip():
            continue
        name = module.get("nazwa")
        label = name.strip() if isinstance(name, str) and name.strip() else module_id
        result.append((module_id.strip(), label))
    return result


def open_modules_access_dialog(owner, login: str) -> None:
    """Wyświetla okno konfiguracji widoczności modułów dla użytkownika."""

    login = (login or "").strip()
    if not login:
        messagebox.showwarning(
            "Brak loginu",
            "Najpierw zapisz użytkownika i upewnij się, że login jest uzupełniony.",
        )
        return

    role = _current_user_role_safe(owner)
    current_login = _current_user_login_safe(owner)

    elevated_roles = ADMIN_ROLE_NAMES | {"brygadzista"}
    allowed = False
    if (role or "").lower() in elevated_roles:
        allowed = True
    elif current_login == login:
        allowed = True
    else:
        try:
            profiles = load_profiles()
            if isinstance(profiles, dict):
                me = profiles.get(current_login) or {}
                fallback_role = me.get("rola")
                if (fallback_role or "").lower() in elevated_roles:
                    allowed = True
        except Exception:  # pragma: no cover - defensywne
            pass

    if not allowed and role == "user":
        allowed = True

    if not allowed:
        messagebox.showwarning(
            "Brak uprawnień",
            "Tę operację może wykonać tylko administrator lub brygadzista.",
        )
        return

    disabled = set(get_disabled_modules_for(login))

    module_entries: list[tuple[str, str]] = _load_manifest_modules_safe()

    if not module_entries:
        modules: list[str] = []
        manifest_paths = (
            ("modules_manifest", "defined_modules"),
            ("modules",),
            ("manifest_modulow",),
        )
        for path in manifest_paths:
            try:
                current = owner
                for attr in path:
                    current = getattr(current, attr)
                if isinstance(current, dict):
                    modules = list(current.keys())
                elif isinstance(current, (list, tuple, set)):
                    modules = list(current)
                if modules:
                    break
            except Exception:  # pragma: no cover - defensywne
                continue

        if not modules:
            try:
                buttons = getattr(owner, "left_panel_buttons", [])
                modules = [
                    getattr(button, "module_name")
                    for button in buttons
                    if getattr(button, "module_name", None)
                ]
            except Exception:  # pragma: no cover - defensywne
                pass

        if not modules:
            modules = [
                "narzedzia",
                "maszyny",
                "magazyn",
                "zlecenia",
                "jarvis",
                "ustawienia",
                "profile",
                "panel_glowny",
            ]

        modules = sorted({m for m in modules if isinstance(m, str)}, key=str.lower)
        module_entries = [
            (module, module.replace("_", " ").title()) for module in modules
        ]

    known_ids = {module_id for module_id, _ in module_entries}
    for missing in sorted(disabled - known_ids, key=str.lower):
        module_entries.append((missing, missing.replace("_", " ").title()))

    parent = owner if isinstance(owner, tk.Misc) else None

    try:
        ensure_theme_applied(owner)
    except Exception:  # pragma: no cover - defensywne wywołanie
        pass

    win = tk.Toplevel(parent)
    win.title(f"Dostęp do modułów – {login}")
    if parent is not None:
        win.transient(parent)
    win.grab_set()

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="Widoczność modułów dla użytkownika:",
        font=("", 10, "bold"),
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

    var_map: dict[str, tk.BooleanVar] = {}
    row = 1
    column = 0
    for module_id, label in module_entries:
        var = tk.BooleanVar(value=module_id not in disabled)
        var_map[module_id] = var
        ttk.Checkbutton(frame, text=label, variable=var).grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 16),
            pady=(2, 0),
        )
        column += 1
        if column >= 3:
            column = 0
            row += 1

    buttons = ttk.Frame(frame)
    buttons.grid(row=row + 1, column=0, columnspan=3, sticky="e", pady=(12, 0))

    def _save() -> None:
        try:
            show_map = {module: var.get() for module, var in var_map.items()}
            set_modules_visibility_map(login, show_map)
        except Exception as exc:  # pragma: no cover - IO/zależności
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać zmian:\n{exc}")
            return

        messagebox.showinfo(
            "Zapisano",
            "Zaktualizowano dostęp do modułów.\nAby zobaczyć efekt w menu, odśwież panel.",
        )
        win.destroy()

    ttk.Button(buttons, text="Zapisz", command=_save).pack(side="right")
    ttk.Button(buttons, text="Anuluj", command=win.destroy).pack(
        side="right", padx=(0, 8)
    )


def make_modules_access_button(
    parent, owner, login_getter: Callable[[], str]
) -> tuple[ttk.Frame, Callable[[], None]]:
    """Buduje ramkę z przyciskiem otwierającym dialog modułów."""

    frame = ttk.Frame(parent)
    button = ttk.Button(
        frame,
        text="Dostęp do modułów",
        command=lambda: open_modules_access_dialog(owner, (login_getter() or "").strip()),
    )
    button.pack(side="left")

    def _refresh_state(*_ignored) -> None:
        login_value = (login_getter() or "").strip()
        if login_value:
            button.state(["!disabled"])
        else:
            button.state(["disabled"])

    _refresh_state()
    return frame, _refresh_state


def _load_all_users() -> list[dict]:
    """Zwraca listę użytkowników korzystając z warstwy serwisowej."""

    try:
        data = get_all_users()
    except Exception:  # pragma: no cover - defensywne przed zależnościami
        data = None

    users: list[dict] = []
    if isinstance(data, list):
        users = [value for value in data if isinstance(value, dict)]
    elif isinstance(data, dict):
        if "users" in data and isinstance(data["users"], list):
            users = [value for value in data["users"] if isinstance(value, dict)]
        else:
            users = [value for value in data.values() if isinstance(value, dict)]

    if users:
        return users

    # Fallback – zachowaj kompatybilność z lokalnym plikiem w razie problemów
    path = os.path.join("data", "uzytkownicy.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    if isinstance(data, dict):
        if "users" in data and isinstance(data["users"], list):
            return [value for value in data["users"] if isinstance(value, dict)]
        return [value for value in data.values() if isinstance(value, dict)]
    if isinstance(data, list):
        return [value for value in data if isinstance(value, dict)]
    return []


def _load_profiles_map() -> dict[str, dict]:
    """Wczytuje profiles.json jako słownik login → dane."""

    try:
        raw = load_profiles()
    except Exception:
        raw = {}

    profiles: dict[str, dict] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            login = str(key).strip()
            entry = dict(value)
            if not entry.get("login"):
                entry["login"] = login
            profiles[login] = entry
    return profiles


def _save_profiles_map(profiles: dict[str, dict]) -> None:
    """Zapisuje profiles.json, normalizując strukturę danych."""

    payload: dict[str, dict] = {}
    for login, data in profiles.items():
        if not isinstance(data, dict):
            continue
        entry = dict(data)
        entry["login"] = login
        payload[str(login)] = entry
    save_profiles(payload)


def _profile_display_name(profile: dict) -> str:
    """Zwraca etykietę wyświetlaną dla profilu."""

    if not isinstance(profile, dict):
        return ""
    for key in ("nazwa", "name", "display_name", "imie"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    login = profile.get("login")
    return str(login or "")


def _role_to_choice(role: str | None) -> str:
    """Normalizuje rolę profilu na klucz z nowej listy rang."""

    normalized = str(role or "").strip().lower()
    normalized = LEGACY_ROLE_ALIASES.get(normalized, normalized)
    try:
        normalized = normalize_role_name(normalized)
    except Exception:
        pass
    return normalized if normalized in ROLE_KEYS else "operator"


def _choice_to_role(choice: str) -> str:
    """Mapuje wartość z UI na zapis w profilu."""

    normalized = str(choice or "").strip().lower()
    normalized = LEGACY_ROLE_ALIASES.get(normalized, normalized)
    return normalized if normalized in ROLE_KEYS else "operator"


def _role_key_to_label(role_key: str | None) -> str:
    normalized = _role_to_choice(role_key)
    return ROLE_LABELS_MAP.get(normalized, "Operator / Ślusarz")


def _slugify_login(name: str) -> str:
    """Konwertuje nazwę na prosty login (a-z, 0-9, '_')."""

    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name)
    ascii_name = ascii_name.strip("_")
    return ascii_name or "user"


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

    container = ttk.Frame(frame)
    container.pack(fill="both", expand=True, padx=12, pady=12)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text="Użytkownicy",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", pady=(0, 6))

    tree_container = ttk.Frame(container)
    tree_container.pack(fill="both", expand=True)
    tree_container.grid_rowconfigure(0, weight=1)
    tree_container.grid_columnconfigure(0, weight=1)

    columns = ("name", "pin", "role")
    headers = {
        "name": "Imię",
        "pin": "PIN",
        "role": "Rola",
    }

    tree = ttk.Treeview(
        tree_container,
        columns=columns,
        show="headings",
        selectmode="browse",
        height=14,
    )
    vsb = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")

    tree.column("name", width=220, anchor="w")
    tree.column("pin", width=80, anchor="center")
    tree.column("role", width=110, anchor="w")
    for key in columns:
        tree.heading(key, text=headers[key])

    state: dict[str, dict] = {"profiles": _load_profiles_map()}

    def _refresh_tree(select_login: str | None = None) -> None:
        state["profiles"] = _load_profiles_map()
        for item in tree.get_children():
            tree.delete(item)

        entries = sorted(
            state["profiles"].items(),
            key=lambda item: (
                _profile_display_name(item[1]).lower(),
                str(item[0]).lower(),
            ),
        )
        for login_value, profile in entries:
            name = _profile_display_name(profile)
            pin = str(profile.get("pin", "")) if isinstance(profile, dict) else ""
            role_choice = _role_to_choice(
                profile.get("rola") if isinstance(profile, dict) else None
            )
            role_label = _role_key_to_label(role_choice)
            tree.insert(
                "",
                "end",
                iid=login_value,
                values=(name, pin, role_label),
            )

        if select_login and tree.exists(select_login):
            tree.selection_set(select_login)
            tree.focus(select_login)
            tree.see(select_login)

    def _selected_login() -> str:
        selection = tree.selection()
        if not selection:
            return ""
        return str(selection[0])

    def _open_editor(login_value: str | None = None) -> None:
        profiles = state.get("profiles", {})
        seed = dict(profiles.get(login_value or "", {}))
        original_login = str(seed.get("login") or login_value or "").strip()

        win = tk.Toplevel(frame)
        title_login = original_login or "nowy"
        win.title(f"Edycja profilu – {title_login}")
        ensure_theme_applied(win)
        try:
            win.transient(frame.winfo_toplevel())
        except Exception:
            pass
        try:
            win.grab_set()
        except Exception:
            pass

        form = ttk.Frame(win, padding=12)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        login_var = tk.StringVar(value=original_login)
        name_var = tk.StringVar(value=_profile_display_name(seed))
        role_var = tk.StringVar(value=_role_to_choice(seed.get("rola") or seed.get("role")))
        if role_var.get() not in ROLE_KEYS:
            role_var.set("operator")
        pin_var = tk.StringVar(value=str(seed.get("pin", "")))
        shift_mode_var = tk.StringVar(
            value=_shift_mode_label_from_code(seed.get("tryb_zmian", "111"))
        )
        disable_vars: dict[str, tk.BooleanVar] = {}
        current_disabled = set(seed.get("disabled_modules") or [])

        ttk.Label(form, text="Login:").grid(row=0, column=0, sticky="w")
        ttk.Label(
            form,
            textvariable=login_var,
            foreground="#6b7280",
        ).grid(row=0, column=1, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Nazwa:").grid(row=1, column=0, sticky="w")
        name_entry = ttk.Entry(form, textvariable=name_var)
        name_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Rola:").grid(row=2, column=0, sticky="w")
        role_combo = ttk.Combobox(
            form,
            values=ROLE_KEYS,
            textvariable=role_var,
            state="readonly",
        )
        role_combo.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="PIN:").grid(row=3, column=0, sticky="w")
        pin_entry = ttk.Entry(form, textvariable=pin_var)
        pin_entry.grid(row=3, column=1, sticky="ew", pady=4)
        # ==============================
        # SYSTEM ZMIAN (COMBO)
        # ==============================
        ttk.Label(form, text="System zmian:").grid(row=4, column=0, sticky="w")
        shift_combo = ttk.Combobox(
            form,
            textvariable=shift_mode_var,
            values=list(SHIFT_MODE_CHOICES.keys()),
            state="readonly",
        )
        shift_combo.grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(
            form,
            text="1 zmiana = 6:00–14:00 | 2 zmiana = 14:00–22:00",
            foreground="#6b7280",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # ==============================
        # WYŁĄCZONE MODUŁY
        # ==============================
        ttk.Label(form, text="Wyłączone moduły:").grid(
            row=7, column=0, sticky="w", pady=(10, 0)
        )
        row_offset = 8
        for i, (key, label) in enumerate(SIDEBAR_MODULES):
            var = tk.BooleanVar(value=(key in current_disabled))
            ttk.Checkbutton(form, text=label, variable=var).grid(
                row=row_offset + i, column=1, sticky="w"
            )
            disable_vars[key] = var

        modules_row = row_offset + len(SIDEBAR_MODULES)
        modules_frame, modules_refresh = make_modules_access_button(
            form,
            root,
            lambda: login_var.get().strip(),
        )
        modules_frame.grid(
            row=modules_row, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        login_var.trace_add("write", lambda *_: modules_refresh())
        modules_refresh()

        actions = ttk.Frame(form)
        actions.grid(
            row=modules_row + 1, column=0, columnspan=2, sticky="e", pady=(12, 0)
        )

        def _save() -> None:
            name_value = name_var.get().strip()
            if not name_value:
                messagebox.showerror(
                    "Brak nazwy",
                    "Podaj nazwę profilu.",
                    parent=win,
                )
                name_entry.focus_set()
                return

            role_choice = role_var.get().strip().lower()
            if role_choice not in ROLE_KEYS:
                role_choice = "operator"
                role_var.set("operator")

            pin_value = pin_var.get().strip()
            profiles_map = dict(state.get("profiles", {}))
            base = dict(seed)
            base["nazwa"] = name_value
            base["name"] = name_value
            base["display_name"] = name_value
            canonical_role = _choice_to_role(role_choice)
            base["rola"] = canonical_role
            base["role"] = canonical_role
            base["pin"] = pin_value
            # --- zapis systemu zmian ---
            selected_label = shift_mode_var.get()
            base["tryb_zmian"] = SHIFT_MODE_CHOICES.get(selected_label, "111")
            # --- zapis wyłączonych modułów ---
            base["disabled_modules"] = [k for k, v in disable_vars.items() if v.get()]
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            base["ostatnia_aktualizacja"] = timestamp

            current_login = login_var.get().strip()
            existing_keys = {key for key in profiles_map if key != original_login}
            if not current_login:
                slug = _slugify_login(name_value)
                candidate = slug
                index = 1
                while candidate in existing_keys:
                    index += 1
                    candidate = f"{slug}{index}"
                current_login = candidate
                login_var.set(current_login)
                modules_refresh()

            base["login"] = current_login
            if original_login and original_login != current_login:
                profiles_map.pop(original_login, None)
            profiles_map[current_login] = base

            try:
                _save_profiles_map(profiles_map)
            except Exception as exc:
                messagebox.showerror(
                    "Błąd zapisu",
                    f"Nie udało się zapisać profilu:\n{exc}",
                    parent=win,
                )
                return

            state["profiles"] = profiles_map
            _refresh_tree(select_login=current_login)
            try:
                root.event_generate("<<ProfilesSaved>>", when="tail")
            except Exception:
                pass
            win.destroy()

        ttk.Button(actions, text="Anuluj", command=win.destroy).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(actions, text="Zapisz", command=_save).pack(side="right")

        name_entry.focus_set()
        win.bind("<Return>", lambda _e: _save())
        win.bind("<Escape>", lambda _e: win.destroy())

    def _add_profile() -> None:
        _open_editor(None)

    def _edit_selected(_event=None) -> None:
        login_value = _selected_login()
        if not login_value:
            messagebox.showinfo(
                "Edycja",
                "Najpierw wybierz profil z listy.",
                parent=frame.winfo_toplevel(),
            )
            return
        _open_editor(login_value)

    def _delete_selected() -> None:
        login_value = _selected_login()
        if not login_value:
            messagebox.showinfo(
                "Usuń",
                "Najpierw wybierz profil z listy.",
                parent=frame.winfo_toplevel(),
            )
            return

        profiles_map = dict(state.get("profiles", {}))
        profile = profiles_map.get(login_value) or {}
        label = _profile_display_name(profile) or login_value
        if not messagebox.askyesno(
            "Usuń profil",
            f"Czy na pewno chcesz usunąć profil „{label}”?",
            parent=frame.winfo_toplevel(),
        ):
            return

        profiles_map.pop(login_value, None)
        try:
            _save_profiles_map(profiles_map)
        except Exception as exc:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się usunąć profilu:\n{exc}",
                parent=frame.winfo_toplevel(),
            )
            return

        state["profiles"] = profiles_map
        _refresh_tree()

    buttons = ttk.Frame(container)
    buttons.pack(fill="x", pady=(10, 0))
    ttk.Button(buttons, text="Dodaj", command=_add_profile).pack(side="left")
    ttk.Button(buttons, text="Edytuj", command=_edit_selected).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(buttons, text="Usuń", command=_delete_selected).pack(
        side="left", padx=(6, 0)
    )

    tree.bind("<Double-1>", _edit_selected)
    _refresh_tree()

    if tree.get_children():
        first = next(iter(tree.get_children()))
        tree.selection_set(first)
        tree.focus(first)

def uruchom_panel(root, frame, login=None, rola=None):
    return panel_uzytkownicy(root, frame, login, rola)
