# gui_orders.py
# Wersja pliku: 1.0.0
# Zmiany:
# - [1.0.0] Pierwsza wersja: szkielet okna Zamówienia (Toplevel) + zapis draftu do JSON
# - Minimalna implementacja, bez integracji z Magazynem/Zleceniami/Narzędziami
#
# Uwagi:
# - Teksty w UI po polsku (wymóg WM)
# - Logi: [WM-DBG][ORDERS]
# - Zgodność z dark theme: jeżeli globalne apply_theme() istnieje, użyj

import os
import json
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox

# --- USTAWIENIA MODUŁU ZAMÓWIENIA ---
DEFAULT_ORDERS_SETTINGS = {
    "enabled": True,
    "enabled_steps": ["typ", "kontekst", "pozycje", "dostawca", "terminy_status", "podsumowanie"],
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


class OrdersWindow(tk.Toplevel):
    def __init__(self, master=None, context=None):
        super().__init__(master)
        self.title("Zamówienia")
        self.geometry("760x520")
        self.minsize(720, 480)

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
            messagebox.showwarning(
                "Zamówienia",
                "Moduł Zamówienia jest wyłączony w Ustawieniach.",
            )
            self.destroy()
            return

        global ORDERS_DIR
        ORDERS_DIR = os.path.normpath(
            self.settings.get("data_dir") or "data/zamowienia"
        )
        _ensure_orders_dir()

        self.enabled_steps = list(self.settings.get("enabled_steps") or [])
        self.allowed_types = list(self.settings.get("types") or [])
        self.statuses = list(self.settings.get("statuses") or [])
        self.context = context or {}
        self.default_supplier = self.settings.get("default_supplier") or ""

        self.order_draft = {
            "wersja": "1.0.0",
            "id": None,
            "typ": None,
            "powiazania": {},
            "pozycje": [],
            "dostawca": {"nazwa": self.default_supplier}
            if self.default_supplier
            else {},
            "termin_oczekiwany": None,
            "status": "draft"
            if "draft" in self.statuses
            else (self.statuses[0] if self.statuses else "draft"),
            "historia": [],
            "uwagi": "",
        }

        try:
            self._apply_context(self.context)
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd prefill z contextu: {e}")

        self._build_ui()
        print("[WM-DBG][ORDERS] Otwarto okno Zamówienia")

    def _normalize_position(self, item):
        """Zamienia różne nazwy pól z Magazynu/BOM na standard 'pozycje'."""
        kod = (
            item.get("kod")
            or item.get("id")
            or item.get("sku")
            or item.get("symbol")
            or ""
        )
        nazwa = item.get("nazwa") or item.get("name") or item.get("opis") or ""
        ilosc = item.get("ilosc") or item.get("qty") or item.get("quantity") or 0
        jm = (
            item.get("j")
            or item.get("jm")
            or item.get("unit")
            or item.get("jednostka")
            or "szt"
        )
        cena = (
            item.get("cena_netto")
            or item.get("cena")
            or item.get("price")
            or None
        )
        dost = item.get("dostawca") or item.get("supplier") or None

        pos = {"kod": kod, "nazwa": nazwa, "ilosc": ilosc, "j": jm}
        if cena is not None:
            pos["cena_netto"] = cena
        if dost is not None:
            if isinstance(dost, str):
                pos["dostawca"] = dost
            elif isinstance(dost, dict) and dost.get("nazwa"):
                pos["dostawca"] = dost.get("nazwa")
        return pos

    def _apply_context(self, ctx: dict):
        """Obsługuje context przekazany z innych modułów."""
        if not isinstance(ctx, dict):
            return

        typ = ctx.get("typ")
        if typ in self.allowed_types:
            self.order_draft["typ"] = typ

        for key in ("narzedzie_id", "zlecenie_id", "bom_kod"):
            if ctx.get(key):
                self.order_draft["powiazania"][key] = ctx[key]

        items = (
            ctx.get("pozycje")
            or ctx.get("positions")
            or ctx.get("braki")
            or []
        )
        if isinstance(items, list):
            normalized = [
                self._normalize_position(x) for x in items if isinstance(x, dict)
            ]
            normalized = [p for p in normalized if float(p.get("ilosc", 0)) > 0]
            if normalized:
                self.order_draft["pozycje"].extend(normalized)

        if isinstance(ctx.get("dostawca"), str) and ctx["dostawca"]:
            self.order_draft["dostawca"] = {"nazwa": ctx["dostawca"]}

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        lbl = ttk.Label(
            top,
            text="Kreator zamówienia (szkielet)",
            font=("TkDefaultFont", 12, "bold"),
        )
        lbl.pack(side=tk.LEFT)

        btn_save = ttk.Button(top, text="Zapisz draft", command=self._save_draft)
        btn_save.pack(side=tk.RIGHT, padx=(6, 0))
        btn_close = ttk.Button(top, text="Zamknij", command=self.destroy)
        btn_close.pack(side=tk.RIGHT)

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

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
        lbl_info = ttk.Label(
            body,
            text="\n".join(info_lines) + "\n\n" + plan_txt,
            justify=tk.LEFT,
        )
        lbl_info.pack(anchor="w")

    def _generate_id(self) -> str:
        fmt = self.settings.get("auto_id_format") or "ORD-{YYYYMMDD}-{HHMMSS}"
        now = dt.datetime.now()
        token_map = {
            "{YYYY}": now.strftime("%Y"),
            "{MM}": now.strftime("%m"),
            "{DD}": now.strftime("%d"),
            "{YYYYMMDD}": now.strftime("%Y%m%d"),
            "{HH}": now.strftime("%H"),
            "{MMm}": now.strftime("%M"),
            "{SS}": now.strftime("%S"),
            "{HHMMSS}": now.strftime("%H%M%S"),
        }
        for k, v in token_map.items():
            fmt = fmt.replace(k, v)
        return fmt

    def _save_draft(self):
        _ensure_orders_dir()
        if not self.order_draft.get("id"):
            self.order_draft["id"] = self._generate_id()

        self.order_draft["historia"].append(
            {
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "user": "system",
                "akcja": "zapis_draft",
                "komentarz": "",
            }
        )

        path = os.path.join(ORDERS_DIR, f"{self.order_draft['id']}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.order_draft, f, ensure_ascii=False, indent=2)
            print(f"[WM-DBG][ORDERS] Zapisano draft: {path}")
            messagebox.showinfo(
                "Zapisano", f"Zapisano draft zamówienia:\n{self.order_draft['id']}"
            )
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd zapisu draftu: {e}")
            messagebox.showerror(
                "Błąd", f"Nie udało się zapisać: {e}"
            )


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

