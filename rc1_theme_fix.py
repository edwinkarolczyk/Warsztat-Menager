"""RC1 hotfix: poprawa czytelności przycisków w motywie."""

from __future__ import annotations

from typing import Iterable, Mapping

try:  # pragma: no cover - defensywne w środowiskach testowych
    import ui_theme
    from tkinter import ttk
except Exception as exc:  # pragma: no cover
    print(f"[RC1][theme] Pomijam fix motywu: {exc}")
    ui_theme = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]

if ui_theme is not None and getattr(ui_theme, "_RC1_THEME_PATCHED", False) is False:
    ORIGINAL_APPLY = ui_theme.apply_theme
    ui_theme._RC1_THEME_PATCHED = True  # type: ignore[attr-defined]

    def _ensure_button_readability(
        style: ttk.Style, palette: Mapping[str, str]
    ) -> None:
        text_color = palette.get("text", "#ffffff")
        muted_color = palette.get("muted", text_color)
        styles: Iterable[str] = (
            "TButton",
            "WM.Button.TButton",
            "WM.Side.TButton",
            "WM.Outline.TButton",
        )
        state_map = [
            ("pressed", text_color),
            ("active", text_color),
            ("!disabled", text_color),
            ("disabled", muted_color),
        ]
        for style_name in styles:
            try:
                style.configure(style_name, foreground=text_color)
                style.map(style_name, foreground=state_map)
            except Exception as err:  # pragma: no cover - loguj i kontynuuj
                print(f"[RC1][theme] Nie mogę ustawić koloru {style_name}: {err}")

    def apply_theme(style: ttk.Style, name: str = ui_theme.DEFAULT_THEME) -> None:
        ORIGINAL_APPLY(style, name)
        palette: Mapping[str, str] = ui_theme.THEMES.get(  # type: ignore[arg-type]
            name, ui_theme.THEMES.get(ui_theme.DEFAULT_THEME, {})
        )
        _ensure_button_readability(style, palette)

    ui_theme.apply_theme = apply_theme
    print("[RC1][theme] Patch czytelności przycisków aktywny")
