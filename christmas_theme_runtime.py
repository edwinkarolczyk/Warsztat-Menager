# WM-VERSION: 0.1
# version: 1.0
# Moduł: christmas_theme_runtime
#
# Motyw Świąteczny dla Warsztat Menager:
# - wybór „Świąteczny” w Ustawieniach zapisuje kanoniczne ui.theme=christmas,
# - wykorzystuje centralny ui_theme zamiast tworzyć drugi system stylów,
# - po zapisie stosuje motyw od razu,
# - dekoruje główne okno lekką animacją tekstową: śnieg + Mikołaj + sanie,
# - przełączenie na inny motyw usuwa dekoracje i przywraca oryginalne tytuły.

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

logger = logging.getLogger(__name__)

_DISPLAY_TO_VALUE = {
    "Ciemny": "dark",
    "Jasny": "light",
    "Auto": "auto",
    "Świąteczny": "christmas",
}
_VALUE_TO_DISPLAY = {
    "default": "Ciemny",
    "dark": "Ciemny",
    "light": "Jasny",
    "auto": "Auto",
    "christmas": "Świąteczny",
    "świąteczny": "Świąteczny",
    "swiateczny": "Świąteczny",
}

_SNOW_FRAMES = (
    "❄  ·  ❄  ·",
    "·  ❄  ·  ❄",
    "❄  ❄  ·  ·",
    "·  ·  ❄  ❄",
)
_SLEIGH_FRAMES = (
    "🎅🛷      ",
    "  🎅🛷    ",
    "    🎅🛷  ",
    "      🎅🛷",
    "    🎅🛷  ",
    "  🎅🛷    ",
)
_ANIMATION_MS = 650

_ORIGINAL_APPLY_THEME_SAFE = None


def _all_descendants(widget: tk.Misc):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _all_descendants(child)


