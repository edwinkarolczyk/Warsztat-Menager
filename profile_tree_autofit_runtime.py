# version: 1.0
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
        try:
            # Wiersze są dodawane zaraz po _make_tree; after_idle uruchamia pomiar
            # dopiero po zakończeniu całego renderowania bieżącej tabeli.
            tree.after_idle(lambda current=tree: _autofit_tree(current))
        except Exception:
            pass
        return tree

    cls._make_tree = _make_tree
    cls._wm_tree_autofit_v1 = True
    _INSTALLED = True


__all__ = ["install", "_autofit_tree"]
