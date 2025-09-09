"""Obsługa narzędzi przez skaner QR."""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from tkinter import ttk

from narzedzia_history import append_tool_history
from ui_utils import _ensure_topmost, _msg_error, _msg_info
from utils.path_utils import cfg_path

CONFIG_PATH = cfg_path("config.json")


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = "\n".join(
                line for line in f if not line.lstrip().startswith("#")
            )
        return json.loads(content) if content.strip() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _resolve_tools_dir() -> str:
    cfg = _load_config()
    base = (cfg.get("sciezka_danych") or "").strip()
    if base and not os.path.isabs(base):
        base = os.path.normpath(base)
    return os.path.join(base, "narzedzia") if base else "narzedzia"


def _read_tool(numer_3: str) -> dict | None:
    folder = _resolve_tools_dir()
    path = os.path.join(folder, f"{numer_3}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _save_tool(data: dict) -> None:
    folder = _resolve_tools_dir()
    os.makedirs(folder, exist_ok=True)
    obj = dict(data)
    obj["numer"] = str(obj.get("numer", "")).zfill(3)
    path = os.path.join(folder, f"{obj['numer']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _info(parent: tk.Misc, msg: str) -> None:
    print(f"[WM-DBG][QR] info: {msg}")
    _ensure_topmost(parent, parent)
    _msg_info(parent, "QR", msg)


def _error(parent: tk.Misc, msg: str) -> None:
    print(f"[WM-DBG][QR] error: {msg}")
    _ensure_topmost(parent, parent)
    _msg_error(parent, "QR", msg)


def handle_action(tool_id: str, mode: str, login: str, parent: tk.Misc) -> bool:
    tool_id = str(tool_id).strip().zfill(3)
    data = _read_tool(tool_id)
    if not data:
        _error(parent, f"Brak narzędzia {tool_id}")
        return False

    if mode == "issue":
        data["pracownik"] = login
        action = "qr_issue"
        print(f"[WM-DBG][QR] issue {tool_id} -> {login}")
    elif mode == "return":
        data["pracownik"] = ""
        action = "qr_return"
        print(f"[WM-DBG][QR] return {tool_id}")
    elif mode == "fault":
        data["status"] = "awaria"
        action = "qr_fault"
        print(f"[WM-DBG][QR] fault {tool_id}")
    else:
        _error(parent, f"Nieznany tryb: {mode}")
        return False

    append_tool_history(tool_id, login, action)
    data.pop("historia", None)
    _save_tool(data)
    _info(parent, f"Zapisano {tool_id}")
    return True


class QRWindow(tk.Tk):
    def __init__(self, login: str) -> None:
        super().__init__()
        self.login = login
        self.title("Narzędzia QR")
        self.attributes("-topmost", True)
        print("[WM-DBG][QR] window init")

        self.mode = tk.StringVar(value="issue")
        modes = [("Wydanie", "issue"), ("Zwrot", "return"), ("Awaria", "fault")]
        for text, val in modes:
            ttk.Radiobutton(self, text=text, variable=self.mode, value=val).pack(
                anchor="w", padx=10
            )

        self.entry = ttk.Entry(self)
        self.entry.pack(fill="x", padx=10, pady=10)
        self.entry.focus_set()
        self.entry.bind("<Return>", self._on_enter)

    def _on_enter(self, _event: tk.Event) -> None:
        tool_id = self.entry.get()
        if handle_action(tool_id, self.mode.get(), self.login, self):
            self.entry.delete(0, tk.END)


def main(login: str) -> None:
    win = QRWindow(login)
    win.mainloop()


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LOGIN") or "anon"
    main(user)