def _canonical_theme(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "dark"
    if raw in _DISPLAY_TO_VALUE:
        return _DISPLAY_TO_VALUE[raw]
    lowered = raw.casefold()
    if lowered in {"świąteczny", "swiateczny", "christmas"}:
        return "christmas"
    if lowered in {"default", "ciemny", "dark"}:
        return "dark"
    if lowered in {"jasny", "light"}:
        return "light"
    if lowered == "auto":
        return "auto"
    return lowered


def _main_root(target: Any = None) -> tk.Misc | None:
    if isinstance(target, ttk.Style):
        target = getattr(target, "master", None)
    if isinstance(target, tk.Misc):
        try:
            root = target._root()
            if isinstance(root, tk.Misc):
                return root
        except Exception:
            pass
    try:
        root = tk._default_root
        return root if isinstance(root, tk.Misc) else None
    except Exception:
        return None


def _existing_title_labels(root: tk.Misc) -> list[tk.Misc]:
    labels: list[tk.Misc] = []
    for child in _all_descendants(root):
        if not isinstance(child, (tk.Label, ttk.Label)):
            continue
        try:
            text = str(child.cget("text") or "")
        except Exception:
            continue
        original = str(getattr(child, "_wm_christmas_original_text", "") or "")
        candidate = original or text
        if "warsztat menager" not in candidate.casefold():
            continue
        if not original:
            try:
                setattr(child, "_wm_christmas_original_text", candidate)
            except Exception:
                pass
        labels.append(child)
    return labels


def _restore_labels(root: tk.Misc) -> None:
    cached = list(getattr(root, "_wm_christmas_labels", []) or [])
    for child in cached:
        try:
            if not child.winfo_exists():
                continue
            original = getattr(child, "_wm_christmas_original_text", None)
            if original is not None:
                child.configure(text=original)
        except Exception:
            pass
    try:
        root._wm_christmas_labels = []
    except Exception:
        pass


def _stop_christmas_animation(root: tk.Misc) -> None:
    job = getattr(root, "_wm_christmas_job", None)
    if job:
        try:
            root.after_cancel(job)
        except Exception:
            pass
    try:
        root._wm_christmas_job = None
        root._wm_christmas_active = False
    except Exception:
        pass

    original_title = getattr(root, "_wm_christmas_original_title", None)
    if original_title is not None:
        try:
            root.title(original_title)
        except Exception:
            pass
    _restore_labels(root)


def _start_christmas_animation(root: tk.Misc) -> None:
    try:
        if not root.winfo_exists():
            return
    except Exception:
        return

    if getattr(root, "_wm_christmas_active", False):
        return

    try:
        root._wm_christmas_original_title = root.title()
    except Exception:
        root._wm_christmas_original_title = "Warsztat Menager"

    root._wm_christmas_active = True
    root._wm_christmas_frame = 0
    root._wm_christmas_labels = _existing_title_labels(root)

    def _tick() -> None:
        try:
            if not root.winfo_exists() or not getattr(root, "_wm_christmas_active", False):
                root._wm_christmas_job = None
                return
        except Exception:
            return

        frame = int(getattr(root, "_wm_christmas_frame", 0) or 0)
        snow = _SNOW_FRAMES[frame % len(_SNOW_FRAMES)]
        sleigh = _SLEIGH_FRAMES[frame % len(_SLEIGH_FRAMES)]
        base_title = str(getattr(root, "_wm_christmas_original_title", "Warsztat Menager") or "Warsztat Menager")

        try:
            root.title(f"{snow}  {base_title}  •  Świąteczny  •  {sleigh}  {snow}")
        except Exception:
            pass

        # Co kilka klatek odświeżamy listę, bo panel może przebudować nagłówek.
        if frame % 8 == 0:
            try:
                root._wm_christmas_labels = _existing_title_labels(root)
            except Exception:
                pass

        for label in list(getattr(root, "_wm_christmas_labels", []) or []):
            try:
                if not label.winfo_exists():
                    continue
                original = str(getattr(label, "_wm_christmas_original_text", "") or "Warsztat Menager")
                label.configure(text=f"{original}   {snow}  {sleigh}")
            except Exception:
                pass

        try:
            root._wm_christmas_frame = frame + 1
            root._wm_christmas_job = root.after(_ANIMATION_MS, _tick)
        except Exception:
            root._wm_christmas_job = None

    _tick()


def _sync_christmas_decorations(target: Any, scheme: Any) -> None:
    root = _main_root(target)
    if root is None:
        return
    if _canonical_theme(scheme) == "christmas":
        _start_christmas_animation(root)
    else:
        _stop_christmas_animation(root)


def _install_palette_and_theme_hook() -> None:
    global _ORIGINAL_APPLY_THEME_SAFE

    try:
        import ui_theme
    except Exception:
        logger.exception("[CHRISTMAS] Nie udało się zaimportować ui_theme")
        return

    # Centralna paleta. Nie tworzymy równoległego stylowania widgetów.
    try:
        ui_theme.THEMES["christmas"] = {
            "bg": "#07150d",
            "panel": "#0f2418",
            "card": "#163020",
            "text": "#fffaf0",
            "muted": "#c9d8ce",
            "accent": "#c62828",
            "accent_hover": "#e53935",
            "line": "#31543b",
            "success": "#2e7d32",
            "warning": "#d4af37",
            "error": "#ef5350",
            "entry_bg": "#0b1e13",
            "entry_fg": "#fffaf0",
            "entry_bd": "#3a6046",
            "tab_active": "#d4af37",
            "tab_inactive": "#8fb49a",
            "selection": "#2f6b45",
            "selection_soft": "#edf7f0",
        }
        ui_theme.THEME_ALIASES["świąteczny"] = "christmas"
        ui_theme.THEME_ALIASES["swiateczny"] = "christmas"
    except Exception:
        logger.exception("[CHRISTMAS] Nie udało się zarejestrować palety")

    if getattr(ui_theme, "_wm_christmas_theme_hook", False):
        return

    original = getattr(ui_theme, "apply_theme_safe", None)
    if not callable(original):
        return
    _ORIGINAL_APPLY_THEME_SAFE = original

    def _apply_theme_safe_with_christmas(target=None, scheme=None, *, config_path=None):
        result = original(target, scheme=scheme, config_path=config_path)
        effective = scheme
        if effective is None:
            try:
                from config_manager import ConfigManager
                effective = ConfigManager().get("ui.theme", "dark")
            except Exception:
                effective = getattr(ui_theme, "_ACTIVE_THEME_NAME", "dark")
        _sync_christmas_decorations(target, effective)
        return result

    ui_theme.apply_theme_safe = _apply_theme_safe_with_christmas
    ui_theme._wm_christmas_theme_hook = True


def _find_theme_combo(panel: Any) -> ttk.Combobox | None:
    source_var = getattr(panel, "var_theme", None)
    if source_var is None:
        return None
    source_name = str(source_var)
    root = getattr(panel, "master", None)
    if not isinstance(root, tk.Misc):
        return None

    for child in _all_descendants(root):
        if not isinstance(child, ttk.Combobox):
            continue
        try:
            if str(child.cget("textvariable") or "") == source_name:
                return child
        except Exception:
            continue
    return None


def _decorate_theme_selector(panel: Any) -> None:
    combo = _find_theme_combo(panel)
    source_var = getattr(panel, "var_theme", None)
    if combo is None or source_var is None:
        return
    if getattr(combo, "_wm_christmas_selector", False):
        return

    display_var = tk.StringVar(master=combo)

    def _sync_from_source(*_args: Any) -> None:
        canonical = _canonical_theme(source_var.get())
        display_var.set(_VALUE_TO_DISPLAY.get(canonical, str(source_var.get() or canonical)))

    def _apply_display_choice(_event=None) -> None:
        selected = str(display_var.get() or "").strip()
        canonical = _DISPLAY_TO_VALUE.get(selected)
        if canonical is not None:
            source_var.set(canonical)

    combo.configure(
        textvariable=display_var,
        values=tuple(_DISPLAY_TO_VALUE.keys()),
        state="readonly",
    )
    combo.bind("<<ComboboxSelected>>", _apply_display_choice, add="+")
    try:
        source_var.trace_add("write", _sync_from_source)
    except Exception:
        pass
    _sync_from_source()

    combo._wm_christmas_selector = True
    combo._wm_christmas_display_var = display_var


def _apply_saved_theme(panel: Any) -> None:
    source_var = getattr(panel, "var_theme", None)
    if source_var is None:
        return
    canonical = _canonical_theme(source_var.get())
    if canonical not in {"dark", "light", "auto", "christmas"}:
        canonical = "dark"
    try:
        if str(source_var.get()) != canonical:
            source_var.set(canonical)
    except Exception:
        pass

    try:
        root = panel.master.winfo_toplevel()
    except Exception:
        root = _main_root()

    try:
        import ui_theme
        ui_theme.apply_theme_safe(root, scheme=canonical)
    except Exception:
        logger.exception("[CHRISTMAS] Nie udało się zastosować zapisanego motywu")


def install_christmas_theme_runtime(settings_panel_cls: type) -> None:
    """Zarejestruj motyw i podłącz go do aktywnego panelu Ustawień."""

    _install_palette_and_theme_hook()

    if getattr(settings_panel_cls, "_wm_christmas_theme_runtime", False):
        return

    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    original_save = getattr(settings_panel_cls, "save", None)
    if not callable(original_build_ui) or not callable(original_save):
        return

    def _build_ui_with_christmas(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        try:
            _decorate_theme_selector(self)
        except Exception:
            logger.exception("[CHRISTMAS] Nie udało się rozszerzyć wyboru motywu")
        return result

    def _save_with_christmas(self, *args: Any, **kwargs: Any):
        source_var = getattr(self, "var_theme", None)
        if source_var is not None:
            try:
                source_var.set(_canonical_theme(source_var.get()))
            except Exception:
                pass
        result = original_save(self, *args, **kwargs)
        _apply_saved_theme(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_christmas
    settings_panel_cls.save = _save_with_christmas
    settings_panel_cls._wm_christmas_theme_runtime = True


__all__ = ["install_christmas_theme_runtime"]
