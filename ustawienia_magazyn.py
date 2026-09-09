# ustawienia_magazyn.py
# version: 1.1
# Zmiany 1.1:
# - uporządkowano nazwy sekcji Magazynu;
# - wartości liczbowe mają Spinbox zamiast ręcznego Entry;
# - techniczny plik sekwencji PZ ukryto z normalnego widoku;
# - dodano istniejące ustawienie ponownej autoryzacji PZ/WZ;
# - zapis może być wywołany przez główne „Zapisz wszystko”.

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox

SLOWNIKI_PATH = os.path.join("data", "magazyn", "slowniki.json")


def _load_slowniki():
    """Wczytaj słowniki magazynu (typy, jednostki). Zapewnij bezpieczne domyślne."""
    os.makedirs(os.path.dirname(SLOWNIKI_PATH), exist_ok=True)
    if not os.path.exists(SLOWNIKI_PATH):
        return {
            "typy": ["profil", "rura", "polprodukt"],
            "jednostki": ["szt", "mb"],
        }
    try:
        with open(SLOWNIKI_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if "typy" not in data or not isinstance(data["typy"], list) or not data["typy"]:
            data["typy"] = ["profil", "rura", "polprodukt"]
        if "jednostki" not in data or not isinstance(data["jednostki"], list) or not data["jednostki"]:
            data["jednostki"] = ["szt", "mb"]
        data["typy"] = _dedup_str_list(data["typy"])
        data["jednostki"] = _dedup_str_list(data["jednostki"])
        return data
    except Exception:
        return {
            "typy": ["profil", "rura", "polprodukt"],
            "jednostki": ["szt", "mb"],
        }


def _save_slowniki(data):
    """Zapis słowników do pliku JSON."""
    try:
        os.makedirs(os.path.dirname(SLOWNIKI_PATH), exist_ok=True)
        with open(SLOWNIKI_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "typy": _dedup_str_list(data.get("typy", [])),
                    "jednostki": _dedup_str_list(data.get("jednostki", [])),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        return True
    except Exception as e:
        messagebox.showerror("Błąd zapisu słowników", str(e))
        return False


def _dedup_str_list(items):
    out, seen = [], set()
    for x in items or []:
        s = (x or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


class MagazynSettingsFrame(ttk.Frame):
    """Zakładka ustawień magazynu."""

    def __init__(self, master, config_manager, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.config_manager = config_manager
        self.slowniki = _load_slowniki()

        nb = ttk.Notebook(self)
        self._settings_nb = nb
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_ogolne = ttk.Frame(nb)
        self._tab_slowniki = ttk.Frame(nb)
        self._tab_pz = ttk.Frame(nb)
        self._tab_rez = ttk.Frame(nb)
        self._tab_alerty = ttk.Frame(nb)
        self._tab_perms = ttk.Frame(nb)

        nb.add(self._tab_ogolne, text="Ogólne")
        nb.add(self._tab_rez, text="Logika — rezerwacje")
        nb.add(self._tab_alerty, text="Logika — alerty")
        nb.add(self._tab_slowniki, text="Słowniki")
        nb.add(self._tab_pz, text="Dokumenty PZ")
        nb.add(self._tab_perms, text="Uprawnienia")

        self._build_tab_ogolne(self._tab_ogolne)
        self._build_tab_slowniki(self._tab_slowniki)
        self._build_tab_pz(self._tab_pz)
        self._build_tab_rezerwacje(self._tab_rez)
        self._build_tab_alerty(self._tab_alerty)
        self._build_tab_perms(self._tab_perms)

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(bar, text="Zmiany zapisuje główny przycisk „Zapisz wszystko”.").pack(side="left")
        ttk.Button(bar, text="Domyślne dla Magazynu", command=self.reset_defaults).pack(side="right", padx=8)

    def iter_setting_vars(self):
        """Zmienne używane przez integrację głównego zapisu Ustawień."""
        names = (
            "var_require_reauth",
            "var_rounding", "var_default_unit", "var_unit_mm", "var_unit_mb",
            "var_pz_prefix", "var_pz_width", "var_pz_zero_reset", "var_pz_seq_path",
            "var_auto_res", "var_only_started", "var_positive_only",
            "var_alert_pct", "var_auto_order",
            "var_perm_bryg_edit", "var_perm_bryg_pz", "var_perm_mag_edit", "var_perm_mag_pz",
        )
        for name in names:
            var = getattr(self, name, None)
            if isinstance(var, tk.Variable):
                yield var

    # =========================  OGÓLNE  =========================
    def _build_tab_ogolne(self, root):
        pad = dict(padx=8, pady=6)

        self.var_require_reauth = tk.BooleanVar(
            value=self.config_manager.get("magazyn.require_reauth", True)
        )
        ttk.Checkbutton(
            root,
            text="Wymagaj ponownej autoryzacji przy PZ/WZ",
            variable=self.var_require_reauth,
        ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.var_rounding = tk.BooleanVar(
            value=self.config_manager.get("magazyn.round_quantities", True)
        )
        ttk.Checkbutton(
            root,
            text="Zaokrąglaj ilości tam, gdzie wymaga tego jednostka",
            variable=self.var_rounding,
        ).grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        self.var_default_unit = tk.StringVar(
            value=self.config_manager.get("magazyn.default_unit", "szt")
        )
        ttk.Label(root, text="Domyślna jednostka:").grid(row=2, column=0, sticky="w", **pad)
        self.cmb_default_unit = ttk.Combobox(
            root,
            values=self.slowniki.get("jednostki", ["szt", "mb"]),
            textvariable=self.var_default_unit,
            state="readonly",
            width=12,
        )
        self.cmb_default_unit.grid(row=2, column=1, sticky="w", **pad)

        self.var_unit_mm = tk.BooleanVar(value=self.config_manager.get("magazyn.dim_in_mm", True))
        self.var_unit_mb = tk.BooleanVar(value=self.config_manager.get("magazyn.len_in_mb", True))
        ttk.Checkbutton(root, text="Wymiary w mm", variable=self.var_unit_mm).grid(row=3, column=0, sticky="w", **pad)
        ttk.Checkbutton(root, text="Długości w mb", variable=self.var_unit_mb).grid(row=3, column=1, sticky="w", **pad)

    # =========================  SŁOWNIKI  =========================
    def _build_tab_slowniki(self, root):
        pad = dict(padx=8, pady=6)

        ttk.Label(root, text="Typy pozycji widoczne w Magazynie:").grid(row=0, column=0, sticky="w", **pad)
        self.lst_typy = tk.Listbox(root, height=6, exportselection=False)
        self.lst_typy.grid(row=1, column=0, sticky="nsew", **pad)
        for t in self.slowniki.get("typy", []):
            self.lst_typy.insert("end", t)

        typ_btns = ttk.Frame(root)
        typ_btns.grid(row=1, column=1, sticky="ns", **pad)
        self.var_new_typ = tk.StringVar()
        ttk.Entry(typ_btns, textvariable=self.var_new_typ, width=18).pack(pady=(0, 6))
        ttk.Button(typ_btns, text="Dodaj", command=self._typy_add).pack(fill="x")
        ttk.Button(typ_btns, text="Usuń", command=self._typy_del).pack(fill="x", pady=(6, 0))

        ttk.Label(root, text="Jednostki:").grid(row=2, column=0, sticky="w", **pad)
        self.lst_jm = tk.Listbox(root, height=6, exportselection=False)
        self.lst_jm.grid(row=3, column=0, sticky="nsew", **pad)
        for j in self.slowniki.get("jednostki", []):
            self.lst_jm.insert("end", j)

        jm_btns = ttk.Frame(root)
        jm_btns.grid(row=3, column=1, sticky="ns", **pad)
        self.var_new_jm = tk.StringVar()
        ttk.Entry(jm_btns, textvariable=self.var_new_jm, width=18).pack(pady=(0, 6))
        ttk.Button(jm_btns, text="Dodaj", command=self._jm_add).pack(fill="x")
        ttk.Button(jm_btns, text="Usuń", command=self._jm_del).pack(fill="x", pady=(6, 0))
        root.columnconfigure(0, weight=1)

    def _typy_add(self):
        val = (self.var_new_typ.get() or "").strip()
        if not val:
            return
        cur = [self.lst_typy.get(i) for i in range(self.lst_typy.size())]
        cur = _dedup_str_list(cur + [val])
        self.lst_typy.delete(0, "end")
        for item in cur:
            self.lst_typy.insert("end", item)
        self.var_new_typ.set("")

    def _typy_del(self):
        for i in reversed(self.lst_typy.curselection()):
            self.lst_typy.delete(i)

    def _jm_add(self):
        val = (self.var_new_jm.get() or "").strip()
        if not val:
            return
        cur = [self.lst_jm.get(i) for i in range(self.lst_jm.size())]
        cur = _dedup_str_list(cur + [val])
        self.lst_jm.delete(0, "end")
        for item in cur:
            self.lst_jm.insert("end", item)
        self.var_new_jm.set("")
        self.cmb_default_unit.configure(values=cur)

    def _jm_del(self):
        for i in reversed(self.lst_jm.curselection()):
            self.lst_jm.delete(i)
        values = [self.lst_jm.get(i) for i in range(self.lst_jm.size())]
        self.cmb_default_unit.configure(values=values)
        if values and self.var_default_unit.get() not in values:
            self.var_default_unit.set(values[0])

    # =========================  PZ  =========================
    def _build_tab_pz(self, root):
        pad = dict(padx=8, pady=6)
        ttk.Label(root, text="Numeracja dokumentów PZ").grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.var_pz_prefix = tk.StringVar(value=self.config_manager.get("magazyn.pz.prefix", "PZ"))
        self.var_pz_width = tk.IntVar(value=self.config_manager.get("magazyn.pz.width", 5))
        self.var_pz_zero_reset = tk.BooleanVar(value=self.config_manager.get("magazyn.pz.reset_daily", False))
        self.var_pz_seq_path = tk.StringVar(
            value=self.config_manager.get("magazyn.pz.seq_file", os.path.join("data", "magazyn", "_seq_pz.json"))
        )

        ttk.Label(root, text="Prefiks:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(root, textvariable=self.var_pz_prefix, width=10).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(root, text="Liczba cyfr numeru:").grid(row=2, column=0, sticky="e", **pad)
        ttk.Spinbox(root, from_=1, to=10, textvariable=self.var_pz_width, width=7).grid(row=2, column=1, sticky="w", **pad)

        ttk.Checkbutton(root, text="Zeruj licznik codziennie", variable=self.var_pz_zero_reset).grid(row=3, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(
            root,
            text="Przykład: prefiks PZ i 5 cyfr daje numer PZ-00001.",
        ).grid(row=4, column=0, columnspan=2, sticky="w", **pad)

    # =========================  REZERWACJE  =========================
    def _build_tab_rezerwacje(self, root):
        pad = dict(padx=8, pady=6)
        self.var_auto_res = tk.BooleanVar(value=self.config_manager.get("magazyn.auto_rezerwacje", True))
        self.var_only_started = tk.BooleanVar(value=self.config_manager.get("magazyn.rezerwacje_only_started_orders", True))
        self.var_positive_only = tk.BooleanVar(value=self.config_manager.get("magazyn.rezerwacje_positive_only", True))

        ttk.Checkbutton(root, text="Automatyczne rezerwacje materiałów", variable=self.var_auto_res).grid(row=0, column=0, sticky="w", **pad)
        ttk.Checkbutton(root, text="Rezerwuj tylko dla rozpoczętych zleceń", variable=self.var_only_started).grid(row=1, column=0, sticky="w", **pad)
        ttk.Checkbutton(root, text="Odrzucaj ilości równe 0 i ujemne", variable=self.var_positive_only).grid(row=2, column=0, sticky="w", **pad)

    # =========================  ALERTY  =========================
    def _build_tab_alerty(self, root):
        pad = dict(padx=8, pady=6)
        self.var_alert_pct = tk.IntVar(value=self.config_manager.get("magazyn.alert_procent", 10))
        self.var_auto_order = tk.BooleanVar(value=self.config_manager.get("magazyn.low_stock_auto_order", True))

        ttk.Label(root, text="Próg alertu niskiego stanu:").grid(row=0, column=0, sticky="e", **pad)
        ttk.Spinbox(root, from_=1, to=100, textvariable=self.var_alert_pct, width=7).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(root, text="%").grid(row=0, column=2, sticky="w")

        ttk.Checkbutton(
            root,
            text="Automatycznie twórz „zamówienie materiału” przy niskim stanie",
            variable=self.var_auto_order,
        ).grid(row=1, column=0, columnspan=3, sticky="w", **pad)

    # =========================  UPRAWNIENIA  =========================
    def _build_tab_perms(self, root):
        pad = dict(padx=8, pady=6)
        ttk.Label(root, text="Uprawnienia do czynności w Magazynie").grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.var_perm_bryg_edit = tk.BooleanVar(value=self.config_manager.get("magazyn.perms.brygadzista.edit", True))
        self.var_perm_bryg_pz = tk.BooleanVar(value=self.config_manager.get("magazyn.perms.brygadzista.pz", False))
        self.var_perm_mag_edit = tk.BooleanVar(value=self.config_manager.get("magazyn.perms.magazynier.edit", True))
        self.var_perm_mag_pz = tk.BooleanVar(value=self.config_manager.get("magazyn.perms.magazynier.pz", True))

        ttk.Label(root, text="Brygadzista:").grid(row=1, column=0, sticky="w", **pad)
        frm_b = ttk.Frame(root)
        frm_b.grid(row=1, column=1, sticky="w", **pad)
        ttk.Checkbutton(frm_b, text="Edycja stanów/pozycji", variable=self.var_perm_bryg_edit).pack(side="left")
        ttk.Checkbutton(frm_b, text="Dokumenty PZ", variable=self.var_perm_bryg_pz).pack(side="left", padx=10)

        ttk.Label(root, text="Magazynier:").grid(row=2, column=0, sticky="w", **pad)
        frm_m = ttk.Frame(root)
        frm_m.grid(row=2, column=1, sticky="w", **pad)
        ttk.Checkbutton(frm_m, text="Edycja stanów/pozycji", variable=self.var_perm_mag_edit).pack(side="left")
        ttk.Checkbutton(frm_m, text="Dokumenty PZ", variable=self.var_perm_mag_pz).pack(side="left", padx=10)

    # =========================  ZAPIS / RESET  =========================
    def save_all(self, show_message=True):
        self.config_manager.set("magazyn.require_reauth", bool(self.var_require_reauth.get()))
        self.config_manager.set("magazyn.round_quantities", bool(self.var_rounding.get()))
        self.config_manager.set("magazyn.default_unit", self.var_default_unit.get())
        self.config_manager.set("magazyn.dim_in_mm", bool(self.var_unit_mm.get()))
        self.config_manager.set("magazyn.len_in_mb", bool(self.var_unit_mb.get()))

        self.config_manager.set("magazyn.pz.prefix", (self.var_pz_prefix.get() or "PZ").strip() or "PZ")
        self.config_manager.set("magazyn.pz.width", max(1, min(10, int(self.var_pz_width.get() or 5))))
        self.config_manager.set("magazyn.pz.reset_daily", bool(self.var_pz_zero_reset.get()))
        self.config_manager.set(
            "magazyn.pz.seq_file",
            (self.var_pz_seq_path.get() or os.path.join("data", "magazyn", "_seq_pz.json")).strip(),
        )

        self.config_manager.set("magazyn.auto_rezerwacje", bool(self.var_auto_res.get()))
        self.config_manager.set("magazyn.rezerwacje_only_started_orders", bool(self.var_only_started.get()))
        self.config_manager.set("magazyn.rezerwacje_positive_only", bool(self.var_positive_only.get()))

        self.config_manager.set("magazyn.alert_procent", max(1, min(100, int(self.var_alert_pct.get() or 10))))
        self.config_manager.set("magazyn.low_stock_auto_order", bool(self.var_auto_order.get()))

        self.config_manager.set("magazyn.perms.brygadzista.edit", bool(self.var_perm_bryg_edit.get()))
        self.config_manager.set("magazyn.perms.brygadzista.pz", bool(self.var_perm_bryg_pz.get()))
        self.config_manager.set("magazyn.perms.magazynier.edit", bool(self.var_perm_mag_edit.get()))
        self.config_manager.set("magazyn.perms.magazynier.pz", bool(self.var_perm_mag_pz.get()))

        typy = [self.lst_typy.get(i) for i in range(self.lst_typy.size())]
        jm = [self.lst_jm.get(i) for i in range(self.lst_jm.size())]
        saved = _save_slowniki({"typy": typy, "jednostki": jm})

        self.config_manager.save()
        if show_message:
            if saved:
                messagebox.showinfo("Ustawienia", "Zapisano ustawienia i słowniki Magazynu.")
            else:
                messagebox.showwarning("Ustawienia", "Ustawienia zapisane. Słowniki nie zostały zapisane.")
        return saved

    def reset_defaults(self):
        if not messagebox.askyesno("Potwierdź", "Przywrócić domyślne ustawienia Magazynu?"):
            return
        self.var_require_reauth.set(True)
        self.var_rounding.set(True)
        self.var_default_unit.set("szt")
        self.var_unit_mm.set(True)
        self.var_unit_mb.set(True)

        self.var_pz_prefix.set("PZ")
        self.var_pz_width.set(5)
        self.var_pz_zero_reset.set(False)
        self.var_pz_seq_path.set(os.path.join("data", "magazyn", "_seq_pz.json"))

        self.var_auto_res.set(True)
        self.var_only_started.set(True)
        self.var_positive_only.set(True)
        self.var_alert_pct.set(10)
        self.var_auto_order.set(True)

        self.var_perm_bryg_edit.set(True)
        self.var_perm_bryg_pz.set(False)
        self.var_perm_mag_edit.set(True)
        self.var_perm_mag_pz.set(True)

        self.lst_typy.delete(0, "end")
        for item in ["profil", "rura", "polprodukt"]:
            self.lst_typy.insert("end", item)
        self.lst_jm.delete(0, "end")
        for item in ["szt", "mb"]:
            self.lst_jm.insert("end", item)
        self.cmb_default_unit.configure(values=["szt", "mb"])
