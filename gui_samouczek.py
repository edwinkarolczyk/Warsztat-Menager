# WM-VERSION: 0.2.0
# Moduł: gui_samouczek
# Niezależny podgląd samouczka WM. Nie modyfikuje danych programu.
# 0.2.0: nagłówek pokazuje bieżącą wersję WM i datę ostatniej aktualizacji samouczka.

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

try:
    from __version__ import __version__ as CURRENT_WM_VERSION
except Exception:  # pragma: no cover - awaryjny fallback uruchomieniowy
    CURRENT_WM_VERSION = "dev"


CONTENT_PATH = Path(__file__).with_name("samouczek") / "samouczek.json"


def _format_updated(value: Any) -> str:
    """Zamień ISO YYYY-MM-DD na czytelne DD.MM.YYYY bez ryzyka crasha."""
    text = str(value or "").strip()
    if not text:
        return "brak daty"
    try:
        return date.fromisoformat(text).strftime("%d.%m.%Y")
    except ValueError:
        return text


def load_tutorial(path: Path | str = CONTENT_PATH) -> dict[str, Any]:
    """Wczytaj samouczek z osobnego pliku JSON.

    Pole ``wm_version`` w pamięci jest zawsze synchronizowane z centralną
    wersją WM z ``__version__.py``. Dzięki temu nagłówek nie może pokazać
    starego numeru wersji nawet wtedy, gdy plik treści czeka na aktualizację.
    """
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Nieprawidłowy format samouczka")
    slides = data.get("slides")
    if not isinstance(slides, list):
        raise ValueError("Brak listy slajdów w samouczku")
    data["wm_version"] = CURRENT_WM_VERSION
    return data


def open_tutorial(root: tk.Misc) -> tk.Toplevel | None:
    """Otwórz samouczek w niezależnym oknie prezentacyjnym."""
    try:
        data = load_tutorial()
    except Exception as exc:
        messagebox.showerror(
            "Samouczek WM",
            f"Nie udało się wczytać samouczka:\n{exc}",
            parent=root,
        )
        return None

    slides = [slide for slide in data.get("slides", []) if isinstance(slide, dict)]
    if not slides:
        messagebox.showinfo(
            "Samouczek WM",
            "Samouczek nie zawiera jeszcze żadnych kroków.",
            parent=root,
        )
        return None

    wm_version = str(data.get("wm_version") or CURRENT_WM_VERSION)
    updated_text = _format_updated(data.get("updated"))

    win = tk.Toplevel(root)
    win.title(
        f"{str(data.get('title') or 'Samouczek Warsztat Menager')} — WM v{wm_version}"
    )
    win.geometry("1100x700")
    win.minsize(880, 560)
    try:
        win.transient(root)
    except Exception:
        pass

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(1, weight=1)
    outer.rowconfigure(1, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    header.columnconfigure(0, weight=1)

    ttk.Label(
        header,
        text="Samouczek WM",
        font=("Segoe UI", 20, "bold"),
    ).grid(row=0, column=0, sticky="w")

    ttk.Label(
        header,
        text=f"WM v{wm_version}   |   Aktualizacja samouczka: {updated_text}",
        font=("Segoe UI", 10),
    ).grid(row=0, column=1, sticky="e", padx=(16, 0))

    nav = ttk.Frame(outer)
    nav.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
    ttk.Label(nav, text="Tematy", font=("Segoe UI", 11, "bold")).pack(
        anchor="w", pady=(0, 6)
    )
    topic_list = tk.Listbox(nav, width=28, exportselection=False)
    topic_list.pack(fill="y", expand=True)

    card = ttk.Frame(outer, padding=18)
    card.grid(row=1, column=1, sticky="nsew")
    card.columnconfigure(0, weight=1)
    card.rowconfigure(3, weight=1)

    module_var = tk.StringVar(master=win)
    title_var = tk.StringVar(master=win)
    lead_var = tk.StringVar(master=win)
    counter_var = tk.StringVar(master=win)

    ttk.Label(card, textvariable=module_var, font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(card, textvariable=title_var, font=("Segoe UI", 18, "bold")).grid(
        row=1, column=0, sticky="w", pady=(4, 8)
    )
    ttk.Label(
        card,
        textvariable=lead_var,
        wraplength=720,
        justify="left",
    ).grid(row=2, column=0, sticky="ew", pady=(0, 12))

    body = ttk.Frame(card)
    body.grid(row=3, column=0, sticky="nsew")
    body.columnconfigure(1, weight=1)

    tip_box = ttk.LabelFrame(card, text="! Podpowiedź")
    tip_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    tip_label = ttk.Label(tip_box, wraplength=700, justify="left")
    tip_label.pack(fill="x", padx=10, pady=10)

    footer = ttk.Frame(card)
    footer.grid(row=5, column=0, sticky="ew", pady=(16, 0))
    footer.columnconfigure(1, weight=1)
    prev_btn = ttk.Button(footer, text="← Wstecz")
    prev_btn.grid(row=0, column=0, sticky="w")
    ttk.Label(footer, textvariable=counter_var).grid(row=0, column=1)
    next_btn = ttk.Button(footer, text="Dalej →")
    next_btn.grid(row=0, column=2, sticky="e")

    state = {"index": 0}

    for slide in slides:
        module = str(slide.get("module") or "Temat")
        title = str(slide.get("title") or "Bez tytułu")
        topic_list.insert("end", f"{module} — {title}")

    def _render(index: int) -> None:
        index = max(0, min(index, len(slides) - 1))
        state["index"] = index
        slide = slides[index]
        module_var.set(str(slide.get("module") or "WM"))
        title_var.set(str(slide.get("title") or ""))
        lead_var.set(str(slide.get("lead") or ""))
        tip_label.configure(
            text=str(slide.get("tip") or "Brak dodatkowej podpowiedzi.")
        )
        counter_var.set(f"{index + 1} / {len(slides)}")

        for child in body.winfo_children():
            child.destroy()

        steps = slide.get("steps")
        if not isinstance(steps, list):
            steps = []
        for row, raw_step in enumerate(steps):
            ttk.Label(
                body,
                text=str(row + 1),
                width=3,
                anchor="center",
                font=("Segoe UI", 11, "bold"),
            ).grid(row=row, column=0, sticky="n", padx=(0, 8), pady=6)
            ttk.Label(
                body,
                text=str(raw_step),
                wraplength=680,
                justify="left",
            ).grid(row=row, column=1, sticky="nw", pady=6)

        prev_btn.configure(state="disabled" if index == 0 else "normal")
        next_btn.configure(state="disabled" if index == len(slides) - 1 else "normal")
        topic_list.selection_clear(0, "end")
        topic_list.selection_set(index)
        topic_list.see(index)

    def _move(delta: int) -> None:
        _render(state["index"] + delta)

    def _pick(_event=None) -> None:
        selected = topic_list.curselection()
        if selected:
            _render(int(selected[0]))

    prev_btn.configure(command=lambda: _move(-1))
    next_btn.configure(command=lambda: _move(1))
    topic_list.bind("<<ListboxSelect>>", _pick)
    win.bind("<Left>", lambda _e: _move(-1))
    win.bind("<Right>", lambda _e: _move(1))
    win.bind("<Escape>", lambda _e: win.destroy())

    _render(0)
    try:
        win.focus_set()
    except Exception:
        pass
    return win


__all__ = [
    "CONTENT_PATH",
    "CURRENT_WM_VERSION",
    "load_tutorial",
    "open_tutorial",
]
