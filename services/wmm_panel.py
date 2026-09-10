from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


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


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for bit in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> bit) & 1) * x
    return z & 0xFF


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = _gf_mul(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for value in data:
        factor = value ^ result[0]
        result = result[1:] + [0]
        for index, coefficient in enumerate(divisor):
            result[index] ^= _gf_mul(coefficient, factor)
    return result


def _qr_v4_l_matrix(text: str) -> list[list[bool]]:
    """Zbuduj QR v4-L bez zewnętrznego pakietu ``qrcode``."""
    payload = text.encode("utf-8")
    if len(payload) > 78:
        raise ValueError("Dane połączenia WMM są zbyt długie dla QR v4-L")

    bits: list[int] = []

    def append_bits(value: int, count: int) -> None:
        bits.extend((value >> bit) & 1 for bit in range(count - 1, -1, -1))

    append_bits(0b0100, 4)
    append_bits(len(payload), 8)
    for value in payload:
        append_bits(value, 8)

    capacity_bits = 80 * 8
    bits.extend([0] * min(4, capacity_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    data: list[int] = []
    for offset in range(0, len(bits), 8):
        value = 0
        for bit in bits[offset : offset + 8]:
            value = (value << 1) | bit
        data.append(value)

    pad_index = 0
    pads = (0xEC, 0x11)
    while len(data) < 80:
        data.append(pads[pad_index & 1])
        pad_index += 1

    codewords = data + _rs_remainder(data, _rs_divisor(20))

    size = 33
    modules = [[False] * size for _ in range(size)]
    functions = [[False] * size for _ in range(size)]

    def set_function(row: int, col: int, value: bool) -> None:
        if 0 <= row < size and 0 <= col < size:
            modules[row][col] = bool(value)
            functions[row][col] = True

    def draw_finder(center_row: int, center_col: int) -> None:
        for delta_row in range(-4, 5):
            for delta_col in range(-4, 5):
                row = center_row + delta_row
                col = center_col + delta_col
                if not (0 <= row < size and 0 <= col < size):
                    continue
                distance = max(abs(delta_row), abs(delta_col))
                set_function(row, col, distance != 2 and distance != 4)

    draw_finder(3, 3)
    draw_finder(3, size - 4)
    draw_finder(size - 4, 3)

    for index in range(8, size - 8):
        if not functions[6][index]:
            set_function(6, index, index % 2 == 0)
        if not functions[index][6]:
            set_function(index, 6, index % 2 == 0)

    for delta_row in range(-2, 3):
        for delta_col in range(-2, 3):
            distance = max(abs(delta_row), abs(delta_col))
            set_function(26 + delta_row, 26 + delta_col, distance != 1)

    format_data = 1 << 3
    remainder = format_data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    format_bits = ((format_data << 10) | remainder) ^ 0x5412

    def format_bit(index: int) -> bool:
        return bool((format_bits >> index) & 1)

    for index in range(6):
        set_function(index, 8, format_bit(index))
    set_function(7, 8, format_bit(6))
    set_function(8, 8, format_bit(7))
    set_function(8, 7, format_bit(8))
    for index in range(9, 15):
        set_function(8, 14 - index, format_bit(index))
    for index in range(8):
        set_function(8, size - 1 - index, format_bit(index))
    for index in range(8, 15):
        set_function(size - 15 + index, 8, format_bit(index))
    set_function(size - 8, 8, True)

    data_bits: list[int] = []
    for value in codewords:
        data_bits.extend((value >> bit) & 1 for bit in range(7, -1, -1))

    data_index = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        upward = ((right + 1) & 2) == 0
        for vertical in range(size):
            row = size - 1 - vertical if upward else vertical
            for side in range(2):
                col = right - side
                if functions[row][col]:
                    continue
                if data_index < len(data_bits):
                    modules[row][col] = bool(data_bits[data_index])
                    data_index += 1
        right -= 2

    for row in range(size):
        for col in range(size):
            if not functions[row][col] and (row + col) % 2 == 0:
                modules[row][col] = not modules[row][col]

    return modules


def _draw_qr(canvas, text: str, *, module_px: int = 6, border: int = 4) -> None:
    matrix = _qr_v4_l_matrix(text)
    size = len(matrix)
    pixels = (size + border * 2) * module_px
    canvas.configure(width=pixels, height=pixels, bg="white", highlightthickness=0)
    canvas.delete("all")
    for row, values in enumerate(matrix):
        for col, enabled in enumerate(values):
            if not enabled:
                continue
            x0 = (col + border) * module_px
            y0 = (row + border) * module_px
            canvas.create_rectangle(
                x0,
                y0,
                x0 + module_px,
                y0 + module_px,
                fill="black",
                outline="black",
            )


def _center_window(win, root, width: int, height: int) -> None:
    try:
        root.update_idletasks()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - width) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        win.geometry(f"{width}x{height}")


def show_wmm_popup(root) -> None:
    """Pokaż jedno proste okno połączenia WMM po otwarciu Panelu głównego."""
    if threading.current_thread() is not threading.main_thread():
        return

    existing = getattr(root, "_wmm_popup", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass

    try:
        import tkinter as tk

        from services.wmm_api import mobile_status, pairing_info

        info = pairing_info()
        popup = tk.Toplevel(root)
        root._wmm_popup = popup
        popup.title("Warsztat Menager Mobile — połączenie")
        popup.resizable(False, False)
        popup.transient(root)
        popup.configure(bg="#171A1D")
        _center_window(popup, root, 390, 565)

        pending_timers: set[str] = set()
        closed = False

        def schedule(delay, callback) -> None:
            if closed:
                return

            def run() -> None:
                pending_timers.discard(timer_id)
                if not closed:
                    callback()

            timer_id = popup.after(delay, run)
            pending_timers.add(timer_id)

        def cancel_timers(event=None) -> None:
            nonlocal closed
            if event is not None and event.widget is not popup:
                return
            closed = True
            for timer_id in tuple(pending_timers):
                try:
                    popup.after_cancel(timer_id)
                except tk.TclError:
                    pass
            pending_timers.clear()
            if getattr(root, "_wmm_popup", None) is popup:
                root._wmm_popup = None

        popup.bind("<Destroy>", cancel_timers, add="+")

        def close_popup() -> None:
            cancel_timers()
            try:
                popup.destroy()
            except Exception:
                pass

        popup.protocol("WM_DELETE_WINDOW", close_popup)

        tk.Label(
            popup,
            text="Warsztat Menager Mobile",
            fg="#F3F4F6",
            bg="#171A1D",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(16, 2))
        tk.Label(
            popup,
            text="● API aktywne",
            fg="#22C55E",
            bg="#171A1D",
            font=("Segoe UI", 10, "bold"),
        ).pack(pady=(0, 10))

        qr_canvas = tk.Canvas(popup, bd=0, bg="white", highlightthickness=0)
        qr_canvas.pack(pady=(0, 10))
        try:
            _draw_qr(qr_canvas, str(info.get("qr") or ""))
        except Exception as exc:
            qr_canvas.configure(width=246, height=80, bg="#202428")
            qr_canvas.create_text(
                123,
                40,
                text=f"Nie udało się narysować QR:\n{exc}",
                fill="#FCA5A5",
                justify="center",
                width=225,
            )

        host_text = f"{info.get('host', '—')}:{info.get('port', '—')}"
        key_text = str(info.get("key") or "—")
        version_text = str(info.get("wmm_version") or "—")

        tk.Label(
            popup,
            text=host_text,
            fg="#F3F4F6",
            bg="#171A1D",
            font=("Consolas", 12, "bold"),
        ).pack()
        tk.Label(
            popup,
            text=f"Klucz: {key_text}    WMM: v{version_text}",
            fg="#AEB4BC",
            bg="#171A1D",
            font=("Segoe UI", 9),
        ).pack(pady=(3, 8))
        tk.Label(
            popup,
            text="Zeskanuj QR w aplikacji WMM.",
            fg="#AEB4BC",
            bg="#171A1D",
            font=("Segoe UI", 9),
        ).pack(pady=(0, 8))

        presence_var = tk.StringVar(value="Brak zalogowanych WMM")
        presence_label = tk.Label(
            popup,
            textvariable=presence_var,
            fg="#9AA0A6",
            bg="#171A1D",
            font=("Segoe UI", 9),
            justify="center",
            wraplength=340,
        )
        presence_label.pack(pady=(0, 10))

        buttons = tk.Frame(popup, bg="#171A1D")
        buttons.pack(pady=(0, 12))

        def copy_connection() -> None:
            try:
                popup.clipboard_clear()
                popup.clipboard_append(str(info.get("qr") or ""))
            except Exception:
                pass

        tk.Button(
            buttons,
            text="Kopiuj dane",
            command=copy_connection,
            bg="#252A2F",
            fg="#F3F4F6",
            activebackground="#343A40",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=14,
            pady=6,
        ).pack(side="left", padx=5)
        tk.Button(
            buttons,
            text="Zamknij",
            command=close_popup,
            bg="#FF7A00",
            fg="#111111",
            activebackground="#FF8C1A",
            activeforeground="#111111",
            relief="flat",
            padx=18,
            pady=6,
        ).pack(side="left", padx=5)

        def refresh_presence() -> None:
            try:
                if not popup.winfo_exists():
                    return
                state = mobile_status()
                users = state.get("users") if isinstance(state, dict) else []
                users = users if isinstance(users, list) else []
                if users:
                    presence_var.set("Połączeni: " + _format_users(users).replace("\n", ", "))
                    presence_label.configure(fg="#22C55E")
                else:
                    presence_var.set("Brak zalogowanych WMM")
                    presence_label.configure(fg="#9AA0A6")
                _update_footer(root)
                schedule(2000, refresh_presence)
            except Exception:
                logger.exception("[WMM] Błąd odświeżania okna połączenia")

        _update_footer(root)
        schedule(500, refresh_presence)
        popup.lift()
        try:
            popup.attributes("-topmost", True)
            schedule(250, lambda: popup.attributes("-topmost", False))
        except Exception:
            pass
        print("[WM-WMM][GUI] Otwarto okno połączenia WMM")
    except Exception:
        logger.exception("[WMM] Nie udało się otworzyć okna połączenia WMM")


__all__ = ["show_wmm_popup"]
