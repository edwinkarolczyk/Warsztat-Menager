# Wersja pliku: 1.4.12.1
# Plik: gui_logowanie.py
# Zmiany 1.4.12.1:
# - Przywrócony układ z 1.4.12 (logo wyśrodkowane, PIN pośrodku, przycisk "Zamknij program" przyklejony na dole, stopka z wersją)
# - Dodany pasek postępu zmiany (1/3 szerokości ekranu, wyśrodkowany)
# - Bezpieczny timer (after) + anulowanie przy Destroy
# - Spójny wygląd z motywem (apply_theme), brak pływania elementów

import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# Pasek zmiany i przejście do panelu głównego
import gui_panel  # używamy: _shift_bounds, _shift_progress, uruchom_panel

# Motyw
from ui_theme import apply_theme_safe as apply_theme


# --- informacje o ostatniej aktualizacji ---
def load_last_update_info():
    """Pobierz informację o ostatniej aktualizacji.

    Funkcja próbuje odczytać ostatni wpis ``data`` i ``wersje`` z pliku
    ``logi_wersji.json``. Jeżeli plik nie istnieje lub jest uszkodzony,
    analizowana jest linia ``Data:`` w ``CHANGES_PROFILES_UPDATE.txt``.
    Jeżeli obie metody zawiodą, zwracane jest ``None``.

    Returns:
        tuple[str, str | None] | None: ``(tekst, wersja)`` z ostatniej
        aktualizacji; gdy brak danych o wersji drugi element to ``None``.
        ``None`` oznacza brak informacji o aktualizacjach.
    """

    try:
        with open("logi_wersji.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            last = data[-1]
            data_str = last.get("data")
            wersje = last.get("wersje", {})
            version = None
            if isinstance(wersje, dict):
                version = next(iter(wersje.values()), None)
            if data_str:
                return f"Ostatnia aktualizacja: {data_str}", version
    except Exception:
        pass

    try:
        with open("CHANGES_PROFILES_UPDATE.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().lower().startswith("data:"):
                    date_str = line.split(":", 1)[1].strip()
                    if date_str:
                        return f"Ostatnia aktualizacja: {date_str}", None
    except Exception:
        pass

    return None

# --- zmienne globalne dla kontrolki PIN i okna ---
entry_pin = None
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
    global entry_pin, root_global, _on_login_cb
    if root is None:
        root = tk.Tk()
    root_global = root
    _on_login_cb = on_login

    # wyczyść i ustaw motyw
    for w in root.winfo_children():
        w.destroy()
    apply_theme(root)

    # pełny ekran i tytuł
    root.title("Warsztat Menager")
    root.attributes("-fullscreen", True)

    # bazowe rozmiary ekranu
    szer, wys = root.winfo_screenwidth(), root.winfo_screenheight()

    # --- GÓRA: LOGO (wyśrodkowane, stabilne) ---
    top = ttk.Frame(root, style="WM.TFrame")
    top.pack(fill="x", pady=(32, 8))

    # logo (jeśli jest) — używamy tk.Label dla image
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(logo_path).resize((300, 100))
            logo_img = ImageTk.PhotoImage(img)
            lbl_logo = tk.Label(top, image=logo_img, bg=root["bg"] if "bg" in root.keys() else "#0f1113")
            lbl_logo.image = logo_img  # pin referencji
            lbl_logo.pack()
        except Exception:
            # brak PIL lub błąd pliku — po prostu nazwa
            ttk.Label(top, text="Warsztat Menager", style="WM.H1.TLabel").pack()

    # --- ŚRODEK: BOX PIN (wyśrodkowany stabilnie) ---
    center = ttk.Frame(root, style="WM.TFrame")
    center.pack(fill="both", expand=True)

    box = ttk.Frame(center, style="WM.Card.TFrame", padding=16)
    box.place(relx=0.5, rely=0.45, anchor="center")  # trochę wyżej niż idealne 0.5, by było miejsce na pasek

    ttk.Label(box, text="Podaj PIN:", style="WM.H2.TLabel").pack(pady=(8, 6))
    entry_pin = ttk.Entry(box, show="*", width=22)
    entry_pin.pack(ipadx=10, ipady=6)
    ttk.Button(box, text="Zaloguj", command=logowanie, style="WM.Side.TButton").pack(pady=16)

    # --- PASEK POSTĘPU ZMIANY (1/3 szer., wyśrodkowany) ---
    prefooter = ttk.Frame(root, style="WM.TFrame")
    prefooter.pack(fill="x", pady=(0, 10))

    wrap = ttk.Frame(prefooter, style="WM.Card.TFrame")
    wrap.pack()  # centralnie

    ttk.Label(wrap, text="Zmiana", style="WM.Card.TLabel").pack(anchor="w", padx=8, pady=(8, 2))

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
    update_info = load_last_update_info()
    if update_info is None:
        update_text = "brak danych o aktualizacjach"
    else:
        update_text = update_info[0]
    lbl_update = ttk.Label(root, text=update_text, style="WM.Muted.TLabel")
    lbl_update.pack(side="bottom", pady=(0, 2))
    try:
        subprocess.run(["git", "fetch", "origin", "proby-rozwoju"], check=True)
        remote_commit = subprocess.check_output(
            ["git", "rev-parse", "origin/proby-rozwoju"], text=True  # remote commit
        ).strip()
        local_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True  # local commit
        ).strip()
        status = "Aktualna" if local_commit == remote_commit else "Nieaktualna"
        colour = "green" if status == "Aktualna" else "red"
        lbl_update.configure(text=f"{update_text} – {status}", foreground=colour)
    except (subprocess.CalledProcessError, FileNotFoundError):
        lbl_update.configure(text=update_text)
    if update_available:
        ttk.Label(
            root,
            text="Dostępna aktualizacja – uruchom 'git pull'",
            style="WM.Muted.TLabel",
        ).pack(side="bottom", pady=(0, 2))

def logowanie():
    pin = entry_pin.get().strip()
    try:
        with open("uzytkownicy.json", "r", encoding="utf-8") as f:
            users = json.load(f)

        # Kompatybilność: dict (stary format) lub list (nowy format)
        if isinstance(users, dict):
            iterator = users.items()
        elif isinstance(users, list):
            iterator = (
                (str(rec.get("login") or idx), rec)
                for idx, rec in enumerate(users)
                if isinstance(rec, dict)
            )
        else:
            raise TypeError("uzytkownicy.json: nieobsługiwany format (oczekiwano dict lub list)")

        for login, dane in iterator:
            if str(dane.get("pin", "")).strip() == pin:
                status = str(dane.get("status", "")).strip().lower()
                if dane.get("nieobecny") or status in {"nieobecny", "urlop", "l4"}:
                    messagebox.showerror("Błąd", "Użytkownik oznaczony jako nieobecny")
                    return
                rola = dane.get("rola", "pracownik")
                if _on_login_cb:
                    try:
                        _on_login_cb(login, rola, None)
                    except Exception:
                        pass
                else:
                    gui_panel.uruchom_panel(root_global, login, rola)
                return
        messagebox.showerror("Błąd", "Nieprawidłowy PIN")
    except Exception as e:
        messagebox.showerror("Błąd", f"Błąd podczas logowania: {e}")

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
