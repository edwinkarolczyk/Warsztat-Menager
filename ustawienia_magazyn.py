# ===============================================
# PLIK 2/2 (NOWY): ustawienia_magazyn.py
# ===============================================
# Wersja: 1.0.0
# - Zakładka ustawień Magazynu (re-auth, rounding) + edycja słowników (Typy/Jednostki)

import tkinter as tk
from tkinter import ttk, messagebox

from magazyn_slowniki import load as sl_load, save as sl_save


class MagazynSettingsPane(ttk.Frame):
    def __init__(self, master, config_manager=None):
        super().__init__(master, padding=12)
        self.cm = config_manager  # obiekt z get()/set()/save() albo dict
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        grp_ops = ttk.LabelFrame(self, text="Operacje (PZ/WZ)")
        grp_ops.pack(fill="x", pady=(0, 8))

        self.var_reauth = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            grp_ops,
            text="Wymagaj re-autoryzacji (login+PIN) dla PZ/WZ",
            variable=self.var_reauth,
        ).pack(anchor="w", pady=2)

        frm_round = ttk.Frame(grp_ops)
        frm_round.pack(fill="x", pady=(6, 2))
        ttk.Label(frm_round, text="Precyzja dla 'mb':").pack(side="left")
        self.var_mb_prec = tk.IntVar(value=3)
        ttk.Spinbox(
            frm_round, from_=0, to=6, textvariable=self.var_mb_prec, width=5
        ).pack(side="left", padx=(6, 12))

        self.var_szt_int = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            grp_ops,
            text="Wymuszaj liczby całkowite dla 'szt'",
            variable=self.var_szt_int,
        ).pack(anchor="w", pady=2)

        ttk.Button(grp_ops, text="Zapisz ustawienia", command=self._save_config).pack(
            anchor="e", pady=(6, 0)
        )

        grp_dicts = ttk.LabelFrame(
            self, text="Słowniki (dla comboboxów w Magazynie)"
        )
        grp_dicts.pack(fill="both", expand=True, pady=(8, 0))

        box1 = ttk.Frame(grp_dicts)
        box1.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(box1, text="Jednostki").pack(anchor="w")
        self.lb_jm = tk.Listbox(box1, height=8, exportselection=False)
        self.lb_jm.pack(fill="both", expand=True, pady=(2, 4))
        frm_jm = ttk.Frame(box1)
        frm_jm.pack(fill="x")
        self.ent_jm = ttk.Entry(frm_jm, width=12)
        self.ent_jm.pack(side="left")
        ttk.Button(frm_jm, text="Dodaj", command=self._add_jm).pack(
            side="left", padx=4
        )
        ttk.Button(frm_jm, text="Usuń zazn.", command=self._del_jm).pack(side="left")

        box2 = ttk.Frame(grp_dicts)
        box2.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(box2, text="Typy").pack(anchor="w")
        self.lb_typ = tk.Listbox(box2, height=8, exportselection=False)
        self.lb_typ.pack(fill="both", expand=True, pady=(2, 4))
        frm_t = ttk.Frame(box2)
        frm_t.pack(fill="x")
        self.ent_typ = ttk.Entry(frm_t, width=12)
        self.ent_typ.pack(side="left")
        ttk.Button(frm_t, text="Dodaj", command=self._add_typ).pack(
            side="left", padx=4
        )
        ttk.Button(frm_t, text="Usuń zazn.", command=self._del_typ).pack(side="left")

        ttk.Button(self, text="Zapisz słowniki", command=self._save_dicts).pack(
            anchor="e", pady=(8, 0)
        )

    # -------------------- helpers cfg --------------------
    def _get_cfg(self):
        """
        Zwraca cały bieżący config jako dict.
        Wcześniej wywoływano self.cm.get() bez klucza, co powodowało TypeError.
        """
        try:
            if hasattr(self.cm, "data") and isinstance(self.cm.data, dict):
                return dict(self.cm.data)
        except Exception as e:
            print(
                f"[ERROR][USTAWIENIA_MAGAZYN] Nie udało się pobrać self.cm.data: {e}"
            )

        try:
            if hasattr(self.cm, "get"):
                try:
                    return self.cm.get("magazyn") or {}
                except TypeError:
                    return {}
        except Exception as e:
            print(
                f"[ERROR][USTAWIENIA_MAGAZYN] Fallback get('magazyn') nieudany: {e}"
            )

        if isinstance(self.cm, dict):
            return dict(self.cm)
        return {}

    def _set_cfg(self, cfg: dict):
        if hasattr(self.cm, "set"):
            self.cm.set(cfg)
        elif isinstance(self.cm, dict):
            self.cm.clear()
            self.cm.update(cfg)

    def _save_cfg_to_disk(self, cfg: dict):
        if hasattr(self.cm, "save"):
            try:
                self.cm.save()
            except Exception as e:
                messagebox.showerror(
                    "Błąd", f"Nie udało się zapisać configu:\n{e}", parent=self
                )

    # -------------------- lifecycle --------------------
    def _load_values(self):
        cfg = self._get_cfg()
        require = bool(((cfg.get("magazyn") or {}).get("require_reauth", True)))
        mbp = int(
            ((cfg.get("magazyn") or {}).get("rounding") or {}).get("mb_precision", 3)
        )
        szti = bool(
            ((cfg.get("magazyn") or {}).get("rounding") or {}).get(
                "enforce_integer_for_szt", True
            )
        )
        self.var_reauth.set(require)
        self.var_mb_prec.set(max(0, min(6, mbp)))
        self.var_szt_int.set(szti)

        d = sl_load()
        self._fill_lb(self.lb_jm, d.get("jednostki", []))
        self._fill_lb(self.lb_typ, d.get("typy", []))

    def _save_config(self):
        cfg = self._get_cfg()
        mag = cfg.setdefault("magazyn", {})
        rnd = mag.setdefault("rounding", {})
        mag["require_reauth"] = bool(self.var_reauth.get())
        rnd["mb_precision"] = int(self.var_mb_prec.get())
        rnd["enforce_integer_for_szt"] = bool(self.var_szt_int.get())
        self._set_cfg(cfg)
        self._save_cfg_to_disk(cfg)
        messagebox.showinfo("OK", "Ustawienia zapisane.", parent=self)

    # -------------------- listbox ops --------------------
    def _fill_lb(self, lb: tk.Listbox, arr):
        lb.delete(0, tk.END)
        for x in arr or []:
            lb.insert(tk.END, str(x))

    def _add_jm(self):
        val = self.ent_jm.get().strip()
        if not val:
            return
        existing = [self.lb_jm.get(i) for i in range(self.lb_jm.size())]
        if val.lower() in {x.lower() for x in existing}:
            messagebox.showwarning(
                "Uwaga", "Taka jednostka już istnieje.", parent=self
            )
            return
        self.lb_jm.insert(tk.END, val)
        self.ent_jm.delete(0, tk.END)

    def _del_jm(self):
        for i in reversed(self.lb_jm.curselection()):
            self.lb_jm.delete(i)

    def _add_typ(self):
        val = self.ent_typ.get().strip()
        if not val:
            return
        existing = [self.lb_typ.get(i) for i in range(self.lb_typ.size())]
        if val.lower() in {x.lower() for x in existing}:
            messagebox.showwarning(
                "Uwaga", "Taki typ już istnieje.", parent=self
            )
            return
        self.lb_typ.insert(tk.END, val)
        self.ent_typ.delete(0, tk.END)

    def _del_typ(self):
        for i in reversed(self.lb_typ.curselection()):
            self.lb_typ.delete(i)

    def _save_dicts(self):
        jednostki = [self.lb_jm.get(i) for i in range(self.lb_jm.size())]
        typy = [self.lb_typ.get(i) for i in range(self.lb_typ.size())]
        try:
            sl_save({"jednostki": jednostki, "typy": typy})
            messagebox.showinfo("OK", "Słowniki zapisane.", parent=self)
        except Exception as e:
            messagebox.showerror(
                "Błąd", f"Nie udało się zapisać słowników:\n{e}", parent=self
            )

