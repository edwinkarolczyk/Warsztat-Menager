# gui_orders.py
# Wersja pliku: 1.2.0
# Zmiany:
# - [1.0.0] Szkielet okna + zapis draftu
# - [1.1.0] Prefill z contextu (Magazyn/Zlecenia/Narzędzia)
# - [1.2.0] Indeks zamówień (lista) + filtr statusów + zmiana statusu i zapis
#
# Uwagi:
# - Teksty w UI po polsku (wymóg WM)
# - Logi: [WM-DBG][ORDERS]
# - Zgodność z dark theme: jeżeli globalne apply_theme() istnieje, użyj

import os
import json
import glob
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox

# --- USTAWIENIA MODUŁU ZAMÓWIENIA ---
DEFAULT_ORDERS_SETTINGS = {
    "enabled": True,
    "enabled_steps": [
        "typ",
        "kontekst",
        "pozycje",
        "dostawca",
        "terminy_status",
        "podsumowanie",
    ],
    "types": ["zakup", "naprawa", "uzupelnienie"],
    "statuses": [
        "draft",
        "oczekuje_wyslania",
        "wyslane",
        "w_realizacji",
        "dostarczone",
        "zamkniete",
        "anulowane",
    ],
    "data_dir": "data/zamowienia",
    "default_supplier": "",
    "auto_id_format": "ORD-{YYYYMMDD}-{HHMMSS}",
    "permissions": {
        "create": ["brygadzista", "kierownik", "admin"],
        "receive": ["magazynier", "kierownik", "admin"],
        "cancel": ["kierownik", "admin"],
    },
}

def _get_orders_settings(master) -> dict:
    cfg = DEFAULT_ORDERS_SETTINGS.copy()
    try:
        # Preferowana ścieżka: master.config_manager.data["orders"]
        if hasattr(master, "config_manager") and getattr(master.config_manager, "data", None):
            data = master.config_manager.data.get("orders", {})
        elif hasattr(master, "get_config"):
            data = (master.get_config() or {}).get("orders", {})
        else:
            data = {}
        if isinstance(data, dict):
            for k in cfg.keys():
                if k in data:
                    cfg[k] = data[k]
    except Exception as e:
        print(f"[ERROR][ORDERS] Nie udało się wczytać ustawień Zamówień: {e}")
    return cfg

# Ustalane dynamicznie wg ustawień (patrz __init__)
ORDERS_DIR = "data/zamowienia"

def _ensure_orders_dir():
    try:
        os.makedirs(ORDERS_DIR, exist_ok=True)
    except Exception as e:
        print(f"[ERROR][ORDERS] Nie można utworzyć katalogu {ORDERS_DIR}: {e}")

