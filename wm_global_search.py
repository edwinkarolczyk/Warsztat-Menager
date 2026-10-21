# Plik: wm_global_search.py
# Wyszukiwarka przekrojowa kartotek WM (tylko odczyt danych z aktywnego ROOT).
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager
from utils.gui_helpers import clear_frame


SEARCH_FIELDS = (
    "kod", "id", "numer", "nr", "nr_ewid", "nazwa", "symbol", "tytul",
    "produkt", "zlec_wew", "typ", "rodzaj", "model", "opis",
    "lokalizacja", "hala", "oznaczenie",
)

# Źródła są rozdzielone według modułu, żeby nie pokazywać danych z
# modułów niedostępnych zalogowanemu pracownikowi.
SOURCES = (
    ("planowanie", "Zlecenie", "zlecenia", "*.json"),
    ("planowanie", "Produkt", "produkty", "*.json"),
    ("planowanie", "Półprodukt", "polprodukty", "*.json"),
    ("magazyn", "Surowiec", "magazyn", "surowce.json"),
    ("magazyn", "Magazyn", "magazyn", "magazyn.json"),
    ("narzedzia", "Narzędzie", "narzedzia", "*.json"),
    ("maszyny", "Maszyna", "maszyny", "maszyny.json"),
    ("zlecenia", "Dyspozycja", "dyspozycje", "*.json"),
    ("zlecenia", "Dyspozycja", ".", "dyspozycje.json"),
)


def _normal(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(c for c in value if not unicodedata.combining(c)).replace("ł", "l")


def _records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "pozycje", "zlecenia", "dyspozycje", "maszyny", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            return [dict(row, id=row.get("id") or code) for code, row in value.items() if isinstance(row, dict)]
    if any(k in payload for k in ("kod", "id", "nazwa", "numer", "nr_ewid", "tytul", "produkt")):
        return [payload]
    return [dict(row, id=row.get("id") or code) for code, row in payload.items() if isinstance(row, dict)]


def search_wm(query: str, allowed_modules: set[str], *, data_dir: Path | None = None, limit: int = 100) -> list[dict]:
    """Szukaj w bieżących kartotekach; bez modyfikowania plików i bez danych profili."""
    needle = _normal(query.strip())
    if len(needle) < 2:
        return []
    if data_dir is None:
        data_dir = Path(ConfigManager().path_data())

    results: list[tuple[int, dict]] = []
    for module, category, folder, pattern in SOURCES:
        if module not in allowed_modules:
            continue
        directory = data_dir / folder
        if not directory.is_dir():
            continue
        for path in directory.glob(pattern):
            if not path.is_file() or path.name.startswith("_"):
                continue
            if module == "narzedzia" and not path.stem.isdigit():
                # Słowniki narzędzi nie są samodzielnymi kartami narzędzi.
                continue
            try:
                with path.open(encoding="utf-8") as stream:
                    payload = json.load(stream)
            except (OSError, UnicodeError, ValueError):
                continue
            for row in _records(payload):
                search_text = " ".join(str(row.get(k) or "") for k in SEARCH_FIELDS)
                if needle not in _normal(search_text):
                    continue
                code = str(
                    row.get("kod") or row.get("id") or row.get("numer")
                    or row.get("nr_ewid") or row.get("symbol")
                    or path.stem
                ).strip()
                title = str(row.get("nazwa") or row.get("tytul") or row.get("produkt") or code).strip()
                context = " · ".join(
                    str(row[k]) for k in ("typ", "status", "hala", "lokalizacja")
                    if row.get(k) not in (None, "")
                )
                score = 0 if _normal(code) == needle else 1 if _normal(code).startswith(needle) else 2 if _normal(title).startswith(needle) else 3
                results.append((score, {
                    "module": module,
                    "category": category,
                    "code": code,
                    "title": title,
                    "context": context,
                }))
    results.sort(key=lambda entry: (entry[0], _normal(entry[1]["title"]), _normal(entry[1]["code"])))
    return [row for _, row in results[:limit]]


def mount_global_search(header, root, content, *, login: str, role: str, allowed_modules, open_module) -> None:
    """Stała wyszukiwarka w nagłówku po zalogowaniu; Enter lub przycisk Szukaj."""
    if str(login or "").strip().casefold() in {"", "guest", "gość", "gosc"}:
        root.bind("<Control-f>", lambda _event: None)
        return

    bar = ttk.Frame(header, style="WM.TFrame")
    bar.pack(side="left", padx=(16, 8), fill="x", expand=True)
    ttk.Label(bar, text="Szukaj w WM:", style="WM.Muted.TLabel").pack(side="left", padx=(0, 6))
    query_var = tk.StringVar(master=root)
    field = ttk.Entry(bar, textvariable=query_var)
    field.pack(side="left", fill="x", expand=True)

    def execute(_event=None):
        value = query_var.get().strip()
        if len(value) < 2:
            return
        try:
            results = search_wm(value, set(allowed_modules()))
        except Exception as exc:
            clear_frame(content)
            ttk.Label(content, text=f"Wyszukiwanie nie powiodło się: {exc}").pack(anchor="w", padx=12, pady=12)
            return
        clear_frame(content)
        area = ttk.Frame(content, padding=12)
        area.pack(fill="both", expand=True)
        ttk.Label(area, text=f"Wyniki wyszukiwania: {value} ({len(results)}; maks. 100)", style="WM.H1.TLabel").pack(anchor="w", pady=(0, 10))
        table_area = ttk.Frame(area)
        table_area.pack(fill="both", expand=True)
        columns = ("category", "code", "title", "context")
        tree = ttk.Treeview(table_area, columns=columns, show="headings", selectmode="browse")
        for key, title, width in (
            ("category", "Obszar", 125),
            ("code", "Numer / ID", 135),
            ("title", "Nazwa", 320),
            ("context", "Szczegóły", 270),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w", stretch=(key in {"title", "context"}))
        scrollbar = ttk.Scrollbar(table_area, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for index, row in enumerate(results):
            tree.insert("", "end", iid=str(index), values=(row["category"], row["code"], row["title"], row["context"]))

        def open_selected(_event=None):
            selected = tree.selection()
            if not selected:
                return
            item = results[int(selected[0])]
            open_module(item["module"], item["code"])

        tree.bind("<Double-1>", open_selected)
        ttk.Button(area, text="Otwórz zaznaczony moduł", command=open_selected).pack(anchor="e", pady=(8, 0))
        if not results:
            ttk.Label(area, text="Brak wyników w dostępnych modułach.").pack(anchor="w")

    ttk.Button(bar, text="Szukaj", command=execute).pack(side="left", padx=(6, 0))
    field.bind("<Return>", execute)
    root.bind("<Control-f>", lambda _event: (field.focus_set(), field.select_range(0, "end"), "break")[-1])
