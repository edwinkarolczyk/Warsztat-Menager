# version: 1.0.1
# Moduł: settings_color_preview_runtime
# UI-only: podgląd kolorów i szybki wybór bez zmiany kluczy konfiguracji.
# 1.0.1: po dodaniu pickera zmienia starą podpowiedź „wpisuj HEX” na wybór z podglądem.

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Any


_DYSP_DEFAULTS = {
    0: "#9ca3af",  # zamknięte
    1: "#facc15",  # nowe
    2: "#ffffff",  # nowe - miganie
    3: "#ef4444",  # po terminie
    4: "#ffffff",  # po terminie - miganie tekst
    5: "#7f1d1d",  # po terminie - miganie tło
}


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _variable_for_entry(entry: tk.Misc) -> tk.StringVar | None:
    try:
        var_name = str(entry.cget("textvariable") or "").strip()
    except Exception:
        return None
    if not var_name:
        return None
    try:
        return tk.StringVar(master=entry, name=var_name)
    except Exception:
        return None


def _set_swatch_color(swatch: tk.Label, owner: tk.Misc, value: str) -> None:
    color = str(value or "").strip()
    try:
        owner.winfo_rgb(color)
    except Exception:
        color = "#2b2f36"
    try:
        swatch.configure(bg=color)
    except Exception:
        pass


def _make_swatch(parent: tk.Misc, var: tk.StringVar) -> tk.Label:
    swatch = tk.Label(
        parent,
        text="   ",
        width=4,
        relief="solid",
        borderwidth=1,
        cursor="hand2",
    )

    def _refresh(*_args: Any) -> None:
        _set_swatch_color(swatch, parent, var.get())

    _refresh()
    var.trace_add("write", _refresh)
    return swatch


def _pick_color(owner: tk.Misc, var: tk.StringVar) -> None:
    current = str(var.get() or "").strip()
    kwargs: dict[str, Any] = {"parent": owner.winfo_toplevel()}
    try:
        owner.winfo_rgb(current)
        kwargs["color"] = current
    except Exception:
        pass
    try:
        selected = colorchooser.askcolor(**kwargs)[1]
    except Exception:
        selected = None
    if selected:
        var.set(str(selected).lower())


def _attach_generic_color_previews(panel: Any) -> None:
    """Rozszerza istniejące pola schema widget=color o podgląd i Domyślny."""
    root = getattr(panel, "_content_area", None)
    if root is None:
        return

    for button in _all_descendants(root):
        if not isinstance(button, ttk.Button):
            continue
        try:
            if str(button.cget("text") or "") != "Kolor":
                continue
            holder = button.master
            if getattr(holder, "_wm_color_preview_decorated", False):
                continue
        except Exception:
            continue

        entry = None
        for child in holder.winfo_children():
            if isinstance(child, ttk.Entry):
                entry = child
                break
        if entry is None:
            continue

        var = _variable_for_entry(entry)
        if var is None:
            continue

        swatch = _make_swatch(holder, var)
        swatch.pack(side="left", padx=(4, 2))
        swatch.bind("<Button-1>", lambda _e, h=holder, v=var: _pick_color(h, v))

        default_value = None
        try:
            var_name = str(entry.cget("textvariable") or "")
            for key, candidate_var in getattr(panel, "vars", {}).items():
                if str(candidate_var) == var_name:
                    default_value = getattr(panel, "_defaults", {}).get(key)
                    break
        except Exception:
            default_value = None

        if default_value not in (None, ""):
            ttk.Button(
                holder,
                text="Domyślny",
                command=lambda v=var, d=default_value: v.set(str(d)),
            ).pack(side="left", padx=(2, 0))

        setattr(holder, "_wm_color_preview_decorated", True)