def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class OrdersWindow(tk.Toplevel):
    def __init__(self, master=None, context=None):  # Etap 2: context
        super().__init__(master)
        self.title("Zamówienia")
        self.geometry("960x560")
        self.minsize(900, 520)

        # Ciemny motyw, jeśli dostępny
        try:
            if hasattr(master, "apply_theme"):
                master.apply_theme()
            elif "apply_theme" in globals():
                globals()["apply_theme"]()
        except Exception:
            pass

        # Ustawienia
        self.settings = _get_orders_settings(master)
        if self.settings.get("enabled") is False:
            messagebox.showwarning("Zamówienia", "Moduł Zamówienia jest wyłączony w Ustawieniach.")
            self.destroy()
            return

        global ORDERS_DIR
        ORDERS_DIR = os.path.normpath(self.settings.get("data_dir") or "data/zamowienia")
        _ensure_orders_dir()

        self.enabled_steps = list(self.settings.get("enabled_steps") or [])
        self.allowed_types = list(self.settings.get("types") or [])
        self.statuses = list(self.settings.get("statuses") or [])
        self.default_supplier = self.settings.get("default_supplier") or ""

        # Kontekst (Etap 2)
        self.context = context or {}

        # Aktualny order w edycji (po prawej)
        self.order_path = None
        self.order_draft = {
            "wersja": "1.2.0",
            "id": None,
            "typ": None,  # 'zakup' | 'naprawa' | 'uzupelnienie'
            "powiazania": {},
            "pozycje": [],
            "dostawca": {"nazwa": self.default_supplier}
            if self.default_supplier
            else {},
            "termin_oczekiwany": None,
            "status": (
                "draft"
                if "draft" in self.statuses
                else (self.statuses[0] if self.statuses else "draft")
            ),
            "historia": [],
            "uwagi": "",
        }

        # Prefill (Etap 2)
        try:
            self._apply_context(self.context)
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd prefill z contextu: {e}")

        # Stan indeksu (Etap 3)
        self.index_rows = []  # list[dict]: {"id","status","path"}
        self.index_filter = tk.StringVar(value="wszystkie")

        self._build_ui()
        self._refresh_index()  # wczytaj listę na starcie

        print("[WM-DBG][ORDERS] Otwarto okno Zamówienia")

    # ========== UI ==========
    def _build_ui(self):
        rootpw = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        rootpw.pack(fill=tk.BOTH, expand=True)

        # Lewy panel: indeks zamówień
        left = ttk.Frame(rootpw, width=280)
        rootpw.add(left, weight=1)

        filt_frame = ttk.Frame(left)
        filt_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(filt_frame, text="Filtr statusu:").pack(side=tk.LEFT)
        cb = ttk.Combobox(filt_frame, state="readonly",
                          values=["wszystkie"] + self.statuses,
                          textvariable=self.index_filter, width=22)
        cb.pack(side=tk.LEFT, padx=(6, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_index())

        self.lb = tk.Listbox(left, height=22)
        self.lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))
        self.lb.bind("<<ListboxSelect>>", lambda e: self._on_index_select())

        # Prawy panel: obecny „kreator” (na razie opis + akcje)
        right = ttk.Frame(rootpw)
        rootpw.add(right, weight=3)

        # Pasek górny
        top = ttk.Frame(right)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        ttk.Label(
            top,
            text="Kreator zamówienia (szkielet)",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side=tk.LEFT)

        btn_save = ttk.Button(top, text="Zapisz draft", command=self._save_draft)
        btn_save.pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(top, text="Zamknij", command=self.destroy).pack(side=tk.RIGHT)

        # Pasek statusu zamówienia (Etap 3)
        stat = ttk.Frame(right)
        stat.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0,10))

        ttk.Label(stat, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value=self.order_draft["status"])
        self.status_cb = ttk.Combobox(stat, state="readonly", width=28,
                                      values=self.statuses, textvariable=self.status_var)
        self.status_cb.pack(side=tk.LEFT, padx=6)

        ttk.Button(
            stat,
            text="Zmień status",
            command=self._change_status,
        ).pack(side=tk.LEFT, padx=6)

        # Treść „kreatora” – opis (jak dotąd)
        body = ttk.Frame(right)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        plan_txt = (
            "Kroki (wg Ustawień):\n"
            "1) typ\n"
            "2) kontekst\n"
            "3) pozycje\n"
            "4) dostawca\n"
            "5) terminy_status\n"
            "6) podsumowanie\n\n"
            "Obecnie to tylko szkielet – bez logiki integracji."
        )
        info_lines = [
            "Kroki aktywne: " + ", ".join(self.enabled_steps),
            "Dozwolone typy: " + ", ".join(self.allowed_types),
            "Statusy: " + " → ".join(self.statuses),
            f"Katalog danych: {ORDERS_DIR}",
        ]
        ttk.Label(body, text="\n".join(info_lines) + "\n\n" + plan_txt,
                  justify=tk.LEFT).pack(anchor="w")

    # ========== Indeks (Etap 3) ==========
    def _scan_orders_dir(self):
        rows = []
        for path in sorted(glob.glob(os.path.join(ORDERS_DIR, "ORD-*.json"))):
            try:
                data = _read_json(path)
                oid = data.get("id") or os.path.splitext(os.path.basename(path))[0]
                st = data.get("status") or "draft"
                rows.append({"id": oid, "status": st, "path": path})
            except Exception as e:
                print(f"[ERROR][ORDERS] Nie można odczytać {path}: {e}")
        return rows

    def _refresh_index(self):
        self.index_rows = self._scan_orders_dir()
        flt = self.index_filter.get()
        self.lb.delete(0, tk.END)
        for r in self.index_rows:
            if flt != "wszystkie" and r["status"] != flt:
                continue
            self.lb.insert(tk.END, f"{r['id']} · {r['status']}")

    def _find_row_by_label(self, label):
        # label format: "ORD-YYYYMMDD-HHMMSS · status"
        oid = label.split(" · ", 1)[0].strip()
        for r in self.index_rows:
            if r["id"] == oid:
                return r
        return None

    def _on_index_select(self):
        if not self.lb.curselection():
            return
        label = self.lb.get(self.lb.curselection()[0])
        row = self._find_row_by_label(label)
        if not row:
            return
        try:
            data = _read_json(row["path"])
            self.order_path = row["path"]
            self.order_draft = data
            # ustaw combobox statusu pod bieżący dokument
            self.status_var.set(self.order_draft.get("status", "draft"))
            print(f"[WM-DBG][ORDERS] Załadowano: {row['path']}")
        except Exception as e:
            print(f"[ERROR][ORDERS] Nie można załadować {row['path']}: {e}")

    # ========== Zmiana statusu (Etap 3) ==========
    def _change_status(self):
        new_st = self.status_var.get()
        if not new_st:
            messagebox.showwarning("Status", "Wybierz status.")
            return
        if new_st not in self.statuses:
            messagebox.showerror("Status", f"Status '{new_st}' nie jest dozwolony.")
            return

        self.order_draft["status"] = new_st
        self.order_draft.setdefault("historia", []).append({
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "user": "system",
            "akcja": f"status->{new_st}",
            "komentarz": ""
        })

        # Zapisz do bieżącego pliku (jeśli to nie-tymczasowy)
        path = self.order_path or os.path.join(
            ORDERS_DIR,
            f"{self.order_draft.get('id') or self._generate_id()}.json",
        )
        # Upewnij się, że mamy ID
        if not self.order_draft.get("id"):
            self.order_draft["id"] = os.path.splitext(os.path.basename(path))[0]

        try:
            _write_json(path, self.order_draft)
            self.order_path = path
            print(f"[WM-DBG][ORDERS] Zmieniono status i zapisano: {path}")
            self._refresh_index()
            messagebox.showinfo("Zapisano", f"Zmieniono status na: {new_st}")
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd zapisu po zmianie statusu: {e}")
            messagebox.showerror("Błąd", f"Nie udało się zapisać zmian statusu:\n{e}")

    # ========== Prefill z contextu (Etap 2) ==========
    def _normalize_position(self, item):
        """Zamienia różne nazwy pól z Magazynu/BOM na standard 'pozycje'."""
        kod = item.get("kod") or item.get("id") or item.get("sku") or item.get("symbol") or ""
        nazwa = item.get("nazwa") or item.get("name") or item.get("opis") or ""
        ilosc = item.get("ilosc") or item.get("qty") or item.get("quantity") or 0
        jm = item.get("j") or item.get("jm") or item.get("unit") or item.get("jednostka") or "szt"
        cena = item.get("cena_netto") or item.get("cena") or item.get("price") or None
        dost = item.get("dostawca") or item.get("supplier") or None

        pos = {"kod": kod, "nazwa": nazwa, "ilosc": ilosc, "j": jm}
        if cena is not None: pos["cena_netto"] = cena
        if dost is not None:
            if isinstance(dost, str):
                pos["dostawca"] = dost
            elif isinstance(dost, dict) and dost.get("nazwa"):
                pos["dostawca"] = dost.get("nazwa")
        return pos

    def _apply_context(self, ctx: dict):
        if not isinstance(ctx, dict):
            return

        typ = ctx.get("typ")
        if typ in self.allowed_types:
            self.order_draft["typ"] = typ

        for key in ("narzedzie_id", "zlecenie_id", "bom_kod"):
            if ctx.get(key):
                self.order_draft["powiazania"][key] = ctx[key]

        items = ctx.get("pozycje") or ctx.get("positions") or ctx.get("braki") or []
        if isinstance(items, list):
            normalized = [self._normalize_position(x) for x in items if isinstance(x, dict)]
            normalized = [p for p in normalized if float(p.get("ilosc", 0)) > 0]
            if normalized:
                self.order_draft["pozycje"].extend(normalized)

        if isinstance(ctx.get("dostawca"), str) and ctx["dostawca"]:
            self.order_draft["dostawca"] = {"nazwa": ctx["dostawca"]}

    # ========== ID + Zapis draftu ==========
    def _generate_id(self) -> str:
        fmt = self.settings.get("auto_id_format") or "ORD-{YYYYMMDD}-{HHMMSS}"
        now = dt.datetime.now()
        token_map = {
            "{YYYY}": now.strftime("%Y"),
            "{MM}": now.strftime("%m"),
            "{DD}": now.strftime("%d"),
            "{YYYYMMDD}": now.strftime("%Y%m%d"),
            "{HH}": now.strftime("%H"),
            "{MMm}": now.strftime("%M"),  # inny token dla minut, aby nie mylić z miesiącem
            "{SS}": now.strftime("%S"),
            "{HHMMSS}": now.strftime("%H%M%S")
        }
        for k, v in token_map.items():
            fmt = fmt.replace(k, v)
        return fmt

    def _save_draft(self):
        _ensure_orders_dir()
        if not self.order_draft.get("id"):
            self.order_draft["id"] = self._generate_id()

        self.order_draft.setdefault("historia", []).append({
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "user": "system",
            "akcja": "zapis_draft",
            "komentarz": ""
        })

        path = os.path.join(ORDERS_DIR, f"{self.order_draft['id']}.json")
        try:
            _write_json(path, self.order_draft)
            self.order_path = path
            print(f"[WM-DBG][ORDERS] Zapisano draft: {path}")
            messagebox.showinfo("Zapisano", f"Zapisano draft zamówienia:\n{self.order_draft['id']}")
            self._refresh_index()
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd zapisu draftu: {e}")
            messagebox.showerror("Błąd", f"Nie udało się zapisać: {e}")

def open_orders_window(master=None, context=None):
    """Funkcja pomocnicza do otwarcia okna z innych modułów."""
    try:
        win = OrdersWindow(master=master, context=context)
        win.transient(master)
        win.grab_set()
        win.focus_set()
    except Exception as e:
        print(f"[ERROR][ORDERS] Nie udało się otworzyć okna Zamówienia: {e}")

# ⏹ KONIEC KODU

