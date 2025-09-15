# gui_orders.py
# Wersja pliku: 1.1.0
# Zmiany:
# - [1.1.0] Dodano obsługę konfiguracji modułu Zamówień (flaga włączenia i
#           katalog) oraz zabezpieczenie w ``open_orders_window``.
# - [1.0.0] Pierwsza wersja: szkielet okna Zamówienia (Toplevel) +
#           zapis draftu do JSON
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

ORDERS_DIR = os.path.join("data", "zamowienia")

# Domyślne ustawienia modułu Zamówień
DEFAULT_ORDERS_SETTINGS = {
    "enabled": True,
    "dir": ORDERS_DIR,
}


def _get_orders_settings(master=None):
    """Pobierz ustawienia modułu Zamówień z konfiguracji.

    Najpierw pobiera domyślne wartości z ``DEFAULT_ORDERS_SETTINGS`` i nadpisuje
    je wartościami z ``master.config_manager`` jeśli taki obiekt jest dostępny.
    W przeciwnym razie próbuje skorzystać z funkcji ``get_config()`` jeżeli
    została zdefiniowana globalnie.
    """

    settings = DEFAULT_ORDERS_SETTINGS.copy()
    cm = getattr(master, "config_manager", None) if master else None

    if cm and hasattr(cm, "get"):
        settings["enabled"] = cm.get(
            "orders.enabled", settings["enabled"]
        )
        settings["dir"] = cm.get("orders.dir", settings["dir"])
        return settings

    get_cfg = globals().get("get_config")
    if callable(get_cfg):
        try:
            cfg = get_cfg()
        except Exception:
            cfg = None

        if isinstance(cfg, dict):
            orders = cfg.get("orders") or {}
            if isinstance(orders, dict):
                settings.update({k: orders.get(k, settings[k]) for k in settings})
            else:
                settings["enabled"] = cfg.get(
                    "orders.enabled", settings["enabled"]
                )
                settings["dir"] = cfg.get("orders.dir", settings["dir"])
        elif hasattr(cfg, "get"):
            settings["enabled"] = cfg.get(
                "orders.enabled", settings["enabled"]
            )
            settings["dir"] = cfg.get("orders.dir", settings["dir"])

    return settings


def _ensure_orders_dir():
    try:
        os.makedirs(ORDERS_DIR, exist_ok=True)
    except Exception as e:
        print(
            f"[ERROR][ORDERS] Nie można utworzyć katalogu {ORDERS_DIR}: {e}"
        )


class OrdersWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        settings = _get_orders_settings(master)
        if not settings.get("enabled", True):
            messagebox.showinfo(
                "Zamówienia", "Moduł Zamówienia jest wyłączony."
            )
            self.destroy()
            return

        global ORDERS_DIR
        ORDERS_DIR = settings.get("dir", ORDERS_DIR)
        _ensure_orders_dir()

        self.title("Zamówienia")
        self.geometry("760x520")
        self.minsize(720, 480)
        self.order_draft = {
            "wersja": "1.0.0",
            "id": None,
            "typ": None,  # 'zakup' | 'naprawa' | 'uzupelnienie'
            "powiazania": {},
            "pozycje": [],
            "dostawca": {},
            "termin_oczekiwany": None,
            "status": "draft",
            "historia": [],
            "uwagi": "",
        }

        # Ciemny motyw, jeśli dostępny
        try:
            if hasattr(master, "apply_theme"):
                master.apply_theme()
            elif "apply_theme" in globals():
                globals()["apply_theme"]()
        except Exception as _:
            pass

        self._build_ui()
        print("[WM-DBG][ORDERS] Otwarto okno Zamówienia")

    def _build_ui(self):
        # Pasek górny (nagłówek + akcje)
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

        # Placeholder kroków kreatora (1–6)
        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        txt = (
            "Kroki (plan):\n"
            "1) Typ zamówienia (Zakup / Naprawa / Uzupełnienie)\n"
            "2) Źródło / kontekst (auto z Magazynu/Narzędzi/Zleceń) lub ręcznie\n"
            "3) Pozycje (tabela: kod, nazwa, ilość, j.m., cena, dostawca)\n"
            "4) Dostawca / Wykonawca\n"
            "5) Terminy i status\n"
            "6) Podsumowanie (ID, zapis, podgląd)\n\n"
            "Obecnie to tylko szkielet – bez logiki integracji."
        )
        lbl_info = ttk.Label(body, text=txt, justify=tk.LEFT)
        lbl_info.pack(anchor="w")

    def _generate_id(self) -> str:
        today = dt.datetime.now().strftime("%Y%m%d")
        seq = int(dt.datetime.now().strftime("%H%M%S"))
        return f"ORD-{today}-{seq:06d}"

    def _save_draft(self):
        _ensure_orders_dir()
        if not self.order_draft.get("id"):
            self.order_draft["id"] = self._generate_id()

        self.order_draft["historia"].append(
            {
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "user": "system",  # do podmiany po integracji z profilami
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
            messagebox.showerror("Błąd", f"Nie udało się zapisać: {e}")


def open_orders_window(master=None):
    """Funkcja pomocnicza do otwarcia okna z innych modułów."""
    try:
        win = OrdersWindow(master=master)
        if not win.winfo_exists():
            return
        win.transient(master)
        win.grab_set()
        win.focus_set()
    except Exception as e:
        print(f"[ERROR][ORDERS] Nie udało się otworzyć okna Zamówienia: {e}")

# ⏹ KONIEC KODU