def _attach_dispatches_color_previews(panel: Any) -> None:
    """Dodaje próbki + picker do ręcznej sekcji Moduły → Dyspozycje."""
    parent = getattr(panel, "_dispatches_container", None)
    if parent is None:
        return

    colors_box = None
    for child in parent.winfo_children():
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            if str(child.cget("text") or "") == "Kolory":
                colors_box = child
                break
        except Exception:
            continue
    if colors_box is None or getattr(colors_box, "_wm_color_preview_decorated", False):
        return

    for child in colors_box.winfo_children():
        if not isinstance(child, ttk.Entry):
            continue
        try:
            row = int(child.grid_info().get("row"))
        except Exception:
            continue
        if row not in _DYSP_DEFAULTS:
            continue

        var = _variable_for_entry(child)
        if var is None:
            continue

        swatch = _make_swatch(colors_box, var)
        swatch.grid(row=row, column=2, sticky="w", padx=(0, 6), pady=4)
        swatch.bind(
            "<Button-1>",
            lambda _e, h=colors_box, v=var: _pick_color(h, v),
        )

        ttk.Button(
            colors_box,
            text="Wybierz…",
            command=lambda h=colors_box, v=var: _pick_color(h, v),
        ).grid(row=row, column=3, sticky="w", padx=(0, 4), pady=4)

        ttk.Button(
            colors_box,
            text="Domyślny",
            command=lambda v=var, d=_DYSP_DEFAULTS[row]: v.set(d),
        ).grid(row=row, column=4, sticky="w", padx=(0, 8), pady=4)

    colors_box.columnconfigure(1, weight=1)
    ttk.Label(
        colors_box,
        text=(
            "Kliknij próbkę albo „Wybierz…”, aby wybrać kolor. "
            "Kod HEX można nadal wpisać ręcznie."
        ),
    ).grid(row=6, column=0, columnspan=5, sticky="w", padx=8, pady=(4, 8))

    for child in parent.winfo_children():
        if not isinstance(child, ttk.Label):
            continue
        try:
            old_text = str(child.cget("text") or "")
        except Exception:
            continue
        if "Kolory wpisuj jako HEX" not in old_text:
            continue
        child.configure(
            text=(
                "Kolory wybieraj przyciskiem „Wybierz…” lub klikając próbkę; "
                "HEX pozostaje opcją ręczną. Częstotliwość w milisekundach: "
                "2000 = 2 sekundy, 500 = pół sekundy."
            )
        )
        break

    setattr(colors_box, "_wm_color_preview_decorated", True)


def _attach_appearance_preview(panel: Any) -> None:
    """Dodaje prosty podgląd motywu i rozmiaru czcionki w zakładce Wygląd."""
    parent = getattr(panel, "_ui_container", None)
    if parent is None or getattr(parent, "_wm_appearance_preview_added", False):
        return

    theme_var = getattr(panel, "var_theme", None)
    font_var = getattr(panel, "var_font_size", None)
    if theme_var is None or font_var is None:
        return

    box = ttk.LabelFrame(parent, text="Podgląd wyglądu")
    box.pack(fill="x", expand=False, padx=8, pady=(0, 8))

    preview = tk.Frame(box, bd=1, relief="solid")
    preview.pack(fill="x", padx=8, pady=8)

    title = tk.Label(preview, text="Warsztat Menager — przykład")
    title.pack(anchor="w", padx=10, pady=(9, 3))

    row = tk.Frame(preview)
    row.pack(fill="x", padx=10, pady=(2, 4))
    name = tk.Label(row, text="Przegląd cykliczny — Przecinarka")
    name.pack(side="left")
    status = tk.Label(row, text="Nowa")
    status.pack(side="right")

    hint = tk.Label(
        preview,
        text="Podgląd zmienia się od razu. Zapis ustawień działa tak jak dotychczas.",
    )
    hint.pack(anchor="w", padx=10, pady=(2, 9))

    def _refresh(*_args: Any) -> None:
        try:
            size = max(8, min(18, int(font_var.get())))
        except Exception:
            size = 10
        mode = str(theme_var.get() or "dark").strip().lower()

        if mode == "light":
            card = "#ffffff"
            fg = "#15171a"
            muted = "#5f6670"
            accent = "#b45309"
        else:
            # Dla auto pokazujemy bezpieczny wariant ciemny do czasu zastosowania motywu.
            card = "#202329"
            fg = "#f3f4f6"
            muted = "#a5abb3"
            accent = "#facc15"

        try:
            box.configure(text=f"Podgląd wyglądu — {mode}")
            preview.configure(bg=card)
            row.configure(bg=card)
            title.configure(bg=card, fg=fg, font=("", size + 2, "bold"))
            name.configure(bg=card, fg=fg, font=("", size))
            status.configure(bg=card, fg=accent, font=("", size, "bold"))
            hint.configure(bg=card, fg=muted, font=("", max(8, size - 1)))
        except Exception:
            pass

    _refresh()
    theme_var.trace_add("write", _refresh)
    font_var.trace_add("write", _refresh)

    setattr(parent, "_wm_appearance_preview_added", True)


def _decorate_panel(panel: Any) -> None:
    for decorator in (
        _attach_appearance_preview,
        _attach_generic_color_previews,
        _attach_dispatches_color_previews,
    ):
        try:
            decorator(panel)
        except Exception:
            pass


def install_settings_color_preview_runtime(settings_panel_cls: type) -> None:
    """Instaluje dekorację SettingsPanel bez zmiany logiki zapisu konfiguracji."""
    if getattr(settings_panel_cls, "_wm_color_preview_runtime_installed", False):
        return

    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original_build_ui):
        return

    def _build_ui_with_color_preview(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        _decorate_panel(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_color_preview
    settings_panel_cls._wm_color_preview_runtime_installed = True
