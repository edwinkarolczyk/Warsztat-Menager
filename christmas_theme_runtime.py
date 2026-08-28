# WM-VERSION: 0.1
# version: 1.1
# Moduł: christmas_theme_runtime
# Zmiany 1.1:
# - Motyw Świąteczny korzysta zawsze z aktywnego ConfigManager, więc Toplevel/moduły
#   nie cofają globalnych stylów ttk do "default".
# - Dodano krótki opad śniegu po całym ekranie co ok. 20 s (Windows, click-through).
# - Wyłączenie motywu zatrzymuje wszystkie timery i usuwa warstwę śniegu.
#
# Motyw Świąteczny dla Warsztat Menager:
# - wybór „Świąteczny” w Ustawieniach zapisuje kanoniczne ui.theme=christmas,
# - wykorzystuje centralny ui_theme zamiast tworzyć drugi system stylów,
# - po zapisie stosuje motyw od razu,
# - dekoruje główne okno animacją tekstową: śnieg + Mikołaj + sanie,
# - przełączenie na inny motyw usuwa dekoracje i przywraca oryginalne tytuły.

from __future__ import annotations

import logging
import random
import time
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

_SNOW_INTERVAL_MS = 20_000
_SNOW_DURATION_MS = 6_500
_SNOW_TICK_MS = 70
_SNOW_FLAKES = 42
_SNOW_TRANSPARENT = "#010203"

_ORIGINAL_APPLY_THEME_SAFE = None
_ORIGINAL_LOAD_THEME_NAME = None


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


def _runtime_theme_name(ui_theme_module: Any, fallback: Any = None) -> str:
    """Odczytaj motyw z aktywnego ConfigManager, a nie z przypadkowego ./config.json."""
    try:
        from config_manager import ConfigManager

        value = ConfigManager().get("ui.theme", None)
        if value not in (None, ""):
            canonical = _canonical_theme(value)
            resolved = ui_theme_module.resolve_theme_name(canonical)
            if resolved in ui_theme_module.THEMES:
                return resolved
    except Exception:
        pass

    if fallback not in (None, ""):
        try:
            canonical = _canonical_theme(fallback)
            resolved = ui_theme_module.resolve_theme_name(canonical)
            if resolved in ui_theme_module.THEMES:
                return resolved
        except Exception:
            pass

    active = str(getattr(ui_theme_module, "_ACTIVE_THEME_NAME", "") or "").strip()
    if active in getattr(ui_theme_module, "THEMES", {}):
        return active
    return "default"


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


def _destroy_snow_overlay(root: tk.Misc) -> None:
    overlay = getattr(root, "_wm_christmas_snow_overlay", None)
    if overlay is not None:
        try:
            if overlay.winfo_exists():
                overlay.destroy()
        except Exception:
            pass
    try:
        root._wm_christmas_snow_overlay = None
    except Exception:
        pass


def _stop_snow(root: tk.Misc) -> None:
    job = getattr(root, "_wm_christmas_snow_job", None)
    if job:
        try:
            root.after_cancel(job)
        except Exception:
            pass
    try:
        root._wm_christmas_snow_job = None
    except Exception:
        pass
    _destroy_snow_overlay(root)


def _make_overlay_click_through(overlay: tk.Toplevel) -> None:
    """Na Windows warstwa śniegu nie blokuje kliknięć w WM."""
    try:
        if str(overlay.tk.call("tk", "windowingsystem")) != "win32":
            return
    except Exception:
        return

    try:
        import ctypes

        overlay.update_idletasks()
        hwnd = int(overlay.winfo_id())
        parent_hwnd = int(ctypes.windll.user32.GetParent(hwnd))
        if parent_hwnd:
            hwnd = parent_hwnd

        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_LAYERED = 0x00080000
        WS_EX_NOACTIVATE = 0x08000000

        get_style = ctypes.windll.user32.GetWindowLongW
        set_style = ctypes.windll.user32.SetWindowLongW
        style = int(get_style(hwnd, GWL_EXSTYLE))
        set_style(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE,
        )
    except Exception:
        pass


