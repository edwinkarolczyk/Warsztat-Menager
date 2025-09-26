# -*- coding: utf-8 -*-
"""RC1 hotfix: ulepszenia toolbaru w module Magazyn."""

from __future__ import annotations

from typing import Iterable

try:
    import tkinter as tk  # type: ignore
    from tkinter import ttk  # type: ignore
except Exception:  # pragma: no cover - środowisko bez Tk
    tk = None  # type: ignore
    ttk = None  # type: ignore

import ui_theme as _theme

try:  # pragma: no cover - opcjonalne współdzielenie logiki
    from rc1_theme_fix import _pick_text_color  # type: ignore
except Exception:  # pragma: no cover - fallback jeśli theme fix nie działa
    _pick_text_color = None

__all__ = ["style_toolbar"]


def _log(message: str) -> None:
    print(f"WM|RC1|magazyn_fix|{message}")


def _current_palette() -> dict[str, str]:
    try:
        name = _theme.resolve_theme_name(
            _theme.load_theme_name(_theme.CONFIG_FILE)
        )
    except Exception:
        name = _theme.DEFAULT_THEME
    palette = _theme.THEMES.get(name)
    if isinstance(palette, dict):
        return palette
    return dict(_theme.THEMES.get(_theme.DEFAULT_THEME, {}))


def _pick_accent_text(background: str, preferred: str, fallback: str) -> str:
    if callable(_pick_text_color):
        try:
            return _pick_text_color(background, preferred)
        except Exception:
            pass
    return preferred if preferred else fallback


def style_toolbar(toolbar: tk.Misc) -> None:
    """Nadaje przyciskom w toolbarze styl o wysokim kontraście."""

    if ttk is None:
        _log("tkinter-missing")
        return

    try:
        children: Iterable[tk.Misc] = toolbar.winfo_children()
    except Exception:
        _log("no-children")
        return

    buttons = [child for child in children if isinstance(child, ttk.Button)]
    if not buttons:
        _log("no-buttons")
        return

    try:
        style = ttk.Style(toolbar)
    except Exception:
        _log("style-error")
        return

    palette = _current_palette()
    accent = palette.get("accent", "#d43c3c")
    accent_hover = palette.get("accent_hover", accent)
    text = palette.get("text", "#ffffff")
    muted = palette.get("muted_on_accent", palette.get("muted", text))
    accent_text = palette.get("accent_text") or _pick_accent_text(accent, text, "#ffffff")
    accent_hover_text = palette.get("accent_hover_text") or _pick_accent_text(
        accent_hover, text, accent_text
    )

    style_name = "WM.ToolbarAccent.TButton"
    try:
        style.configure(
            style_name,
            background=accent,
            foreground=accent_text,
            padding=(10, 6),
            borderwidth=0,
        )
        style.map(
            style_name,
            background=[("active", accent_hover), ("pressed", accent)],
            foreground=[
                ("disabled", muted),
                ("active", accent_hover_text),
                ("pressed", accent_text),
            ],
        )
    except Exception:
        _log("style-config-error")
        return

    applied = 0
    for btn in buttons:
        try:
            current = btn.cget("style") or ""
        except Exception:
            continue
        if current and current != "TButton":
            continue
        try:
            btn.configure(style=style_name)
            applied += 1
        except Exception:
            continue

    _log(f"styled-buttons={applied}")
