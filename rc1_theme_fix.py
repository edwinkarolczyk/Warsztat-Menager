"""RC1 hotfix dla motywu WM – poprawa kontrastu przycisków akcentowych."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Mapping

from tkinter import ttk

import ui_theme

LOGGER = logging.getLogger(__name__)

_ORIG_APPLY_THEME_SAFE: Callable[..., None] | None = None
_ORIG_APPLY_THEME: Callable[..., None] | None = None
_INSTALLED = False


def _parse_hex_color(value: str) -> tuple[float, float, float]:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Nieprawidłowy kolor HEX: {value!r}")
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return r, g, b


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    def _channel(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _preferred_foreground(color: str) -> str:
    try:
        luminance = _relative_luminance(_parse_hex_color(color))
    except Exception:
        return "#ffffff"
    return "#111111" if luminance >= 0.5 else "#f7f7f7"


def _apply_button_contrast(style: ttk.Style, palette: Mapping[str, Any]) -> None:
    accent = palette.get("accent")
    if not isinstance(accent, str):
        return
    accent_hover = palette.get("accent_hover", accent)
    muted = palette.get("muted", "#888888")

    normal_fg = _preferred_foreground(accent)
    hover_fg = _preferred_foreground(accent_hover if isinstance(accent_hover, str) else accent)

    style.configure("WM.Button.TButton", foreground=normal_fg)
    style.map(
        "WM.Button.TButton",
        background=[("active", accent_hover), ("pressed", accent)],
        foreground=[
            ("disabled", muted),
            ("active", hover_fg),
            ("pressed", normal_fg),
        ],
    )

    style.map(
        "TButton",
        background=[("active", accent_hover), ("pressed", accent)],
        foreground=[
            ("disabled", muted),
            ("active", hover_fg),
            ("pressed", normal_fg),
        ],
    )

    style.map(
        "WM.Outline.TButton",
        background=[("active", accent_hover), ("pressed", accent)],
        bordercolor=[("active", accent_hover), ("pressed", accent)],
        foreground=[
            ("disabled", muted),
            ("active", hover_fg),
            ("pressed", normal_fg),
        ],
    )


def _post_apply_theme(style: ttk.Style, name: str | None) -> None:
    resolved = ui_theme.resolve_theme_name(name or ui_theme.DEFAULT_THEME)
    palette = ui_theme.THEMES.get(resolved)
    if palette is None:
        return
    _apply_button_contrast(style, palette)


def _wrap_apply_theme_safe() -> None:
    global _ORIG_APPLY_THEME_SAFE
    if _ORIG_APPLY_THEME_SAFE is None:
        _ORIG_APPLY_THEME_SAFE = ui_theme.apply_theme_safe

    def patched(
        target: Any | None = None,
        name: str | None = None,
        *,
        config_path: Path | None = None,
    ) -> None:
        assert _ORIG_APPLY_THEME_SAFE is not None
        _ORIG_APPLY_THEME_SAFE(target, name=name, config_path=config_path)
        try:
            style = target if isinstance(target, ttk.Style) else ttk.Style(target)
            if name is None:
                path = config_path or ui_theme.CONFIG_FILE
                name = ui_theme.load_theme_name(path)
            _post_apply_theme(style, name)
        except Exception:  # pragma: no cover - defensywne logowanie
            LOGGER.exception("rc1_theme_fix.apply_theme_safe failed")

    ui_theme.apply_theme_safe = patched  # type: ignore[assignment]


def _wrap_apply_theme() -> None:
    global _ORIG_APPLY_THEME
    if _ORIG_APPLY_THEME is None:
        _ORIG_APPLY_THEME = ui_theme.apply_theme

    def patched(style: ttk.Style, name: str = ui_theme.DEFAULT_THEME) -> None:
        assert _ORIG_APPLY_THEME is not None
        _ORIG_APPLY_THEME(style, name)
        try:
            _post_apply_theme(style, name)
        except Exception:  # pragma: no cover - defensywne logowanie
            LOGGER.exception("rc1_theme_fix.apply_theme failed")

    ui_theme.apply_theme = patched  # type: ignore[assignment]


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _wrap_apply_theme()
    _wrap_apply_theme_safe()
    _INSTALLED = True
    LOGGER.info("[RC1][THEME] Hotfix motywu zainstalowany")


install()
