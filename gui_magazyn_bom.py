"""GUI for editing BOM items with technological operations."""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager


DATA_DIR = os.path.join("data", "polprodukty")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _write_json(path: str, data: dict) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _ensure_non_negative(
    value: str, field: str, ctx: str
) -> int | float | None:
    """Validate that a numeric field is not negative.

    Parameters
    ----------
    value:
        Text value from an entry widget.
    field:
        Name of the validated field used in error messages.
    ctx:
        Context prefix for :func:`messagebox.showerror`.

    Returns
    -------
    int | float | None
        Parsed number or ``None`` when validation failed.
    """

    if value == "":
        return 0
    try:
        num = float(value) if "." in value else int(value)
    except Exception:
        messagebox.showerror(ctx, f"Pole '{field}' musi być liczbą.")
        return None
    if num < 0:
        messagebox.showerror(ctx, f"Pole '{field}' musi być ≥ 0.")
        return None
    return num


def validate_surowiec(rec: dict) -> bool:
    """Sprawdź poprawność danych surowca.

    Wymagane są pola ``kod``, ``nazwa``, ``rodzaj`` oraz ``jednostka``.
    Wszystkie pola liczbowe muszą być nieujemne.
    """

    for field in ("kod", "nazwa", "rodzaj", "jednostka"):
        if not str(rec.get(field, "")).strip():
            messagebox.showerror("Surowce", f"Pole '{field}' jest wymagane.")
            return False
    for field in ("dlugosc", "ilosc", "prog_alertu_procent"):
        if field in rec:
            num = _ensure_non_negative(str(rec[field]), field, "Surowce")
            if num is None:
                return False
            rec[field] = num
    return True


def validate_polprodukt(rec: dict) -> bool:
    """Sprawdź poprawność danych półproduktu."""

    if not rec.get("kod") or not rec.get("nazwa"):
        messagebox.showerror(
            "Półprodukty", "Wymagane pola: kod i nazwa."
        )
        return False
    sr = rec.get("surowiec") or {}
    if not sr.get("kod"):
        messagebox.showerror(
            "Półprodukty", "Wymagany jest kod surowca."
        )
        return False
    norma_raw = rec.get("norma_strat_procent", 0)
    try:
        norma = float(norma_raw)
    except Exception:
        messagebox.showerror(
            "Półprodukty", "Norma strat musi być liczbą."
        )
        return False
    if not 0 <= norma <= 100:
        messagebox.showerror(
            "Półprodukty", "Norma strat musi być w zakresie 0–100."
        )
        return False
    rec["norma_strat_procent"] = norma
    return True


def validate_produkt(rec: dict) -> bool:
    """Sprawdź poprawność danych produktu."""

    if not rec.get("symbol") or not rec.get("nazwa"):
        messagebox.showerror(
            "Produkty", "Wymagane pola: symbol i nazwa."
        )
        return False
    bom = rec.get("BOM") or rec.get("bom") or []
    if not bom:
        messagebox.showerror(
            "Produkty", "BOM musi mieć co najmniej jedną pozycję."
        )
        return False
    return True


def make_window(root: tk.Misc) -> ttk.Frame:
    cfg = ConfigManager()
    ops = cfg.get("czynnosci_technologiczne", [])

    frame = ttk.Frame(root)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Kod").grid(
        row=0, column=0, sticky="w", padx=6, pady=4
    )
    var_kod = tk.StringVar()
    ttk.Entry(frame, textvariable=var_kod).grid(
        row=0, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(frame, text="Nazwa").grid(
        row=1, column=0, sticky="w", padx=6, pady=4
    )
    var_nazwa = tk.StringVar()
    ttk.Entry(frame, textvariable=var_nazwa).grid(
        row=1, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(frame, text="Kod surowca").grid(
        row=2, column=0, sticky="w", padx=6, pady=4
    )
    var_sr_kod = tk.StringVar()
    ttk.Entry(frame, textvariable=var_sr_kod).grid(
        row=2, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(frame, text="Czynności").grid(
        row=3, column=0, sticky="nw", padx=6, pady=4
    )
    lb = tk.Listbox(frame, selectmode="multiple", height=min(6, len(ops)))
    for op in ops:
        lb.insert("end", op)
    lb.grid(row=3, column=1, sticky="nsew", padx=6, pady=4)

    ttk.Label(frame, text="Norma strat [%]").grid(
        row=4, column=0, sticky="w", padx=6, pady=4
    )
    var_norma = tk.StringVar()
    ttk.Entry(frame, textvariable=var_norma).grid(
        row=4, column=1, sticky="ew", padx=6, pady=4
    )

    def _save() -> None:
        sel = [ops[int(i)] for i in lb.curselection()]
        rec = {
            "kod": var_kod.get().strip(),
            "nazwa": var_nazwa.get().strip(),
            "surowiec": {"kod": var_sr_kod.get().strip()},
            "norma_strat_procent": var_norma.get().strip() or 0,
            "czynnosci": sel,
        }
        if not validate_polprodukt(rec):
            return
        path = os.path.join(DATA_DIR, f"{rec['kod']}.json")
        _write_json(path, rec)
        messagebox.showinfo("Zapis", "Zapisano dane")

    ttk.Button(frame, text="Zapisz", command=_save).grid(
        row=5, column=1, sticky="e", padx=6, pady=4
    )
    return frame

