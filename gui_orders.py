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
    "enabled_steps": ["typ","kontekst","pozycje","dostawca","terminy_status","podsumowanie"],
    "types": ["zakup","naprawa","uzupelnienie"],
    "statuses": ["draft","oczekuje_wyslania","wyslane","w_realizacji","dostarczone","zamkniete","anulowane"],
    "data_dir": "data/zamowienia",
    "default_supplier": "",
    "auto_id_format": "ORD-{YYYYMMDD}-{HHMMSS}",
    "permissions": {
        "create": ["brygadzista","kierownik","admin"],
        "receive": ["magazynier","kierownik","admin"],
        "cancel": ["kierownik","admin"]
    }
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

class OrdersWindow(tk.Toplevel):
    def __init__(self, master=None):
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

        self.order_draft = {
            "wersja": "1.0.0",
            "id": None,
            "typ": None,  # 'zakup' | 'naprawa' | 'uzupelnienie'
            "powiazania": {},
            "pozycje": [],
            "dostawca": {"nazwa": self.default_supplier} if self.default_supplier else {},
            "termin_oczekiwany": None,
            "status": "draft" if "draft" in self.statuses else (self.statuses[0] if self.statuses else "draft"),
            "historia": [],
            "uwagi": ""
        }

        self._build_ui()
        print("[WM-DBG][ORDERS] Otwarto okno Zamówienia")

    def _build_ui(self):
        # Pasek górny (nagłówek + akcje)
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        lbl = ttk.Label(top, text="Kreator zamówienia (szkielet)", font=("TkDefaultFont", 12, "bold"))
        lbl.pack(side=tk.LEFT)

        btn_save = ttk.Button(top, text="Zapisz draft", command=self._save_draft)
        btn_save.pack(side=tk.RIGHT, padx=(6, 0))
        btn_close = ttk.Button(top, text="Zamknij", command=self.destroy)
        btn_close.pack(side=tk.RIGHT)

        # Placeholder kroków kreatora (1–6)
        body = ttk.Frame(self)
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
        lbl_info = ttk.Label(body, text="\n".join(info_lines) + "\n\n" + plan_txt, justify=tk.LEFT)
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
            "{MMm}": now.strftime("%M"),  # uwaga: inny token dla minut niż {MM} miesiąca
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

        self.order_draft["historia"].append({
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "user": "system",  # do podmiany po integracji z profilami
            "akcja": "zapis_draft",
            "komentarz": ""
        })

        path = os.path.join(ORDERS_DIR, f"{self.order_draft['id']}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.order_draft, f, ensure_ascii=False, indent=2)
            print(f"[WM-DBG][ORDERS] Zapisano draft: {path}")
            messagebox.showinfo("Zapisano", f"Zapisano draft zamówienia:\n{self.order_draft['id']}")
        except Exception as e:
            print(f"[ERROR][ORDERS] Błąd zapisu draftu: {e}")
            messagebox.showerror("Błąd", f"Nie udało się zapisać: {e}")

def open_orders_window(master=None):
    """Funkcja pomocnicza do otwarcia okna z innych modułów."""
    try:
        win = OrdersWindow(master=master)
        win.transient(master)
        win.grab_set()
        win.focus_set()
    except Exception as e:
        print(f"[ERROR][ORDERS] Nie udało się otworzyć okna Zamówienia: {e}")

# ⏹ KONIEC KODU
