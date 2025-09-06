"""Okno ustawień aplikacji."""

# Wersja pliku: 1.5.0
# Zmiany: Dodano klasę SettingsWindow – ekran ustawień
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config_manager import ConfigManager


class SettingsWindow(ttk.Frame):
    """Proste okno z ustawieniami aplikacji."""

    def __init__(
        self,
        parent: tk.Widget,
        config_path: str = "config.json",
        schema_path: str = "settings_schema.json",
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path)
        self.backup_dir = Path("backup_dir")
        self._unsaved = False
        self.warn_on_unsaved = True
        self._load_files()
        self._build_ui()
        self._notebook.bind(
            "<<NotebookTabChanged>>", lambda _e: self._maybe_warn_unsaved()
        )
        self.winfo_toplevel().protocol(
            "WM_DELETE_WINDOW", self._on_close
        )

    # ------------------------------------------------------------------
    def _load_files(self) -> None:
        """Read configuration and schema files."""

        print("[WM-DBG] [SETTINGS] _load_files")
        cfg = ConfigManager()
        self.config = copy.deepcopy(cfg.global_cfg or {})
        self.schema = cfg.schema

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build notebook with configuration widgets."""

        for child in self.winfo_children():
            child.destroy()
        self._vars: dict[str, tk.Variable] = {}

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._notebook = nb
        tabs = []
        for i in range(7):
            frame = ttk.Frame(nb)
            nb.add(frame, text=f"Tab {i + 1}")
            tabs.append(frame)

        groups: dict[str, ttk.LabelFrame] = {}
        tab_index = 0
        for opt in self.schema.get("options", []):
            group = opt.get("group", "Inne")
            if group not in groups:
                parent = tabs[tab_index % len(tabs)]
                lf = ttk.LabelFrame(parent, text=group)
                lf.pack(fill="x", padx=5, pady=5)
                groups[group] = lf
                tab_index += 1
            self._add_option(groups[group], opt)
        self.vars = self._vars

    # ------------------------------------------------------------------
    def _add_option(self, parent: ttk.LabelFrame, opt: dict) -> None:
        key = opt.get("key")
        opt_type = opt.get("type")
        desc = opt.get("description", "")

        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(frame, text=opt.get("label", key)).pack(side="left")

        value = self._get_conf_value(key, opt.get("default"))
        if opt_type == "bool":
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(
                frame,
                variable=var,
                command=lambda k=key, v=var: self._set_conf_value(k, v.get()),
            )
        elif opt_type == "int":
            var = tk.StringVar(value=str(value))
            widget = ttk.Entry(frame, textvariable=var)

            def on_int(event, k=key, v=var) -> None:
                try:
                    self._set_conf_value(k, int(v.get()))
                except ValueError:
                    pass

            widget.bind("<FocusOut>", on_int)
        elif opt_type == "string" or opt_type == "str":
            var = tk.StringVar(value=str(value))
            widget = ttk.Entry(frame, textvariable=var)
            widget.bind(
                "<FocusOut>",
                lambda _e, k=key, v=var: self._set_conf_value(k, v.get()),
            )
        elif opt_type in {"list_int", "list_str"}:
            var = tk.StringVar(value=json.dumps(value))
            widget = ttk.Entry(frame, textvariable=var)

            def on_list(event, k=key, v=var, t=opt_type) -> None:
                try:
                    data = json.loads(v.get() or "[]")
                    if t == "list_int":
                        data = [int(x) for x in data]
                    else:
                        data = [str(x) for x in data]
                    self._set_conf_value(k, data)
                except Exception:
                    pass

            widget.bind("<FocusOut>", on_list)
        else:
            var = tk.StringVar(value=str(value))
            widget = ttk.Entry(frame, textvariable=var)
            widget.bind(
                "<FocusOut>",
                lambda _e, k=key, v=var: self._set_conf_value(k, v.get()),
            )

        widget.pack(side="right", fill="x", expand=True)
        self._vars[key] = var
        if desc:
            self._add_tooltip(widget, desc)

    # ------------------------------------------------------------------
    def _add_tooltip(self, widget: tk.Widget, text: str) -> None:
        tip: tk.Toplevel | None = None

        def show(_e: tk.Event) -> None:
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.geometry(
                f"+{widget.winfo_rootx() + 20}+{widget.winfo_rooty() + 20}"
            )
            ttk.Label(tip, text=text, relief="solid", borderwidth=1).pack()

        def hide(_e: tk.Event) -> None:
            nonlocal tip
            if tip is not None:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ------------------------------------------------------------------
    def _get_conf_value(self, dotted_key: str, default: object) -> object:
        cfg = self.config
        for part in dotted_key.split(".")[:-1]:
            cfg = cfg.setdefault(part, {})  # type: ignore[assignment]
        return cfg.get(dotted_key.split(".")[-1], default)

    def _set_conf_value(self, dotted_key: str, value: object) -> None:
        cfg = self.config
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            cfg = cfg.setdefault(part, {})  # type: ignore[assignment]
        cfg[parts[-1]] = value  # type: ignore[index]
        self._unsaved = True
        print(f"[WM-DBG] [SETTINGS] set {dotted_key}={value}")

    # ------------------------------------------------------------------
    def _maybe_warn_unsaved(self) -> None:
        if self.warn_on_unsaved and self._unsaved:
            if messagebox.askyesno(
                "Zmiany", "Masz niezapisane zmiany. Zapisać?"
            ):
                self.on_save()

    def _on_close(self) -> None:
        self._maybe_warn_unsaved()
        self.winfo_toplevel().destroy()

    # ------------------------------------------------------------------
    def on_save(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = self.backup_dir / f"config_{ts}.json"
        with backup_file.open("w", encoding="utf-8") as fh:
            json.dump(self.config, fh, indent=2, ensure_ascii=False)

        cfg = ConfigManager()
        cfg.global_cfg = copy.deepcopy(self.config)
        cfg.merged = cfg._merge_all()
        cfg._validate_all()
        cfg.save_all()
        self._unsaved = False

    # ------------------------------------------------------------------
    def restore_defaults(self) -> None:
        for opt in self.schema.get("options", []):
            key = opt.get("key")
            if not key:
                continue
            default = opt.get("default")
            if key in self._vars:
                self._vars[key].set(default)
                self._set_conf_value(key, default)

    def save(self) -> None:
        self.on_save()

    def refresh_panel(self) -> None:
        self._load_files()
        self._build_ui()

    # ------------------------------------------------------------------
    def on_restore(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=self.backup_dir, filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        with open(path, encoding="utf-8") as fh:
            self.config = json.load(fh)
        self._build_ui()
        messagebox.showinfo(
            "Przywrócono", "Aby zmiany zadziałały, wymagany jest restart."
        )


# Backwards compatibility alias
SettingsPanel = SettingsWindow


# ⏹ KONIEC KODU

