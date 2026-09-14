# version: 1.2
"""QR WMM dla Maszyn bez zapisywania dodatkowych pól w danych."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

MACHINE_QR_PREFIX = "WMM:MACHINE:"
PRINT_DPI = 300
_PRINT_FORMAT_MM = {
    "A5": (148, 210),
    "A6": (105, 148),
}


def machine_qr_payload(machine_id: object) -> str:
    """Zbuduj stabilny payload QR z istniejącego identyfikatora maszyny."""

    value = str(machine_id or "").strip()
    if not value:
        raise ValueError("Brak identyfikatora maszyny.")
    return f"{MACHINE_QR_PREFIX}{value}"


def build_machine_qr_image(payload: str):
    """Wygeneruj obraz QR bez zależności od Tkintera."""

    import qrcode

    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def _pip_qrcode_command(python_executable: str | None = None) -> list[str]:
    return [
        python_executable or sys.executable,
        "-m",
        "pip",
        "install",
        "qrcode",
    ]


def install_qrcode_package() -> tuple[bool, str]:
    """Zainstaluj brakującą obsługę QR po wyraźnej akcji użytkownika."""

    if getattr(sys, "frozen", False):
        return (
            False,
            "Ta wersja EXE nie zawiera biblioteki qrcode. "
            "Zaktualizuj program do buildu zawierającego obsługę QR.",
        )

    try:
        result = subprocess.run(
            _pip_qrcode_command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return False, f"Nie udało się uruchomić instalatora: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if len(detail) > 800:
            detail = detail[-800:]
        return False, detail or "Instalacja biblioteki qrcode nie powiodła się."

    importlib.invalidate_caches()
    return True, "Obsługa QR została zainstalowana."


def _mm_to_px(value_mm: float, dpi: int = PRINT_DPI) -> int:
    return round(float(value_mm) / 25.4 * dpi)


def machine_qr_print_size(page_format: str) -> tuple[int, int]:
    """Zwróć rozmiar strony A5/A6 w pikselach dla wydruku 300 DPI."""

    fmt = str(page_format or "").strip().upper()
    if fmt not in _PRINT_FORMAT_MM:
        raise ValueError("Obsługiwane formaty wydruku QR to A5 i A6.")
    width_mm, height_mm = _PRINT_FORMAT_MM[fmt]
    return _mm_to_px(width_mm), _mm_to_px(height_mm)


def _font_candidates(*, bold: bool) -> list[Path]:
    windows_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    if bold:
        names = ("arialbd.ttf", "segoeuib.ttf")
        linux = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else:
        names = ("arial.ttf", "segoeui.ttf")
        linux = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return [*(windows_dir / name for name in names), Path(linux)]


def _load_print_font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    for path in _font_candidates(bold=bold):
        if not path.is_file():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_print_font(
    draw,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
    *,
    bold: bool = False,
):
    size = max(start_size, min_size)
    while size >= min_size:
        font = _load_print_font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        size -= 2
    return _load_print_font(min_size, bold=bold)


def _draw_centered(draw, page_width: int, y: int, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    x = max(0, (page_width - text_width) // 2)
    draw.text((x, y - box[1]), text, fill="black", font=font)
    return y + text_height


def build_machine_qr_print_page(
    payload: str,
    machine_id: object,
    *,
    label: str = "",
    page_format: str = "A5",
):
    """Zbuduj pionową stronę A5/A6 z dużym kodem QR do druku."""

    from PIL import Image, ImageDraw

    fmt = str(page_format or "").strip().upper()
    page_width, page_height = machine_qr_print_size(fmt)
    page = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(page)

    margin_mm = 10 if fmt == "A5" else 8
    margin = _mm_to_px(margin_mm)
    content_width = page_width - 2 * margin
    machine_id_text = str(machine_id or "").strip()
    machine_name = str(label or "").strip()

    if fmt == "A5":
        title_size, id_size, name_size, small_size = 64, 120, 78, 40
        gap = _mm_to_px(4)
    else:
        title_size, id_size, name_size, small_size = 48, 90, 60, 30
        gap = _mm_to_px(3)

    y = margin
    title_font = _fit_print_font(
        draw,
        "WARSZTAT MENAGER",
        content_width,
        title_size,
        max(30, title_size // 2),
        bold=True,
    )
    y = _draw_centered(draw, page_width, y, "WARSZTAT MENAGER", title_font)
    y += gap

    id_text = f"MASZYNA {machine_id_text}"
    id_font = _fit_print_font(
        draw,
        id_text,
        content_width,
        id_size,
        max(44, id_size // 2),
        bold=True,
    )
    y = _draw_centered(draw, page_width, y, id_text, id_font)

    if machine_name and machine_name != machine_id_text:
        y += max(8, gap // 2)
        name_font = _fit_print_font(
            draw,
            machine_name,
            content_width,
            name_size,
            max(32, name_size // 2),
            bold=True,
        )
        y = _draw_centered(draw, page_width, y, machine_name, name_font)

    y += gap
    footer_font = _load_print_font(small_size)
    footer_bold = _load_print_font(small_size, bold=True)
    footer_box = draw.textbbox((0, 0), "Zeskanuj w WMM", font=footer_bold)
    footer_height = (footer_box[3] - footer_box[1]) * 2 + gap * 2
    available_qr_height = max(1, page_height - y - footer_height - margin)
    qr_size = min(content_width, available_qr_height)
    qr_size = max(1, int(qr_size * 0.94))

    qr_image = build_machine_qr_image(payload)
    resampling = getattr(Image, "Resampling", Image)
    qr_image = qr_image.resize((qr_size, qr_size), resampling.NEAREST)
    qr_x = (page_width - qr_size) // 2
    page.paste(qr_image, (qr_x, y))
    y += qr_size + gap

    y = _draw_centered(draw, page_width, y, "Zeskanuj w WMM", footer_bold)
    y += max(6, gap // 3)
    payload_font = _fit_print_font(
        draw,
        payload,
        content_width,
        small_size,
        max(20, small_size // 2),
    )
    _draw_centered(draw, page_width, y, payload, payload_font)
    return page


def create_machine_qr_pdf(
    output_path: str | os.PathLike[str],
    payload: str,
    machine_id: object,
    *,
    label: str = "",
    page_format: str = "A5",
) -> Path:
    """Zapisz jedną stronę QR jako PDF A5/A6 w rzeczywistym rozmiarze."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    page = build_machine_qr_print_page(
        payload,
        machine_id,
        label=label,
        page_format=page_format,
    )
    page.save(path, "PDF", resolution=float(PRINT_DPI))
    return path


