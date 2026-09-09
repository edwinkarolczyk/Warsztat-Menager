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


def _find_sidebar(root):
    """Znajdź stały lewy sidebar utworzony bezpośrednio przez gui_panel."""
    try:
        for child in root.winfo_children():
            try:
                info = child.pack_info()
            except Exception:
                continue
            if str(info.get("side", "")).lower() != "left":
                continue
            try:
                style = str(child.cget("style") or "")
            except Exception:
                style = ""
            if style == "WM.Side.TFrame":
                return child
    except Exception:
        pass
    return None


def _build_panel(root) -> None:
    """Dodaj stały panel WMM na samym dole lewego panelu głównego WM."""
    if _panel_exists(root):
        _update_footer(root)
        return

    try:
        import tkinter as tk
        from tkinter import ttk

        import qrcode
        from PIL import ImageTk

        from services.wmm_api import mobile_status, pairing_info

        side = _find_sidebar(root)
        if side is None or not side.winfo_exists():
            return

        info = pairing_info()
        panel = ttk.Frame(side, style="WM.Card.TFrame", padding=8)
        panel.pack(side="bottom", fill="x", padx=8, pady=(6, 8))
        root._wmm_main_panel = panel

        ttk.Label(panel, text="WMM", style="WM.H2.TLabel").pack(anchor="w")

        api_label = ttk.Label(
            panel,
            text="● API aktywne",
            style="WM.Muted.TLabel",
            foreground="#22c55e",
        )
        api_label.pack(anchor="w", pady=(0, 4))

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

        presence_label = ttk.Label(
            panel,
            text="Brak zalogowanych WMM",
            style="WM.Muted.TLabel",
            foreground="#9aa0a6",
            justify="left",
            wraplength=170,
        )
        presence_label.pack(anchor="w", pady=(4, 0))

        def refresh_presence() -> None:
            try:
                if not panel.winfo_exists():
                    return
                state = mobile_status()
                users = state.get("users") if isinstance(state, dict) else []
                users = users if isinstance(users, list) else []
                if users:
                    presence_label.configure(
                        text="Połączeni:\n" + _format_users(users),
                        foreground="#22c55e",
                    )
                else:
                    presence_label.configure(
                        text="Brak zalogowanych WMM",
                        foreground="#9aa0a6",
                    )
                _update_footer(root)
                root.after(2000, refresh_presence)
            except Exception:
                logger.exception("[WMM] Błąd odświeżania statusu WMM")

        _update_footer(root)
        root.after(500, refresh_presence)
    except Exception:
        logger.exception("[WMM] Nie udało się zbudować panelu WMM w gui_panel")


def _resolve_root():
    module = sys.modules.get("gui_panel")
    if module is not None:
        for attr in ("root_global", "root"):
            root = getattr(module, attr, None)
            if root is not None:
                return root
    try:
        import tkinter as tk

        return tk._default_root
    except Exception:
        return None


def _watch_gui_panel() -> None:
    """Podłącz panel, gdy właściwy sidebar gui_panel jest już utworzony."""
    while True:
        try:
            root = _resolve_root()
            if root is not None:
                try:
                    exists = bool(root.winfo_exists())
                except Exception:
                    exists = False
                if exists:
                    try:
                        root.after(0, lambda r=root: _build_panel(r))
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
