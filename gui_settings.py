# Wersja pliku: 1.5.8
# Moduł: gui_settings
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import datetime
import json
import os, sys, subprocess, threading
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog
from tkinter import ttk, messagebox

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
        self._fields_vars: list[tuple[tk.Variable, dict[str, Any]]] = []
        self._unsaved = False
        self._open_windows: dict[str, tk.Toplevel] = {}
        self._mod_vars: dict[str, tk.BooleanVar] = {}
        self._user_var: tk.StringVar | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create notebook tabs and widgets based on current schema."""

        self._unsaved = False
        self._fields_vars = []
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
        self._add_magazyn_tab()
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
                self._fields_vars.append((var, field_def))
                var.trace_add("write", lambda *_: setattr(self, "_unsaved", True))

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
        for key, var in self.vars.items():
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
