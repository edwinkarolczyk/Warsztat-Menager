# Wersja pliku: 1.5.7
# Moduł: gui_settings
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import datetime
import json
import os
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog, messagebox, ttk

import config_manager as cm
from config_manager import ConfigManager
from gui_products import ProductsMaterialsTab
import ustawienia_produkty_bom
from ui_utils import _ensure_topmost


def _is_deprecated(node: dict) -> bool:
    """Return True if schema node is marked as deprecated."""

    return node.get("deprecated") is True


def _create_widget(
    option: dict[str, Any], parent: tk.Widget
) -> tuple[ttk.Frame, tk.Variable]:
    """Return a frame containing label, widget and description for the option."""

    frame = ttk.Frame(parent)
    ttk.Label(frame, text=option.get("label", "")).grid(
        row=0, column=0, sticky="w", padx=5, pady=(5, 0)
    )

    opt_type = option.get("type")
    widget_type = option.get("widget")
    default = option.get("default")

    if opt_type == "bool":
        var = tk.BooleanVar(value=default)
        widget = ttk.Checkbutton(frame, variable=var)
    elif opt_type in {"int", "float"}:
        if opt_type == "int":
            var = tk.IntVar(value=default)
        else:
            var = tk.DoubleVar(value=default)
        spin_args: dict[str, Any] = {}
        if "min" in option:
            spin_args["from_"] = option["min"]
        if "max" in option:
            spin_args["to"] = option["max"]
        widget = ttk.Spinbox(frame, textvariable=var, **spin_args)
    elif opt_type == "enum":
        var = tk.StringVar(value=default)
        enum_list = option.get("enum")
        values_list = option.get("values")
        if enum_list is not None:
            print(f"[WM-DBG] enum values: {len(enum_list)}")
        if values_list is not None:
            print(f"[WM-DBG] values: {len(values_list)}")
        enum_vals = enum_list or values_list or []
        widget = ttk.Combobox(
            frame,
            textvariable=var,
            values=enum_vals,
            state="readonly",
        )
    elif opt_type == "path":
        var = tk.StringVar(value=default or "")
        sub = ttk.Frame(frame)
        entry = ttk.Entry(sub, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)

        def browse() -> None:
            if widget_type == "dir":
                path = filedialog.askdirectory()
            else:
                path = filedialog.askopenfilename()
            if path:
                var.set(path)

        ttk.Button(sub, text="Przeglądaj", command=browse).pack(
            side="left", padx=2
        )
        widget = sub
    elif opt_type == "array":
        default_list = option.get("default", []) or []
        lines = "\n".join(str(x) for x in default_list)
        item_type = option.get("value_type")
        if item_type in {"float", "int"} or (
            default_list and all(isinstance(x, (int, float)) for x in default_list)
        ):
            var: tk.StringVar = FloatListVar(value=lines)
        else:
            var = StrListVar(value=lines)
        text = tk.Text(frame, height=4)
        text.insert("1.0", lines)

        def update_var(*_args: Any) -> None:
            var.set(text.get("1.0", "end").strip())

        text.bind("<KeyRelease>", update_var)
        widget = text
    elif opt_type in {"dict", "object"}:
        default_dict: Dict[str, Any] = option.get("default", {}) or {}
        lines = "\n".join(f"{k} = {v}" for k, v in default_dict.items())
        if option.get("value_type") == "float":
            var = FloatDictVar(value=lines)
        else:
            var = StrDictVar(value=lines)
        text = tk.Text(frame, height=4)
        text.insert("1.0", lines)

        def update_dict(*_args: Any) -> None:
            var.set(text.get("1.0", "end").strip())

        text.bind("<KeyRelease>", update_dict)
        widget = text
    elif opt_type == "string" and widget_type == "color":
        var = tk.StringVar(value=default or "")
        sub = ttk.Frame(frame)
        entry = ttk.Entry(sub, textvariable=var, width=10)
        entry.pack(side="left", fill="x", expand=True)

        def pick_color() -> None:
            color = colorchooser.askcolor(var.get())[1]
            if color:
                var.set(color)

        ttk.Button(sub, text="Kolor", command=pick_color).pack(
            side="left", padx=2
        )
        widget = sub
    elif opt_type == "string" and widget_type == "password":
        var = tk.StringVar(value=default or "")
        widget = ttk.Entry(frame, textvariable=var, show="*")
    else:
        var = tk.StringVar(value=default or "")
        widget = ttk.Entry(frame, textvariable=var)

    widget.grid(row=0, column=1, sticky="w", padx=5, pady=(5, 0))

    tip = (
        option.get("tooltip")
        or option.get("help")
        or option.get("description")
    )
    if tip:
        _bind_tooltip(widget, tip)

    desc = option.get("description") or option.get("help")
    if desc:
        ttk.Label(frame, text=desc, font=("", 8)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5)
        )

    frame.columnconfigure(1, weight=1)
    return frame, var


