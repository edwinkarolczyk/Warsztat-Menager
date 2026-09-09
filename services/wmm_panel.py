from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _panel_exists(root) -> bool:
    try:
        panel = getattr(root, "_wmm_main_panel", None)
        return bool(panel) and bool(panel.winfo_exists())
    except Exception:
        return False


def _update_footer(root) -> None:
    """Dopisz zgodność WMM do istniejącej stopki WM."""
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


def _build_panel(root, side) -> None:
    """Zbuduj panel WMM. Ta funkcja może działać wyłącznie w wątku Tk."""
    if threading.current_thread() is not threading.main_thread():
        logger.warning("[WMM] Pominięto próbę budowy GUI poza głównym wątkiem Tk")
        return
    if _panel_exists(root):
        _update_footer(root)
        return

    try:
        import tkinter as tk
        from tkinter import ttk

        import qrcode
        from PIL import ImageTk

        from services.wmm_api import mobile_status, pairing_info

        if side is None or not side.winfo_exists():
            return

        info = pairing_info()
        panel = ttk.Frame(side, style="WM.Card.TFrame", padding=8)
        panel.pack(side="bottom", fill="x", padx=8, pady=(6, 8))
        root._wmm_main_panel = panel

        ttk.Label(panel, text="WMM", style="WM.H2.TLabel").pack(anchor="w")
        ttk.Label(
            panel,
            text="● API aktywne",
            style="WM.Muted.TLabel",
            foreground="#22c55e",
        ).pack(anchor="w", pady=(0, 4))

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


def mount_wmm_panel(root, side) -> None:
    """Osadź panel WMM w istniejącym sidebarze gui_panel."""
    _build_panel(root, side)


__all__ = ["mount_wmm_panel"]
