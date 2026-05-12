# WM-VERSION: 0.1
# version: 1.0
# Plik: gui_logowanie.py (beta)
# Zmiany 1.4.12.1:
# - Przywrócony układ z 1.4.12 (logo wyśrodkowane, PIN pośrodku, przycisk "Zamknij program" przyklejony na dole, stopka z wersją).
# - Dodany pasek postępu zmiany (1/3 szerokości ekranu, wyśrodkowany)
# - Bezpieczny timer (after) + anulowanie przy Destroy
# - Spójny wygląd z motywem (apply_theme), brak pływania elementów

import json
import importlib
import logging
import os
import subprocess
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

try:  # opcjonalny Pillow
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - brak Pillow
    Image = None
    ImageTk = None

from config_manager import ConfigManager
from grafiki.shifts_schedule import who_is_on_now
from profiles_store import load_profiles_users, resolve_profiles_path
from updates_utils import load_last_update_info, remote_branch_exists
from utils import error_dialogs

wm_root_paths = (
    importlib.import_module("core.root_paths")
    if importlib.util.find_spec("core.root_paths")
    else None
)

from services.profile_service import (
    ProfileService,
    authenticate,
    ensure_brygadzista_account,
    find_first_brygadzista,
)
import profile_utils
# [ATTENDANCE] minimalna ewidencja obecności (plan / log / potwierdzenie)
import attendance_utils

# Pasek zmiany i przejście do panelu głównego
import gui_panel  # używamy: _shift_bounds, _shift_progress, uruchom_panel

# Motyw
from ui_theme import apply_theme_tree

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

try:  # kompatybilność z testami monkeypatchującymi tkinter
    TclError = tk.TclError
except AttributeError:  # pragma: no cover - fallback dla stubów
    TclError = Exception

# Alias zachowany dla kompatybilności testów
apply_theme = apply_theme_tree


def _save_root_choice_to_config(root_path: str) -> None:
    """Zapisz główny ROOT WM z ekranu logowania.

    Nowy mechanizm ROOT zapisuje wybór do wm_root.json.
    Nie zapisujemy już paths.anchor_root / paths.data_root z poziomu logowania,
    bo to miesza ConfigManager z core.root_paths.
    """

    normalized = str(Path(root_path).expanduser().resolve())
    if wm_root_paths is not None:
        root_file = wm_root_paths.root_file_path()
        root_file.parent.mkdir(parents=True, exist_ok=True)
        with root_file.open("w", encoding="utf-8") as handle:
            json.dump({"root": normalized}, handle, ensure_ascii=False, indent=2)
        os.environ["WM_ROOT"] = normalized
        os.environ["WM_DATA_ROOT"] = str(Path(normalized) / "data")
        os.environ["WM_CONFIG_FILE"] = str(Path(normalized) / "config.json")
        try:
            wm_root_paths.ensure_root_tree()
        except Exception:
            logger.exception("[WM-ERR][LOGIN] ensure_root_tree failed after ROOT change")
        print(f"[WM-ROOT][LOGIN] zapisano ROOT_FILE={root_file} root={normalized}")
        return

    cfg = ConfigManager()
    cfg.set("paths.anchor_root", normalized)
    cfg.set("paths.data_root", str(Path(normalized) / "data"))
    cfg.save_all() if hasattr(cfg, "save_all") else cfg.save()


def _choose_root_from_login() -> None:
    """Mały, ukryty wybór głównego katalogu WM z ekranu logowania."""

    try:
        messagebox.showinfo(
            "Wybór ROOT WM",
            "Wskaż główny folder danych WM.\n\n"
            "Nie wybieraj pojedynczego podfolderu typu:\n"
            "- data\n"
            "- magazyn\n"
            "- narzedzia\n"
            "- zlecenia\n\n"
            "Może to być dowolny folder na dysku albo pendrive.",
        )
        selected = filedialog.askdirectory(title="Wybierz główny folder danych WM")
        if not selected:
            return

        _save_root_choice_to_config(selected)
        messagebox.showinfo(
            "ROOT WM ustawiony",
            "Ustawiono główny folder WM:\n\n"
            f"{Path(selected).expanduser().resolve()}\n\n"
            "Najlepiej uruchom logowanie/program ponownie, żeby wszystkie "
            "moduły czytały dane z nowego ROOT.",
        )
    except Exception as exc:
        logger.exception("[WM-ERR][LOGIN] Nie udało się ustawić ROOT WM")
        try:
            messagebox.showwarning(
                "ROOT WM",
                "Nie udało się zapisać głównego folderu WM.\n\n"
                f"Szczegóły: {exc}",
            )
        except Exception:
            pass


def _looks_like_default_admin_only(entries: list[dict]) -> bool:
    if len(entries) != 1:
        return False
    entry = entries[0] if isinstance(entries[0], dict) else {}
    login = str(entry.get("login", "") or "").strip().lower()
    return login == "admin"


