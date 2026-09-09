from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_HOOK_INSTALLED = False
_ORIGINAL_FRAME_INIT = None


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


def _hide_jarvis_alert_card(side) -> None:
    """Ukryj wyłącznie kartę „Alerty Jarvisa” w sidebarze."""
    try:
        children = list(side.winfo_children())
    except Exception:
        return
    for child in children:
        try:
            labels = list(child.winfo_children())
        except Exception:
            continue
        for label in labels:
            try:
                if str(label.cget("text") or "").strip() == "Alerty Jarvisa":
                    child.destroy()
                    break
            except Exception:
                continue


def _build_panel(root, side) -> None:
    """Zbuduj panel WMM w miejscu karty Alerty Jarvisa, tylko w wątku Tk."""
    if threading.current_thread() is not threading.main_thread():
        logger.warning("[WMM] Pominięto próbę budowy GUI poza głównym wątkiem Tk")
        return

    _hide_jarvis_alert_card(side)
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
        tk.Label(
            panel,
            text="● API aktywne",
            fg="#22c55e",
            bg="#1A1D1F",
            bd=0,
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

        presence_label = tk.Label(
            panel,
            text="Brak zalogowanych WMM",
            fg="#9aa0a6",
            bg="#1A1D1F",
            bd=0,
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
                        fg="#22c55e",
                    )
                else:
                    presence_label.configure(
                        text="Brak zalogowanych WMM",
                        fg="#9aa0a6",
                    )
                _update_footer(root)
                root.after(2000, refresh_presence)
            except Exception:
                logger.exception("[WMM] Błąd odświeżania statusu WMM")

        _update_footer(root)
        root.after(500, refresh_presence)
    except Exception:
        logger.exception("[WMM] Nie udało się zbudować panelu WMM w gui_panel")


def _ensure_panel_loop(root, side) -> None:
    """Odtwarzaj panel po clear_frame(side), zawsze z głównego wątku Tk."""
    if getattr(root, "_wmm_ensure_loop_started", False):
        return
    root._wmm_ensure_loop_started = True

    def ensure() -> None:
        try:
            if not side.winfo_exists():
                root._wmm_ensure_loop_started = False
                return
            _hide_jarvis_alert_card(side)
            if not _panel_exists(root):
                _build_panel(root, side)
            else:
                _update_footer(root)
            root.after(1000, ensure)
        except Exception:
            logger.exception("[WMM] Błąd kontroli panelu WMM")
            try:
                root.after(1000, ensure)
            except Exception:
                root._wmm_ensure_loop_started = False

    root.after_idle(ensure)


def mount_wmm_panel(root, side) -> None:
    """Osadź panel WMM w istniejącym sidebarze gui_panel."""
    _ensure_panel_loop(root, side)


def install_gui_panel_hook() -> None:
    """Jednorazowo wykryj sidebar gui_panel, potem pilnuj go przez root.after()."""
    global _HOOK_INSTALLED, _ORIGINAL_FRAME_INIT
    if _HOOK_INSTALLED:
        return

    try:
        from tkinter import ttk
    except Exception:
        return

    original = ttk.Frame.__init__
    _ORIGINAL_FRAME_INIT = original

    def frame_init(self, master=None, **kw):
        global _HOOK_INSTALLED
        original(self, master, **kw)

        if threading.current_thread() is not threading.main_thread():
            return
        style = str(kw.get("style") or "")
        try:
            width = int(kw.get("width") or 0)
        except Exception:
            width = 0
        if style != "WM.Side.TFrame" or width != 220 or master is None:
            return

        try:
            ttk.Frame.__init__ = original
        except Exception:
            pass
        _HOOK_INSTALLED = True

        try:
            root = self.winfo_toplevel()
            _ensure_panel_loop(root, self)
        except Exception:
            logger.exception("[WMM] Nie udało się uruchomić panelu WMM")

    ttk.Frame.__init__ = frame_init


__all__ = ["install_gui_panel_hook", "mount_wmm_panel"]
