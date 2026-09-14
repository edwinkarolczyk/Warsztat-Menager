"""QR WMM dla Maszyn bez zapisywania dodatkowych pól w danych."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

MACHINE_QR_PREFIX = "WMM:MACHINE:"


def machine_qr_payload(machine_id: object) -> str:
    """Zbuduj stabilny payload QR z istniejącego identyfikatora maszyny."""

    value = str(machine_id or "").strip()
    if not value:
        raise ValueError("Brak identyfikatora maszyny.")
    return f"{MACHINE_QR_PREFIX}{value}"


def open_machine_qr(
    master: tk.Misc,
    machine_id: object,
    *,
    label: str = "",
) -> tk.Toplevel:
    """Pokaż kod QR WMM dla wskazanej maszyny."""

    payload = machine_qr_payload(machine_id)
    machine_label = str(label or machine_id or "").strip()

    win = tk.Toplevel(master)
    win.title(f"Kod QR WMM — {machine_label}")
    win.resizable(False, False)
    try:
        win.transient(master.winfo_toplevel())
    except Exception:
        pass

    body = ttk.Frame(win, padding=14)
    body.pack(fill="both", expand=True)

    ttk.Label(
        body,
        text=f"Maszyna: {machine_label}",
        font=("Segoe UI", 11, "bold"),
    ).pack(pady=(0, 8))

    try:
        import qrcode
        from PIL import ImageTk

        qr = qrcode.QRCode(version=None, box_size=8, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        photo = ImageTk.PhotoImage(image)
        image_label = ttk.Label(body, image=photo)
        image_label.image = photo
        image_label.pack(pady=4)
        win._wm_machine_qr_photo = photo
    except Exception as exc:
        ttk.Label(
            body,
            text=f"Nie udało się wygenerować obrazu QR:\n{exc}",
            justify="center",
        ).pack(padx=12, pady=18)

    ttk.Label(body, text=payload).pack(pady=(8, 4))

    buttons = ttk.Frame(body)
    buttons.pack(fill="x", pady=(8, 0))

    def _copy() -> None:
        win.clipboard_clear()
        win.clipboard_append(payload)
        win.update_idletasks()

    ttk.Button(buttons, text="Kopiuj kod", command=_copy).pack(side="left")
    ttk.Button(buttons, text="Zamknij", command=win.destroy).pack(side="right")
    return win


def _machine_actions_frame(tree: Any):
    """Znajdź istniejący pasek akcji Maszyn bez zależności od jego indeksu."""

    try:
        parent = tree.master
        children = parent.winfo_children()
    except Exception:
        return None

    for child in children:
        try:
            nested = child.winfo_children()
        except Exception:
            continue
        for widget in nested:
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                continue
            if text == "Drukuj pustą kartę maszyny":
                return child
    return None


def _selected_machine_id(tree: Any) -> str:
    try:
        selected = tree.selection()
    except Exception:
        return ""
    if not selected:
        return ""
    return str(selected[0] or "").strip()


def _install_button(module: Any, tree: Any, root: Any) -> None:
    if tree is None or getattr(tree, "_wm_machine_qr_button_installed", False):
        return

    actions = _machine_actions_frame(tree)
    if actions is None:
        return

    def _show_qr() -> None:
        machine_id = _selected_machine_id(tree)
        if not machine_id:
            messagebox.showinfo(
                "Kod QR WMM",
                "Wybierz maszynę z listy, a potem kliknij „Kod QR WMM”.",
                parent=root if getattr(root, "tk", None) is not None else None,
            )
            return
        try:
            open_machine_qr(root, machine_id)
        except Exception as exc:
            messagebox.showerror(
                "Kod QR WMM",
                f"Nie udało się otworzyć kodu QR:\n{exc}",
                parent=root if getattr(root, "tk", None) is not None else None,
            )

    button = ttk.Button(actions, text="Kod QR WMM", command=_show_qr)
    button.pack(side="left", padx=(6, 0))
    tree._wm_machine_qr_button = button
    tree._wm_machine_qr_button_installed = True


def install_machine_qr(module: Any) -> None:
    """Dodaj QR WMM do bieżącego panelu Maszyn bez zmiany modelu danych."""

    if getattr(module, "_WM_MACHINE_QR_RUNTIME", False):
        return

    original_open_panel = module._open_machines_panel

    def _open_machines_panel_with_qr(*args, **kwargs):
        tree = original_open_panel(*args, **kwargs)
        root = args[0] if args else kwargs.get("root")
        try:
            _install_button(module, tree, root)
        except Exception:
            logger = getattr(module, "logger", None)
            if logger is not None:
                logger.exception("[Maszyny] nie udało się dodać przycisku QR WMM")
        return tree

    module._open_machines_panel = _open_machines_panel_with_qr
    module.machine_qr_payload = machine_qr_payload
    module.open_machine_qr = open_machine_qr
    module._WM_MACHINE_QR_RUNTIME = True