def _safe_filename_piece(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    return text.strip("._-") or "maszyna"


def machine_qr_pdf_filename(machine_id: object, page_format: str) -> str:
    fmt = str(page_format or "").strip().upper()
    machine = _safe_filename_piece(machine_id)
    return f"QR_maszyna_{machine}_{fmt}.pdf"


def _open_generated_file(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _render_qr_image(
    frame: ttk.Frame,
    win: tk.Toplevel,
    payload: str,
) -> bool:
    for child in frame.winfo_children():
        child.destroy()

    try:
        from PIL import ImageTk

        image = build_machine_qr_image(payload)
        photo = ImageTk.PhotoImage(image)
        image_label = ttk.Label(frame, image=photo)
        image_label.image = photo
        image_label.pack(pady=4)
        win._wm_machine_qr_photo = photo
        return True
    except ModuleNotFoundError as exc:
        if exc.name != "qrcode":
            raise

        ttk.Label(
            frame,
            text=(
                "Brakuje biblioteki obsługującej kody QR.\n"
                "Kliknij poniżej, aby zainstalować ją dla tego WM."
            ),
            justify="center",
        ).pack(padx=12, pady=(18, 10))

        if getattr(sys, "frozen", False):
            ttk.Label(
                frame,
                text=(
                    "Ta wersja EXE wymaga aktualizacji do buildu "
                    "zawierającego qrcode."
                ),
                justify="center",
            ).pack(padx=12, pady=(0, 18))
            return False

        install_button = ttk.Button(frame, text="Zainstaluj obsługę QR")
        install_button.pack(pady=(0, 18))

        def _install_and_retry() -> None:
            install_button.state(["disabled"])
            win.update_idletasks()
            ok, detail = install_qrcode_package()
            if ok:
                _render_qr_image(frame, win, payload)
                return
            install_button.state(["!disabled"])
            messagebox.showerror(
                "Kod QR WMM",
                f"Nie udało się zainstalować obsługi QR:\n{detail}",
                parent=win,
            )

        install_button.configure(command=_install_and_retry)
        return False
    except Exception as exc:
        ttk.Label(
            frame,
            text=f"Nie udało się wygenerować obrazu QR:\n{exc}",
            justify="center",
        ).pack(padx=12, pady=18)
        return False


def open_machine_qr(
    master: tk.Misc,
    machine_id: object,
    *,
    label: str = "",
) -> tk.Toplevel:
    """Pokaż kod QR WMM dla wskazanej maszyny."""

    payload = machine_qr_payload(machine_id)
    machine_id_text = str(machine_id or "").strip()
    machine_name = str(label or "").strip()
    machine_label = machine_id_text
    if machine_name and machine_name != machine_id_text:
        machine_label = f"{machine_id_text} - {machine_name}"

    win = tk.Toplevel(master)
    win.title(f"Kod QR WMM — {machine_id_text}")
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

    qr_frame = ttk.Frame(body)
    qr_frame.pack(fill="both", expand=True)
    _render_qr_image(qr_frame, win, payload)

    ttk.Label(body, text=payload).pack(pady=(8, 4))

    print_buttons = ttk.Frame(body)
    print_buttons.pack(fill="x", pady=(8, 0))

    def _save_pdf(page_format: str) -> None:
        target = filedialog.asksaveasfilename(
            parent=win,
            title=f"Zapisz kod QR maszyny {machine_id_text} - {page_format}",
            initialfile=machine_qr_pdf_filename(machine_id_text, page_format),
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not target:
            return
        try:
            path = create_machine_qr_pdf(
                target,
                payload,
                machine_id_text,
                label=machine_name,
                page_format=page_format,
            )
        except ModuleNotFoundError as exc:
            if exc.name == "qrcode":
                messagebox.showwarning(
                    "Kod QR WMM",
                    "Najpierw zainstaluj obsługę QR przyciskiem w tym oknie.",
                    parent=win,
                )
                return
            raise
        except Exception as exc:
            messagebox.showerror(
                "Kod QR WMM",
                f"Nie udało się utworzyć PDF {page_format}:\n{exc}",
                parent=win,
            )
            return

        try:
            _open_generated_file(path)
        except Exception:
            messagebox.showinfo(
                "Kod QR WMM",
                f"PDF {page_format} zapisany:\n{path}\n\n"
                "Otwórz go ręcznie i drukuj w skali 100%.",
                parent=win,
            )

    ttk.Button(
        print_buttons,
        text="Druk A5 (PDF)",
        command=lambda: _save_pdf("A5"),
    ).pack(side="left")
    ttk.Button(
        print_buttons,
        text="Druk A6 (PDF)",
        command=lambda: _save_pdf("A6"),
    ).pack(side="left", padx=(6, 0))

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


def _selected_machine_name(tree: Any) -> str:
    try:
        selected = tree.selection()
        if not selected:
            return ""
        values = tree.item(selected[0], "values")
    except Exception:
        return ""
    if isinstance(values, (list, tuple)) and len(values) >= 2:
        return str(values[1] or "").strip()
    return ""


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
            open_machine_qr(
                root,
                machine_id,
                label=_selected_machine_name(tree),
            )
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