class FloatListVar(tk.StringVar):
    """StringVar that parses lines into a list of floats."""

    def get(self) -> list[float]:  # type: ignore[override]
        vals: list[float] = []
        for line in super().get().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                vals.append(float(line))
            except ValueError:
                continue
        return vals


class FloatDictVar(tk.StringVar):
    """StringVar that parses "key = value" lines into a float dictionary."""

    def get(self) -> Dict[str, float]:  # type: ignore[override]
        result: Dict[str, float] = {}
        for line in super().get().splitlines():
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            try:
                result[key] = float(val)
            except ValueError:
                continue
        return result


class StrListVar(tk.StringVar):
    """StringVar that returns non-empty lines as a list of strings."""

    def get(self) -> list[str]:  # type: ignore[override]
        return [ln.strip() for ln in super().get().splitlines() if ln.strip()]


class StrDictVar(tk.StringVar):
    """StringVar that parses "key = value" lines into a string dictionary."""

    def get(self) -> Dict[str, str]:  # type: ignore[override]
        result: Dict[str, str] = {}
        for line in super().get().splitlines():
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                result[key] = val
        return result


def _bind_tooltip(widget, text: str):
    import tkinter as tk

    tip = {"w": None}

    def _show(_=None):
        if tip["w"] or not text:
            return
        x = widget.winfo_rootx() + 16
        y = widget.winfo_rooty() + 20
        tw = tk.Toplevel(widget)
        _ensure_topmost(tw, widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw,
            text=text,
            bg="#2A2F37",
            fg="#E8E8E8",
            bd=1,
            relief="solid",
            justify="left",
        )
        lbl.pack(ipadx=8, ipady=6)
        tip["w"] = tw

    def _hide(_=None):
        if tip["w"]:
            tip["w"].destroy()
            tip["w"] = None

    widget.bind("<Enter>", _show, add="+")
    widget.bind("<Leave>", _hide, add="+")


def save_all(options: Dict[str, tk.Variable], cfg: ConfigManager | None = None) -> None:
    """Persist all options from mapping using ConfigManager."""

    cfg = cfg or ConfigManager()
    for key, var in options.items():
        value = var.get()
        cfg.set(key, value)
    cfg.save_all()




