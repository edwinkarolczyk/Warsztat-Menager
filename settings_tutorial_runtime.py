# version: 1.1
# Moduł: settings_tutorial_runtime
# Izolowane ustawienie widoczności przycisku Samouczek.
# 1.1: plik ustawienia jest wyznaczany względem aktywnego WM_ROOT.

from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any


_DEFAULT_ENABLED = True


def _resolve_settings_path() -> Path:
    """Zwróć osobny plik ustawień samouczka w aktywnym WM_ROOT."""
    try:
        from core import root_paths as wm_root_paths

        root = wm_root_paths.get_root_anchor()
        if root:
            return Path(root) / "samouczek" / "ustawienia.json"
    except Exception:
        pass
    env_root = str(os.environ.get("WM_ROOT") or "").strip()
    if env_root:
        return Path(env_root).expanduser() / "samouczek" / "ustawienia.json"
    return Path.home() / ".warsztat-menager" / "samouczek" / "ustawienia.json"


SETTINGS_PATH = _resolve_settings_path()


def is_tutorial_button_enabled() -> bool:
    """Zwróć stan przycisku. Brak pliku oznacza domyślnie WŁĄCZONY."""
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return bool(data.get("show_tutorial_button", _DEFAULT_ENABLED))
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _DEFAULT_ENABLED


def set_tutorial_button_enabled(enabled: bool) -> None:
    """Zapisz ustawienie w osobnym pliku samouczka, poza configiem WM."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"show_tutorial_button": bool(enabled)}
    with SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _show_help(owner: tk.Misc) -> None:
    title = "Przycisk Samouczek"
    body = (
        "Włącza lub ukrywa przycisk Samouczek pod modułami w głównym panelu WM. "
        "Zmiana dotyczy tylko wejścia do samouczka i nie modyfikuje działania modułów ani danych produkcyjnych."
    )
    try:
        from settings_help_runtime import _show_help as shared_show_help
        shared_show_help(owner, title, body)
        return
    except Exception:
        pass
    messagebox.showinfo(title, body, parent=owner)


def _decorate(panel: Any) -> None:
    root = getattr(panel, "_general_container", None)
    if root is None:
        root = getattr(panel, "_content_area", None)
    if root is None or getattr(panel, "_wm_tutorial_setting_done", False):
        return

    box = ttk.LabelFrame(root, text="Samouczek WM")
    box.pack(fill="x", padx=10, pady=6)

    row = ttk.Frame(box)
    row.pack(fill="x", padx=10, pady=(9, 4))
    enabled_var = tk.BooleanVar(master=row, value=is_tutorial_button_enabled())
    check = ttk.Checkbutton(
        row,
        text="Pokaż przycisk „Samouczek” w panelu głównym",
        variable=enabled_var,
    )
    check.pack(side="left")
    ttk.Button(row, text="!", width=3, command=lambda: _show_help(check)).pack(
        side="left", padx=(6, 0)
    )

    ttk.Label(
        box,
        text="To ustawienie jest odseparowane od konfiguracji modułów WM i działa od razu.",
    ).pack(anchor="w", padx=10, pady=(0, 9))

    def _apply() -> None:
        enabled = bool(enabled_var.get())
        try:
            set_tutorial_button_enabled(enabled)
        except Exception as exc:
            messagebox.showerror(
                "Samouczek WM",
                f"Nie udało się zapisać ustawienia:\n{exc}",
                parent=panel.master,
            )
            enabled_var.set(is_tutorial_button_enabled())
            return
        try:
            top = panel.master.winfo_toplevel()
            setter = getattr(top, "wm_set_tutorial_button_visible", None)
            if callable(setter):
                setter(enabled)
        except Exception:
            pass

    check.configure(command=_apply)
    setattr(panel, "_wm_tutorial_setting_done", True)


def install_settings_tutorial_runtime(settings_panel_cls: type) -> None:
    """Dopnij izolowane ustawienie do istniejących Ustawień ogólnych."""
    if getattr(settings_panel_cls, "_wm_settings_tutorial_runtime", False):
        return
    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original_build_ui):
        return

    def _build_ui_with_tutorial(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        try:
            _decorate(self)
        except Exception:
            pass
        return result

    settings_panel_cls._build_ui = _build_ui_with_tutorial
    settings_panel_cls._wm_settings_tutorial_runtime = True


__all__ = [
    "SETTINGS_PATH",
    "install_settings_tutorial_runtime",
    "is_tutorial_button_enabled",
    "set_tutorial_button_enabled",
]
