# version: 1.0
"""Entry point for the Dyspozycje wizard."""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Dict, Optional, Type

from dyspozycje_store import get_dyspozycje_path
from wm.gui.i18n import t
from wm.settings.util import get_conf

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None  # type: ignore

try:
    from config_manager import ConfigManager, get_machines_path, get_profiles_path, resolve_rel
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore
    get_machines_path = None  # type: ignore
    get_profiles_path = None  # type: ignore
    resolve_rel = None  # type: ignore

from .constants import TYPES_REGISTRY
from .validators import validate_required


class _Wizard:
    def __init__(self, parent: tk.Misc | None, context: Optional[Dict] = None) -> None:
        self.root = tk.Toplevel(parent)
        self.root.title(t("wizard.dyspo.title"))
        self.root.geometry("540x420")
        self.root.transient(parent)
        self.root.grab_set()
        self.context = context or {}
        self._paths = _resolve_wizard_paths()
        self.context.setdefault("paths", self._paths)
        self._log_paths()
        self._current_step: ttk.Frame | None = None
        self._current_code: str | None = None
        self._content = ttk.Frame(self.root)
        self._content.pack(fill="both", expand=True)
        self._controls = ttk.Frame(self.root)
        self._controls.pack(fill="x", pady=8)
        self._validate_btn = ttk.Button(
            self._controls,
            text=t("wizard.dyspo.validate"),
            state="disabled",
            command=self._validate,
        )
        self._validate_btn.pack(side=tk.RIGHT, padx=8)
        ttk.Button(
            self._controls,
            text=t("wizard.dyspo.close"),
            command=self.root.destroy,
        ).pack(side=tk.RIGHT, padx=8)
        self._show_selection()
        self.root.update_idletasks()
        self._center_on_parent(parent)

    def _log_paths(self) -> None:
        print(f"[WM-DBG][DYSP-WIZARD] profiles={self._paths['profiles']}")
        print(f"[WM-DBG][DYSP-WIZARD] tools={self._paths['tools']}")
        print(f"[WM-DBG][DYSP-WIZARD] machines={self._paths['machines']}")
        print(f"[WM-DBG][DYSP-WIZARD] warehouse={self._paths['warehouse']}")
        print(f"[WM-DBG][DYSP-WIZARD] dyspozycje={self._paths['dyspozycje']}")

    def _center_on_parent(self, parent: tk.Misc | None) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if parent is not None:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        else:
            x = (self.root.winfo_screenwidth() - width) // 2
            y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _clear_content(self) -> None:
        for widget in self._content.winfo_children():
            widget.destroy()

    def _show_selection(self) -> None:
        self._clear_content()
        frame = ttk.Frame(self._content)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(
            frame,
            text=t("wizard.dyspo.choose_type"),
            font=("TkDefaultFont", 12),
        ).pack(pady=(0, 12))
        for code, meta in TYPES_REGISTRY.items():
            ttk.Button(
                frame,
                text=meta["button"],
                command=lambda c=code: self._show_step(c),
            ).pack(fill="x", pady=4)
        self._validate_btn.configure(state="disabled")

    def _show_step(self, code: str) -> None:
        self._clear_content()
        meta = TYPES_REGISTRY.get(code)
        if meta is None:
            messagebox.showerror(t("wizard.dyspo.title"), f"Brak definicji kroku dla {code}.")
            return
        try:
            module_path, class_name = meta["step"].rsplit(".", 1)
            module = importlib.import_module(module_path)
            step_class: Type[ttk.Frame] = getattr(module, class_name)
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror(
                t("wizard.dyspo.title"),
                f"Nie udało się załadować kroku {code}: {exc}",
            )
            return
        step = step_class(self._content, context=self.context, title=meta["label"])
        step.pack(fill="both", expand=True, padx=12, pady=12)
        if hasattr(step, "render"):
            step.render()
        self._current_step = step
        self._current_code = code
        self._validate_btn.configure(state="normal")

    def _validate(self) -> None:
        if not self._current_step or not self._current_code:
            return
        data = {}
        if hasattr(self._current_step, "collect_data"):
            try:
                data = self._current_step.collect_data()
            except Exception:
                data = {}
        conf = get_conf()
        errors = validate_required(data or {}, self._current_code, conf)
        if errors:
            messagebox.showerror(t("wizard.dyspo.title"), "\n".join(errors))
        else:
            messagebox.showinfo(
                t("wizard.dyspo.title"),
                t("wizard.dyspo.valid"),
            )


def open_dyspo_wizard(parent: tk.Misc | None, context: Optional[Dict] = None) -> _Wizard:
    """Open Dyspozycje wizard and return controller instance."""

    return _Wizard(parent, context)


def _resolve_wizard_paths() -> dict[str, str]:
    cfg = get_conf() or {}
    manager = None
    if ConfigManager is not None:
        try:
            manager = ConfigManager()
        except Exception:
            manager = None

    tools = ""
    if root_paths is not None:
        try:
            tools = str(root_paths.path_tools_dir())
        except Exception:
            tools = ""
    if not tools and manager is not None:
        try:
            tools = str(manager.path_data("narzedzia"))
        except Exception:
            tools = ""

    machines = ""
    if root_paths is not None:
        try:
            machines = str(root_paths.path_machines())
        except Exception:
            machines = ""
    if not machines and callable(get_machines_path):
        try:
            machines = str(get_machines_path(cfg))
        except Exception:
            machines = ""

    warehouse = ""
    if root_paths is not None:
        try:
            warehouse = str(root_paths.path_warehouse())
        except Exception:
            warehouse = ""
    if not warehouse and callable(resolve_rel):
        try:
            warehouse = str(resolve_rel(cfg, "warehouse_stock") or "")
        except Exception:
            warehouse = ""

    profiles = ""
    if root_paths is not None:
        try:
            profiles = str(root_paths.path_profiles())
        except Exception:
            profiles = ""
    if not profiles and callable(get_profiles_path):
        try:
            profiles = str(get_profiles_path(cfg))
        except Exception:
            profiles = ""

    dyspozycje = str(get_dyspozycje_path())

    return {
        "profiles": str(Path(profiles)) if profiles else "",
        "tools": str(Path(tools)) if tools else "",
        "machines": str(Path(machines)) if machines else "",
        "warehouse": str(Path(warehouse)) if warehouse else "",
        "dyspozycje": str(Path(dyspozycje)) if dyspozycje else "",
    }


__all__ = ["open_dyspo_wizard"]