class SettingsPanel:
    """Dynamic panel generated from :class:`ConfigManager` schema."""

    # >>> WM PATCH START: SettingsPanel schema getter
    def _get_schema(self):
        if hasattr(self, "cfg") and getattr(self.cfg, "schema", None):
            return self.cfg.schema
        if hasattr(self.master, "schema"):
            return self.master.schema
        parent = getattr(self.master, "master", None)
        if parent is not None and hasattr(parent, "schema"):
            return parent.schema
        return None
    # >>> WM PATCH END

    def __init__(
        self,
        master: tk.Misc,
        config_path: str | None = None,
        schema_path: str | None = None,
    ):
        self.master = master
        self.config_path = config_path
        self.schema_path = schema_path
        if config_path is not None or schema_path is not None:
            self.cfg = ConfigManager.refresh(
                config_path=config_path, schema_path=schema_path
            )
        else:
            self.cfg = ConfigManager()
        self.vars: Dict[str, tk.Variable] = {}
        self._initial: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._options: Dict[str, dict[str, Any]] = {}
        self._unsaved = False
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create notebook tabs and widgets based on current schema."""

        self._unsaved = False
        for child in self.master.winfo_children():
            child.destroy()

        schema = self._get_schema()
        print(f"[WM-DBG] using schema via _get_schema(): {schema is not None}")
        schema = schema or {}

        self.nb = ttk.Notebook(self.master)
        print("[WM-DBG] [SETTINGS] notebook created")
        self.nb.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # state for lazy creation of magazyn subtabs
        self._magazyn_frame: ttk.Frame | None = None
        self._magazyn_schema: dict[str, Any] | None = None
        self._magazyn_initialized = False

        for tab in schema.get("tabs", []):
            title = tab.get("title", tab.get("id", ""))
            print("[WM-DBG] [SETTINGS] add tab:", title)
            frame = ttk.Frame(self.nb)
            self.nb.add(frame, text=title)

            if tab.get("id") == "magazyn":
                self._magazyn_frame = frame
                self._magazyn_schema = tab
            else:
                grp_count, fld_count = self._populate_tab(frame, tab)
                print(
                    f"[WM-DBG] tab='{title}' groups={grp_count} fields={fld_count}"
                )

        base_dir = Path(__file__).resolve().parent
        self.products_tab = ProductsMaterialsTab(self.nb, base_dir=base_dir)
        self.nb.add(self.products_tab, text="Produkty i materiały")
        print("[WM-DBG] [SETTINGS] zakładka Produkty i materiały: OK")
        print("[WM-DBG] [SETTINGS] notebook packed")

        self.btns = ttk.Frame(self.master)
        self.btns.pack(pady=5)
        ttk.Button(self.btns, text="Zapisz", command=self.save).pack(
            side="left", padx=5
        )
        ttk.Button(
            self.btns, text="Przywróć domyślne", command=self.restore_defaults
        ).pack(side="left", padx=5)
        ttk.Button(self.btns, text="Odśwież", command=self.refresh_panel).pack(
            side="left", padx=5
        )

        self.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.on_close)

    def _populate_tab(self, parent: tk.Widget, tab: dict[str, Any]) -> tuple[int, int]:
        """Populate a single tab or subtab frame and return counts."""

        grp_count = 0
        fld_count = 0

        for group in tab.get("groups", []):
            if _is_deprecated(group):
                ident = group.get("label") or group.get("id") or "group"
                print(
                    f"[WM-DBG][SETTINGS] pomijam deprecated {ident}"
                )
                continue
            grp_count += 1
            grp_frame = ttk.LabelFrame(parent, text=group.get("label", ""))
            grp_frame.pack(fill="both", expand=True, padx=5, pady=5)
            if tip := group.get("tooltip"):
                _bind_tooltip(grp_frame, tip)
            inner = ttk.Frame(grp_frame)
            inner.pack(fill="both", expand=True, padx=8, pady=6)

            for field_def in group.get("fields", []):
                if _is_deprecated(field_def):
                    ident = field_def.get("key", "field")
                    print(
                        f"[WM-DBG][SETTINGS] pomijam deprecated {ident}"
                    )
                    continue
                fld_count += 1
                key = field_def["key"]
                self._options[key] = field_def
                current = self.cfg.get(key, field_def.get("default"))
                opt_copy = dict(field_def)
                opt_copy["default"] = current
                field, var = _create_widget(opt_copy, inner)
                field.pack(fill="x", padx=5, pady=2)
                self.vars[key] = var
                self._initial[key] = current
                self._defaults[key] = field_def.get("default")
                var.trace_add("write", lambda *_: setattr(self, "_unsaved", True))

            if tab.get("id") == "narzedzia" and group.get("key") == "narzedzia":
                ttk.Button(
                    inner,
                    text="Konfiguruj typy/statusy/zadania",
                    command=self._open_tools_config,
                ).pack(fill="x", padx=5, pady=5)

        if subtabs := tab.get("subtabs"):
            nb = ttk.Notebook(parent)
            nb.pack(fill="both", expand=True)
            for sub in subtabs:
                title = sub.get("title", sub.get("id", ""))
                sub_frame = ttk.Frame(nb)
                nb.add(sub_frame, text=title)
                g, f = self._populate_tab(sub_frame, sub)
                grp_count += g
                fld_count += f

        if tab.get("id") == "update":
            self._add_patch_section(parent)

        return grp_count, fld_count

    def _open_tools_config(self) -> None:
        """Open tools configuration window in top-most mode."""

        parent = self.master.winfo_toplevel()
        try:
            import gui_tools_config  # type: ignore
        except Exception as exc:  # pragma: no cover - import error handling
            messagebox.showerror(
                "Błąd",
                f"Nie można otworzyć konfiguracji narzędzi:\n{exc}",
                parent=parent,
            )
            return

        if hasattr(gui_tools_config, "open_window"):
            win = gui_tools_config.open_window(parent)  # type: ignore[assignment]
        elif hasattr(gui_tools_config, "ToolsConfigWindow"):
            win = gui_tools_config.ToolsConfigWindow(parent)  # type: ignore[assignment]
        else:  # pragma: no cover - unexpected api
            messagebox.showerror(
                "Błąd",
                "Brak funkcji otwierającej okno konfiguracji",
                parent=parent,
            )
            return

        try:
            win.transient(parent)
            win.attributes("-topmost", True)
            win.grab_set()
        except Exception as exc:  # pragma: no cover - tk specifics
            messagebox.showwarning(
                "Uwaga",
                f"Nie udało się poprawnie przygotować okna:\n{exc}",
                parent=parent,
            )

    def _add_patch_section(self, parent: tk.Widget) -> None:
        """Append patching and version controls to the Updates tab."""

        from tools import patcher

        frame = ttk.LabelFrame(parent, text="Paczowanie i wersje")
        frame.pack(fill="x", expand=True, padx=5, pady=5)

        def audit(action: str, detail: str) -> None:
            rec = {
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
                "user": "system",
                "key": action,
                "before": "",
                "after": detail,
            }
            os.makedirs(cm.AUDIT_DIR, exist_ok=True)
            path = Path(cm.AUDIT_DIR) / "config_changes.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        def run_patch(dry: bool) -> None:
            patch_path = filedialog.askopenfilename()
            if not patch_path:
                return
            print(f"[WM-DBG] apply_patch dry_run={dry} path={patch_path}")
            patcher.apply_patch(patch_path, dry_run=dry)
            audit("patch.dry_run" if dry else "patch.apply", patch_path)

        ttk.Button(
            frame,
            text="Sprawdź patch (dry-run)",
            command=lambda: run_patch(True),
        ).pack(side="left", padx=5, pady=5)
        ttk.Button(
            frame,
            text="Zastosuj patch",
            command=lambda: run_patch(False),
        ).pack(side="left", padx=5, pady=5)

        commits = patcher.get_commits()
        print(f"[WM-DBG] available commits: {len(commits)}")
        roll_frame = ttk.Frame(frame)
        roll_frame.pack(fill="x", padx=5, pady=5)
        commit_var = tk.StringVar()
        ttk.Combobox(
            roll_frame,
            textvariable=commit_var,
            values=commits,
            state="readonly",
        ).pack(side="left", fill="x", expand=True)

        def rollback() -> None:
            commit = commit_var.get()
            if not commit:
                return
            print(f"[WM-DBG] rollback to {commit}")
            patcher.rollback_to(commit)
            audit("patch.rollback", commit)

        ttk.Button(
            roll_frame,
            text="Cofnij do wersji",
            command=rollback,
        ).pack(side="left", padx=5)

    def _init_magazyn_tab(self) -> None:
        """Create subtabs for the 'magazyn' section on first use."""
        if self._magazyn_frame is None or self._magazyn_schema is None:
            return
        nb = ttk.Notebook(self._magazyn_frame)
        nb.pack(fill="both", expand=True)

        ustawienia_frame = ttk.Frame(nb)
        nb.add(ustawienia_frame, text="Ustawienia magazynu")
        print("[WM-DBG] init magazyn tab")
        self._populate_tab(ustawienia_frame, self._magazyn_schema)

        self._magazyn_initialized = True

    def _on_tab_change(self, _=None):
        if self._magazyn_frame is not None and not self._magazyn_initialized:
            if self.nb.select() == str(self._magazyn_frame):
                self._init_magazyn_tab()

        if self.cfg.warn_on_unsaved and self._unsaved:
            if messagebox.askyesno(
                "Niezapisane zmiany",
                "Masz niezapisane zmiany. Zapisać teraz?",
                parent=self.master,
            ):
                self.save()

    def restore_defaults(self) -> None:
        for key, var in self.vars.items():
            opt = self._options[key]
            default = self._defaults.get(key)
            opt_type = opt.get("type")
            widget_type = opt.get("widget")
            if opt_type == "array":
                default_list = default or []
                lines = "\n".join(str(x) for x in default_list)
                var.set(lines)
            elif opt_type in {"dict", "object"}:
                default_dict: Dict[str, Any] = default or {}
                lines = "\n".join(f"{k} = {v}" for k, v in default_dict.items())
                var.set(lines)
            elif opt_type == "string" and widget_type == "color":
                var.set(default or "")
            elif opt_type == "path":
                var.set(default or "")
            else:
                var.set(default)

    def on_close(self) -> None:
        changed = any(var.get() != self._initial[key] for key, var in self.vars.items())
        if changed:
            if messagebox.askyesno("Zapisz", "Czy zapisać zmiany?", parent=self.master):
                self.save()
        self.master.winfo_toplevel().destroy()

    def save(self) -> None:
        for key, var in self.vars.items():
            value = var.get()
            self.cfg.set(key, value)
            self._initial[key] = value
        self.cfg.save_all()
        self._unsaved = False

    def refresh_panel(self) -> None:
        """Reload configuration and rebuild widgets."""

        self.cfg = ConfigManager.refresh(
            config_path=self.config_path, schema_path=self.schema_path
        )
        self.vars.clear()
        self._initial.clear()
        self._defaults.clear()
        self._options.clear()
        self._build_ui()


class SettingsWindow(SettingsPanel):
    """Okno ustawień oparte na :class:`SettingsPanel`."""

    def __init__(
        self,
        master: tk.Misc,
        config_path: str = "config.json",
        schema_path: str = "settings_schema.json",
    ) -> None:
        import os

        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(config_path):
            config_path = os.path.join(base_dir, config_path)
        if not os.path.isabs(schema_path):
            schema_path = os.path.join(base_dir, schema_path)
        self.config_path = config_path
        self.schema_path = schema_path
        print(f"[WM-DBG] config_path={self.config_path}")
        print(f"[WM-DBG] schema_path={self.schema_path}")

        super().__init__(master, config_path=config_path, schema_path=schema_path)
        self.schema = self.cfg.schema
        print(f"[WM-DBG] tabs loaded: {len(self.schema.get('tabs', []))}")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    SettingsPanel(root)
    root.mainloop()

# ⏹ KONIEC KODU
