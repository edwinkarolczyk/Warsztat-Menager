# version: 1.1
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
    """Ustaw responsywny układ historii i oznacz bieżący status jako Aktualny."""
    if gui_module is None:
        return False

    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None:
        return False
    if getattr(ttk_module, "_wm_machine_history_layout_proxy", False):
        return True

    real_treeview = getattr(ttk_module, "Treeview", None)
    real_labelframe = getattr(ttk_module, "LabelFrame", None)
    if real_treeview is None or real_labelframe is None:
        return False

    class _HistoryLabelFrame(real_labelframe):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._wm_history_box_text = _frame_text(self)

        def pack(self, *args, **kwargs):
            if self._wm_history_box_text not in _FULL_HISTORY_BOXES:
                return super().pack(*args, **kwargs)

            master = getattr(self, "master", None)
            if master is None:
                return super().pack(*args, **kwargs)

            try:
                master.columnconfigure(0, weight=1)
                master.rowconfigure(0, weight=1, uniform="wm_history_rows")
                master.rowconfigure(1, weight=1, uniform="wm_history_rows")

                if self._wm_history_box_text == "Pełna historia statusów":
                    row = 0
                    pady = (0, 8)
                else:
                    row = 1
                    pady = (0, 0)

                return self.grid(
                    row=row,
                    column=0,
                    sticky="nsew",
                    pady=pady,
                )
            except Exception:
                return super().pack(*args, **kwargs)

    class _HistoryTreeview(real_treeview):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._wm_history_box_text = _frame_text(getattr(self, "master", None))

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
        LabelFrame = _HistoryLabelFrame

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkLayoutProxy()
    return True


__all__ = ["install_machine_history_layout"]
