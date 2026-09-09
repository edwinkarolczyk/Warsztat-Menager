from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _panel_exists(root, side=None) -> bool:
    try:
        panel = getattr(root, "_wmm_main_panel", None)
        if not panel or not panel.winfo_exists():
            return False
        if side is not None and panel.master is not side:
            return False
        return True
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


def _sidebar_button_texts(side) -> set[str]:
    out: set[str] = set()
    try:
        children = list(side.winfo_children())
    except Exception:
        return out
    for child in children:
        try:
            text = str(child.cget("text") or "").strip()
        except Exception:
            text = ""
        if text:
            out.add(text.replace("  🔒", "").strip())
    return out


def _is_gui_panel_sidebar(side) -> bool:
    """Rozpoznaj właściwy lewy pasek gui_panel po realnych przyciskach modułów."""
    texts = _sidebar_button_texts(side)
    if "Dyspozycje" not in texts:
        return False
    expected = {"Narzędzia", "Maszyny", "Magazyn", "Planista", "Ustawienia", "Profil"}
    return len(texts.intersection(expected)) >= 3


def _hide_jarvis_alert_card(side) -> None:
    """Usuń wyłącznie kartę „Alerty Jarvisa”; moduł/przycisk Jarvis zostaje."""
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
    """Zbuduj kartę WMM dokładnie po modułach, w miejscu dawnej karty Jarvisa."""
    if threading.current_thread() is not threading.main_thread():
        logger.warning("[WMM] Pominięto próbę budowy GUI poza głównym wątkiem Tk")
        return
    if not _is_gui_panel_sidebar(side):
        return

    _hide_jarvis_alert_card(side)
    if _panel_exists(root, side):
        _update_footer(root)
        return

    try:
        import tkinter as tk
        from tkinter import ttk

        import qrcode
        from PIL import ImageTk

        from services.wmm_api import mobile_status, pairing_info

        info = pairing_info()
        panel = ttk.Frame(side, style="WM.Card.TFrame", padding=8)
        panel.pack(fill="x", padx=10, pady=6)
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
            wraplength=180,
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
        print("[WM-WMM][GUI] Panel WMM osadzony zamiast Alertów Jarvisa")
    except Exception:
        logger.exception("[WMM] Nie udało się zbudować panelu WMM w gui_panel")


def mount_wmm_panel(root, side) -> None:
    """Osadź WMM synchronicznie; wywołanie ma pochodzić z głównego wątku Tk."""
    _build_panel(root, side)


__all__ = ["mount_wmm_panel"]
