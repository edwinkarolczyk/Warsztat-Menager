# Plik: gui_panel.py
# Wersja pliku: 1.6.17
# Zmiany 1.6.17:
# - Dodano przycisk w stopce otwierający changelog.
# - Zapamiętywanie czasu ostatniego obejrzenia changeloga.
# Poprzednio (1.6.16):
# - Dodano przycisk „Magazyn” (wymaga gui_magazyn.open_panel_magazyn)
# - Pasek nagłówka pokazuje kto jest zalogowany (label po prawej)
# - Reszta bez zmian względem 1.6.15
#
# Poprzednio (1.6.15):
# - Adapter zgodności do panelu zleceń.

import json
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, time, timedelta, timezone

from services.profile_service import get_user, save_user

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
# [PR-1165-MERGE-FIX] unikajmy zbyt szerokiego importu z start (ryzyko cyklu)
from start import CONFIG_MANAGER, open_settings_window
import gui_changelog
from logger import log_akcja
from profile_utils import SIDEBAR_MODULES

# --- PROFIL: nowy widok ---
try:
    from gui_profile import ProfileView
except Exception as e:  # pragma: no cover - import fallback
    print(
        f"[ERROR][PROFILE] Nie można zaimportować ProfileView z gui_profile.py: {e}"
    )
    ProfileView = None


def _get_app_version() -> str:
    """Zwróć numer wersji z ``__version__.py`` lub ``pyproject.toml``."""
    try:
        from __version__ import __version__  # type: ignore
        return __version__
    except Exception:
        try:
            import tomllib  # type: ignore
            with open("pyproject.toml", "rb") as fh:
                data = tomllib.load(fh)
            return data.get("project", {}).get("version", "dev")
        except Exception:
            return "dev"


APP_VERSION = _get_app_version()


