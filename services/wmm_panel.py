from __future__ import annotations

import logging
import sys
import threading
import time

logger = logging.getLogger(__name__)

_WATCHER_STARTED = False
_WATCHER_LOCK = threading.Lock()


def _panel_exists(root) -> bool:
    try:
        panel = getattr(root, "_wmm_main_panel", None)
        return bool(panel) and bool(panel.winfo_exists())
    except Exception:
        return False


def _update_footer(root) -> None:
    """Dopisz zgodność WMM do istniejącej stopki WM bez przebudowy stopki."""
    try:
        from __version__ import __version__ as wm_version
        from services.wmm_api import WMM_COMPAT_VERSION

        wanted = (
            f"Warsztat Menager v{wm_version} | "
            f"Kompatybilne z WMM v{WMM_COMPAT_VERSION}"
        )

        queue = [root]
        while queue:
            widget = queue.pop(0)
            try:
                queue.extend(widget.winfo_children())
            except Exception:
                continue
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                continue
            if text.startswith("Warsztat Menager v") and text != wanted:
                try:
                    widget.configure(text=wanted)
                except Exception:
                    pass
    except Exception:
        logger.exception("[WMM] Nie udało się uzupełnić stopki WM")


def _format_users(users: list[dict]) -> str:
    lines: list[str] = []
    for user in users:
        name = str(user.get("name") or user.get("login") or "—").strip()
        role = str(user.get("role") or "").strip()
        lines.append(f"{name} ({role})" if role else name)
    return "\n".join(lines)


def _build_panel(root) -> None:
    """Dodaj stały panel WMM na dole lewego panelu głównego WM."""
    if _panel_exists(root):
        _update_footer(root)
        return

    try:
        import tkinter as tk
        from tkinter import ttk

        import qrcode
        from PIL import ImageTk

        from services.wmm_api import mobile_status, pairing_info

        jarvis_box = getattr(root, "frm_jarvis_alerts", None)
        if jarvis_box is None or not jarvis_box.winfo_exists():
            return

        side_alerts = jarvis_box.master
        side = getattr(side_alerts, "master", None)
        if side is None or not side.winfo_exists():
            return

        info = pairing_info()
        panel = ttk.Frame(side, style="WM.Card.TFrame", padding=8)
        panel.pack(side="bottom", fill="x", pady=(6, 0))
        root._wmm_main_panel = panel

        ttk.Label(panel, text="WMM", style="WM.H2.TLabel").pack(anchor="w")

        status_label = ttk.Label(
            panel,
            text="○ Brak zalogowanych",
            style="WM.Muted.TLabel",
            foreground="#9aa0a6",
        )
        status_label.pack(anchor="w", pady=(0, 4))

        qr = qrcode.QRCode(version=None, box_size=2, border=2)
        qr.add_data(str(info["qr"]))
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        photo = ImageTk.PhotoImage(image)
        qr_label = tk.Label(panel, image=photo, bd=0, bg="white")
        qr_label.image = photo
        qr_label.pack(pady=(0, 4))

        ttk.Label(
            panel,
            text=f"{info['host']}:{info['port']}",
            style="WM.Muted.TLabel",
        ).pack(anchor="center")

        users_label = ttk.Label(
            panel,
            text="Zeskanuj QR w WMM",
            style="WM.Muted.TLabel",
            justify="left",
            wraplength=145,
        )
        users_label.pack(anchor="w", pady=(2, 0))

        def refresh_presence() -> None:
            try:
                if not panel.winfo_exists():
                    return
                state = mobile_status()
                users = state.get("users") if isinstance(state, dict) else []
                users = users if isinstance(users, list) else []
                if users:
                    status_label.configure(
                        text="● WMM połączone",
                        foreground="#22c55e",
                    )
                    users_label.configure(text=_format_users(users))
                else:
                    status_label.configure(
                        text="○ Brak zalogowanych",
                        foreground="#9aa0a6",
                    )
                    users_label.configure(text="Zeskanuj QR w WMM")
                _update_footer(root)
                root.after(2000, refresh_presence)
            except Exception:
                logger.exception("[WMM] Błąd odświeżania statusu WMM")

        _update_footer(root)
        root.after(500, refresh_presence)
    except Exception:
        logger.exception("[WMM] Nie udało się zbudować panelu WMM w gui_panel")


def _watch_gui_panel() -> None:
    """Czekaj aż gui_panel utworzy sidebar i podłącz panel WMM w wątku Tk."""
    while True:
        try:
            module = sys.modules.get("gui_panel")
            if module is not None:
                root = getattr(module, "root_global", None)
                if root is None:
                    root = getattr(module, "root", None)
                if root is None:
                    try:
                        import tkinter as tk

                        root = tk._default_root
                    except Exception:
                        root = None
                if root is not None:
                    jarvis_box = getattr(root, "frm_jarvis_alerts", None)
                    if jarvis_box is not None and not _panel_exists(root):
                        try:
                            root.after(0, lambda r=root: _build_panel(r))
                        except Exception:
                            pass
                    elif _panel_exists(root):
                        try:
                            root.after(0, lambda r=root: _update_footer(r))
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(0.5)


def start_gui_panel_watcher() -> None:
    global _WATCHER_STARTED
    with _WATCHER_LOCK:
        if _WATCHER_STARTED:
            return
        _WATCHER_STARTED = True
        threading.Thread(
            target=_watch_gui_panel,
            name="wm-wmm-gui-panel",
            daemon=True,
        ).start()
