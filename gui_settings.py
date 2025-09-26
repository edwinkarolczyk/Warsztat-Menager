# Wersja pliku: 1.7.1
# Moduł: gui_settings
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import copy
import datetime
import json
import os, sys, subprocess, threading
import re
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog
from tkinter import ttk, messagebox

from gui.settings_action_handlers import (
    bind as settings_actions_bind,
    execute as settings_action_exec,
)
from config.paths import bind_settings, ensure_core_tree

try:
    from wm_log import (
        bind_settings_getter as wm_bind_settings_getter,
        dbg as wm_dbg,
        err as wm_err,
        info as wm_info,
    )
except ImportError:  # pragma: no cover - fallback for environments without wm_log
    def wm_bind_settings_getter(_getter):
        return None


    def wm_dbg(*_args, **_kwargs):
        return None


    def wm_err(*_args, **_kwargs):
        return None


    def wm_info(*_args, **_kwargs):
        return None

class ScrollableFrame(ttk.Frame):
    """Generic vertically scrollable frame with mouse wheel support."""

    def __init__(self, parent: tk.Misc, *args: object, **kwargs: object) -> None:
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._canvas_alive = True
        self.canvas.bind("<Destroy>", lambda e: setattr(self, "_canvas_alive", False))
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", lambda event: self._scroll(-120))
        self.canvas.bind_all("<Button-5>", lambda event: self._scroll(120))
        top = self.winfo_toplevel()
        top.bind("<Destroy>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Ensure the inner frame matches the canvas width."""

        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Scroll canvas when mouse wheel is used (Windows/Linux)."""

        delta = getattr(event, "delta", 0) or 0
        try:
            step = -int(delta / 120) * 30
        except Exception:
            step = 0
        if step:
            self._scroll(step)

    def _scroll(self, units: int) -> None:
        """Perform vertical scrolling by the given unit delta, handling widget teardown."""

        c = getattr(self, "canvas", None)
        if not c or not self._canvas_alive:
            print("[WM-DBG][SETTINGS] Scroll przerwany: canvas nie istnieje/already destroyed")
            return
        try:
            if c.winfo_exists():
                c.yview_scroll(units, "units")
            else:
                print("[WM-DBG][SETTINGS] Scroll przerwany: winfo_exists=False")
        except tk.TclError:
            # Canvas został zniszczony w trakcie callbacku – ignorujemy
            self._canvas_alive = False
            print("[WM-DBG][SETTINGS] Ignoruję scroll po zniszczeniu canvas (TclError)")

# A-2e: alias do edytora advanced (wyszukiwarka, limity, kolekcje NN/SN)
try:
    from gui_tools_config import ToolsConfigDialog  # preferuje advanced, fallback prosty
except Exception:  # pragma: no cover - środowisko bez gui_tools_config
    ToolsConfigDialog = None

import config_manager as cm
from config_manager import ConfigManager
from gui_products import ProductsMaterialsTab
from ustawienia_magazyn import MagazynSettingsFrame
import ustawienia_produkty_bom
from ui_utils import _ensure_topmost
import logika_zadan as LZ
from profile_utils import SIDEBAR_MODULES
from services import profile_service
from logger import log_akcja

from zlecenia_utils import DEFAULT_ORDER_TYPES


MAG_DICT_PATH = "data/magazyn/slowniki.json"


def _is_deprecated(node: dict) -> bool:
    """Return True if schema node is marked as deprecated."""

    return node.get("deprecated") is True


def _create_widget(
    option: dict[str, Any], parent: tk.Widget
) -> tuple[ttk.Frame, tk.Variable]:
    """Return a frame containing label, widget and description for the option."""

    frame = ttk.Frame(parent)
    ttk.Label(
        frame,
        text=option.get("label_pl") or option.get("label") or option["key"],
    ).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))

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
        enum_vals = values_list or enum_list or []
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

    tip = option.get("help_pl") or option.get("help") or ""
    if tip:
        _bind_tooltip(widget, tip)

    desc = option.get("help_pl") or option.get("help") or option.get("description")
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


class CSVListVar(tk.StringVar):
    """StringVar that normalizes comma-separated values into a list."""

    def _split(self, raw: str) -> list[str]:
        parts: list[str] = []
        for chunk in raw.replace(";", ",").replace("\n", ",").split(","):
            text = chunk.strip()
            if text:
                parts.append(text)
        return parts

    def get(self) -> list[str]:  # type: ignore[override]
        return self._split(super().get())

    def set(self, value: Any) -> None:  # type: ignore[override]
        if isinstance(value, str):
            tokens = self._split(value)
        elif isinstance(value, (list, tuple, set)):
            tokens = [str(item).strip() for item in value if str(item).strip()]
        else:
            tokens = [str(value).strip()] if value is not None else []
        super().set(", ".join(tokens))


class NestedListVar(tk.StringVar):
    """StringVar that parses "typ: status1, status2" lines into dict list."""

    def get(self) -> dict[str, list[str]]:  # type: ignore[override]
        result: dict[str, list[str]] = {}
        for raw_line in super().get().splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, values = line.split(":", 1)
            key = key.strip()
            if not key:
                continue
            tokens = [
                token.strip()
                for token in re.split(r"[;,]", values)
                if token.strip()
            ]
            result[key] = tokens
        return result

    def set(self, value: Any) -> None:  # type: ignore[override]
        if isinstance(value, dict):
            lines: list[str] = []
            for key, items in value.items():
                key_str = str(key).strip()
                if not key_str:
                    continue
                joined = ", ".join(
                    str(item).strip()
                    for item in items
                    if str(item).strip()
                )
                lines.append(f"{key_str}: {joined}" if joined else key_str)
            super().set("\n".join(lines))
        else:
            super().set("" if value is None else str(value))


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
        self.settings_state = self._load_settings_state()
        wm_bind_settings_getter(lambda k: self.settings_state.get(k))
        bind_settings(self.settings_state)
        ensure_core_tree()
        settings_actions_bind(self.settings_state, on_change=self.on_setting_changed)
        self.vars: Dict[str, tk.Variable] = {}
        self._initial: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._options: Dict[str, dict[str, Any]] = {}
        self._fields_vars: list[tuple[tk.Variable, dict[str, Any]]] = []
        self._orders_vars: dict[str, tk.Variable] = {}
        self._orders_meta: dict[str, dict[str, Any]] = {}
        self._unsaved = False
        self._open_windows: dict[str, tk.Toplevel] = {}
        self._mod_vars: dict[str, tk.BooleanVar] = {}
        self._user_var: tk.StringVar | None = None

        self._container = ttk.Frame(self.master)
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self._scroll_area = ScrollableFrame(self._container)
        self._scroll_area.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        self._content_area = self._scroll_area.inner

        self._footer_frame = ttk.Frame(self._container)
        self._footer_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        self._footer_frame.grid_columnconfigure(0, weight=1)

        self.btns = ttk.Frame(self._footer_frame)
        self.btns.grid(row=0, column=0, sticky="ew")

        self._build_ui()

    # ------------------------------------------------------------------
    def _load_settings_state(self) -> dict[str, Any]:
        """Return mapping of config keys to their current values."""

        try:
            cfg = getattr(self, "cfg", None)
            if cfg is None:
                return {}

            schema = self._get_schema() or {}
            state: dict[str, Any] = {}

            def _iter_fields(node: dict[str, Any]):
                for field in node.get("fields", []):
                    if field.get("deprecated"):
                        continue
                    key = field.get("key")
                    if key:
                        yield key, field
                for child_key in ("tabs", "groups", "subtabs"):
                    for child in node.get(child_key, []):
                        yield from _iter_fields(child)

            for key, field in _iter_fields(schema):
                state[key] = cfg.get(key, field.get("default"))

            for option in schema.get("options", []):
                if option.get("deprecated"):
                    continue
                key = option.get("key")
                if key:
                    state[key] = cfg.get(key, option.get("default"))

            return state
        except Exception:
            return {}

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create notebook tabs and widgets based on current schema."""

        self._unsaved = False
        self._fields_vars = []
        self.settings_state.clear()
        content_parent = getattr(self, "_content_area", self.master)
        for child in content_parent.winfo_children():
            child.destroy()
        if hasattr(self, "btns"):
            for child in self.btns.winfo_children():
                child.destroy()

        schema = self._get_schema()
        print(f"[WM-DBG] using schema via _get_schema(): {schema is not None}")
        schema = schema or {}

        self.nb = ttk.Notebook(content_parent)
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

            tab_id = tab.get("id")
            if tab_id == "magazyn":
                self._magazyn_frame = frame
                self._magazyn_schema = tab
            elif tab_id == "zlecenia":
                grp_count, fld_count = self._build_orders_tab(frame, tab)
                print(
                    f"[WM-DBG] tab='{title}' groups={grp_count} fields={fld_count}"
                )
            elif tab_id == "narzedzia":
                grp_count, fld_count = self._build_tools_tab(frame, tab)
                print(
                    f"[WM-DBG] tab='{title}' groups={grp_count} fields={fld_count}"
                )
            else:
                grp_count, fld_count = self._populate_tab(frame, tab)
                print(
                    f"[WM-DBG] tab='{title}' groups={grp_count} fields={fld_count}"
                )

        base_dir = Path(__file__).resolve().parent
        self._add_magazyn_tab()
        self.products_tab = ProductsMaterialsTab(self.nb, base_dir=base_dir)
        self.nb.add(self.products_tab, text="Produkty i materiały")
        print("[WM-DBG] [SETTINGS] zakładka Produkty i materiały: OK")
        print("[WM-DBG] [SETTINGS] notebook packed")

        left_btns = ttk.Frame(self.btns)
        left_btns.pack(side="left", padx=5)
        ttk.Button(left_btns, text="Anuluj", command=self._close_window).pack(
            side="left", padx=5
        )
        ttk.Button(
            left_btns,
            text="Przywróć domyślne",
            command=self.restore_defaults,
        ).pack(side="left", padx=5)
        ttk.Button(left_btns, text="Odśwież", command=self.refresh_panel).pack(
            side="left", padx=5
        )

        right_btns = ttk.Frame(self.btns)
        right_btns.pack(side="right", padx=5)
        ttk.Button(right_btns, text="Zapisz", command=self.save).pack(
            side="right", padx=5
        )

        self.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.on_close)

    def _close_window(self) -> None:
        """Invoke the standard close flow used by the Cancel button."""

        try:
            self.on_close()
        except Exception:
            try:
                self.master.winfo_toplevel().destroy()
            except Exception:
                pass

    def _add_magazyn_tab(self) -> None:
        try:
            frame = MagazynSettingsFrame(self.nb, self.cfg)
        except Exception as e:
            import tkinter as tk
            from tkinter import ttk
            frame = ttk.Frame(self.nb)
            lbl = ttk.Label(frame, text=f"Błąd ładowania zakładki Magazyn:\n{e}")
            lbl.pack(padx=12, pady=12)
        self.nb.add(frame, text="Magazyn")

    def _coerce_default_for_var(self, opt: dict[str, Any], default: Any) -> Any:
        """Return value adjusted for Tk variable according to option definition."""

        opt_type = opt.get("type")
        widget_type = opt.get("widget")
        if opt_type == "array":
            default_list = default or []
            return "\n".join(str(x) for x in default_list)
        if opt_type in {"dict", "object"}:
            default_dict: Dict[str, Any] = default or {}
            return "\n".join(f"{k} = {v}" for k, v in default_dict.items())
        if opt_type == "string" and widget_type == "color":
            return default or ""
        if opt_type == "path":
            return default or ""
        return default

    def _register_option_var(
        self,
        key: str,
        var: tk.Variable,
        field_def: dict[str, Any] | None,
    ) -> None:
        """Register Tk variable for config option with bookkeeping."""

        opt = dict(field_def) if field_def else {"key": key}
        self.vars[key] = var
        self._options[key] = opt
        self._initial[key] = var.get()
        self._defaults[key] = opt.get("default")
        self._fields_vars.append((var, opt))
        self.settings_state[key] = var.get()
        var.trace_add("write", lambda *_: self._on_var_write(key, var))

    def _create_button_field(
        self, parent: tk.Widget, field_def: dict[str, Any]
    ) -> ttk.Button:
        """Return ttk button configured for schema action field."""

        text = (
            field_def.get("label_pl")
            or field_def.get("label")
            or field_def.get("key")
            or "Akcja"
        )
        btn = ttk.Button(
            parent,
            text=text,
            command=lambda f=field_def, lbl=text: self._on_button_field_clicked(
                f, lbl
            ),
        )
        tip = field_def.get("help_pl") or field_def.get("help")
        if tip:
            _bind_tooltip(btn, tip)
        return btn

    def _on_var_write(self, key: str, var: tk.Variable) -> None:
        """Handle Tk variable updates by tracking unsaved state and cache."""

        setattr(self, "_unsaved", True)
        try:
            self.settings_state[key] = var.get()
        except Exception:
            pass

    def _on_button_field_clicked(self, field: dict[str, Any], label: str) -> None:
        """Execute configured action for schema button field."""

        action = field.get("action")
        params = field.get("params", {}) or {}
        wm_dbg("ui.button", "click", label=label, action=action, params=params)
        if not action:
            return
        try:
            result = settings_action_exec(action, params)
            ok = True
            if isinstance(result, dict) and "ok" in result:
                ok = bool(result["ok"])
            wm_info(
                "ui.button",
                "done",
                label=label,
                action=action,
                ok=ok,
                result=result,
            )
        except RuntimeError as exc:
            wm_err(
                "ui.button",
                "action failed",
                exc,
                label=label,
                action=action,
                params=params,
            )
            messagebox.showerror(
                "Błąd akcji ustawień",
                str(exc),
                parent=self.master,
            )
            return
        except Exception as exc:
            wm_err(
                "ui.button",
                "action failed",
                exc,
                label=label,
                action=action,
                params=params,
            )
            messagebox.showerror(
                "Błąd akcji ustawień",
                f"Nie udało się wykonać akcji: {exc}",
                parent=self.master,
            )
            return

        write_to_key = params.get("write_to_key")
        if write_to_key:
            self.on_setting_changed(
                write_to_key, self.settings_state.get(write_to_key)
            )

    def on_setting_changed(self, key: str, value: Any) -> None:
        """Callback invoked by action handlers when config value changes."""

        wm_info("ui.settings.change", "value updated", key=key, value=value)
        self.settings_state[key] = value
        var = self.vars.get(key)
        if var is None:
            return
        opt = self._options.get(key, {"key": key})
        try:
            coerced = self._coerce_default_for_var(opt, value)
        except Exception as exc:
            wm_err(
                "ui.settings.change",
                "coerce failed",
                exc,
                key=key,
                value=value,
            )
            coerced = value
        try:
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            elif isinstance(var, tk.IntVar):
                var.set(int(value))
            elif isinstance(var, tk.DoubleVar):
                var.set(float(value))
            else:
                var.set(coerced)
        except Exception as exc:
            wm_err(
                "ui.settings.change",
                "var set failed",
                exc,
                key=key,
                value=value,
            )
            try:
                var.set(value)
            except Exception as fallback_exc:
                wm_err(
                    "ui.settings.change",
                    "var fallback set failed",
                    fallback_exc,
                    key=key,
                    value=value,
                )

    def _add_group(
        self,
        parent: tk.Widget,
        title: str,
        *,
        description: str | None = None,
        namespace: str | None = None,
    ) -> ttk.LabelFrame:
        """Create labeled frame for manual settings sections."""

        group = ttk.LabelFrame(parent, text=title)
        group.pack(fill="x", padx=10, pady=(10, 6))
        group.columnconfigure(0, weight=1)
        if namespace:
            setattr(group, "_settings_namespace", namespace)
        if description:
            ttk.Label(
                group,
                text=description,
                wraplength=560,
                font=("", 9, "italic"),
            ).pack(anchor="w", padx=8, pady=(6, 2))
        return group

    def _add_field(
        self,
        group: ttk.LabelFrame,
        key: str,
        label: str,
        *,
        field_type: str = "string",
        default: Any = None,
        description: str = "",
    ) -> tk.Variable:
        """Create a labeled field inside ``group`` and register variable."""

        namespace = getattr(group, "_settings_namespace", None)
        if namespace and "." not in key:
            full_key = f"{namespace}.{key}"
        else:
            full_key = key

        frame = ttk.Frame(group)
        frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(frame, text=label).pack(anchor="w")

        def format_list(value: Any) -> str:
            if isinstance(value, (list, tuple, set)):
                return "\n".join(str(item).strip() for item in value if str(item).strip())
            if isinstance(value, str):
                return value
            return ""

        def format_dict(value: Any) -> str:
            if isinstance(value, dict):
                return "\n".join(f"{k} = {v}" for k, v in value.items())
            if isinstance(value, str):
                return value
            return ""

        def format_nested(value: Any) -> str:
            if isinstance(value, dict):
                lines: list[str] = []
                for k, vals in value.items():
                    key_str = str(k).strip()
                    if not key_str:
                        continue
                    vals_list = [str(item).strip() for item in vals if str(item).strip()]
                    joined = ", ".join(vals_list)
                    lines.append(f"{key_str}: {joined}" if joined else key_str)
                return "\n".join(lines)
            if isinstance(value, str):
                return value
            return ""

        widget: tk.Widget
        var: tk.Variable
        field_def: dict[str, Any]

        if field_type == "list":
            text_value = format_list(default)
            var = StrListVar(master=frame)
            var.set(text_value)
            text = tk.Text(frame, height=4, wrap="word")
            text.insert("1.0", text_value)

            def update_list(*_args: Any) -> None:
                var.set(text.get("1.0", "end").strip())

            text.bind("<KeyRelease>", update_list)
            text.pack(fill="x", expand=True, pady=(2, 0))
            widget = text
            field_def = {
                "key": full_key,
                "type": "array",
                "value_type": "string",
                "default": default if isinstance(default, list) else [],
            }
        elif field_type == "dict_float":
            text_value = format_dict(default)
            var = FloatDictVar(master=frame)
            var.set(text_value)
            text = tk.Text(frame, height=4, wrap="word")
            text.insert("1.0", text_value)

            def update_fdict(*_args: Any) -> None:
                var.set(text.get("1.0", "end").strip())

            text.bind("<KeyRelease>", update_fdict)
            text.pack(fill="x", expand=True, pady=(2, 0))
            widget = text
            field_def = {
                "key": full_key,
                "type": "dict",
                "value_type": "float",
                "default": default if isinstance(default, dict) else {},
            }
        elif field_type == "dict":
            text_value = format_dict(default)
            var = StrDictVar(master=frame)
            var.set(text_value)
            text = tk.Text(frame, height=4, wrap="word")
            text.insert("1.0", text_value)

            def update_dict(*_args: Any) -> None:
                var.set(text.get("1.0", "end").strip())

            text.bind("<KeyRelease>", update_dict)
            text.pack(fill="x", expand=True, pady=(2, 0))
            widget = text
            field_def = {
                "key": full_key,
                "type": "dict",
                "value_type": "string",
                "default": default if isinstance(default, dict) else {},
            }
        elif field_type == "nested_list":
            text_value = format_nested(default)
            var = NestedListVar(master=frame)
            var.set(text_value)
            text = tk.Text(frame, height=6, wrap="word")
            text.insert("1.0", text_value)

            def update_nested(*_args: Any) -> None:
                var.set(text.get("1.0", "end").strip())

            text.bind("<KeyRelease>", update_nested)
            text.pack(fill="x", expand=True, pady=(2, 0))
            widget = text
            field_def = {
                "key": full_key,
                "type": "dict",
                "default": default if isinstance(default, dict) else {},
            }
        elif field_type == "int":
            value = default if isinstance(default, int) else 0
            var = tk.IntVar(master=frame, value=value)
            spin = ttk.Spinbox(frame, from_=1, to=10, textvariable=var, width=6)
            spin.pack(anchor="w", pady=(2, 0))
            widget = spin
            field_def = {"key": full_key, "type": "int", "default": value}
        else:
            value = "" if default is None else str(default)
            var = tk.StringVar(master=frame, value=value)
            entry = ttk.Entry(frame, textvariable=var)
            entry.pack(fill="x", expand=True, pady=(2, 0))
            widget = entry
            field_def = {"key": full_key, "type": "string", "default": value}

        if description:
            ttk.Label(
                frame,
                text=description,
                wraplength=560,
                font=("", 9),
                foreground="#565656",
            ).pack(anchor="w", pady=(2, 0))

        self._register_option_var(full_key, var, field_def)

        if full_key.startswith("_orders."):
            if not hasattr(self, "_orders_vars"):
                self._orders_vars = {}
            if not hasattr(self, "_orders_meta"):
                self._orders_meta = {}
            name = full_key.split(".", 1)[1]
            self._orders_vars[name] = var
            self._orders_meta[name] = {
                "type": field_type,
                "widget": widget,
            }

        return var

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
                key = field_def.get("key")
                if not key:
                    continue
                fld_count += 1
                self._options[key] = field_def
                if field_def.get("type") == "button":
                    btn = self._create_button_field(inner, field_def)
                    btn.pack(fill="x", padx=5, pady=2)
                    continue
                current = self.cfg.get(key, field_def.get("default"))
                opt_copy = dict(field_def)
                opt_copy["default"] = current
                field, var = _create_widget(opt_copy, inner)
                field.pack(fill="x", padx=5, pady=2)
                self.vars[key] = var
                self._initial[key] = current
                self._defaults[key] = field_def.get("default")
                self._fields_vars.append((var, field_def))
                self.settings_state[key] = current
                var.trace_add("write", lambda *_: self._on_var_write(key, var))

            if tab.get("id") == "narzedzia" and group.get("key") == "narzedzia":
                ttk.Button(
                    inner,
                    text="Edytor definicji zadań…",
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

        if tab.get("id") == "profile":
            users = [u.get("login", "") for u in profile_service.get_all_users()]
            sel = ttk.Frame(parent)
            sel.pack(fill="x", padx=5, pady=5)
            ttk.Label(sel, text="Użytkownik:").pack(side="left")
            self._user_var = tk.StringVar()
            cmb = ttk.Combobox(
                sel, values=users, textvariable=self._user_var, state="readonly"
            )
            cmb.pack(side="left", fill="x", expand=True, padx=5)
            cmb.bind(
                "<<ComboboxSelected>>",
                lambda _e: self._load_user_modules(self._user_var.get()),
            )
            box = ttk.LabelFrame(parent, text="Widoczność modułów")
            box.pack(fill="x", padx=5, pady=5)
            self._mod_vars = {}
            for key, label in SIDEBAR_MODULES:
                var = tk.BooleanVar(value=True)
                self._mod_vars[key] = var
                ttk.Checkbutton(box, text=label, variable=var).pack(anchor="w")
            ttk.Button(
                parent,
                text="Zastosuj teraz",
                command=self._apply_user_modules,
            ).pack(fill="x", padx=5, pady=(0, 5))

        if tab.get("id") == "update":
            self._add_patch_section(parent)

        return grp_count, fld_count

    def _build_orders_tab(
        self, parent: tk.Widget, tab: dict[str, Any]
    ) -> tuple[int, int]:
        """Create advanced editor for the Orders settings tab."""

        self._orders_vars = {}
        self._orders_meta = {}

        orders_cfg_raw = self.cfg.get("orders", {})
        orders_cfg = orders_cfg_raw if isinstance(orders_cfg_raw, dict) else {}
        orders_cfg = copy.deepcopy(orders_cfg)

        types_raw = orders_cfg.get("types", {})
        base_types: dict[str, dict[str, Any]] = {
            code: copy.deepcopy(data) for code, data in DEFAULT_ORDER_TYPES.items()
        }
        if isinstance(types_raw, dict):
            for code, data in types_raw.items():
                if isinstance(data, dict):
                    target = base_types.setdefault(
                        code, copy.deepcopy(DEFAULT_ORDER_TYPES.get(code, {}))
                    )
                    target.update(copy.deepcopy(data))

        for code, data in base_types.items():
            data.setdefault("label", DEFAULT_ORDER_TYPES.get(code, {}).get("label", code))
            data.setdefault(
                "prefix", DEFAULT_ORDER_TYPES.get(code, {}).get("prefix", f"{code}-")
            )
            statuses_default = DEFAULT_ORDER_TYPES.get(code, {}).get("statuses", ["nowe"])
            data.setdefault("statuses", list(statuses_default))
            if "enabled" not in data:
                data["enabled"] = bool(
                    DEFAULT_ORDER_TYPES.get(code, {}).get("enabled", True)
                )

        enabled_types = [
            code for code, data in base_types.items() if data.get("enabled", True)
        ]
        prefixes = {
            code: data.get("prefix", f"{code}-") for code, data in base_types.items()
        }
        statuses_map = {
            code: list(data.get("statuses", [])) for code, data in base_types.items()
        }

        id_width_raw = orders_cfg.get("id_width", 4)
        try:
            id_width = int(id_width_raw)
        except (TypeError, ValueError):
            id_width = 4

        colors = orders_cfg.get("status_colors")
        colors = colors if isinstance(colors, dict) else {}

        tasks = orders_cfg.get("tasks")
        if not isinstance(tasks, list):
            fallback_tasks = self.cfg.get("czynnosci_technologiczne", [])
            tasks = fallback_tasks if isinstance(fallback_tasks, list) else []

        alerts_raw = orders_cfg.get("alert_thresholds_pct")
        alerts: dict[str, float] = {}
        if isinstance(alerts_raw, dict):
            for key, value in alerts_raw.items():
                try:
                    alerts[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        elif isinstance(alerts_raw, list):
            codes = list(base_types.keys())
            for idx, code in enumerate(codes):
                try:
                    alerts[code] = float(alerts_raw[idx])
                except (IndexError, TypeError, ValueError):
                    alerts[code] = 50.0
        if not alerts:
            alerts = {code: 50.0 for code in base_types.keys()}

        links = orders_cfg.get("module_links")
        if not isinstance(links, dict) or not links:
            links = {
                "ZN": "Powiąż z kartoteką narzędzi (zakres SN 500–1000)",
                "ZM": "Powiąż z modułem Maszyny",
                "ZZ": "Powiąż z modułem Magazyn → Zamówienia",
            }

        defaults_cfg = orders_cfg.get("defaults")
        if isinstance(defaults_cfg, dict):
            defaults = {
                str(k): str(v) if not isinstance(v, (int, float)) else str(v)
                for k, v in defaults_cfg.items()
            }
        else:
            defaults = {}
        defaults.setdefault("author", "zalogowany_uzytkownik")
        defaults.setdefault("status", "nowe")
        defaults.setdefault("id_width", str(id_width))

        grp_count = 0
        fld_count = 0

        group = self._add_group(
            parent,
            "Definicje typów zleceń (ZW/ZN/ZM/ZZ)",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group,
            "enabled_types",
            "Typy aktywne",
            field_type="list",
            default=enabled_types,
            description=(
                "Lista aktywnych typów zleceń. Dostępne: ZW (wewnętrzne), "
                "ZN (na narzędzie), ZM (maszyny), ZZ (zakup). Podaj jeden kod w "
                "wierszu."
            ),
        )
        fld_count += 1
        self._add_field(
            group,
            "prefixes",
            "Prefiksy ID",
            field_type="dict",
            default=prefixes,
            description=(
                "Prefiks używany w numeracji zleceń (np. ZW- lub ZN-). Wpisuj "
                "w formacie `ZW = ZW-`."
            ),
        )
        fld_count += 1
        self._add_field(
            group,
            "id_width",
            "Szerokość ID",
            field_type="int",
            default=id_width,
            description="Ile cyfr ma mieć numer zlecenia. Np. 4 = ZW-0001.",
        )
        fld_count += 1

        group_status = self._add_group(
            parent,
            "Statusy i kolory",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group_status,
            "statuses",
            "Lista statusów",
            field_type="nested_list",
            default=statuses_map,
            description=(
                "Definicje statusów dla poszczególnych typów zleceń. Każdy wiersz "
                "w formacie `ZW: nowe, w przygotowaniu, w realizacji`."
            ),
        )
        fld_count += 1
        self._add_field(
            group_status,
            "colors",
            "Kolory statusów",
            field_type="dict",
            default=colors,
            description=(
                "Kolor przypisany do statusu. Przykład: `w realizacji = #F1C40F`, "
                "`awaria = blink_red`."
            ),
        )
        fld_count += 1

        group_tasks = self._add_group(
            parent,
            "Czynności technologiczne",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group_tasks,
            "tasks",
            "Lista czynności",
            field_type="list",
            default=tasks,
            description=(
                "Standardowe czynności technologiczne przypisywane do statusów "
                "(np. Sprawdź magazyn, Zarezerwuj półprodukty). Jeden wpis na "
                "wiersz."
            ),
        )
        fld_count += 1

        group_alerts = self._add_group(
            parent,
            "Progi alertów (%)",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group_alerts,
            "alerts",
            "Alerty dla typów",
            field_type="dict_float",
            default=alerts,
            description=(
                "Próg procentowy poniżej którego system zgłasza alert (osobno "
                "dla ZW, ZN, ZM, ZZ). Format: `ZW = 75`."
            ),
        )
        fld_count += 1

        group_links = self._add_group(
            parent,
            "Powiązania modułowe",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group_links,
            "links",
            "Powiązania",
            field_type="dict",
            default=links,
            description=(
                "Powiązania z innymi modułami: ZN → narzędzia SN (500–1000), "
                "ZM → maszyny, ZZ → magazyn (zamówienia)."
            ),
        )
        fld_count += 1

        group_defaults = self._add_group(
            parent,
            "Domyślne wartości",
            namespace="_orders",
        )
        grp_count += 1
        self._add_field(
            group_defaults,
            "defaults",
            "Ustawienia domyślne",
            field_type="dict",
            default=defaults,
            description=(
                "Domyślny autor = zalogowany użytkownik, domyślny status = nowe, "
                "szerokość ID = 4 cyfry. Możesz rozszerzyć o inne pola np. "
                "`priority = normal`."
            ),
        )
        fld_count += 1

        return grp_count, fld_count

    def _apply_orders_config(self, values: dict[str, Any]) -> None:
        """Persist composite Orders settings based on manual fields."""

        orders_cfg_raw = self.cfg.get("orders", {})
        orders_cfg = orders_cfg_raw if isinstance(orders_cfg_raw, dict) else {}
        orders_cfg = copy.deepcopy(orders_cfg)

        types_raw = orders_cfg.get("types", {})
        types_cfg: dict[str, dict[str, Any]] = {}
        if isinstance(types_raw, dict):
            for code, data in types_raw.items():
                if isinstance(data, dict):
                    types_cfg[code] = copy.deepcopy(data)
                else:
                    types_cfg[code] = {}

        for code, defaults in DEFAULT_ORDER_TYPES.items():
            base = types_cfg.setdefault(code, copy.deepcopy(defaults))
            if not isinstance(base, dict):
                base = copy.deepcopy(defaults)
                types_cfg[code] = base
            base.setdefault("label", defaults.get("label", code))
            base.setdefault("prefix", defaults.get("prefix", f"{code}-"))
            base.setdefault("statuses", list(defaults.get("statuses", ["nowe"])))
            base.setdefault("enabled", bool(defaults.get("enabled", True)))

        def ensure_type_entry(code: str) -> dict[str, Any]:
            norm = code.strip().upper()
            if not norm:
                return {}
            entry = types_cfg.get(norm)
            if not isinstance(entry, dict):
                defaults = DEFAULT_ORDER_TYPES.get(norm, {})
                entry = copy.deepcopy(defaults) if isinstance(defaults, dict) else {}
                entry.setdefault("label", defaults.get("label", norm) if isinstance(defaults, dict) else norm)
                entry.setdefault("prefix", defaults.get("prefix", f"{norm}-") if isinstance(defaults, dict) else f"{norm}-")
                entry.setdefault(
                    "statuses",
                    list(defaults.get("statuses", ["nowe"]))
                    if isinstance(defaults, dict)
                    else ["nowe"],
                )
                entry.setdefault("enabled", True)
                types_cfg[norm] = entry
            return entry

        if "prefixes" in values:
            prefixes: dict[str, Any] = values.get("prefixes", {}) or {}
            for code, prefix in prefixes.items():
                entry = ensure_type_entry(str(code))
                prefix_str = str(prefix).strip()
                if prefix_str:
                    entry["prefix"] = prefix_str

        if "statuses" in values:
            statuses_val: dict[str, list[str]] = values.get("statuses", {}) or {}
            for code, statuses in statuses_val.items():
                entry = ensure_type_entry(str(code))
                cleaned = [
                    str(item).strip()
                    for item in statuses
                    if isinstance(item, str) and str(item).strip()
                ]
                if cleaned:
                    entry["statuses"] = cleaned

        if "enabled_types" in values:
            enabled = {
                str(code).strip().upper()
                for code in values.get("enabled_types", [])
                if str(code).strip()
            }
            for code in list(types_cfg.keys()):
                types_cfg[code]["enabled"] = code in enabled if code else False
            for code in enabled:
                ensure_type_entry(code)["enabled"] = True

        if "id_width" in values:
            try:
                orders_cfg["id_width"] = max(1, int(values["id_width"]))
            except (TypeError, ValueError):
                pass

        if "colors" in values:
            colors_src: dict[str, Any] = values.get("colors", {}) or {}
            colors: dict[str, str] = {}
            for key, val in colors_src.items():
                key_str = str(key).strip()
                val_str = str(val).strip()
                if key_str and val_str:
                    colors[key_str] = val_str
            orders_cfg["status_colors"] = colors

        if "tasks" in values:
            tasks_raw = values.get("tasks", []) or []
            tasks_list = [
                str(item).strip()
                for item in tasks_raw
                if isinstance(item, str) and str(item).strip()
            ]
            orders_cfg["tasks"] = tasks_list

        if "alerts" in values:
            alerts_src: dict[str, Any] = values.get("alerts", {}) or {}
            alerts_dict: dict[str, float] = {}
            for key, val in alerts_src.items():
                key_str = str(key).strip().upper()
                if not key_str:
                    continue
                try:
                    alerts_dict[key_str] = float(val)
                except (TypeError, ValueError):
                    continue
            orders_cfg["alert_thresholds_pct"] = alerts_dict

        if "links" in values:
            links_src: dict[str, Any] = values.get("links", {}) or {}
            links_dict: dict[str, str] = {}
            for key, val in links_src.items():
                key_str = str(key).strip()
                val_str = str(val).strip()
                if key_str and val_str:
                    links_dict[key_str] = val_str
            orders_cfg["module_links"] = links_dict

        if "defaults" in values:
            defaults_src: dict[str, Any] = values.get("defaults", {}) or {}
            defaults_dict: dict[str, str] = {}
            for key, val in defaults_src.items():
                key_str = str(key).strip()
                if not key_str:
                    continue
                defaults_dict[key_str] = str(val).strip()
            if "id_width" in values and "id_width" not in defaults_dict:
                defaults_dict["id_width"] = str(values["id_width"])
            orders_cfg["defaults"] = defaults_dict
        elif "id_width" in values:
            defaults_existing = orders_cfg.get("defaults")
            if isinstance(defaults_existing, dict):
                defaults_dict = dict(defaults_existing)
            else:
                defaults_dict = {}
            defaults_dict.setdefault("id_width", str(values["id_width"]))
            orders_cfg["defaults"] = defaults_dict

        orders_cfg["types"] = types_cfg
        self.cfg.set("orders", orders_cfg)

    def _build_tools_tab(
        self, parent: tk.Widget, tab: dict[str, Any]
    ) -> tuple[int, int]:
        """Custom layout for the Tools tab with preview tree."""

        print(
            "[INFO][WM-DBG] Buduję zakładkę: Ustawienia → Narzędzia (UI-only patch)"
        )
        field_defs: dict[str, dict[str, Any]] = {}
        for group in tab.get("groups", []):
            if _is_deprecated(group):
                continue
            for field_def in group.get("fields", []):
                if _is_deprecated(field_def):
                    continue
                key = field_def.get("key")
                if key:
                    field_defs[key] = field_def

        grp_count = 0
        fld_count = 0

        # === Kolekcje narzędzi ===
        collections_group = ttk.LabelFrame(parent, text="Kolekcje narzędzi")
        collections_group.pack(fill="x", padx=10, pady=(10, 6))
        grp_count += 1
        collections_group.grid_columnconfigure(1, weight=1)

        ttk.Label(
            collections_group,
            text="Włączone kolekcje (NN, SN):",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        collections_var = CSVListVar(master=collections_group)
        collections_value = self.cfg.get(
            "tools.collections_enabled",
            field_defs.get("tools.collections_enabled", {}).get("default", []),
        )
        collections_var.set(collections_value or [])
        self.entry_tools_collections_enabled = ttk.Entry(
            collections_group, width=40, textvariable=collections_var
        )
        self.entry_tools_collections_enabled.grid(
            row=0, column=1, sticky="we", padx=8, pady=6
        )
        fld_count += 1
        self._register_option_var(
            "tools.collections_enabled",
            collections_var,
            field_defs.get("tools.collections_enabled"),
        )

        default_values = ["NN", "SN"]
        for item in collections_var.get():
            if item not in default_values:
                default_values.append(item)

        ttk.Label(collections_group, text="Domyślna kolekcja:").grid(
            row=1, column=0, sticky="w", padx=8, pady=6
        )
        default_field = field_defs.get("tools.default_collection")
        default_value = self.cfg.get(
            "tools.default_collection",
            default_field.get("default") if default_field else None,
        )
        if not isinstance(default_value, str):
            default_value = str(default_value or "")
        if default_value and default_value not in default_values:
            default_values.append(default_value)
        if not default_value and default_values:
            default_value = default_values[0]
        state = "readonly" if default_values else "normal"
        default_var = tk.StringVar(value=default_value)
        self.combo_tools_default_collection = ttk.Combobox(
            collections_group,
            width=20,
            textvariable=default_var,
            values=default_values,
            state=state,
        )
        self.combo_tools_default_collection.grid(
            row=1, column=1, sticky="w", padx=8, pady=6
        )
        fld_count += 1
        self._register_option_var(
            "tools.default_collection", default_var, default_field
        )

        # === Statusy globalne ===
        global_group = ttk.LabelFrame(parent, text="Statusy globalne (zakończenia)")
        global_group.pack(fill="x", padx=10, pady=6)
        grp_count += 1

        ttk.Label(
            global_group,
            text=(
                "Lista statusów traktowanych jako globalne zakończenia "
                "(np. sprawne, zakończone):"
            ),
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        statuses_var = CSVListVar(master=global_group)
        statuses_value = self.cfg.get(
            "tools.auto_check_on_status_global",
            field_defs.get("tools.auto_check_on_status_global", {}).get(
                "default", []
            ),
        )
        statuses_var.set(statuses_value or [])
        self.entry_tools_global_statuses = ttk.Entry(
            global_group, width=60, textvariable=statuses_var
        )
        self.entry_tools_global_statuses.grid(
            row=1, column=0, sticky="we", padx=8, pady=(0, 8)
        )
        global_group.grid_columnconfigure(0, weight=1)
        fld_count += 1
        self._register_option_var(
            "tools.auto_check_on_status_global",
            statuses_var,
            field_defs.get("tools.auto_check_on_status_global"),
        )

        # === Podgląd definicji ===
        preview_group = ttk.LabelFrame(
            parent, text="Podgląd definicji NN/SN (tylko do odczytu)"
        )
        preview_group.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        grp_count += 1

        self.tools_preview_tree = ttk.Treeview(
            preview_group,
            columns=("info",),
            show="tree headings",
            selectmode="browse",
            height=14,
        )
        self.tools_preview_tree.heading("#0", text="Struktura")
        self.tools_preview_tree.heading("info", text="Info")
        self.tools_preview_tree.column("#0", width=420, stretch=True)
        self.tools_preview_tree.column("info", width=180, stretch=False)
        self.tools_preview_tree.pack(fill="both", expand=True, padx=8, pady=8)

        counters_frame = ttk.Frame(preview_group)
        counters_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.lbl_counter_types = ttk.Label(counters_frame, text="Typy: 0")
        self.lbl_counter_statuses = ttk.Label(counters_frame, text="Statusy: 0")
        self.lbl_counter_tasks = ttk.Label(counters_frame, text="Zadania: 0")
        self.lbl_counter_types.pack(side="left", padx=(0, 16))
        self.lbl_counter_statuses.pack(side="left", padx=(0, 16))
        self.lbl_counter_tasks.pack(side="left")

        btns = ttk.Frame(preview_group)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        self.btn_open_tools_def_editor = ttk.Button(
            btns,
            text="Otwórz edytor definicji zadań…",
            command=self._open_tools_definitions_editor,
        )
        self.btn_open_tools_def_editor.pack(side="left")

        self._tools_paths_hidden = True

        self._refresh_tools_def_preview()

        return grp_count, fld_count

    def _open_tools_definitions_editor(self) -> None:
        try:
            self._open_tools_config()
        except Exception as exc:
            print("[INFO] Edytor definicji zadań niedostępny w tej wersji UI:", exc)

    def _refresh_tools_def_preview(self) -> None:
        """Build read-only tree with NN/SN definitions summary."""

        print("[WM-DBG] Odświeżam podgląd definicji NN/SN (read-only)")
        tree = getattr(self, "tools_preview_tree", None)
        if tree is None:
            return

        for item in tree.get_children():
            tree.delete(item)

        # --- helpers: zgodność PL/EN i różne kształty ---
        def _pick(dct: Any, *names: str) -> Any:
            if isinstance(dct, dict):
                for name in names:
                    if name in dct:
                        return dct[name]
            return None

        def _as_dict(
            obj: Any,
            key_name_for_items: str = "name",
            alt_key_name: str = "nazwa",
        ) -> dict[str, Any]:
            """Return mapping created from list of dicts or existing dict."""

            if isinstance(obj, dict):
                return obj
            if isinstance(obj, list):
                result: dict[str, Any] = {}
                for item in obj:
                    if isinstance(item, dict):
                        key = (
                            item.get(key_name_for_items)
                            or item.get(alt_key_name)
                            or item.get("key")
                            or item.get("id")
                        )
                        if key is None:
                            key = f"poz_{len(result) + 1}"
                        result[str(key)] = item
                    elif isinstance(item, str):
                        result[str(item)] = {}
                return result
            return {}

        def _extract_tasks(val: Any) -> list[str]:
            """Return list of tasks supporting PL/EN keys and plain lists."""

            if isinstance(val, list):
                return [str(x) for x in val]
            if isinstance(val, dict):
                tasks = _pick(val, "tasks", "zadania")
                if isinstance(tasks, list):
                    return [str(x) for x in tasks]
            return []

        definitions: dict[str, Any] | None = None
        definitions_path: str | None = None
        try:
            definitions_path = self.cfg.get("tools.definitions_path")
        except Exception:
            definitions_path = None
        if not definitions_path:
            definitions_path = "data/zadania_narzedzia.json"

        if definitions_path and os.path.exists(definitions_path):
            try:
                with open(definitions_path, "r", encoding="utf-8") as f:
                    definitions = json.load(f)
                    print(
                        f"[INFO] Wczytano definicje z pliku: {definitions_path}"
                    )
            except Exception as exc:
                print("[ERROR] Nie udało się wczytać definicji z pliku:", exc)

        if definitions is None and hasattr(self, "tools_definitions"):
            definitions = getattr(self, "tools_definitions")  # type: ignore[attr-defined]
            print("[INFO] Używam definicji z pamięci (self.tools_definitions)")

        lbl_types = getattr(self, "lbl_counter_types", None)
        lbl_statuses = getattr(self, "lbl_counter_statuses", None)
        lbl_tasks = getattr(self, "lbl_counter_tasks", None)

        if not isinstance(definitions, dict):
            print(
                "[WM-DBG] Brak definicji lub niepoprawny format. Podgląd będzie pusty."
            )
            if lbl_types:
                lbl_types.config(text="Typy: 0")
            if lbl_statuses:
                lbl_statuses.config(text="Statusy: 0")
            if lbl_tasks:
                lbl_tasks.config(text="Zadania: 0")
            return

        # Zgodność PL/EN: collections/kolekcje → types/typy → statuses/statusy → tasks/zadania
        collections = _pick(definitions, "collections", "kolekcje") or {}
        collections_dict = _as_dict(collections)

        total_types = 0
        total_statuses = 0
        total_tasks = 0

        for coll_key, coll_val in collections_dict.items():
            coll_id = tree.insert(
                "",
                "end",
                text=str(coll_key),
                values=("kolekcja",),
            )
            types = _pick(coll_val, "types", "typy") or {}
            types_dict = _as_dict(types)

            for type_name, type_val in types_dict.items():
                statuses = _pick(type_val, "statuses", "statusy") or {}
                statuses_dict = _as_dict(statuses)

                status_count = 0
                task_count = 0
                type_id = tree.insert(
                    coll_id,
                    "end",
                    text=f"• {type_name}",
                    values=("typ",),
                )

                for status_name, status_val in statuses_dict.items():
                    status_count += 1
                    tasks = _extract_tasks(status_val)
                    task_count += len(tasks)
                    status_id = tree.insert(
                        type_id,
                        "end",
                        text=f"- {status_name}",
                        values=(f"{len(tasks)}",),
                    )
                    for task in tasks:
                        tree.insert(
                            status_id,
                            "end",
                            text=f"· {task}",
                            values=("zadanie",),
                        )

                tree.item(
                    type_id,
                    values=(f"{status_count} status., {task_count} zadań",),
                )
                total_types += 1
                total_statuses += status_count
                total_tasks += task_count

        if lbl_types:
            lbl_types.config(text=f"Typy: {total_types}")
        if lbl_statuses:
            lbl_statuses.config(text=f"Statusy: {total_statuses}")
        if lbl_tasks:
            lbl_tasks.config(text=f"Zadania: {total_tasks}")
        print(
            "[WM-DBG] Podgląd OK: "
            f"typy={total_types}, statusy={total_statuses}, zadania={total_tasks} "
            f"(plik: {definitions_path})"
        )

    def _open_tools_config(self) -> None:
        """Otwiera alias ``gui_tools_config`` (advanced lub fallback JSON)."""

        if ToolsConfigDialog is None:
            messagebox.showerror(
                "Błąd",
                "Moduł edytora narzędzi jest niedostępny.",
            )
            return

        if not hasattr(self, "_open_windows"):
            self._open_windows = {}

        try:
            existing = self._open_windows.get("tools_config")
            if existing is not None and existing.winfo_exists():
                try:
                    existing.attributes("-topmost", True)
                except Exception:
                    pass
                try:
                    existing.lift()
                    existing.focus_force()
                except Exception:
                    pass
                return
        except Exception:
            pass

        path = self._get_tools_config_path()
        try:
            # master=None, żeby uniknąć błędu
            # "SettingsWindow object has no attribute 'tk'"
            dlg = ToolsConfigDialog(
                master=None, path=path, on_save=self._on_tools_config_saved
            )
        except Exception as exc:
            # Pokaż dokładny błąd – łatwiej debugować.
            messagebox.showerror(
                "Błąd",
                (
                    "Nie udało się otworzyć edytora narzędzi:\n"
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return

        self._open_windows["tools_config"] = dlg

        def _cleanup(*_args: object) -> None:
            if self._open_windows.get("tools_config") is dlg:
                self._open_windows.pop("tools_config", None)

        try:
            dlg.bind("<Destroy>", _cleanup, add="+")
        except Exception:
            pass

        try:
            dlg.attributes("-topmost", True)
            dlg.lift()
            dlg.focus_force()
        except Exception:
            pass

        try:
            print("[WM-DBG][SETTINGS] Tools editor opened (advanced).")
            messagebox.showinfo(
                "Edytor narzędzi",
                "Otworzono edytor definicji zadań (wersja advanced).",
            )
        except Exception:
            pass

        def _fallback_topmost(win: tk.Misc) -> None:
            try:
                win.transient(self)
                win.grab_set()
                win.lift()
            except Exception:
                pass

        # A-2g: preferujemy nowe API helpera, ale obsłuż oba warianty.
        try:
            _ensure_topmost(dlg, self)
        except TypeError:
            try:
                _ensure_topmost(dlg)
            except Exception:
                _fallback_topmost(dlg)
        except Exception:
            _fallback_topmost(dlg)

        try:
            self.wait_window(dlg)
        except Exception as exc:  # pragma: no cover - wait_window error handling
            log_akcja(f"[SETTINGS] ToolsConfigDialog wait failed: {exc}")
        finally:
            _cleanup()

    def _get_tools_config_path(self) -> str:
        """Ścieżka do definicji typów/statusów narzędzi (NN/SN)."""

        try:
            cfg = getattr(self, "cfg", None)
            if cfg is not None:
                path = cfg.get("tools.definitions_path", None)  # type: ignore[attr-defined]
                if isinstance(path, str) and path.strip():
                    return path
        except Exception:
            pass
        return os.path.join("data", "zadania_narzedzia.json")

    def _on_tools_config_saved(self) -> None:
        """Callback po zapisie konfiguracji narzędzi."""

        invalidate = getattr(LZ, "invalidate_cache", None)
        if callable(invalidate):
            try:
                invalidate()
            except Exception:
                pass
        try:
            self._reload_tools_section()
        except Exception:
            pass

    def _reload_tools_section(self) -> None:
        """Odświeża sekcję Narzędzia po zmianie definicji."""

        try:
            self.refresh_panel()
        except Exception:
            pass

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

    def _load_magazyn_dicts(self) -> dict[str, list[str]]:
        try:
            with open(MAG_DICT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {
                        k: [str(v) for v in data.get(k, [])]
                        for k in ("kategorie", "typy_materialu", "jednostki")
                    }
        except Exception:
            pass
        return {"kategorie": [], "typy_materialu": [], "jednostki": []}

    def _save_magazyn_dicts(self, data: dict[str, list[str]]) -> None:
        os.makedirs(os.path.dirname(MAG_DICT_PATH), exist_ok=True)
        with open(MAG_DICT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _build_slowniki_tab(self, parent: tk.Widget) -> None:
        data = self._load_magazyn_dicts()
        editors: list[tuple[str, tk.Listbox]] = []

        def make_editor(key: str, label: str) -> None:
            frame = ttk.LabelFrame(parent, text=label)
            frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

            lb = tk.Listbox(frame, height=8, exportselection=False)
            for item in data.get(key, []):
                lb.insert("end", item)
            lb.pack(fill="both", expand=True, padx=5, pady=5)
            _bind_tooltip(lb, f"Lista: {label.lower()}")

            entry = ttk.Entry(frame)
            entry.pack(fill="x", padx=5, pady=(0, 5))

            btns = ttk.Frame(frame)
            btns.pack(pady=2)

            def add_item() -> None:
                val = entry.get().strip()
                if val:
                    lb.insert("end", val)
                    entry.delete(0, "end")

            def del_item() -> None:
                for idx in reversed(lb.curselection()):
                    lb.delete(idx)

            def move_up() -> None:
                sel = lb.curselection()
                if not sel:
                    return
                idx = sel[0]
                if idx <= 0:
                    return
                val = lb.get(idx)
                lb.delete(idx)
                lb.insert(idx - 1, val)
                lb.selection_set(idx - 1)

            def move_down() -> None:
                sel = lb.curselection()
                if not sel:
                    return
                idx = sel[0]
                if idx >= lb.size() - 1:
                    return
                val = lb.get(idx)
                lb.delete(idx)
                lb.insert(idx + 1, val)
                lb.selection_set(idx + 1)

            b_add = ttk.Button(btns, text="Dodaj", command=add_item)
            b_del = ttk.Button(btns, text="Usuń", command=del_item)
            b_up = ttk.Button(btns, text="Góra", command=move_up)
            b_down = ttk.Button(btns, text="Dół", command=move_down)
            b_add.grid(row=0, column=0, padx=2)
            b_del.grid(row=0, column=1, padx=2)
            b_up.grid(row=0, column=2, padx=2)
            b_down.grid(row=0, column=3, padx=2)
            _bind_tooltip(b_add, "Dodaj wpis do listy")
            _bind_tooltip(b_del, "Usuń zaznaczony wpis")
            _bind_tooltip(b_up, "Przesuń w górę")
            _bind_tooltip(b_down, "Przesuń w dół")

            editors.append((key, lb))

        make_editor("kategorie", "Kategorie")
        make_editor("typy_materialu", "Typy materiału")
        make_editor("jednostki", "Jednostki")

        def save_all_dicts() -> None:
            payload = {key: list(lb.get(0, "end")) for key, lb in editors}
            self._save_magazyn_dicts(payload)

        btn_save = ttk.Button(parent, text="Zapisz", command=save_all_dicts)
        btn_save.pack(anchor="e", padx=5, pady=5)
        _bind_tooltip(btn_save, "Zapisz słowniki")

    def _init_magazyn_tab(self) -> None:
        """Create subtabs for the 'magazyn' section on first use."""
        if self._magazyn_frame is None or self._magazyn_schema is None:
            return
        nb = ttk.Notebook(self._magazyn_frame)
        nb.pack(fill="both", expand=True)
        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        ustawienia_frame = ttk.Frame(nb)
        nb.add(ustawienia_frame, text="Ustawienia magazynu")
        print("[WM-DBG] init magazyn tab")
        self._populate_tab(ustawienia_frame, self._magazyn_schema)

        slowniki_frame = ttk.Frame(nb)
        nb.add(slowniki_frame, text="Słowniki")
        self._build_slowniki_tab(slowniki_frame)

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
        for var, opt in self._fields_vars:
            default = opt.get("default")
            try:
                value = self._coerce_default_for_var(opt, default)
                var.set(value)
            except Exception:
                if opt.get("type") == "bool":
                    var.set(str(bool(default)))

    def on_close(self) -> None:
        changed = any(var.get() != self._initial[key] for key, var in self.vars.items())
        if changed:
            if messagebox.askyesno("Zapisz", "Czy zapisać zmiany?", parent=self.master):
                self.save()
        self.master.winfo_toplevel().destroy()

    def _load_user_modules(self, user_id: str) -> None:
        user = profile_service.get_user(user_id) or {}
        disabled = {
            str(m).strip().lower()
            for m in user.get("disabled_modules", [])
            if m
        }
        for key, var in self._mod_vars.items():
            var.set(key not in disabled)

    def _save_user_modules(self, user_id: str) -> list[str]:
        if not user_id:
            return []
        user = profile_service.get_user(user_id) or {"login": user_id}
        disabled = [k for k, v in self._mod_vars.items() if not v.get()]
        user["disabled_modules"] = disabled
        profile_service.save_user(user)
        return disabled

    def _apply_user_modules(self) -> None:
        if self._user_var is None:
            return
        uid = self._user_var.get().strip()
        if not uid:
            return
        disabled = self._save_user_modules(uid)
        try:
            root = self.master.winfo_toplevel().master
            root.event_generate("<<SidebarReload>>", when="tail")
        except Exception:
            pass
        log_akcja(f"[SETTINGS] zastosowano moduły {uid}: {', '.join(disabled)}")

    def save(self) -> None:
        special_orders: dict[str, Any] = {}
        for key, var in self.vars.items():
            if key.startswith("_orders."):
                name = key.split(".", 1)[1]
                special_orders[name] = var.get()
                continue
            opt = self._options.get(key, {})
            value = var.get()
            if opt.get("type") == "bool" and isinstance(value, str):
                if value in {"0", "1"}:
                    value = value == "1"
            if opt.get("type") == "enum":
                allowed = (
                    opt.get("allowed")
                    or opt.get("enum")
                    or opt.get("values")
                    or []
                )
                if allowed and value not in allowed:
                    value = allowed[0]
            self.cfg.set(key, value)
            self._initial[key] = value
        if special_orders:
            self._apply_orders_config(special_orders)
            for name, value in special_orders.items():
                self._initial[f"_orders.{name}"] = value
        self.cfg.save_all()
        self._unsaved = False
        if self._user_var is not None:
            uid = self._user_var.get().strip()
            if uid:
                disabled = self._save_user_modules(uid)
                log_akcja(
                    f"[SETTINGS] zapisano moduły {uid}: {', '.join(disabled)}"
                )

    def refresh_panel(self) -> None:
        """Reload configuration and rebuild widgets."""

        self.cfg = ConfigManager.refresh(
            config_path=self.config_path, schema_path=self.schema_path
        )
        self.vars.clear()
        self._initial.clear()
        self._defaults.clear()
        self._options.clear()
        self._fields_vars.clear()
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
        self._init_audit_tab()
        self._reorder_tabs()

    def _reorder_tabs(self) -> None:
        """Place the audit tab before the products tab."""

        tabs = {self.nb.tab(t, "text"): t for t in self.nb.tabs()}
        audit_id = tabs.get("Audyt")
        products_id = tabs.get("Produkty i materiały")
        if audit_id and products_id:
            index = self.nb.index(products_id)
            self.nb.insert(index, audit_id)

    def _init_audit_tab(self) -> None:
        """Create the Audit tab with controls."""

        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="Audyt")
        btn = ttk.Button(frame, text="Uruchom audyt", command=self._run_audit_now)
        btn.pack(anchor="w", padx=5, pady=5)
        txt = tk.Text(frame, height=15)
        txt.pack(fill="both", expand=True, padx=5, pady=5)
        self.btn_audit_run = btn
        self.txt_audit = txt

    def _append_audit_out(self, s: str) -> None:
        try:
            self.txt_audit.insert("end", s)
            self.txt_audit.see("end")
        except Exception:
            pass

    def _run_audit_now(self) -> None:
        try:
            self.btn_audit_run.config(state="disabled")
        except Exception:
            pass
        self._append_audit_out("\n[INFO] Uruchamiam audyt...\n")

        def _worker() -> None:
            try:
                import wm_audit_runtime

                result = wm_audit_runtime.run_audit()
                path = "audit_wm_report.txt"
                with open(path, "w", encoding="utf-8") as f:
                    f.write(result)
                msg = result + f"\n[INFO] Raport zapisano do {path}\n"
                self.txt_audit.after(0, self._append_audit_out, msg)
            except Exception as exc:
                self.txt_audit.after(
                    0, self._append_audit_out, f"[ERROR] {exc!r}\n"
                )
            finally:
                try:
                    self.btn_audit_run.after(
                        0, lambda: self.btn_audit_run.config(state="normal")
                    )
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _append_tests_out(self, s: str):
        try:
            self.txt_tests.insert("end", s)
            self.txt_tests.see("end")
        except Exception:
            pass

    def _run_all_tests(self):
        try:
            self.btn_tests_run.config(state="disabled")
        except Exception:
            pass
        self._append_tests_out("\n[INFO] Uruchamiam: pytest -q\n")
        print("[WM-DBG][SETTINGS][TESTS] start")

        def _worker():
            try:
                cmd = [sys.executable, "-m", "pytest", "-q"]
                proc = subprocess.Popen(
                    cmd,
                    cwd=os.getcwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    self.txt_tests.after(0, self._append_tests_out, line)
                ret = proc.wait()
                self.txt_tests.after(
                    0, self._append_tests_out, f"\n[INFO] Zakończono: kod wyjścia = {ret}\n"
                )
                print(f"[WM-DBG][SETTINGS][TESTS] finished ret={ret}")
            except FileNotFoundError:
                self.txt_tests.after(
                    0,
                    self._append_tests_out,
                    "\n[ERROR] Nie znaleziono pytest. Zainstaluj: pip install pytest\n",
                )
                print("[WM-DBG][SETTINGS][TESTS] pytest not found")
            except Exception as e:
                self.txt_tests.after(
                    0, self._append_tests_out, f"\n[ERROR] Błąd uruchamiania testów: {e!r}\n"
                )
                print(f"[WM-DBG][SETTINGS][TESTS] error: {e!r}")
            finally:
                try:
                    self.btn_tests_run.after(0, lambda: self.btn_tests_run.config(state="normal"))
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _install_pytest(self):
        try:
            self.btn_install_pytest.config(state="disabled")
        except Exception:
            pass
        self._append_tests_out(
            "\n[INFO] Uruchamiam: python -m pip install -U pytest\n"
        )
        print("[WM-DBG][SETTINGS][TESTS] install start")

        def _worker():
            try:
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-U",
                    "pytest",
                ]
                proc = subprocess.Popen(
                    cmd,
                    cwd=os.getcwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    self.txt_tests.after(0, self._append_tests_out, line)
                ret = proc.wait()
                self.txt_tests.after(
                    0, self._append_tests_out, f"\n[INFO] Zakończono: kod wyjścia = {ret}\n"
                )
                print(f"[WM-DBG][SETTINGS][TESTS] install finished ret={ret}")
            except Exception as e:
                self.txt_tests.after(
                    0,
                    self._append_tests_out,
                    f"\n[ERROR] Błąd instalacji pytest: {e!r}\n",
                )
                print(f"[WM-DBG][SETTINGS][TESTS] install error: {e!r}")
            finally:
                try:
                    self.btn_install_pytest.after(
                        0, lambda: self.btn_install_pytest.config(state="normal")
                    )
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia")
    SettingsPanel(root)
    root.mainloop()

# ⏹ KONIEC KODU