def _load_last_visit(login: str) -> datetime:
    """Odczytaj datę ostatniej wizyty z profilu użytkownika."""
    user = get_user(login) or {}
    ts = user.get("ostatnia_wizyta")
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _save_last_visit(login: str, dt: datetime) -> None:
    """Zapisz datę ostatniej wizyty w profilu użytkownika."""
    user = get_user(login) or {"login": login}
    user["ostatnia_wizyta"] = (
        dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    save_user(user)


def _active_login(self) -> str:
    """Zwraca aktualny login użytkownika na potrzeby nagłówka profilu."""
    for attr in ("active_login", "current_user", "username", "_wm_login"):
        if hasattr(self, attr):
            value = getattr(self, attr)
            if value:
                return str(value)
    return "uzytkownik"


def _center_container(self):
    """Zwraca główny kontener na widoki (centralny panel)."""
    for attr in ("content", "main_content", "content_frame", "body"):
        if hasattr(self, attr):
            container = getattr(self, attr)
            if container is not None:
                return container
    return self


def _open_profile(self):
    """Wstawia nowy widok profilu do centralnego kontenera."""
    if ProfileView is None:
        print("[ERROR][PROFILE] Brak klasy ProfileView – sprawdź gui_profile.py")
        try:
            container = _center_container(self)
        except Exception:
            return
        if container is self:
            return
        try:
            for widget in container.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
            ttk.Label(
                container,
                text="Widok profilu jest niedostępny.",
                foreground="#e53935",
            ).pack(pady=20)
        except Exception:
            pass
        return
    try:
        container = _center_container(self)
        if container is self:
            raise RuntimeError("Nie znaleziono kontenera centralnego dla profilu")
        try:
            for widget in container.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        login = _active_login(self)
        view = ProfileView(container, login=login)
        try:
            if hasattr(self, "_show"):
                self._show(view)
            else:
                view.pack(fill="both", expand=True)
        except Exception:
            view.pack(fill="both", expand=True)

        print(f"[WM-DBG][PROFILE] Załadowano nowy widok profilu dla: {login}")
    except Exception as exc:
        print(f"[ERROR][PROFILE] Nie udało się otworzyć widoku profilu: {exc}")


try:
    from logger import log_akcja
except Exception:
    def log_akcja(msg: str):
        print(f"[LOG] {msg}")

# --- IMPORT ZLECEŃ Z ADAPTEREM ZGODNOŚCI ---
try:
    # oryginalna funkcja z gui_zlecenia: panel_zlecenia(parent, root=None, app=None, notebook=None)
    from gui_zlecenia import panel_zlecenia as _panel_zl_src

    def panel_zlecenia(root, frame, login=None, rola=None):
        """Adapter: zachowuje sygnaturę (root, frame, ...),
        a wewnątrz woła panel_zlecenia(parent, root, None, None) i pakuje wynik do frame.
        """
        # wyczyść miejsce docelowe
        clear_frame(frame)
        try:
            setattr(root, "_wm_login", login)
            setattr(root, "_wm_rola", rola)
        except Exception:
            pass
        try:
            tab = _panel_zl_src(frame, root, None, None)
        except TypeError:
            # fallback dla starszych wersji przyjmujących samo parent
            tab = _panel_zl_src(frame)
        # jeżeli panel zwraca ramkę – spakuj ją do content
        if isinstance(tab, (tk.Widget, ttk.Frame)):
            try:
                tab.pack(fill="both", expand=True)
            except Exception:
                pass
        else:
            # awaryjnie pokaż etykietę, żeby nie było pusto
            ttk.Label(frame, text="Panel Zleceń – załadowano").pack(pady=12)
except Exception:
    def panel_zlecenia(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel zleceń (fallback) – błąd importu gui_zlecenia").pack(pady=20)

# --- IMPORT NARZĘDZI Z CZYTELNYM TRACEBACKIEM ---
try:
    from gui_narzedzia import panel_narzedzia as _panel_narzedzia_real
    _PANEL_NARZ_ERR = None
    def panel_narzedzia(root, frame, login=None, rola=None):
        return _panel_narzedzia_real(root, frame, login, rola)
except Exception as e:
    import traceback
    _PANEL_NARZ_ERR = traceback.format_exc()
    def panel_narzedzia(root, frame, login=None, rola=None):
        clear_frame(frame)
        tk.Label(
            frame,
            text="Błąd importu gui_narzedzia.py:" + _PANEL_NARZ_ERR,
            fg="#e53935", justify="left", anchor="w"
        ).pack(padx=12, pady=12, anchor="w")

try:
    from gui_maszyny import panel_maszyny
except Exception:
    def panel_maszyny(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel maszyn").pack(pady=20)

try:
    from gui_uzytkownicy import panel_uzytkownicy
except Exception:
    def panel_uzytkownicy(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel użytkowników").pack(pady=20)

# --- IMPORT MAGAZYNU ---
from gui_magazyn import open_panel_magazyn


def panel_magazyn(root, frame, login=None, rola=None):
    """Adapter do ``open_panel_magazyn`` osadzający widok w kontenerze."""
    open_panel_magazyn(root, container=frame)


# ---------- Zmiany / czas pracy ----------

def _shift_bounds(dt: datetime):
    """Zwraca (start, end, label) aktywnej / najbliższej zmiany: I (06–14) lub II (14–22)."""
    t = dt.time()
    s1, e1 = time(6, 0), time(14, 0)
    s2, e2 = time(14, 0), time(22, 0)
    if s1 <= t < e1:
        return datetime.combine(dt.date(), s1), datetime.combine(dt.date(), e1), "I"
    if s2 <= t < e2:
        return datetime.combine(dt.date(), s2), datetime.combine(dt.date(), e2), "II"
    if t < s1:
        return datetime.combine(dt.date(), s1), datetime.combine(dt.date(), e1), "I"
    nxt = (dt + timedelta(days=1)).date()
    return datetime.combine(nxt, s1), datetime.combine(nxt, e1), "I"


def _shift_progress(now: datetime):
    """(percent, running) — procent w bieżącej zmianie, czy trwa."""
    s, e, *_ = _shift_bounds(now)
    total = (e - s).total_seconds()
    elapsed = (now - s).total_seconds()
    if elapsed < 0: return 0, False
    if elapsed > total: return 100, False
    return int((elapsed/total)*100), True

# ---------- Główny panel ----------

def uruchom_panel(root, login, rola):
    apply_theme(root)
    root.title(
        f"Warsztat Menager v{APP_VERSION} - zalogowano jako {login} ({rola})"
    )
    clear_frame(root)

    last_visit = _load_last_visit(login)
    profile = get_user(login) or {}
    disabled_modules = {
        str(m).strip().lower() for m in profile.get("disabled_modules", []) if m
    }
    markers: list[tk.Widget] = []
    menu_markers: list[tuple[tk.Menu, int, str]] = []

    def _clear_markers() -> None:
        nonlocal last_visit
        for dot in markers:
            try:
                dot.destroy()
            except Exception:
                pass
        markers.clear()
        for menu, idx, label in menu_markers:
            try:
                menu.entryconfig(idx, label=label, foreground="")
            except Exception:
                pass
        menu_markers.clear()
        last_visit = datetime.now(timezone.utc)
        _save_last_visit(login, last_visit)

    def _maybe_mark_button(widget: tk.Widget) -> None:
        lm = getattr(widget, "last_modified", None)
        if isinstance(lm, datetime) and lm > last_visit:
            try:
                bg = widget.cget("background")
            except tk.TclError:
                try:
                    bg = widget.master.cget("bg")
                except Exception:
                    bg = None
            dot_kwargs = {"text": "\u25CF", "fg": "#e53935"}
            if bg is not None:
                dot_kwargs["bg"] = bg
            dot = tk.Label(widget, **dot_kwargs)
            dot.place(relx=1, x=-4, y=4, anchor="ne")
            markers.append(dot)

    def _maybe_mark_menu(menu: tk.Menu, index: int) -> None:
        lm_map = getattr(menu, "last_modified", {})
        lm = lm_map.get(index)
        if isinstance(lm, datetime) and lm > last_visit:
            label = menu.entrycget(index, "label")
            menu.entryconfig(index, label=f"{label} \u25CF", foreground="#e53935")
            menu_markers.append((menu, index, label))

    def _show_about():
        messagebox.showinfo(
            "O programie", f"Warsztat Menager\nWersja {APP_VERSION}"
        )

    menubar = tk.Menu(root)
    actions_menu = tk.Menu(menubar, tearoff=False)
    actions_menu.add_command(label="Usuń znaczniki", command=_clear_markers)
    actions_menu.add_command(label="Mój profil…", command=lambda: _open_profile_entry())
    menubar.add_cascade(label="Akcje", menu=actions_menu)
    settings_menu = tk.Menu(menubar, tearoff=False)
    settings_menu.add_command(
        label="Ustawienia…",
        command=lambda: open_settings_window(root),
    )
    menubar.add_cascade(label="Ustawienia", menu=settings_menu)
    help_menu = tk.Menu(menubar, tearoff=False)
    help_menu.add_command(label="O programie", command=_show_about)
    help_menu.last_modified = {0: datetime(2025, 8, 1, tzinfo=timezone.utc)}
    menubar.add_cascade(label="Pomoc", menu=help_menu)
    root.config(menu=menubar)
    _maybe_mark_menu(help_menu, 0)

    side  = ttk.Frame(root, style="WM.Side.TFrame", width=220); side.pack(side="left", fill="y")
    main  = ttk.Frame(root, style="WM.TFrame");               main.pack(side="right", fill="both", expand=True)

    header  = ttk.Frame(main, style="WM.TFrame");      header.pack(fill="x", padx=12, pady=(10,6))
    ttk.Label(header, text="Panel główny", style="WM.H1.TLabel").pack(side="left")
    # NOWE: czytelny login/rola po prawej stronie nagłówka
    ttk.Label(header, text=f"{login} ({rola})", style="WM.Muted.TLabel").pack(side="right")

    content = ttk.Frame(main, style="WM.Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=6)
    setattr(root, "content", content)
    setattr(root, "main_content", content)
    setattr(root, "active_login", login)
    setattr(root, "current_user", login)
    setattr(root, "username", login)

    footer  = ttk.Frame(main, style="WM.TFrame");      footer.pack(fill="x", padx=12, pady=(6,10))
    footer_left = ttk.Frame(footer, style="WM.TFrame"); footer_left.pack(side="left")
    footer_btns = ttk.Frame(footer, style="WM.TFrame"); footer_btns.pack(side="right")
    # lewa część: pasek zmiany (1/3 szerokości)
    shift_wrap = ttk.Frame(footer_left, style="WM.Card.TFrame"); shift_wrap.pack(side="left")
    ttk.Label(shift_wrap, text="Zmiana", style="WM.Card.TLabel").pack(anchor="w", padx=8, pady=(6,0))
    CANVAS_W, CANVAS_H = 480, 18
    shift = tk.Canvas(shift_wrap, width=CANVAS_W, height=CANVAS_H, highlightthickness=0, bd=0, bg="#1b1f24")
    shift.pack(padx=8, pady=6)
    shift_info = ttk.Label(shift_wrap, text="", style="WM.Muted.TLabel"); shift_info.pack(anchor="w", padx=8, pady=(0,6))

    # prawa część: stałe przyciski
    def _logout():
        """Powrót do ekranu logowania + opcjonalne oznaczenie wylogowania."""
        # heartbeat logout if available
        try:
            from presence import heartbeat
            heartbeat(login, rola, logout=True)
        except Exception:
            pass
        try:
            import gui_logowanie
            gui_logowanie.ekran_logowania(root)
        except Exception:
            try:
                root.destroy()
            except Exception:
                pass
    changelog_win = {"ref": None}
    btn_changelog = None

    def _has_unseen_changelog(last_seen: str | None) -> bool:
        try:
            seen_dt = datetime.fromisoformat(last_seen) if last_seen else datetime.min
        except ValueError:
            seen_dt = datetime.min
        try:
            with open("CHANGELOG.md", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("##"):
                        m = re.search(r"-\s*(\d{4}-\d{2}-\d{2})", line)
                        if m:
                            try:
                                dt = datetime.fromisoformat(m.group(1))
                            except ValueError:
                                dt = None
                            if dt and dt > seen_dt:
                                return True
        except Exception:
            return False
        return False

    def _close_changelog(_event=None):
        win = changelog_win.get("ref")
        if win is not None and win.winfo_exists():
            try:
                win.destroy()
            except Exception:
                pass
        changelog_win["ref"] = None
        if btn_changelog and btn_changelog.winfo_exists():
            btn_changelog.config(text="Pokaż zmiany")
        _clear_markers()
        try:
            CONFIG_MANAGER.set(
                "changelog.last_viewed",
                datetime.now().isoformat(timespec="seconds"),
                who=login,
            )
            CONFIG_MANAGER.save_all()
        except Exception:
            pass

    def _toggle_changelog(auto: bool = False):
        win = changelog_win.get("ref")
        if win is not None and win.winfo_exists():
            _close_changelog()
            return
        last_seen = None
        try:
            last_seen = CONFIG_MANAGER.get("changelog.last_viewed")
        except Exception:
            last_seen = None
        if auto and not _has_unseen_changelog(last_seen):
            return
        try:
            win = gui_changelog.show_changelog(
                master=root, last_seen=last_seen
            )
            changelog_win["ref"] = win
            if btn_changelog and btn_changelog.winfo_exists():
                btn_changelog.config(text="Ukryj zmiany")
            win.protocol("WM_DELETE_WINDOW", _close_changelog)
            for child in win.winfo_children():
                if isinstance(child, tk.Button) and child.cget("text") == "Zamknij":
                    child.config(command=_close_changelog)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć changeloga: {e}")

    ttk.Button(
        footer_btns, text="Zamknij program", command=root.quit, style="WM.Side.TButton"
    ).pack(side="right")
    btn_changelog = ttk.Button(
        footer_btns,
        text="Pokaż zmiany",
        command=_toggle_changelog,
        style="WM.Side.TButton",
    )
    btn_changelog.last_modified = datetime(2025, 9, 1, tzinfo=timezone.utc)
    btn_changelog.pack(side="right", padx=(6, 0))
    _maybe_mark_button(btn_changelog)
    root.after(100, lambda: _toggle_changelog(auto=True))
    ttk.Button(
        footer_btns, text="Wyloguj", command=_logout, style="WM.Side.TButton"
    ).pack(side="right", padx=(6, 0))
    # --- licznik automatycznego wylogowania ---
    try:
        cm = globals().get("CONFIG_MANAGER")
        _logout_min = int(cm.get("auth.session_timeout_min", 30)) if cm else 30
    except Exception:
        _logout_min = 30
    _logout_total = max(0, _logout_min * 60)
    _logout_deadline = datetime.now() + timedelta(seconds=_logout_total)
    logout_job = {"id": None}
    # label pokazujący czas pozostały do automatycznego wylogowania
    def _logout_tick():
        if not logout_label.winfo_exists():
            logout_job["id"] = None
            return
        remaining = int((_logout_deadline - datetime.now()).total_seconds())
        if remaining <= 0:
            logout_label.config(text="Automatyczne wylogowanie za: 0 min")
            logout_job["id"] = None
            _logout()
            return
        minutes = max(0, remaining // 60)
        logout_label.config(
            text=f"Automatyczne wylogowanie za: {minutes} min"
        )
        logout_job["id"] = root.after(1000, _logout_tick)

    def _on_logout_destroy(_e=None):
        if logout_job["id"]:
            try:
                root.after_cancel(logout_job["id"])
            except Exception:
                pass
            logout_job["id"] = None

    def _reset_logout_timer(_event=None):
        nonlocal _logout_deadline
        try:
            cm = globals().get("CONFIG_MANAGER")
            new_min = int(cm.get("auth.session_timeout_min", 30)) if cm else 30
        except Exception:
            new_min = 30
        total = max(0, new_min * 60)
        _logout_deadline = datetime.now() + timedelta(seconds=total)
        if logout_job["id"]:
            try:
                root.after_cancel(logout_job["id"])
            except Exception:
                pass
            logout_job["id"] = None
        _logout_tick()
        try:
            from start import restart_user_activity_monitor
            restart_user_activity_monitor(total)
        except Exception:
            pass

    btn_reset = ttk.Button(
        footer_btns,
        text="Zresetuj licznik",
        command=_reset_logout_timer,
        style="WM.Side.TButton",
    )
    btn_reset.pack(side="right", padx=(6, 0))
    logout_label = ttk.Label(footer_btns, text="", style="WM.Muted.TLabel")
    logout_label.pack(side="right", padx=(0, 6))

    _logout_tick()
    logout_label.bind("<Destroy>", _on_logout_destroy)
    root.bind("<<AuthTimeoutChanged>>", _reset_logout_timer, add="+")

    # --- bezpieczny timer paska zmiany ---
    shift_job = {"id": None}

    def draw_shift_bar():
        if not shift.winfo_exists(): return
        try:
            shift.delete("all")
            now = datetime.now()
            percent, running = _shift_progress(now)
            s, e, *_ = _shift_bounds(now)

            # tło paska
            bg = "#23272e"; bar_bg = "#2a2f36"
            shift.create_rectangle(0, 0, CANVAS_W, CANVAS_H, fill=bar_bg, outline=bg)

            # lewa zielona (zrobione), prawa szara (pozostało)
            done_w = int(CANVAS_W * (percent / 100.0))
            done_color   = "#34a853" if running and percent > 0 else "#3a4a3f"
            remain_color = "#8d8d8d"

            if done_w > 0:
                shift.create_rectangle(0, 0, done_w, CANVAS_H, fill=done_color, outline=done_color)
            if done_w < CANVAS_W:
                shift.create_rectangle(done_w, 0, CANVAS_W, CANVAS_H, fill=remain_color, outline=remain_color)

            shift_info.config(text=f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}    {percent}%")
        except tk.TclError:
            return

    def _tick():
        if not shift.winfo_exists():
            shift_job["id"] = None; return
        draw_shift_bar()
        shift_job["id"] = root.after(1000, _tick)

    def _on_shift_destroy(_e=None):
        if shift_job["id"]:
            try:
                root.after_cancel(shift_job["id"])
            except Exception as e:
                log_akcja(f"[PANEL] Błąd after_cancel: {e}")
            shift_job["id"] = None

    draw_shift_bar()
    shift_job["id"] = root.after(1000, _tick)
    shift.bind("<Destroy>", _on_shift_destroy)

    # nawigacja
    def wyczysc_content():
        clear_frame(content)

    def otworz_panel(funkcja, nazwa):
        wyczysc_content(); log_akcja(f"Kliknięto: {nazwa}")
        try:
            funkcja(root, content, login, rola)
        except Exception as e:
            log_akcja(f"Błąd przy otwieraniu panelu {nazwa}: {e}")
            ttk.Label(content, text=f"Błąd otwierania panelu: {e}", foreground="#e53935").pack(pady=20)

    # --- role helpers + quick open profile ---
    def _is_admin_role(r):
        return str(r).lower() in {"admin","kierownik","brygadzista","lider"}

    def _open_profile_entry():
        setattr(root, "content", content)
        setattr(root, "main_content", content)
        setattr(root, "active_login", login)
        setattr(root, "current_user", login)
        setattr(root, "username", login)
        try:
            _open_profile(root)
        except Exception as e:
            log_akcja(f"Błąd otwierania panelu profilu: {e}")
            clear_frame(content)
            ttk.Label(
                content,
                text=f"Błąd otwierania panelu: {e}",
                foreground="#e53935",
            ).pack(pady=20)

    def _open_feedback():
        win = tk.Toplevel(root)
        win.title("Wyślij opinię")
        ttk.Label(win, text="Twoja opinia:").pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        txt = tk.Text(win, width=60, height=10)
        txt.pack(padx=10, pady=6)

        def _submit():
            message = txt.get("1.0", "end").strip()
            if not message:
                messagebox.showwarning("Brak treści", "Wpisz treść opinii.")
                return
            payload = {
                "login": login,
                "rola": rola,
                "ts": datetime.now().isoformat(),
                "message": message,
            }
            sent = False
            try:
                import requests

                cm = globals().get("CONFIG_MANAGER")
                url = cm.get("feedback.url", "").strip() if cm else ""
                if url:
                    resp = requests.post(url, json=payload, timeout=5)
                    resp.raise_for_status()
                    sent = True
            except Exception:
                sent = False
            if not sent:
                os.makedirs("data", exist_ok=True)
                path = os.path.join("data", "opinie.json")
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    data = []
                data.append(payload)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Dziękujemy", "Twoja opinia została przesłana."
            )
            win.destroy()

        ttk.Button(win, text="Wyślij", command=_submit).pack(pady=(0, 10))

    def _load_mag_alerts():
        """Lista pozycji magazynowych poniżej progu."""
        try:
            with open("data/magazyn/surowce.json", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return []
        out = []
        if isinstance(data, dict):
            items = ((k, v) for k, v in data.items() if isinstance(v, dict))
        else:
            items = (
                (rec.get("kod"), rec)
                for rec in data
                if isinstance(rec, dict)
            )
        for kod, rec in items:
            if not kod:
                continue
            try:
                stan = float(rec.get("stan", 0))
                prog = float(rec.get("prog_alertu", 0))
            except Exception:
                continue
            if stan <= prog:
                nm = rec.get("nazwa", "")
                out.append(f"{kod} ({nm})")
        return out

    # przyciski boczne
    start_panel = None
    start_name = ""
    admin_roles = {"admin", "kierownik", "brygadzista", "lider"}
    is_admin = str(rola).strip().lower() in admin_roles

    def _build_sidebar(initial: bool = False) -> None:
        nonlocal profile, disabled_modules, start_panel, start_name
        clear_frame(side)
        profile = get_user(login) or {}
        disabled_modules = {
            str(m).strip().lower()
            for m in profile.get("disabled_modules", [])
            if m
        }
        start_panel = None
        start_name = ""
        for key, label in SIDEBAR_MODULES:
            if key in disabled_modules:
                continue
            if key in {"uzytkownicy", "ustawienia"} and not is_admin:
                continue
            if key == "profil" and is_admin:
                continue
            pad = (12, 6) if start_panel is None else 6
            if key == "zlecenia":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda f=panel_zlecenia, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 8, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = panel_zlecenia
                    start_name = f"{label} (start)"
            elif key == "narzedzia":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda f=panel_narzedzia, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 7, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = panel_narzedzia
                    start_name = f"{label} (start)"
            elif key == "maszyny":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda f=panel_maszyny, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 6, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = panel_maszyny
                    start_name = f"{label} (start)"
            elif key == "magazyn":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda f=panel_magazyn, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 5, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = panel_magazyn
                    start_name = f"{label} (start)"
            elif key == "feedback":
                btn = ttk.Button(
                    side, text=label, command=_open_feedback, style="WM.Side.TButton"
                )
                btn.last_modified = datetime(2025, 3, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
            elif key == "uzytkownicy":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda f=panel_uzytkownicy, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 2, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = panel_uzytkownicy
                    start_name = f"{label} (start)"
            elif key == "ustawienia":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=lambda: open_settings_window(root),
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 1, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = lambda r, f, l, ro: open_settings_window(root)
                    start_name = f"{label} (start)"
            elif key == "profil":
                btn = ttk.Button(
                    side,
                    text=label,
                    command=_open_profile_entry,
                    style="WM.Side.TButton",
                )
                btn.last_modified = datetime(2025, 1, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                _maybe_mark_button(btn)
                if start_panel is None:
                    start_panel = lambda r, f, l, ro: _open_profile_entry()
                    start_name = f"{label} (start)"

        alerts = _load_mag_alerts() if "magazyn" not in disabled_modules else []
        if alerts:
            frm_alert = ttk.Frame(side, style="WM.Card.TFrame")
            frm_alert.pack(padx=10, pady=6, fill="x")
            ttk.Label(
                frm_alert, text="Alerty magazynowe", style="WM.Card.TLabel"
            ).pack(anchor="w", padx=8, pady=(6, 0))
            for a in alerts:
                ttk.Label(frm_alert, text=a, style="WM.Muted.TLabel").pack(
                    anchor="w", padx=8
                )
        root.update_idletasks()
        if initial and start_panel is not None:
            otworz_panel(start_panel, start_name)
        root.update_idletasks()

    _build_sidebar(initial=True)
    root.bind("<<SidebarReload>>", lambda _e: _build_sidebar(initial=False))

# eksportowane dla logowania
__all__ = ["uruchom_panel", "_shift_bounds", "_shift_progress"]

# ⏹ KONIEC KODU
