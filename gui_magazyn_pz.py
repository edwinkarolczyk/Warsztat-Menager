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

    return getattr(parent, "config", {}) or {}


def _get(cfg: dict, paths, default=None):
    """Safely fetch value from first existing path in ``paths``."""

    for p in paths:
        cur = cfg
        ok = True
        for key in p:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:  # key missing
                ok = False
                break
        if ok:
            return cur
    return default


def _mb_precision(cfg: dict) -> int:
    """Return rounding precision for unit ``mb`` (0-6, default 3)."""

    val = _get(
        cfg,
        [
            ["magazyn", "rounding", "mb_precision"],
            ["magazyn_precision_mb"],
        ],
        3,
    )
    try:
        val = int(val)
    except Exception:  # pragma: no cover - fallback
        val = 3
    return max(0, min(6, val))


def _enforce_int_for_szt(cfg: dict) -> bool:
    """Return whether quantities in ``szt`` must be integers."""

    val = _get(cfg, [["magazyn", "rounding", "enforce_integer_for_szt"]], True)
    return bool(val)


def _require_reauth(cfg: dict) -> bool:
    """Return whether re-authentication is required for PZ."""

    val = _get(
        cfg,
        [
            ["magazyn", "require_reauth"],
            ["magazyn_require_reauth"],
            ["require_reauth"],
        ],
        True,
    )
    return bool(val)


def _safe_load():
    """Load warehouse data using available backend."""

    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            return magazyn_io.load()
        return LM.load_magazyn()
    except Exception:  # pragma: no cover - load failure
        return {"items": {}, "meta": {}}


def _safe_save(data):
    """Persist warehouse ``data`` using available backend."""

    if HAVE_MAG_IO and hasattr(magazyn_io, "save"):
        return magazyn_io.save(data)
    if hasattr(LM, "save_magazyn"):
        return LM.save_magazyn(data)
    raise RuntimeError("Brak metody zapisu magazynu")


class PZDialog:
    """Dialog for registering goods receipts for single item."""

    def __init__(self, master, item_id: str):
        self.master = master
        self.item_id = item_id
        self.cfg = _cfg(master)

        self.data = _safe_load()
        self.items = self.data.setdefault("items", {})
        self.item = self.items.get(item_id, {})

        self.win = tk.Toplevel(master)
        self.win.title(f"PZ: {item_id}")
        self.win.resizable(False, False)

        frm = ttk.Frame(self.win, padding=12)
        frm.grid(sticky="nsew")
        self.win.columnconfigure(0, weight=1)

        ttk.Label(frm, text="Ilość:").grid(row=0, column=0, sticky="w", pady=2)
        self.var_qty = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_qty, width=18).grid(
            row=0, column=1, sticky="w", pady=2
        )

        ttk.Label(frm, text="Komentarz (opcjonalnie):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.var_cmt = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_cmt, width=40).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right")

        frm.columnconfigure(1, weight=1)

        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def _reauth(self):
        if not _require_reauth(self.cfg):
            return True
        login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=self.win)
        if login is None:
            return False
        pin = simpledialog.askstring("Re-autoryzacja", "PIN:", show="*", parent=self.win)
        if pin is None:
            return False
        return True

    def _parse_qty(self, txt: str):
        txt = (txt or "").strip().replace(",", ".")
        if not txt:
            raise ValueError("Brak ilości")
        q = float(txt)

        jm = str(self.item.get("jednostka", "")).strip().lower()
        if jm == "szt":
            if _enforce_int_for_szt(self.cfg):
                if abs(q - round(q)) > 1e-9:
                    raise ValueError("Dla 'szt' dozwolone są tylko liczby całkowite")
                q = int(round(q))
        elif jm == "mb":
            prec = _mb_precision(self.cfg)
            q = round(q, prec)
        return q

    def on_save(self):
        if not self._reauth():
            return

        try:
            qty = self._parse_qty(self.var_qty.get())
        except Exception as exc:  # pragma: no cover - GUI message
            messagebox.showerror("Błąd", f"Ilość nieprawidłowa: {exc}", parent=self.win)
            return

        cmt = self.var_cmt.get().strip()

        cur = self.item.get("stan", 0)
        try:
            cur = float(cur)
        except Exception:  # pragma: no cover - fallback
            cur = 0.0
        self.item["stan"] = cur + float(qty)

        if hasattr(LM, "append_history"):
            try:  # pragma: no cover - history optional
                LM.append_history(
                    self.data.get("items", {}),
                    self.item_id,
                    user="",
                    op="PZ",
                    qty=qty,
                    komentarz=cmt,
                )
            except Exception:
                pass

        try:
            _safe_save(self.data)
        except Exception as exc:  # pragma: no cover - GUI message
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się zapisać magazynu:\n{exc}",
                parent=self.win,
            )
            return

        self.win.destroy()


def open_pz_dialog(master, item_id: str):
    """Convenience wrapper to open :class:`PZDialog`."""

    PZDialog(master, item_id)


# ⏹ KONIEC KODU

