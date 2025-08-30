# Wersja pliku: 1.1.0
# Plik: gui_maszyny.py

"""Prosty panel zarządzania maszynami.

Założenia:
- Dane o maszynach przechowywane są w pliku ``maszyny.json``.
- Każda maszyna ma listę zadań z polami ``data`` (YYYY-MM-DD),
  ``typ_zadania`` i opcjonalnie ``uwagi``.
- Panel pokazuje listę maszyn w widoku tabeli z kolumnami:
  ``nr_ewid``, ``nazwa``, ``typ`` oraz ``następne_zadanie``.
- Najbliższe zadanie obliczane jest jako najwcześniejsza data w
  przyszłości. W kolumnie widoczna jest data oraz typ zadania.
- Przycisk "Szczegóły" otwiera okno dialogowe z pełną listą zadań
  wybranej maszyny i umożliwia oznaczenie zadania jako wykonane.

Zmiany w wersji 1.1.0:
- Dodano funkcję ``load_machines`` do wczytywania danych z ``maszyny.json``.
- Zaimplementowano widok tabeli / Treeview w panelu maszyn.
- Obliczanie i prezentacja najbliższego zadania dla każdej maszyny.
- Dodano okno "Szczegóły" z listą zadań i opcją oznaczania jako wykonane.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox

from logger import log_akcja

from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame

MACHINES_FILE = os.path.join("data", "maszyny.json")


def load_machines() -> list[dict]:
    """Odczytuje i zwraca listę maszyn z pliku ``maszyny.json``.

    Waliduje istnienie kluczy ``hala``, ``x``, ``y`` oraz ``status``.
    Jeśli plik nie istnieje lub jest niepoprawny zwracana jest pusta lista.
    """

    try:
        with open(MACHINES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        log_akcja(f"[GUI_MASZYNY] Brak pliku {MACHINES_FILE}")
        return []
    except Exception as e:  # pragma: no cover - defensywne
        log_akcja(f"[GUI_MASZYNY] Błąd odczytu {MACHINES_FILE}: {e}")
        return []

    if not isinstance(data, list):
        log_akcja("[GUI_MASZYNY] Nieprawidłowy format danych maszyn")
        return []

    valid: list[dict] = []
    for m in data:
        if not isinstance(m, dict):
            log_akcja("[GUI_MASZYNY] Pominięto rekord – nie jest dict")
            continue
        missing = [k for k in ("hala", "x", "y", "status") if k not in m]
        if missing:
            log_akcja(
                f"[GUI_MASZYNY] Maszyna {m.get('nr_ewid')} brak pól {missing}"
            )
            continue
        if not isinstance(m["x"], (int, float)) or not isinstance(
            m["y"], (int, float)
        ):
            log_akcja(
                f"[GUI_MASZYNY] Maszyna {m.get('nr_ewid')} ma nieprawidłowe "
                "współrzędne"
            )
            continue
        valid.append(m)
    return valid


def _save_machines(data: list[dict]) -> None:
    """Zapisuje listę maszyn do pliku danych."""

    valid: list[dict] = []
    for m in data:
        if not isinstance(m, dict):
            log_akcja("[GUI_MASZYNY] Nieprawidłowy rekord przy zapisie")
            continue
        missing = [k for k in ("hala", "x", "y", "status") if k not in m]
        if missing:
            log_akcja(
                f"[GUI_MASZYNY] Maszyna {m.get('nr_ewid')} brak pól {missing}"
            )
            continue
        valid.append(m)

    try:
        with open(MACHINES_FILE, "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2, ensure_ascii=False)
    except Exception as e:  # pragma: no cover - defensywne
        log_akcja(f"[GUI_MASZYNY] Błąd zapisu {MACHINES_FILE}: {e}")


def _next_task_str(maszyna: dict) -> str:
    """Zwraca opis najbliższego zadania (data + typ) lub pusty string."""

    today = date.today()
    best_date: date | None = None
    best_task: dict | None = None
    for task in maszyna.get("zadania", []):
        try:
            d = datetime.strptime(task.get("data", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if d >= today and (best_date is None or d < best_date):
            best_date = d
            best_task = task
    if best_date and best_task:
        typ = best_task.get("typ_zadania", "")
        return f"{best_date.isoformat()} {typ}".strip()
    return ""


def panel_maszyny(root, frame, login=None, rola=None):
    """Buduje panel maszyn w przekazanym kontenerze ``frame``."""
    clear_frame(frame)

    apply_theme(frame)

    ttk.Label(
        frame,
        text="🛠️ Panel maszyn",
        style="WM.H1.TLabel",
    ).pack(pady=20, fill="x")

    maszyny = load_machines()
    maszyny_map = {str(m.get("nr_ewid")): m for m in maszyny}

    columns = ("nr_ewid", "nazwa", "typ", "nastepne_zadanie")
    tree = ttk.Treeview(
        frame, columns=columns, show="headings", height=15, style="WM.Treeview"
    )
    headings = {
        "nr_ewid": "nr_ewid",
        "nazwa": "nazwa",
        "typ": "typ",
        "nastepne_zadanie": "następne_zadanie",
    }
    for col in columns:
        tree.heading(col, text=headings[col])
        tree.column(col, width=150, anchor="center")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    for m in maszyny:
        iid = str(m.get("nr_ewid"))
        tree.insert(
            "",
            "end",
            iid=iid,
            values=(m.get("nr_ewid", ""), m.get("nazwa", ""), m.get("typ", ""), _next_task_str(m)),
        )

    def _open_details():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Brak wyboru", "Wybierz maszynę z listy")
            return
        key = sel[0]
        maszyna = maszyny_map.get(key)
        if not maszyna:
            return

        win = tk.Toplevel(root)
        win.title(f"Zadania – {maszyna.get('nazwa', '')}")
        apply_theme(win)

        cols = ("data", "typ_zadania", "uwagi")
        tv = ttk.Treeview(
            win, columns=cols, show="headings", height=10, style="WM.Treeview"
        )
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=120, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=10)

        def _refresh_tasks():
            tv.delete(*tv.get_children())
            for i, t in enumerate(maszyna.get("zadania", [])):
                tv.insert("", "end", iid=str(i), values=(t.get("data", ""), t.get("typ_zadania", ""), t.get("uwagi", "")))

        def _mark_done():
            sel_task = tv.selection()
            if not sel_task:
                return
            idx = int(sel_task[0])
            if 0 <= idx < len(maszyna.get("zadania", [])):
                del maszyna["zadania"][idx]
                _save_machines(maszyny)
                _refresh_tasks()
                tree.set(key, "nastepne_zadanie", _next_task_str(maszyna))

        btn = ttk.Button(win, text="Oznacz jako wykonane", command=_mark_done)
        btn.pack(pady=(0, 10))

        _refresh_tasks()

    ttk.Button(frame, text="Szczegóły", command=_open_details).pack(pady=10)
    try:
        from gui_hala import build_hala_view

        build_hala_view(frame)
    except Exception:  # pragma: no cover - opcjonalne
        pass


# Koniec pliku

