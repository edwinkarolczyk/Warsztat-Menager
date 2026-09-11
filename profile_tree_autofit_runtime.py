# version: 1.1
"""Dopasowuje szerokości tabel Profilu Brygadzisty do faktycznej treści.

Zmiana dotyczy wyłącznie szerokości kolumn Treeview tworzonych przez
ForemanProfilePanel. Nie zmienia danych, kolejności kolumn ani źródeł danych.
"""
from __future__ import annotations

from tkinter import ttk

_INSTALLED = False


def _font_width(tree: ttk.Treeview, font_name, text: object) -> int:
    value = str(text if text is not None else "")
    try:
        return int(tree.tk.call("font", "measure", font_name, value))
    except Exception:
        return max(0, len(value)) * 8


def _autofit_tree(tree: ttk.Treeview) -> None:
    """Ustaw każdą kolumnę według najdłuższego nagłówka lub pola w pionie."""
    try:
        columns = list(tree.cget("columns") or ())
        if not columns:
            return

        style = ttk.Style(tree)
        body_font = style.lookup("Foreman.Treeview", "font") or "TkDefaultFont"
        heading_font = style.lookup("Foreman.Treeview.Heading", "font") or body_font
        rows = list(tree.get_children(""))

        for index, column in enumerate(columns):
            try:
                heading = tree.heading(column, "text")
            except Exception:
                heading = column

            width = _font_width(tree, heading_font, heading) + 24
            for iid in rows:
                try:
                    values = tree.item(iid, "values") or ()
                    value = values[index] if index < len(values) else ""
                except Exception:
                    value = ""
                width = max(width, _font_width(tree, body_font, value) + 20)

            # Minimum zapobiega znikaniu krótkich kolumn numerycznych.
            tree.column(column, width=max(42, width))
    except Exception:
        return


def _queue_autofit(tree: ttk.Treeview, *, delay_ms: int = 0) -> None:
    """Przelicz szerokości po zakończeniu bieżącego layoutu Tk."""

    def _run() -> None:
        try:
            if not tree.winfo_exists():
                return
            tree.update_idletasks()
        except Exception:
            return
        _autofit_tree(tree)

    try:
        if delay_ms > 0:
            tree.after(delay_ms, _run)
        else:
            tree.after_idle(_run)
    except Exception:
        _run()


def _bind_visible_autofit(tree: ttk.Treeview) -> None:
    """Ponów autofit, gdy tabela z ukrytej zakładki staje się widoczna."""
    if getattr(tree, "_wm_autofit_visible_v1", False):
        return

    def _on_map(_event=None) -> None:
        # Pierwszy pomiar zaraz po mapowaniu i drugi po ustabilizowaniu Notebooka.
        _queue_autofit(tree)
        _queue_autofit(tree, delay_ms=60)

    try:
        tree.bind("<Map>", _on_map, add="+")
        tree._wm_autofit_visible_v1 = True
    except Exception:
        return


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_tree_autofit_v1", False):
        _INSTALLED = True
        return

    original_make_tree = cls._make_tree

    def _make_tree(self, *args, **kwargs):
        tree = original_make_tree(self, *args, **kwargs)
        _bind_visible_autofit(tree)
        # Dla aktualnie widocznej tabeli zachowaj dotychczasowy szybki pomiar.
        _queue_autofit(tree)
        return tree

    cls._make_tree = _make_tree
    cls._wm_tree_autofit_v1 = True
    _INSTALLED = True


__all__ = ["install", "_autofit_tree", "_queue_autofit", "_bind_visible_autofit"]
