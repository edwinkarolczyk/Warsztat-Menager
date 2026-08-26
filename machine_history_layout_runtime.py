# version: 1.0
"""Kosmetyka widoku historii w oknie Użytkowanie maszyny."""

from __future__ import annotations

from typing import Any

_FULL_HISTORY_BOXES = {
    "Pełna historia statusów",
    "Pełna historia przeglądów / serwisów",
}
_STATUS_HISTORY_BOXES = {
    "Ostatnia historia statusów",
    "Pełna historia statusów",
}


def _frame_text(widget: Any) -> str:
    try:
        return str(widget.cget("text") or "").strip()
    except Exception:
        return ""


def install_machine_history_layout(gui_module) -> bool:
    """Zmniejsz pełne tabele historii i oznacz bieżący status jako Aktualny."""
    if gui_module is None:
        return False

    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None:
        return False
    if getattr(ttk_module, "_wm_machine_history_layout_proxy", False):
        return True

    real_treeview = getattr(ttk_module, "Treeview", None)
    if real_treeview is None:
        return False

    class _HistoryTreeview(real_treeview):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._wm_history_box_text = _frame_text(getattr(self, "master", None))
            if self._wm_history_box_text in _FULL_HISTORY_BOXES:
                # Domyślne okno Użytkowanie maszyny ma 980x720. Sześć wierszy
                # pozwala pokazać obie pełne historie bez ręcznego rozciągania.
                try:
                    self.configure(height=6)
                except Exception:
                    pass

        def insert(self, parent, index, iid=None, **kw):
            values = kw.get("values")
            if (
                self._wm_history_box_text in _STATUS_HISTORY_BOXES
                and values is not None
            ):
                try:
                    adjusted = list(values)
                except TypeError:
                    adjusted = []
                if (
                    len(adjusted) >= 3
                    and str(adjusted[2] or "").strip().casefold() == "w toku"
                ):
                    adjusted[2] = "Aktualny"
                    kw["values"] = tuple(adjusted)
            return super().insert(parent, index, iid=iid, **kw)

    class _TtkLayoutProxy:
        _wm_machine_history_layout_proxy = True
        _wm_base_ttk = ttk_module
        Treeview = _HistoryTreeview

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkLayoutProxy()
    return True


__all__ = ["install_machine_history_layout"]
