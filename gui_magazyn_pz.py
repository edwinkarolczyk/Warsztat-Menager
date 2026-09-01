# version: 1.1
"""Dialog and helpers for recording goods receipts (PZ)."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import logika_magazyn as LM

try:  # pragma: no cover - magazyn_io is optional
    import magazyn_io

    HAVE_MAG_IO = True
except Exception:  # pragma: no cover - module missing
    magazyn_io = None
    HAVE_MAG_IO = False


def _cfg(parent):
    """Return configuration dictionary from ``parent`` if available."""
    return getattr(parent, "config", {}) or getattr(parent, "config_obj", {}) or {}


def _get(cfg, paths, default=None):
    """Safely fetch value from first existing path in ``paths``."""
    getter = getattr(cfg, "get", None)
    for p in paths:
        if isinstance(cfg, dict):
            cur = cfg
            ok = True
            for key in p:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    ok = False
                    break
            if ok:
                return cur
        elif callable(getter):
            dotted = ".".join(p)
            try:
                value = getter(dotted, None)
                if value is not None:
                    return value
            except Exception:
                pass
    return default


def _mb_precision(cfg) -> int:
    val = _get(cfg, [["magazyn", "rounding", "mb_precision"], ["magazyn_precision_mb"]], 3)
    try:
        val = int(val)
    except Exception:
        val = 3
    return max(0, min(6, val))


def _enforce_int_for_szt(cfg) -> bool:
    return bool(_get(cfg, [["magazyn", "rounding", "enforce_integer_for_szt"]], True))


def _require_reauth(cfg) -> bool:
    return bool(
        _get(
            cfg,
            [["magazyn", "require_reauth"], ["magazyn_require_reauth"], ["require_reauth"]],
            True,
        )
    )


def _safe_load():
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            return magazyn_io.load()
        return LM.load_magazyn()
    except Exception:
        return {"items": {}, "meta": {}}


def _safe_save(data):
    if HAVE_MAG_IO and hasattr(magazyn_io, "save"):
        return magazyn_io.save(data)
    if hasattr(LM, "save_magazyn"):
        return LM.save_magazyn(data)
    raise RuntimeError("Brak metody zapisu magazynu")


def _apply_pz_to_item(item: dict, qty: float) -> float:
    """Zwiększa stan pozycji o dodatnią ilość i zwraca nowy stan."""
    amount = float(qty)
    if amount <= 0:
        raise ValueError("Ilość przyjęcia musi być większa od zera")
    try:
        current = float(item.get("stan", 0) or 0)
    except (TypeError, ValueError):
        current = 0.0
    new_stock = current + amount
    item["stan"] = new_stock
    return new_stock


class PZDialog:
    """Dialog rejestrujący przyjęcie jednej pozycji magazynowej."""

    def __init__(self, master, item_id: str, on_saved=None):
        self.master = master
        self.item_id = item_id
        self.on_saved = on_saved
        self.cfg = _cfg(master)

        self.data = _safe_load()
        self.items = self.data.setdefault("items", {})
        self.item = self.items.get(item_id, {})

        self.win = tk.Toplevel(master)
        self.win.title(f"Przyjęcie towaru: {item_id}")
        self.win.resizable(False, False)

        frm = ttk.Frame(self.win, padding=12)
        frm.grid(sticky="nsew")
        self.win.columnconfigure(0, weight=1)

        self.var_qty = tk.StringVar(value="")
        self.var_supplier = tk.StringVar(value="")
        self.var_document = tk.StringVar(value="")
        self.var_cmt = tk.StringVar(value="")

        rows = (
            (0, "Ilość:", self.var_qty),
            (1, "Dostawca:", self.var_supplier),
            (2, "Numer dokumentu:", self.var_document),
            (3, "Komentarz (opcjonalnie):", self.var_cmt),
        )
        for row, label, variable in rows:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 8))
            ttk.Entry(frm, textvariable=variable, width=40).grid(row=row, column=1, sticky="ew", pady=2)

        unit = str(self.item.get("jednostka") or "").strip() or "—"
        current = self.item.get("stan", 0)
        ttk.Label(
            frm,
            text=f"Aktualny stan: {current} {unit}",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 2))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz przyjęcie", command=self.on_save).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right")

        frm.columnconfigure(1, weight=1)
        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def _reauth(self):
        if not _require_reauth(self.cfg):
            return True
        login = simpledialog.askstring("Ponowna autoryzacja", "Login:", parent=self.win)
        if login is None:
            return False
        pin = simpledialog.askstring("Ponowna autoryzacja", "PIN:", show="*", parent=self.win)
        if pin is None:
            return False
        try:
            from services.profile_service import authenticate
            user = authenticate(login, pin)
        except Exception:
            user = True
        if not user:
            messagebox.showerror("Błąd", "Nieprawidłowy login lub PIN", parent=self.win)
            return False
        return True

    def _parse_qty(self, txt: str):
        txt = (txt or "").strip().replace(",", ".")
        if not txt:
            raise ValueError("Brak ilości")
        q = float(txt)
        if q <= 0:
            raise ValueError("Ilość musi być większa od zera")

        jm = str(self.item.get("jednostka", "")).strip().lower()
        if jm in {"szt", "szt."}:
            if _enforce_int_for_szt(self.cfg):
                if abs(q - round(q)) > 1e-9:
                    raise ValueError("Dla 'szt' dozwolone są tylko liczby całkowite")
                q = int(round(q))
        elif jm in {"mb", "m"}:
            q = round(q, _mb_precision(self.cfg))
        return q

    def on_save(self):
        if not self.item:
            messagebox.showerror(
                "Przyjęcie towaru",
                "Wybrana pozycja nie istnieje w Magazynie.",
                parent=self.win,
            )
            return
        if not self._reauth():
            return

        try:
            qty = self._parse_qty(self.var_qty.get())
        except Exception as exc:
            messagebox.showerror("Błąd", f"Ilość nieprawidłowa: {exc}", parent=self.win)
            return

        supplier = self.var_supplier.get().strip()
        document = self.var_document.get().strip()
        comment = self.var_cmt.get().strip()
        details = " | ".join(
            part for part in (
                f"Dostawca: {supplier}" if supplier else "",
                f"Dokument: {document}" if document else "",
                comment,
            ) if part
        )

        try:
            _apply_pz_to_item(self.item, qty)
        except ValueError as exc:
            messagebox.showerror("Przyjęcie towaru", str(exc), parent=self.win)
            return

        if hasattr(LM, "append_history"):
            try:
                LM.append_history(
                    self.data.get("items", {}),
                    self.item_id,
                    user="",
                    op="PZ",
                    qty=qty,
                    comment=details,
                )
            except Exception:
                pass

        try:
            _safe_save(self.data)
        except Exception as exc:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się zapisać magazynu:\n{exc}",
                parent=self.win,
            )
            return

        if callable(self.on_saved):
            try:
                self.on_saved(self.item_id)
            except TypeError:
                self.on_saved()
            except Exception:
                pass
        self.win.destroy()


def open_pz_dialog(master, item_id: str, on_saved=None):
    PZDialog(master, item_id, on_saved=on_saved)


# ⏹ KONIEC KODU
