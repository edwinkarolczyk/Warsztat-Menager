# version: 1.2
"""Kosmetyka widoku historii i informacja o kartach DOCX maszyn."""

from __future__ import annotations

import os
from typing import Any

_FULL_HISTORY_BOXES = {
    "Pełna historia statusów",
    "Pełna historia przeglądów / serwisów",
}
_STATUS_HISTORY_BOXES = {
    "Ostatnia historia statusów",
    "Pełna historia statusów",
}
_MAIN_MACHINE_COLUMNS = {
    "id", "nazwa", "typ", "status", "przeglad", "przeglad_status", "dni"
}


def _frame_text(widget: Any) -> str:
    try:
        return str(widget.cget("text") or "").strip()
    except Exception:
        return ""


def _machine_has_docx(machine: Any) -> bool:
    if not isinstance(machine, dict):
        return False
    path = str(machine.get("service_history_file") or "").strip()
    return bool(path and os.path.splitext(path)[1].casefold() == ".docx")


def _machine_label(machine: dict) -> str:
    machine_id = str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or "—"
    ).strip()
    name = str(machine.get("nazwa") or machine.get("name") or "").strip()
    return f"{machine_id} — {name}" if name else machine_id


def install_machine_history_layout(gui_module) -> bool:
    """Ustaw responsywną historię i pokaż maszyny bez przypisanego DOCX."""
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

    def _load_missing_docx() -> list[dict]:
        loader = getattr(gui_module, "load_machines_rows", None)
        if not callable(loader):
            return []
        try:
            rows = loader()
        except Exception:
            return []
        return [
            row for row in rows
            if isinstance(row, dict) and not _machine_has_docx(row)
        ]

    def _install_docx_notice(tree) -> None:
        try:
            if not tree.winfo_exists():
                return
        except Exception:
            return

        master = getattr(tree, "master", None)
        if master is None or getattr(master, "_wm_docx_notice_installed", False):
            return

        try:
            master._wm_docx_notice_installed = True
        except Exception:
            pass

        frame = ttk_module.Frame(master)
        info_var = gui_module.tk.StringVar(master=master, value="")

        def _refresh_count() -> list[dict]:
            missing = _load_missing_docx()
            info_var.set(f"Brak przypisanej karty DOCX: {len(missing)}")
            return missing

        def _show_missing() -> None:
            missing = _refresh_count()
            messagebox = getattr(gui_module, "messagebox", None)
            if messagebox is None:
                return
            if not missing:
                messagebox.showinfo(
                    "Karty DOCX maszyn",
                    "Wszystkie maszyny mają przypisaną kartę DOCX.",
                    parent=master.winfo_toplevel(),
                )
                return
            lines = [_machine_label(machine) for machine in missing]
            messagebox.showinfo(
                "Maszyny bez karty DOCX",
                "Brak przypisanej karty DOCX:\n\n" + "\n".join(lines),
                parent=master.winfo_toplevel(),
            )

        ttk_module.Label(frame, textvariable=info_var).pack(side="left")
        ttk_module.Button(frame, text="Pokaż", command=_show_missing).pack(
            side="left", padx=(8, 0)
        )
        _refresh_count()

        try:
            frame.pack(fill="x", padx=8, pady=(0, 4), before=tree)
        except Exception:
            frame.pack(fill="x", padx=8, pady=(0, 4))

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

            try:
                columns = set(str(col) for col in (self.cget("columns") or ()))
            except Exception:
                columns = set()
            if columns == _MAIN_MACHINE_COLUMNS:
                try:
                    self.after_idle(lambda: _install_docx_notice(self))
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
        LabelFrame = _HistoryLabelFrame

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkLayoutProxy()
    return True


__all__ = ["install_machine_history_layout"]
