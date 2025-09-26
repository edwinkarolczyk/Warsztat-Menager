# -*- coding: utf-8 -*-
"""RC1 hotfix: poprawa kontrastu napisów w motywie Warsztat Menagera."""

from __future__ import annotations

from typing import Iterable, Tuple

try:
    from tkinter import ttk  # type: ignore
except Exception:  # pragma: no cover - środowisko bez Tk
    ttk = None  # type: ignore

import ui_theme as _theme


def _log(message: str) -> None:
    print(f"WM|RC1|theme_fix|{message}")


def _normalize_hex(color: str) -> str:
    if not isinstance(color, str):
        raise ValueError("color must be a string")
    value = color.strip()
    if not value.startswith("#"):
        raise ValueError("color must start with '#'")
    value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError("expected 6 hex digits")
    int(value, 16)
    return "#" + value.lower()


def _hex_to_rgb(color: str) -> Tuple[float, float, float]:
    norm = _normalize_hex(color)
    r = int(norm[1:3], 16) / 255.0
    g = int(norm[3:5], 16) / 255.0
    b = int(norm[5:7], 16) / 255.0
    return (r, g, b)


def _channel_to_linear(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> float:
    try:
        r, g, b = _hex_to_rgb(color)
    except Exception:
        return 0.0
    r_lin = _channel_to_linear(r)
    g_lin = _channel_to_linear(g)
    b_lin = _channel_to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _contrast_ratio(color_a: str, color_b: str) -> float:
    la = _relative_luminance(color_a)
    lb = _relative_luminance(color_b)
    bright = max(la, lb)
    dark = min(la, lb)
    return (bright + 0.05) / (dark + 0.05)


def _pick_text_color(background: str, preferred: str, *, min_ratio: float = 4.5) -> str:
    candidates: list[tuple[float, str]] = []
    seen: set[str] = set()
    palette: Iterable[str] = (
        preferred,
        "#ffffff",
        "#f4f4f4",
        "#fafafa",
        "#000000",
    )
    for candidate in palette:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            ratio = _contrast_ratio(background, candidate)
        except Exception:
            continue
        candidates.append((ratio, candidate))
    if not candidates:
        return preferred
    candidates.sort(key=lambda item: (item[0], item[1] == preferred), reverse=True)
    best_ratio, best_color = candidates[0]
    if best_ratio >= min_ratio:
        return best_color
    for ratio, candidate in candidates:
        if candidate == preferred and best_ratio - ratio <= 0.5:
            return preferred
    return best_color


def _ensure_palette_metadata(name: str, palette: dict[str, str]) -> dict[str, str]:
    updated = dict(palette)
    try:
        accent = palette.get("accent", "#d43c3c")
        accent_hover = palette.get("accent_hover", accent)
        text = palette.get("text", "#ffffff")
        muted = palette.get("muted", text)
        updated["accent_text"] = _pick_text_color(accent, text)
        updated["accent_hover_text"] = _pick_text_color(accent_hover, text)
        updated["muted_on_accent"] = _pick_text_color(accent, muted, min_ratio=3.0)
    except Exception:
        pass
    _theme.THEMES[name] = updated
    return updated


def _apply_contrast(style: ttk.Style, name: str, palette: dict[str, str]) -> None:
    accent = palette.get("accent", "#d43c3c")
    accent_hover = palette.get("accent_hover", accent)
    text = palette.get("text", "#ffffff")
    muted = palette.get("muted", text)
    accent_text = palette.get("accent_text", _pick_text_color(accent, text))
    accent_hover_text = palette.get(
        "accent_hover_text", _pick_text_color(accent_hover, text)
    )
    muted_on_accent = palette.get(
        "muted_on_accent", _pick_text_color(accent, muted, min_ratio=3.0)
    )

    try:
        style.map(
            "TButton",
            foreground=[
                ("disabled", muted),
                ("active", accent_hover_text),
                ("pressed", accent_text),
            ],
        )
    except Exception:
        pass

    for style_name in ("WM.Button.TButton", "WM.Outline.TButton"):
        try:
            style.configure(style_name, foreground=accent_text)
            style.map(
                style_name,
                foreground=[
                    ("disabled", muted_on_accent),
                    ("active", accent_hover_text),
                    ("pressed", accent_text),
                ],
            )
        except Exception:
            continue

    try:
        style.configure("WM.Banner.TLabel", foreground=accent_text)
    except Exception:
        pass

    try:
        style.map(
            "TNotebook.Tab",
            foreground=[
                ("selected", accent_text),
                ("!selected", text),
            ],
        )
    except Exception:
        pass

    for tree_style in ("Treeview", "WM.Treeview"):
        try:
            style.map(tree_style, foreground=[("selected", accent_text)])
        except Exception:
            continue


def _install_patch() -> None:
    if getattr(_theme, "_rc1_theme_fix_applied", False):
        _log("already-installed")
        return

    if ttk is None:
        _log("tkinter-missing")
        return

    original_apply_theme = _theme.apply_theme

    def wrapped(style: ttk.Style, name: str = _theme.DEFAULT_THEME) -> None:
        original_apply_theme(style, name)
        palette_obj = _theme.THEMES.get(name)
        if not isinstance(palette_obj, dict):
            palette_obj = dict(_theme.THEMES.get(_theme.DEFAULT_THEME, {}))
        palette = _ensure_palette_metadata(name, palette_obj)
        try:
            _apply_contrast(style, name, palette)
        except Exception:
            _log("apply-contrast-error")

    _theme.apply_theme = wrapped  # type: ignore[assignment]
    _theme._rc1_theme_fix_applied = True  # type: ignore[attr-defined]
    _log("installed")


_install_patch()