def _start_snow_burst(root: tk.Misc) -> None:
    """Krótki opad śniegu nad całym głównym oknem."""
    try:
        if not root.winfo_exists() or not getattr(root, "_wm_christmas_active", False):
            return
        if str(root.tk.call("tk", "windowingsystem")) != "win32":
            return
    except Exception:
        return

    _destroy_snow_overlay(root)

    try:
        root.update_idletasks()
        width = max(320, int(root.winfo_width()))
        height = max(240, int(root.winfo_height()))
        x = int(root.winfo_rootx())
        y = int(root.winfo_rooty())

        overlay = tk.Toplevel(root)
        root._wm_christmas_snow_overlay = overlay
        overlay.overrideredirect(True)
        overlay.geometry(f"{width}x{height}+{x}+{y}")
        overlay.configure(bg=_SNOW_TRANSPARENT)
        try:
            overlay.wm_attributes("-transparentcolor", _SNOW_TRANSPARENT)
        except Exception:
            overlay.destroy()
            root._wm_christmas_snow_overlay = None
            return
        try:
            overlay.attributes("-topmost", True)
        except Exception:
            pass

        canvas = tk.Canvas(
            overlay,
            bg=_SNOW_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
        overlay.update_idletasks()
        _make_overlay_click_through(overlay)

        flakes: list[dict[str, float | int]] = []
        for _ in range(_SNOW_FLAKES):
            fx = random.randint(0, width)
            fy = random.randint(-height, 0)
            size = random.randint(10, 22)
            item = canvas.create_text(
                fx,
                fy,
                text=random.choice(("❄", "❅", "❆")),
                fill="white",
                font=("Segoe UI Symbol", size),
            )
            flakes.append(
                {
                    "item": item,
                    "x": float(fx),
                    "y": float(fy),
                    "speed": random.uniform(3.0, 8.0),
                    "drift": random.uniform(-0.8, 0.8),
                }
            )

        started = time.monotonic()

        def _tick_snow() -> None:
            try:
                if (
                    not getattr(root, "_wm_christmas_active", False)
                    or not overlay.winfo_exists()
                    or time.monotonic() - started >= (_SNOW_DURATION_MS / 1000.0)
                ):
                    _destroy_snow_overlay(root)
                    return
            except Exception:
                _destroy_snow_overlay(root)
                return

            for flake in flakes:
                try:
                    flake["x"] = float(flake["x"]) + float(flake["drift"])
                    flake["y"] = float(flake["y"]) + float(flake["speed"])
                    if float(flake["y"]) > height + 25:
                        flake["y"] = float(random.randint(-120, -10))
                        flake["x"] = float(random.randint(0, width))
                    canvas.coords(
                        int(flake["item"]),
                        float(flake["x"]),
                        float(flake["y"]),
                    )
                except Exception:
                    continue

            try:
                overlay.after(_SNOW_TICK_MS, _tick_snow)
            except Exception:
                _destroy_snow_overlay(root)

        _tick_snow()
    except Exception:
        _destroy_snow_overlay(root)


def _ensure_snow_scheduler(root: tk.Misc) -> None:
    if getattr(root, "_wm_christmas_snow_job", None):
        return

    def _cycle() -> None:
        try:
            root._wm_christmas_snow_job = None
            if not root.winfo_exists() or not getattr(root, "_wm_christmas_active", False):
                return
        except Exception:
            return

        _start_snow_burst(root)
        try:
            root._wm_christmas_snow_job = root.after(_SNOW_INTERVAL_MS, _cycle)
        except Exception:
            root._wm_christmas_snow_job = None

    # Pierwszy opad od razu ułatwia sprawdzenie, potem kolejne co ok. 20 s.
    _cycle()


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

    _stop_snow(root)

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
        _ensure_snow_scheduler(root)
        return

    try:
        root._wm_christmas_original_title = root.title()
    except Exception:
        root._wm_christmas_original_title = "Warsztat Menager"

    root._wm_christmas_active = True
    root._wm_christmas_frame = 0
    root._wm_christmas_labels = _existing_title_labels(root)
    _ensure_snow_scheduler(root)

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
        base_title = str(
            getattr(root, "_wm_christmas_original_title", "Warsztat Menager")
            or "Warsztat Menager"
        )

        try:
            root.title(f"{snow}  {base_title}  •  Świąteczny  •  {sleigh}  {snow}")
        except Exception:
            pass

        if frame % 8 == 0:
            try:
                root._wm_christmas_labels = _existing_title_labels(root)
            except Exception:
                pass

        for label in list(getattr(root, "_wm_christmas_labels", []) or []):
            try:
                if not label.winfo_exists():
                    continue
                original = str(
                    getattr(label, "_wm_christmas_original_text", "")
                    or "Warsztat Menager"
                )
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
    global _ORIGINAL_APPLY_THEME_SAFE, _ORIGINAL_LOAD_THEME_NAME

    try:
        import ui_theme
    except Exception:
        logger.exception("[CHRISTMAS] Nie udało się zaimportować ui_theme")
        return

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

    # Ważne: stare aliasy apply_theme_safe (np. zaimportowane wcześniej przez
    # gui_panel) nadal odwołują się do globalnego ui_theme.load_theme_name.
    # Podmieniamy więc także ten odczyt, żeby nie korzystał z ./config.json.
    if not getattr(ui_theme, "_wm_christmas_load_theme_hook", False):
        original_load = getattr(ui_theme, "load_theme_name", None)
        if callable(original_load):
            _ORIGINAL_LOAD_THEME_NAME = original_load

            def _load_theme_name_runtime(config_path):
                active = _runtime_theme_name(ui_theme)
                if active in ui_theme.THEMES:
                    return active
                return original_load(config_path)

            ui_theme.load_theme_name = _load_theme_name_runtime
            ui_theme._wm_christmas_load_theme_hook = True

    if getattr(ui_theme, "_wm_christmas_theme_hook", False):
        return

    original = getattr(ui_theme, "apply_theme_safe", None)
    if not callable(original):
        return
    _ORIGINAL_APPLY_THEME_SAFE = original

    def _apply_theme_safe_with_christmas(target=None, scheme=None, *, config_path=None):
        effective = scheme
        if effective is None:
            effective = _runtime_theme_name(ui_theme)
        result = original(target, scheme=effective, config_path=config_path)
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
        display_var.set(
            _VALUE_TO_DISPLAY.get(canonical, str(source_var.get() or canonical))
        )

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
