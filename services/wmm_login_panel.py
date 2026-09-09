from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_WATCHER_STARTED = False
_WATCHER_LOCK = threading.Lock()


def _panel_exists(root) -> bool:
    try:
        return bool(getattr(root, "_wmm_pairing_panel", None)) and root._wmm_pairing_panel.winfo_exists()
    except Exception:
        return False


def _build_panel(root) -> None:
    """Umieść mały panel parowania WMM w lewym dolnym rogu logowania."""
    if _panel_exists(root):
        return

    try:
        import tkinter as tk
        from tkinter import ttk
        from PIL import ImageTk
        import qrcode
        from services.wmm_api import pairing_info

        info = pairing_info()
        panel = ttk.Frame(root, style="WM.Card.TFrame", padding=10)
        panel.place(x=18, rely=1.0, y=-18, anchor="sw")
        root._wmm_pairing_panel = panel

        ttk.Label(panel, text="WMM", style="WM.H2.TLabel").pack(anchor="w")
        ttk.Label(
            panel,
            text="● API aktywne",
            style="WM.Muted.TLabel",
            foreground="#22c55e",
        ).pack(anchor="w", pady=(0, 6))

        qr = qrcode.QRCode(version=None, box_size=4, border=2)
        qr.add_data(str(info["qr"]))
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        photo = ImageTk.PhotoImage(image)
        label = tk.Label(panel, image=photo, bd=0, bg="white")
        label.image = photo
        label.pack(pady=(0, 6))

        ttk.Label(
            panel,
            text=f"{info['host']}:{info['port']}",
            style="WM.Card.TLabel",
        ).pack(anchor="center")
        ttk.Label(
            panel,
            text="Zeskanuj w WMM",
            style="WM.Muted.TLabel",
        ).pack(anchor="center")
    except Exception:
        logger.exception("[WMM] Nie udało się zbudować panelu QR logowania")


def _watch_login_screen() -> None:
    """Czekaj na gotowy ekran logowania i zleć utworzenie panelu w wątku Tk."""
    while True:
        try:
            import sys

            module = sys.modules.get("gui_logowanie")
            root = getattr(module, "root_global", None) if module is not None else None
            pin = getattr(module, "entry_pin", None) if module is not None else None
            if root is not None and pin is not None:
                try:
                    if root.winfo_exists() and pin.winfo_exists():
                        if not _panel_exists(root):
                            try:
                                root.after(0, lambda r=root: _build_panel(r))
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)


def start_login_panel_watcher() -> None:
    global _WATCHER_STARTED
    with _WATCHER_LOCK:
        if _WATCHER_STARTED:
            return
        _WATCHER_STARTED = True
        threading.Thread(
            target=_watch_login_screen,
            name="wm-wmm-login-panel",
            daemon=True,
        ).start()
