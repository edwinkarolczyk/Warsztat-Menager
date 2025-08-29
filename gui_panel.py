# Plik: gui_panel.py
# Wersja pliku: 1.6.16
# Zmiany 1.6.16:
# - Dodano przycisk „Magazyn” (wymaga gui_magazyn.open_panel_magazyn)
# - Pasek nagłówka pokazuje kto jest zalogowany (label po prawej)
# - Reszta bez zmian względem 1.6.15
#
# Poprzednio (1.6.15):
# - Adapter zgodności do panelu zleceń.

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, time, timedelta

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
from auth.roles import Role, has_role


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

try:
    import gui_profile
except Exception:
    gui_profile = None

try:
    from ustawienia_systemu import panel_ustawien
except Exception as e:
    log_akcja(f"Błąd importu ustawień: {e}")

    def panel_ustawien(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(
            frame,
            text=f"Ustawienia systemu – błąd importu: {e}"
        ).pack(pady=20)

# --- IMPORT MAGAZYNU ---
from gui_magazyn import panel_magazyn


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

    def _show_about():
        messagebox.showinfo(
            "O programie", f"Warsztat Menager\nWersja {APP_VERSION}"
        )

    menubar = tk.Menu(root)
    help_menu = tk.Menu(menubar, tearoff=False)
    help_menu.add_command(label="O programie", command=_show_about)
    menubar.add_cascade(label="Pomoc", menu=help_menu)
    root.config(menu=menubar)

    side  = ttk.Frame(root, style="WM.Side.TFrame", width=220); side.pack(side="left", fill="y")
    main  = ttk.Frame(root, style="WM.TFrame");               main.pack(side="right", fill="both", expand=True)

    header  = ttk.Frame(main, style="WM.TFrame");      header.pack(fill="x", padx=12, pady=(10,6))
    ttk.Label(header, text="Panel główny", style="WM.H1.TLabel").pack(side="left")
    # NOWE: czytelny login/rola po prawej stronie nagłówka
    ttk.Label(header, text=f"{login} ({rola})", style="WM.Muted.TLabel").pack(side="right")

    content = ttk.Frame(main, style="WM.Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=6)

    footer  = ttk.Frame(main, style="WM.TFrame");      footer.pack(fill="x", padx=12, pady=(6,10))
    # lewa część: pasek zmiany (1/3 szerokości)
    shift_wrap = ttk.Frame(footer, style="WM.Card.TFrame"); shift_wrap.pack(side="left")
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
    btns = ttk.Frame(footer, style="WM.TFrame"); btns.pack(side="right")
    ttk.Button(btns, text="Wyloguj", command=_logout, style="WM.Side.TButton").pack(side="right", padx=(6,0))
    ttk.Button(btns, text="Zamknij program", command=root.quit, style="WM.Side.TButton").pack(side="right")
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
    logout_label = ttk.Label(btns, text="", style="WM.Muted.TLabel")
    logout_label.pack(side="right", padx=(0, 6))

    def _logout_tick():
        if not logout_label.winfo_exists():
            logout_job["id"] = None
            return
        remaining = int((_logout_deadline - datetime.now()).total_seconds())
        if remaining <= 0:
            logout_label.config(text="Wylogowanie za 0 s")
            logout_job["id"] = None
            _logout()
            return
        m, s = divmod(remaining, 60)
        if m:
            logout_label.config(text=f"Wylogowanie za {m} min {s} s")
        else:
            logout_label.config(text=f"Wylogowanie za {s} s")
        logout_job["id"] = root.after(1000, _logout_tick)

    def _on_logout_destroy(_e=None):
        if logout_job["id"]:
            try:
                root.after_cancel(logout_job["id"])
            except Exception:
                pass
            logout_job["id"] = None

    _logout_tick()
    logout_label.bind("<Destroy>", _on_logout_destroy)

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
            try: root.after_cancel(shift_job["id"])
            except Exception: pass
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
        return has_role(r, Role.ADMIN, Role.KIEROWNIK, Role.BRYGADZISTA, Role.LIDER)

    def _open_profil():
        # clear content
        clear_frame(content)
        try:
            if gui_profile is None:
                raise RuntimeError("Brak modułu gui_profile")
            gui_profile.uruchom_panel(root, content, login, rola)
        except Exception as e:
            log_akcja(f"Błąd otwierania panelu: {e}")
            ttk.Label(content, text=f"Błąd otwierania panelu: {e}", foreground="#e53935").pack(pady=20)
    
    # przyciski boczne
    ttk.Button(side, text="Zlecenia",  command=lambda: otworz_panel(panel_zlecenia, "Zlecenia"),  style="WM.Side.TButton").pack(padx=10, pady=(12,6), fill="x")
    ttk.Button(side, text="Narzędzia", command=lambda: otworz_panel(panel_narzedzia, "Narzędzia"), style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")
    ttk.Button(side, text="Maszyny",   command=lambda: otworz_panel(panel_maszyny, "Maszyny"),    style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")
    # Wejście do Magazynu
    ttk.Button(side, text="Magazyn",   command=lambda: otworz_panel(panel_magazyn, "Magazyn"),   style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")

    if _is_admin_role(rola):
        ttk.Button(side, text="Użytkownicy", command=lambda: otworz_panel(panel_uzytkownicy, "Użytkownicy"), style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")
        try:
            from ustawienia_systemu import panel_ustawien as _pust
            ttk.Button(side, text="Ustawienia",  command=lambda: otworz_panel(_pust, "Ustawienia"), style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")
        except Exception:
            pass
    else:
        ttk.Button(side, text="Profil", command=_open_profil, style="WM.Side.TButton").pack(padx=10, pady=6, fill="x")
    root.update_idletasks()
    otworz_panel(panel_zlecenia, "Zlecenia (start)")
    root.update_idletasks()

# eksportowane dla logowania
__all__ = ["uruchom_panel", "_shift_bounds", "_shift_progress"]

# ⏹ KONIEC KODU
