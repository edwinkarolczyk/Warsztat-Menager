# Wersja pliku: 1.4.12.1
# Plik: gui_logowanie.py
# Zmiany 1.4.12.1:
# - Przywrócony układ z 1.4.12 (logo wyśrodkowane, PIN pośrodku, przycisk "Zamknij program" przyklejony na dole, stopka z wersją).
# - Dodany pasek postępu zmiany (1/3 szerokości ekranu, wyśrodkowany)
# - Bezpieczny timer (after) + anulowanie przy Destroy
# - Spójny wygląd z motywem (apply_theme), brak pływania elementów

import os
import logging
import subprocess
import tkinter as tk
from datetime import datetime
from PIL import Image, ImageTk
from tkinter import ttk, messagebox
from pathlib import Path

from config_manager import ConfigManager
from grafiki.shifts_schedule import who_is_on_now
from updates_utils import load_last_update_info, remote_branch_exists
from utils import error_dialogs

from services.profile_service import authenticate, find_first_brygadzista

# Pasek zmiany i przejście do panelu głównego
import gui_panel  # używamy: _shift_bounds, _shift_progress, uruchom_panel

# Motyw
from ui_theme import apply_theme_tree

BASE_DIR = Path(__file__).resolve().parent

# Alias zachowany dla kompatybilności testów
apply_theme = apply_theme_tree


 # -- informacje o ostatniej aktualizacji dostarcza moduł updates_utils --

# --- zmienne globalne dla kontrolki PIN i okna ---
entry_pin = None
entry_login = None
root_global = None
_on_login_cb = None

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
    if root is None:
        root = tk.Tk()
    root_global = root
    _on_login_cb = on_login
    cfg = ConfigManager()

    # wyczyść i ustaw motyw
    for w in root.winfo_children():
        w.destroy()
    apply_theme(root)

    # pełny ekran i tytuł
    root.title("Warsztat Menager")
    root.attributes("-fullscreen", True)

    # bazowe rozmiary ekranu
    szer, wys = root.winfo_screenwidth(), root.winfo_screenheight()

    # tło z pliku grafiki/login_bg.png
    bg_path = BASE_DIR / "grafiki" / "login_bg.png"
    bg_failed = False
    try:
        if bg_path.exists():
            img = Image.open(bg_path).resize((szer, wys), Image.LANCZOS)
            bg_image = ImageTk.PhotoImage(img)
            bg_label = tk.Label(root, image=bg_image)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            bg_label.image = bg_image  # pin referencji
            bg_label.lower()
        else:
            raise FileNotFoundError(bg_path)
    except Exception as e:  # pragma: no cover - tylko logowanie
        logging.debug("[WM-DBG] login_bg fallback: %s", e)
        root.configure(bg="#121212")
        bg_failed = True

    # --- GÓRA: LOGO (wyśrodkowane, stabilne) ---
    top = ttk.Frame(root, style="WM.TFrame")
    top.pack(fill="x", pady=(32, 8))

    # logo (jeśli jest) — używamy tk.Label dla image lub fallback
    logo_path = BASE_DIR / "logo.png"
    if bg_failed:
        ttk.Label(top, text="Warsztat Menager", style="WM.H1.TLabel").pack()
    elif logo_path.exists():
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
    entry_login = ttk.Entry(box, width=22, style="Transparent.TEntry")
    entry_login.pack(ipadx=10, ipady=6)
    if hasattr(entry_login, "focus_set"):
        entry_login.focus_set()

    ttk.Label(box, text="Podaj PIN:", style="WM.H2.TLabel").pack(pady=(8, 6))
    entry_pin = ttk.Entry(box, show="*", width=22, style="Transparent.TEntry")
    entry_pin.pack(ipadx=10, ipady=6)
    ttk.Button(box, text="Zaloguj", command=logowanie, style="WM.Side.TButton").pack(pady=16)
    root.bind("<Return>", lambda e: logowanie())
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
        try:
            info = who_is_on_now(datetime.now())
        except Exception as e:
            logging.exception("who_is_on_now error")
            shift_label_bottom.config(text="Grafik zmian: błąd")
            for w in users_box_bottom.winfo_children():
                w.destroy()
            return

        for w in users_box_bottom.winfo_children():
            w.destroy()

        if not info.get("slot"):
            shift_label_bottom.config(text="Poza godzinami zmian")
            ttk.Label(
                users_box_bottom,
                text="Brak aktywnych użytkowników",
                style="WM.Muted.TLabel",
                anchor="w",
            ).pack(anchor="w")
            return

        s, e, *_ = gui_panel._shift_bounds(datetime.now())
        label = "Poranna" if info["slot"] == "RANO" else "Popołudniowa"
        shift_label_bottom.config(
            text=f"{label} {s.strftime('%H:%M')}–{e.strftime('%H:%M')}"
        )
        if info["users"]:
            for name in info["users"]:
                ttk.Label(
                    users_box_bottom, text=name, style="WM.TLabel", anchor="w"
                ).pack(anchor="w")
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
    ttk.Label(root, text="Warsztat Menager – Wersja 1.4.12.1", style="WM.Muted.TLabel").pack(side="bottom", pady=(0, 6))
    update_text, _ = load_last_update_info()
    lbl_update = ttk.Label(root, text=update_text, style="WM.Muted.TLabel")
    lbl_update.pack(side="bottom", pady=(0, 2))
    remote = cfg.get("updates.remote", "origin")
    branch = cfg.get("updates.branch", "proby-rozwoju")
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

def _login_pinless():
    try:
        user = find_first_brygadzista()
        if user:
            login_key = user.get("login")
            if _on_login_cb:
                try:
                    _on_login_cb(login_key, "brygadzista", None)
                except Exception as err:
                    logging.exception("Error in login callback")
                    error_dialogs.show_error_dialog(
                        "Błąd", f"Błąd w callbacku logowania: {err}"
                    )
            else:
                gui_panel.uruchom_panel(root_global, login_key, "brygadzista")
            return
        error_dialogs.show_error_dialog("Błąd", "Nie znaleziono brygadzisty")
    except Exception as e:
        error_dialogs.show_error_dialog("Błąd", f"Błąd podczas logowania: {e}")


def logowanie():
    login = entry_login.get().strip().lower()
    pin = entry_pin.get().strip()
    try:
        user = authenticate(login, pin)
        if user:
            login_key = user.get("login", login)
            status = str(user.get("status", "")).strip().lower()
            if user.get("nieobecny") or status in {"nieobecny", "urlop", "l4"}:
                error_dialogs.show_error_dialog(
                    "Błąd", "Użytkownik oznaczony jako nieobecny"
                )
                return
            rola = user.get("rola", "pracownik")
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