def _legacy_profile_candidates() -> list[Path]:
    candidates = [
        BASE_DIR / "data" / "profiles.json",
        BASE_DIR / "profiles.json",
        BASE_DIR / "uzytkownicy.json",
        Path.cwd() / "data" / "profiles.json",
        Path.cwd() / "profiles.json",
        Path.cwd() / "uzytkownicy.json",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            key = os.path.normcase(str(resolved))
            if key not in seen:
                seen.add(key)
                out.append(resolved)
        except Exception:
            pass
    return out


def _best_legacy_profiles_source(
    *,
    exclude_path: Path | None = None,
) -> tuple[Path | None, list[dict]]:
    excluded = None
    if exclude_path is not None:
        try:
            excluded = os.path.normcase(str(exclude_path.resolve()))
        except Exception:
            excluded = None

    best_entries: list[dict] = []
    best_source: Path | None = None
    for candidate in _legacy_profile_candidates():
        try:
            if not candidate.exists():
                continue
            candidate_norm = os.path.normcase(str(candidate.resolve()))
            if excluded and candidate_norm == excluded:
                continue
            entries = load_profiles_users(path=candidate)
            if len(entries) > len(best_entries):
                best_entries = entries
                best_source = candidate
        except Exception:
            continue
    return best_source, best_entries


def _maybe_migrate_profiles_to_root(root_path: Path) -> None:
    """Przenieś legacy profile do ROOT, jeśli ROOT ma tylko domyślnego admina."""

    try:
        root_entries = load_profiles_users(path=root_path) if root_path.exists() else []
    except Exception:
        root_entries = []

    if root_entries and not _looks_like_default_admin_only(root_entries):
        return

    best_source, best_entries = _best_legacy_profiles_source(exclude_path=root_path)

    if not best_entries or _looks_like_default_admin_only(best_entries):
        return

    root_path.parent.mkdir(parents=True, exist_ok=True)
    with root_path.open("w", encoding="utf-8") as handle:
        json.dump({"users": best_entries}, handle, ensure_ascii=False, indent=2)
    print(
        f"[WM-ROOT][LOGIN] zmigrowano profile: {best_source} -> {root_path} "
        f"users={len(best_entries)}"
    )


def _profiles_path() -> Path:
    root_active = bool(
        str(os.environ.get("WM_ROOT", "")).strip()
        or str(os.environ.get("WM_DATA_ROOT", "")).strip()
    )

    if wm_root_paths is not None and root_active:
        try:
            resolved = wm_root_paths.path_profiles()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            _maybe_migrate_profiles_to_root(resolved)
            try:
                users = load_profiles_users(path=resolved) if resolved.exists() else []
            except Exception:
                users = []
            print(
                f"[WM-ROOT][PROFILES][ACTIVE] path={resolved} "
                f"exists={1 if resolved.exists() else 0} users={len(users)}"
            )
            print(f"[WM-ROOT][LOGIN] profiles_path={resolved}")
            return resolved
        except Exception:
            logger.exception("[WM-ERR][LOGIN] root_paths.path_profiles failed")

    best_legacy_source, best_legacy_entries = _best_legacy_profiles_source()
    if best_legacy_source and not _looks_like_default_admin_only(best_legacy_entries):
        print(f"[WM-ROOT][LOGIN] profiles_path_legacy={best_legacy_source}")
        return best_legacy_source

    try:
        cfg = ConfigManager()
    except Exception:
        cfg = None
    resolved = resolve_profiles_path(cfg)
    try:
        users = load_profiles_users(path=resolved) if resolved.exists() else []
    except Exception:
        users = []
    print(
        f"[WM-ROOT][PROFILES][ACTIVE] path={resolved} "
        f"exists={1 if resolved.exists() else 0} users={len(users)}"
    )
    print(f"[WM-ROOT][LOGIN] profiles_path_fallback={resolved}")
    return resolved


def _is_profile_active(entry: dict) -> bool:
    active = entry.get("active")
    if isinstance(active, bool) and not active:
        return False
    if isinstance(active, str) and active.strip():
        if active.strip().lower() in {"0", "false", "no", "nie", "inactive"}:
            return False
    status = str(entry.get("status", "")).strip().lower()
    if status in {"nieaktywny", "zablokowany", "dezaktywowany", "inactive"}:
        return False
    return True


# ====== SHIFT HELPERS (1111/1212/2121 + start rotacji + dni pracy) ======
def _parse_date_ymd(s: str):
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_ts_z(s: str):
    # akceptuj "2025-12-27T14:18:05.086063Z"
    try:
        ss = str(s).strip()
        if ss.endswith("Z"):
            ss = ss[:-1] + "+00:00"
        return datetime.fromisoformat(ss)
    except Exception:
        return None


def _slot_now(now: datetime):
    t = now.time()
    if t >= datetime.strptime("06:00", "%H:%M").time() and t < datetime.strptime(
        "14:00", "%H:%M"
    ).time():
        return "RANO"
    if t >= datetime.strptime("14:00", "%H:%M").time() and t < datetime.strptime(
        "22:00", "%H:%M"
    ).time():
        return "POPO"
    return None


def _shift_bounds_for_slot(now: datetime, slot: str):
    d = now.date()
    if slot == "RANO":
        s = datetime.combine(d, datetime.strptime("06:00", "%H:%M").time())
        e = datetime.combine(d, datetime.strptime("14:00", "%H:%M").time())
        return s, e
    if slot == "POPO":
        s = datetime.combine(d, datetime.strptime("14:00", "%H:%M").time())
        e = datetime.combine(d, datetime.strptime("22:00", "%H:%M").time())
        return s, e
    return None, None


def _user_workdays(profile: dict):
    wd = profile.get("workdays", None) or profile.get("dni_pracy", None)
    if isinstance(wd, list) and wd:
        # oczekujemy [0..6]
        out = []
        for x in wd:
            try:
                xi = int(x)
                if 0 <= xi <= 6:
                    out.append(xi)
            except Exception:
                pass
        return out if out else [0, 1, 2, 3, 4]
    return [0, 1, 2, 3, 4]  # domyślnie pn-pt


def _user_shift_mode(profile: dict):
    # preferuj tryb_zmian, fallback zmiana_plan/shift_mode
    for k in ("tryb_zmian", "zmiana_plan", "shift_mode"):
        v = profile.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _global_rotation_start() -> date | None:
    """
    Globalna data startu rotacji A/B.
    Preferencja:
    - config: attendance.rotation_start
    - fallback: config presence.rotation_start
    """
    try:
        cfg = ConfigManager()
        for key in ("attendance.rotation_start", "presence.rotation_start"):
            raw = cfg.get(key)
            if isinstance(raw, str) and raw.strip():
                parsed = _parse_date_ymd(raw.strip())
                if parsed:
                    return parsed
    except Exception:
        pass
    return None


def _rotation_week_ab(now: datetime):
    """
    Zwraca aktywny tydzień rotacji: 'A' albo 'B'.
    Jeśli brak daty startu, domyślnie 'A'.
    """
    start = _global_rotation_start()
    if not start:
        return "A"
    try:
        delta_days = (now.date() - start).days
        week_idx = max(0, delta_days // 7)
        return "A" if week_idx % 2 == 0 else "B"
    except Exception:
        return "A"


def _user_shift_mode_for_week(profile: dict, week_ab: str):
    """
    Pobierz tryb zmian użytkownika dla tygodnia A/B.
    Fallback do starego tryb_zmian, jeśli nowe pola nie są ustawione.
    """
    suffix = "A" if str(week_ab).upper() == "A" else "B"
    for key in (
        f"tryb_zmian_{suffix}",
        f"zmiana_plan_{suffix}",
        f"shift_mode_{suffix}",
    ):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _user_shift_mode(profile)


def _user_shift_start(profile: dict):
    # preferuj rotacja_start/shift_start
    for k in ("rotacja_start", "shift_start"):
        v = profile.get(k)
        if isinstance(v, str) and v.strip():
            d = _parse_date_ymd(v)
            if d:
                return d
    return None


def _slot_for_user(profile: dict, now: datetime):
    # jeśli nie pracuje dziś – None
    if now.weekday() not in _user_workdays(profile):
        return None

    # POPRAWKA: tryb zmian interpretujemy jako CYKL TYGODNIOWY (np. 121 / 212 / 111)
    # a nie jako rozkład dni tygodnia
    mode = _user_shift_mode(profile)
    seq = [c for c in mode if c in ("1", "2")]
    if not seq:
        return None

    # liczymy który to tydzień od startu rotacji
    start = _global_rotation_start()
    if not start:
        week_idx = 0
    else:
        delta_days = (now.date() - start).days
        week_idx = max(0, delta_days // 7)

    # wybieramy zmianę dla całego tygodnia
    c = seq[week_idx % len(seq)]
    return "RANO" if c == "1" else "POPO"


def _display_name(profile: dict):
    im = str(profile.get("imie", "") or "").strip()
    na = str(profile.get("nazwisko", "") or "").strip()
    if im or na:
        return f"{im} {na}".strip()
    return str(profile.get("login", "") or "—").strip() or "—"


def _present_logins_in_current_shift(profiles: list[dict], now: datetime, slot: str):
    s, e = _shift_bounds_for_slot(now, slot)
    if not s or not e:
        return set()
    out = set()
    for p in profiles:
        if not isinstance(p, dict):
            continue
        ts = _parse_ts_z(p.get("ostatnia_wizyta", ""))
        if not ts:
            continue
        # porównujemy czas w lokalnym "now" – prosto: traktujemy ts jako porównywalny
        # (minimal patch; bez pełnej strefy czasu)
        try:
            # jeśli ts ma tz, a s/e nie, rzutujemy na naive:
            if ts.tzinfo is not None:
                ts_cmp = ts.replace(tzinfo=None)
            else:
                ts_cmp = ts
        except Exception:
            ts_cmp = ts
        if s <= ts_cmp <= e:
            login = str(p.get("login", "") or "").strip().lower()
            if login:
                out.add(login)
    return out


def _planned_users_for_slot(profiles: list[dict], now: datetime, slot: str):
    planned = []
    planned_logins = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        if not _is_profile_active(p):
            continue
        if _slot_for_user(p, now) == slot:
            planned.append(_display_name(p))
            planned_logins.append(str(p.get("login", "") or "").strip().lower())
    return planned, set([x for x in planned_logins if x])
# ====== END SHIFT HELPERS ======


def _load_profiles() -> list[dict]:
    """Wczytaj profile użytkowników z obsługą błędów UI."""

    path = _profiles_path()
    logger.debug("[WM-DBG][LOGIN] profiles_path = %s", path)

    try:
        entries = load_profiles_users(path=path)
    except FileNotFoundError:
        logger.error("[WM-ERR][LOGIN] profiles file not found: %s", path)
        error_dialogs.show_error_dialog(
            "Profile", f"Brak pliku profili. Utwórz go lub skopiuj ponownie.\n{path}"
        )
        return []
    except json.JSONDecodeError as exc:
        logger.error("[WM-ERR][LOGIN] invalid JSON in profiles file: %s", path)
        logger.error("[WM-ERR][LOGIN] exception: %r", exc)
        error_dialogs.show_error_dialog(
            "Profile", f"Plik profili jest uszkodzony i wymaga naprawy.\n{path}"
        )
        return []
    except ValueError as exc:
        logger.error("[WM-ERR][LOGIN] invalid structure in profiles file: %s", path)
        logger.error("[WM-ERR][LOGIN] exception: %r", exc)
        error_dialogs.show_error_dialog(
            "Profile", f"Nieobsługiwany format profili: {exc}\n{path}"
        )
        return []

    def _normalize_entry(entry: dict, login_hint: str | None = None) -> dict:
        if login_hint and not entry.get("login"):
            entry = {**entry, "login": login_hint}
        login_value = entry.get("login") or entry.get("user") or entry.get("name")
        if login_value:
            entry = {**entry, "login": str(login_value).strip()}
        return entry

    normalized = [_normalize_entry(item) for item in entries if isinstance(item, dict)]
    active = [entry for entry in normalized if _is_profile_active(entry)]
    if not active:
        logger.warning(
            "[WM-WARN][LOGIN] no active profiles loaded (0 users) from %s",
            path,
        )
    return active


 # -- informacje o ostatniej aktualizacji dostarcza moduł updates_utils --

# --- zmienne globalne dla kontrolki PIN i okna ---
entry_pin = None
entry_login = None
root_global = None
_on_login_cb = None
_profiles_by_login: dict[str, dict] = {}
_profiles_widget_ref: tk.Widget | None = None


def _widget_ready(widget: tk.Widget | None) -> bool:
    """Sprawdź, czy kontrolka tkinter nadal istnieje."""

    if widget is None:
        return False
    if not hasattr(widget, "winfo_exists"):
        return True
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False

def ekran_logowania(root=None, on_login=None, update_available=False):
    """Ekran logowania: logo u góry na środku, box PIN w centrum,
       pasek postępu zmiany (1/3 szerokości) wyśrodkowany,
       na samym dole przycisk 'Zamknij program' + stopka z wersją.

       Parametry:
           root: opcjonalne istniejące okno główne tkinter.
           on_login: opcjonalny callback (login, rola, extra=None) wywoływany po poprawnym logowaniu.
           update_available (bool): jeśli True, pokaż komunikat o dostępnej aktualizacji.
    """
    global entry_login, entry_pin, root_global, _on_login_cb
    if root is None or not _widget_ready(root):
        if root is not None and not _widget_ready(root):
            logger.warning(
                "Przekazano zniszczone okno root do ekranu logowania – tworzę nowe"
            )
        root = tk.Tk()
    root_global = root
    _on_login_cb = on_login
    cfg = ConfigManager()

    # wyczyść i ustaw motyw
    try:
        children = list(root.winfo_children())
    except tk.TclError:
        logger.warning(
            "Okno root zostało zniszczone podczas przygotowania logowania – tworzę nowe"
        )
        root = tk.Tk()
        root_global = root
        children = []
    for w in children:
        try:
            w.destroy()
        except tk.TclError:
            continue
    apply_theme(root)

    # pełny ekran i tytuł
    root.title("Warsztat Menager")
    root.attributes("-fullscreen", True)

    # bazowe rozmiary ekranu
    szer, wys = root.winfo_screenwidth(), root.winfo_screenheight()

    # tło z pliku grafiki/login_bg.png
    bg_path = os.path.join("grafiki", "login_bg.png")
    fallback = True
    if not (Image and ImageTk):
        logger.debug("Tło logowania pominięte – brak modułu Pillow")
    elif not os.path.exists(bg_path):
        logger.debug("Tło logowania pominięte – plik %s nie istnieje", bg_path)
    else:
        try:
            img = Image.open(bg_path).resize((szer, wys), Image.LANCZOS)
            bg_image = ImageTk.PhotoImage(img)
            bg_label = tk.Label(root, image=bg_image)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            bg_label.image = bg_image  # pin referencji
            bg_label.lower()
            fallback = False
        except Exception:  # pragma: no cover - opcjonalne tło
            logger.debug("Nie można załadować tła logowania %s", bg_path, exc_info=True)

    if fallback:
        root.configure(bg="#0f1113")
        ttk.Label(root, text="Warsztat Menager", style="WM.H1.TLabel").pack(
            pady=(32, 8)
        )
    else:
        # --- GÓRA: LOGO (wyśrodkowane, stabilne) ---
        top = ttk.Frame(root, style="WM.TFrame")
        top.pack(fill="x", pady=(32, 8))

        # logo (jeśli jest) — używamy tk.Label dla image
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path).resize((300, 100), Image.LANCZOS)
                logo_img = ImageTk.PhotoImage(img)
                lbl_logo = tk.Label(
                    top,
                    image=logo_img,
                    bg=root["bg"] if "bg" in root.keys() else "#0f1113",
                )
                lbl_logo.image = logo_img  # pin referencji
                lbl_logo.pack()
            except Exception:
                # brak PIL lub błąd pliku — po prostu nazwa
                ttk.Label(top, text="Warsztat Menager", style="WM.H1.TLabel").pack()
        else:
            ttk.Label(top, text="Warsztat Menager", style="WM.H1.TLabel").pack()

    # --- ŚRODEK: BOX PIN (wyśrodkowany stabilnie) ---
    center = ttk.Frame(root, style="WM.TFrame")
    center.pack(fill="both", expand=True)

    box = ttk.Frame(center, style="WM.Card.TFrame", padding=16)
    box.place(relx=0.5, rely=0.45, anchor="center")  # trochę wyżej niż idealne 0.5, by było miejsce na pasek

    style = ttk.Style(root)
    bg = root["bg"] if "bg" in root.keys() else "#0f1113"
    try:
        style.configure(
            "Transparent.TEntry",
            fieldbackground=bg,
            background=bg,
            borderwidth=0,
        )
    except TypeError:
        pass

    ttk.Label(box, text="Login:", style="WM.H2.TLabel").pack(pady=(8, 6))
    profile_entries: list[tuple[str, dict]] = []
    for profile in _load_profiles():
        login_value = str(profile.get("login", "")).strip()
        if login_value:
            profile_entries.append((login_value, profile))
    # zachowaj unikalne loginy z zachowaniem kolejności, sortując casefoldem
    seen_logins: set[str] = set()
    ordered_logins: list[str] = []
    login_profiles_map: dict[str, dict] = {}
    for login_value, profile in sorted(
        profile_entries, key=lambda item: item[0].casefold()
    ):
        normalized = login_value.casefold()
        if normalized in seen_logins:
            continue
        seen_logins.add(normalized)
        ordered_logins.append(login_value)
        login_profiles_map[normalized] = profile

    global _profiles_by_login, _profiles_widget_ref
    _profiles_by_login = login_profiles_map
    _profiles_widget_ref = None

    last_user = cfg.get("ostatni_uzytkownik") if hasattr(cfg, "get") else None
    if not isinstance(last_user, str):
        last_user = ""
    try:
        login_var = tk.StringVar(value="")
    except AttributeError:
        class _SimpleVar:
            def __init__(self, value: str = ""):
                self._value = value

            def set(self, value: str) -> None:
                self._value = value

            def get(self) -> str:
                return self._value

        login_var = _SimpleVar("")
    combobox_cls = getattr(ttk, "Combobox", ttk.Entry)
    if ordered_logins:
        entry_login = combobox_cls(
            box,
            textvariable=login_var,
            values=ordered_logins,
            width=24,
            state="readonly",
        )
    else:
        entry_login = combobox_cls(box, textvariable=login_var, width=24)
    entry_login.pack(ipadx=10, ipady=6)
    _profiles_widget_ref = entry_login if _widget_ready(entry_login) else None
    if last_user and any(last_user.strip() == item for item in ordered_logins):
        login_var.set(last_user.strip())
    elif ordered_logins:
        login_var.set(ordered_logins[0])

    def _focus_pin(_event=None):
        if _widget_ready(entry_pin):
            try:
                entry_pin.focus_set()
                entry_pin.selection_range(0, tk.END)
            except (TclError, AttributeError):
                pass

    entry_login.bind("<<ComboboxSelected>>", _focus_pin)

    ttk.Label(box, text="Podaj PIN:", style="WM.H2.TLabel").pack(pady=(8, 6))
    entry_pin = ttk.Entry(box, show="*", width=22, style="Transparent.TEntry")
    entry_pin.pack(ipadx=10, ipady=6)
    _focus_pin()
    ttk.Button(box, text="Zaloguj", command=logowanie, style="WM.Side.TButton").pack(pady=16)
    entry_pin.bind("<Return>", lambda e: logowanie())
    if cfg.get("auth.pinless_brygadzista", False):
        ttk.Button(
            box,
            text="Logowanie bez PIN",
            command=_login_pinless,
            style="WM.Side.TButton",
        ).pack(pady=(0, 16))

    # --- PASEK POSTĘPU ZMIANY (1/3 szer., wyśrodkowany) ---
    prefooter = ttk.Frame(root, style="WM.TFrame")
    prefooter.pack(fill="x", pady=(0, 10))

    wrap = ttk.Frame(prefooter, style="WM.Card.TFrame")
    wrap.pack()  # centralnie

    bottom_banner = ttk.Frame(wrap, style="WM.Card.TFrame", padding=(12, 6))
    bottom_banner.pack(fill="x", pady=(0, 8))

    shift_label_bottom = ttk.Label(
        bottom_banner, text="", style="WM.Banner.TLabel", anchor="w"
    )
    shift_label_bottom.pack(fill="x")

    users_box_bottom = ttk.Frame(bottom_banner, style="WM.TFrame")
    users_box_bottom.pack(fill="x", pady=(2, 0))

    def _update_banner():
        now = datetime.now()
        slot = _slot_now(now)
        week_ab = _rotation_week_ab(now)

        for w in users_box_bottom.winfo_children():
            w.destroy()

        if slot is None:
            shift_label_bottom.config(text="Poza godzinami zmian")
            ttk.Label(
                users_box_bottom, text="—", style="WM.Muted.TLabel", anchor="w"
            ).pack(anchor="w")
            return

        s, e = _shift_bounds_for_slot(now, slot)
        label = "Poranna" if slot == "RANO" else "Popołudniowa"
        shift_label_bottom.config(
            text=(
                f"{label} {s.strftime('%H:%M')}–{e.strftime('%H:%M')}   "
                f"|   Tydzień rotacji: {week_ab}"
            )
        )

        profiles = _load_profiles()
        planned_names, planned_logins = _planned_users_for_slot(profiles, now, slot)
        # [ATTENDANCE] zapisz "plan" do ewidencji
        try:
            attendance_utils.ensure_planned(now.date().isoformat(), slot, planned_logins)
        except Exception:
            pass
        # [ATTENDANCE] map login -> display_name (do statusów i do okna brygadzisty)
        by_login = {}
        for p in profiles:
            lg = str(p.get("login", "") or "").strip().lower()
            if lg:
                by_login[lg] = _display_name(p)

        # [ATTENDANCE] kolory (kropka + tekst)
        COLOR_GREY = "#9aa0a6"  # plan
        COLOR_YELLOW = "#f59e0b"  # zalogował (do potwierdzenia)
        COLOR_GREEN = "#22c55e"  # potwierdzony
        COLOR_RED = "#ef4444"  # brak po 4h

        def _paint_for(login_lower: str) -> str:
            try:
                st = attendance_utils.status_for(
                    now.date().isoformat(),
                    slot,
                    login_lower,
                    shift_start=s,
                    now=now,
                    grace_hours=4,
                )
            except Exception:
                st = "PLANNED"
            if st == "CONFIRMED":
                return COLOR_GREEN
            if st == "LOGGED":
                return COLOR_YELLOW
            if st == "OVERDUE":
                return COLOR_RED
            return COLOR_GREY

        # PLAN
        ttk.Label(
            users_box_bottom, text="Plan:", style="WM.Muted.TLabel", anchor="w"
        ).pack(anchor="w")
        if planned_logins:
            for lg in sorted(planned_logins):
                name = by_login.get(lg, lg)
                color = _paint_for(lg)
                lbl = ttk.Label(
                    users_box_bottom, text=f"● {name}", style="WM.TLabel", anchor="w"
                )
                try:
                    lbl.configure(foreground=color)
                except Exception:
                    logger.exception("[ATTENDANCE] mark_login failed (pinless login)")
                lbl.pack(anchor="w")
        else:
            ttk.Label(
                users_box_bottom, text="—", style="WM.Muted.TLabel", anchor="w"
            ).pack(anchor="w")

    _update_banner()

    ttk.Label(wrap, text="Zmiana", style="WM.Card.TLabel").pack(
        anchor="w", padx=8, pady=(0, 2)
    )

    CANVAS_W = max(int(szer/3), 420)  # 1/3 ekranu, min. 420
    CANVAS_H = 18
    shift = tk.Canvas(wrap, width=CANVAS_W, height=CANVAS_H,
                      highlightthickness=0, bd=0, bg="#1b1f24")
    shift.pack(padx=8, pady=6)

    info = ttk.Label(wrap, text="", style="WM.Muted.TLabel")
    info.pack(anchor="w", padx=8, pady=(0, 8))

    # --- bezpieczny timer paska ---
    shift_job = {"id": None}

    def draw_login_shift():
        # Canvas mógł zniknąć
        if not shift.winfo_exists():
            return
        try:
            shift.delete("all")
            now = datetime.now()
            percent, running = gui_panel._shift_progress(now)
            s, e, *_ = gui_panel._shift_bounds(now)

            # tło paska
            bg = "#23272e"
            bar_bg = "#2a2f36"
            shift.create_rectangle(0, 0, CANVAS_W, CANVAS_H, fill=bar_bg, outline=bg)

            # wypełnienie "jak było": z lewej zielony (zrobione), z prawej szary (pozostało)
            done_w = int(CANVAS_W * (percent / 100.0))
            done_color   = "#34a853" if running and percent > 0 else "#3a4a3f"
            remain_color = "#8d8d8d"

            if done_w > 0:
                shift.create_rectangle(0, 0, done_w, CANVAS_H, fill=done_color, outline=done_color)
            if done_w < CANVAS_W:
                shift.create_rectangle(done_w, 0, CANVAS_W, CANVAS_H, fill=remain_color, outline=remain_color)

            info.config(text=f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}    {percent}%")
        except tk.TclError:
            # Canvas zniknął między sprawdzeniem a rysowaniem — ignoruj
            return

    def _tick():
        if not shift.winfo_exists():
            shift_job["id"] = None
            return
        draw_login_shift()
        _update_banner()
        shift_job["id"] = root.after(1000, _tick)

    def _on_destroy(_e=None):
        if shift_job["id"]:
            try:
                root.after_cancel(shift_job["id"])
            except Exception:
                pass
            shift_job["id"] = None

    draw_login_shift()
    shift_job["id"] = root.after(1000, _tick)
    shift.bind("<Destroy>", _on_destroy)

    # --- DÓŁ: przycisk Zamknij + stopka wersji (stale przyklejone) ---
    bottom = ttk.Frame(root, style="WM.TFrame")
    bottom.pack(side="bottom", fill="x", pady=(0, 12))

    # przycisk na samym dole — stałe miejsce
    ttk.Button(bottom, text="Zamknij program", command=zamknij, style="WM.Side.TButton").pack()
    # stopka
    ttk.Label(root, text="Warsztat Menager – beta", style="WM.Muted.TLabel").pack(side="bottom", pady=(0, 6))
    ttk.Button(
        root,
        text="⚙ root",
        command=_choose_root_from_login,
        style="WM.Side.TButton",
    ).pack(side="bottom", pady=(0, 2))
    update_text, _ = load_last_update_info()
    lbl_update = ttk.Label(root, text=update_text, style="WM.Muted.TLabel")
    lbl_update.pack(side="bottom", pady=(0, 2))
    remote = cfg.get("updates.remote", "origin")
    branch = cfg.get("updates.branch", "Rozwiniecie")
    try:
        if remote_branch_exists(remote, branch):
            subprocess.run(["git", "fetch", remote, branch], check=True)
            remote_commit = subprocess.check_output(
                ["git", "rev-parse", f"{remote}/{branch}"], text=True
            ).strip()
            local_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
            status = "Aktualna" if local_commit == remote_commit else "Nieaktualna"
            colour = "green" if status == "Aktualna" else "red"
            lbl_update.configure(
                text=f"{update_text} – {status}", foreground=colour
            )
        else:
            logging.warning(
                "Remote branch %s/%s not found; skipping fetch", remote, branch
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        lbl_update.configure(text=update_text)
    if update_available:
        ttk.Label(
            root,
            text="Dostępna aktualizacja – uruchom 'git pull'",
            style="WM.Muted.TLabel",
        ).pack(side="bottom", pady=(0, 2))

    return root

def _login_pinless():
    try:
        user = find_first_brygadzista()
        if not user:
            for profile in _load_profiles():
                role = str(profile.get("rola", "")).strip().lower()
                if role == "brygadzista":
                    user = {
                        "login": profile.get("login"),
                        "rola": profile.get("rola", "brygadzista"),
                        "status": profile.get("status", ""),
                        "nieobecny": profile.get("nieobecny", False),
                    }
                    break
        if user:
            login_key = user.get("login")
            rola = user.get("rola", "brygadzista")
            if login_key:
                ProfileService.set_active_user(str(login_key))
                # [ATTENDANCE] zapisz logowanie (slot z zegara, jeśli jesteśmy w godzinach zmian)
                try:
                    now = datetime.now()
                    slot_now = _slot_now(now)
                    if slot_now in ("RANO", "POPO"):
                        attendance_utils.mark_login(
                            now.date().isoformat(),
                            slot_now,
                            str(login_key),
                            now.isoformat(timespec="seconds"),
                        )
                except Exception:
                    pass
                # [ATTENDANCE] jeśli brygadzista – pokaż digest do potwierdzeń / braków
                try:
                    if str(rola or "").strip().lower() == "brygadzista":
                        now = datetime.now()
                        slot_now = _slot_now(now)
                        if slot_now in ("RANO", "POPO"):
                            profiles = _load_profiles()
                            _, planned_logins = _planned_users_for_slot(
                                profiles, now, slot_now
                            )
                            s, _e = _shift_bounds_for_slot(now, slot_now)
                            login_to_name = {}
                            for p in profiles:
                                lg = str(p.get("login", "") or "").strip().lower()
                                if lg:
                                    login_to_name[lg] = _display_name(p)
                except Exception:
                    logger.exception(
                        "[ATTENDANCE] prepare brygadzista modal failed (pinless login)"
                    )
                else:
                    # pokaż okno po przejściu UI w stabilny stan (żeby nie ginęło przy uruchamianiu panelu)
                    try:
                        if str(rola or "").strip().lower() == "brygadzista":
                            now = datetime.now()
                            slot_now = _slot_now(now)
                            if slot_now in ("RANO", "POPO"):
                                profiles = _load_profiles()
                                _, planned_logins = _planned_users_for_slot(
                                    profiles, now, slot_now
                                )
                                s, _e = _shift_bounds_for_slot(now, slot_now)
                                login_to_name = {}
                                for p in profiles:
                                    lg = str(p.get("login", "") or "").strip().lower()
                                    if lg:
                                        login_to_name[lg] = _display_name(p)

                                def _open_att_modal():
                                    attendance_utils.open_brygadzista_modal(
                                        root_global,
                                        title="Potwierdzenie obecności",
                                        date_ymd=now.date().isoformat(),
                                        slot=slot_now,
                                        planned_logins=planned_logins,
                                        login_to_name=login_to_name,
                                        shift_start=s,
                                        now=now,
                                        bryg_login=str(login_key),
                                    )

                                try:
                                    root_global.after(150, _open_att_modal)
                                except Exception:
                                    _open_att_modal()
                    except Exception:
                        logger.exception(
                            "[ATTENDANCE] open brygadzista modal failed (pinless login)"
                        )
            if _on_login_cb:
                try:
                    _on_login_cb(login_key, rola, None)
                except Exception as err:
                    logging.exception("Error in login callback")
                    error_dialogs.show_error_dialog(
                        "Błąd", f"Błąd w callbacku logowania: {err}"
                    )
            else:
                gui_panel.uruchom_panel(root_global, login_key, rola)
            return
        error_dialogs.show_error_dialog("Błąd", "Nie znaleziono brygadzisty")
    except Exception as e:
        error_dialogs.show_error_dialog("Błąd", f"Błąd podczas logowania: {e}")


def logowanie():
    if not _widget_ready(entry_login) or not _widget_ready(entry_pin):
        logging.debug("Wywołanie logowania po zniszczeniu kontrolek logowania")
        return

    login_display = entry_login.get().strip() if _widget_ready(entry_login) else ""
    if not login_display:
        error_dialogs.show_error_dialog("Błąd", "Wybierz użytkownika z listy")
        if _widget_ready(entry_login):
            try:
                entry_login.focus_set()
            except (TclError, AttributeError):
                pass
        return

    login = login_display.lower()
    pin = entry_pin.get().strip()
    if not pin:
        error_dialogs.show_error_dialog("Błąd", "Podaj PIN")
        if _widget_ready(entry_pin):
            try:
                entry_pin.focus_set()
                entry_pin.selection_range(0, tk.END)
            except (TclError, AttributeError):
                pass
        return
    try:
        if hasattr(profile_utils, "refresh_users_file"):
            profile_utils.refresh_users_file()
        user = authenticate(login, pin)
        normalized_key = login_display.casefold()
        selected_profile = None
        if _profiles_by_login:
            selected_profile = _profiles_by_login.get(normalized_key)
            if (
                entry_login is _profiles_widget_ref
                and selected_profile is None
                and _profiles_by_login
            ):
                error_dialogs.show_error_dialog("Błąd", "Wybrany użytkownik nie istnieje")
                return
        if selected_profile is None:
            for profile in _load_profiles():
                profile_login = str(profile.get("login", "")).strip()
                if profile_login.casefold() == normalized_key:
                    selected_profile = profile
                    break
        if not user:
            if selected_profile is None:
                error_dialogs.show_error_dialog("Błąd", "Nieprawidłowy login lub PIN")
                return
            stored_pin = str(selected_profile.get("pin", "")).strip()
            stored_password = str(selected_profile.get("haslo", "")).strip()
            if pin and (pin == stored_pin or pin == stored_password):
                user = {
                    "login": selected_profile.get("login", login_display),
                    "rola": selected_profile.get("rola", "pracownik"),
                    "status": selected_profile.get("status", ""),
                    "nieobecny": selected_profile.get("nieobecny", False),
                    "active": selected_profile.get("active", True),
                }
            else:
                error_dialogs.show_error_dialog("Błąd", "Nieprawidłowy PIN")
                if _widget_ready(entry_pin):
                    try:
                        entry_pin.focus_set()
                        entry_pin.selection_range(0, tk.END)
                    except (TclError, AttributeError):
                        pass
                return
        if user:
            login_key = user.get("login", login)
            status = str(user.get("status", "")).strip().lower()
            if user.get("active") is False or status in {"nieaktywny", "zablokowany"}:
                error_dialogs.show_error_dialog(
                    "Błąd", "Konto użytkownika jest nieaktywne"
                )
                return
            if login_key:
                ProfileService.set_active_user(str(login_key))
                try:
                    cfg = ConfigManager()
                    cfg.set("ostatni_uzytkownik", str(login_key), who="logowanie")
                    cfg.save_all()
                except Exception:
                    logger.exception("Nie udało się zapisać ostatniego użytkownika")
            # Ostrzeżenie: logowanie poza własną zmianą / dniem pracy (bez blokowania)
            try:
                now = datetime.now()
                slot_now = _slot_now(now)
                if slot_now:
                    profiles = _load_profiles()
                    prof = None
                    for p in profiles:
                        if (
                            str(p.get("login", "")).strip().lower()
                            == str(login_key).strip().lower()
                        ):
                            prof = p
                            break
                    if prof:
                        slot_user = _slot_for_user(prof, now)
                        if slot_user is None:
                            messagebox.showwarning(
                                "Uwaga – zmiana",
                                "Dziś nie jesteś zaplanowany do pracy (dni pracy).",
                            )
                            # [ATTENDANCE][ALERT] brak planu dziś
                            attendance_utils.add_alert(
                                now.date().isoformat(),
                                kind="NO_PLAN_TODAY",
                                login=str(login_key),
                                msg="Logowanie w dzień bez planu (dni pracy).",
                                meta={"slot_now": slot_now, "slot_user": None},
                                ts_iso=now.isoformat(timespec="seconds"),
                            )
                        elif slot_user != slot_now:
                            messagebox.showwarning(
                                "Uwaga – zmiana", "Logujesz się poza swoją zmianą."
                            )
                            # [ATTENDANCE][ALERT] logowanie poza zmianą
                            attendance_utils.add_alert(
                                now.date().isoformat(),
                                kind="OUTSIDE_SHIFT",
                                login=str(login_key),
                                msg=(
                                    "Zalogował się poza zmianą "
                                    f"(plan: {slot_user}, teraz: {slot_now})."
                                ),
                                meta={"slot_now": slot_now, "slot_user": slot_user},
                                ts_iso=now.isoformat(timespec="seconds"),
                            )
            except Exception:
                pass
            if user.get("nieobecny") or status in {"nieobecny", "urlop", "l4"}:
                error_dialogs.show_error_dialog(
                    "Błąd", "Użytkownik oznaczony jako nieobecny"
                )
                return
            # [ATTENDANCE] zapisz logowanie dopiero po zaliczeniu kontroli nieobecności/urlopu/L4
            try:
                now_att = datetime.now()
                slot_now_att = _slot_now(now_att)
                if slot_now_att in ("RANO", "POPO"):
                    attendance_utils.mark_login(
                        now_att.date().isoformat(),
                        slot_now_att,
                        str(login_key),
                        now_att.isoformat(timespec="seconds"),
                    )
            except Exception:
                logger.exception("[ATTENDANCE] mark_login failed (PIN login)")
            if (
                str(login_key).strip().lower()
                == profile_utils.DEFAULT_ADMIN_LOGIN
                and pin == profile_utils.DEFAULT_ADMIN_PASSWORD
            ):
                try:
                    ensure_brygadzista_account()
                except Exception:
                    logger.exception("[LOGIN] Nie udało się utworzyć konta brygadzisty")
            rola = user.get("rola", "pracownik")
            # [ATTENDANCE] brygadzista dostaje info i może potwierdzić (zielony) tych, co się zalogowali (żółty)
            try:
                if str(rola or "").strip().lower() == "brygadzista":
                    now = datetime.now()
                    slot_now = _slot_now(now)
                    if slot_now in ("RANO", "POPO"):
                        profiles = _load_profiles()
                        _, planned_logins = _planned_users_for_slot(
                            profiles, now, slot_now
                        )
                        s, _e = _shift_bounds_for_slot(now, slot_now)
                        login_to_name = {}
                        for p in profiles:
                            lg = str(p.get("login", "") or "").strip().lower()
                            if lg:
                                login_to_name[lg] = _display_name(p)
            except Exception:
                logger.exception(
                    "[ATTENDANCE] prepare brygadzista modal failed (PIN login)"
                )
            else:
                # pokaż okno po przejściu UI w stabilny stan (żeby nie ginęło przy uruchamianiu panelu)
                try:
                    if str(rola or "").strip().lower() == "brygadzista":
                        now = datetime.now()
                        slot_now = _slot_now(now)
                        if slot_now in ("RANO", "POPO"):
                            profiles = _load_profiles()
                            _, planned_logins = _planned_users_for_slot(
                                profiles, now, slot_now
                            )
                            s, _e = _shift_bounds_for_slot(now, slot_now)
                            login_to_name = {}
                            for p in profiles:
                                lg = str(p.get("login", "") or "").strip().lower()
                                if lg:
                                    login_to_name[lg] = _display_name(p)

                            def _open_att_modal():
                                attendance_utils.open_brygadzista_modal(
                                    root_global,
                                    title="Potwierdzenie obecności",
                                    date_ymd=now.date().isoformat(),
                                    slot=slot_now,
                                    planned_logins=planned_logins,
                                    login_to_name=login_to_name,
                                    shift_start=s,
                                    now=now,
                                    bryg_login=str(login_key),
                                )

                            try:
                                root_global.after(150, _open_att_modal)
                            except Exception:
                                _open_att_modal()
                except Exception:
                    logger.exception(
                        "[ATTENDANCE] open brygadzista modal failed (PIN login)"
                    )
            if _on_login_cb:
                try:
                    _on_login_cb(login_key, rola, None)
                except Exception as err:
                    logging.exception("Error in login callback")
                    error_dialogs.show_error_dialog(
                        "Błąd", f"Błąd w callbacku logowania: {err}"
                    )
            else:
                gui_panel.uruchom_panel(root_global, login_key, rola)
            return
        error_dialogs.show_error_dialog("Błąd", "Nieprawidłowy login lub PIN")
    except Exception as e:
        error_dialogs.show_error_dialog("Błąd", f"Błąd podczas logowania: {e}")

def zamknij():
    # Zamknij zawsze z dołu, bez pływania
    try:
        root_global.destroy()
    finally:
        os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    ekran_logowania(root)
    root.mainloop()
