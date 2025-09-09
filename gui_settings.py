# Wersja pliku: 1.5.7
# Moduł: gui_settings
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import json
import subprocess
import tkinter as tk
from pathlib import Path
from typing import Any, Dict
from tkinter import colorchooser, filedialog, messagebox, ttk

import config_manager as cm
from config_manager import ConfigManager
from gui_products import ProductsMaterialsTab


def _git_state() -> tuple[bool, int, int]:
    """Return (dirty, ahead, behind) for current git repo."""
    dirty = False
    ahead = behind = 0
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        dirty = bool(out.stdout.strip())
        out = subprocess.run(
            [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                "origin/Rozwiniecie...HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0:
            behind, ahead = map(int, out.stdout.strip().split())
    except Exception:
        pass
    return dirty, ahead, behind


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
        enum_vals = option.get("enum") or option.get("values") or []
        print(f"[WM-DBG] enum values: {len(enum_vals)}")
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

    tip = option.get("help") or option.get("description")
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
            if tab.get("id") == "update":
                dirty, ahead, behind = _git_state()
                badges: list[str] = []
                if dirty:
                    badges.append("DIRTY")
                if ahead > 0:
                    badges.append(f"AHEAD: {ahead}")
                if behind > 0:
                    badges.append(f"BEHIND: {behind}")
                if badges:
                    title = f"{title} [{' '.join(badges)}]"
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
                if tab.get("id") == "update":
                    self._add_patch_group(frame)

        base_dir = Path(__file__).resolve().parent
        self.products_tab = ProductsMaterialsTab(self.nb, base_dir=base_dir)
        title = "Produkty i materiały"
        lock_path = base_dir / "data" / "magazyn" / "magazyn.json.lock"
        if lock_path.exists():
            title += " [LOCK]"
            print("[WM-DBG][SETTINGS][PIM] LOCK wykryty")
        self.nb.add(self.products_tab, text=title)
        # [WM-DBG] dodaj zakładkę "Patche"
        try:
            self._add_patch_manager_tab(base_dir)
        except Exception as _e:  # pragma: no cover - debug output
            print("[WM-DBG] [PATCH] pominieto zakladke Patche:", _e)
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
            grp_count += 1
            grp_frame = ttk.LabelFrame(parent, text=group.get("label", ""))
            grp_frame.pack(fill="both", expand=True, padx=5, pady=5)
            if tip := group.get("tooltip"):
                _bind_tooltip(grp_frame, tip)
            inner = ttk.Frame(grp_frame)
            inner.pack(fill="both", expand=True, padx=8, pady=6)

            for field_def in group.get("fields", []):
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

        return grp_count, fld_count

    def _add_patch_group(self, parent: tk.Widget) -> None:
        from tools import patcher

        grp = ttk.LabelFrame(parent, text="Paczowanie i wersje")
        grp.pack(fill="x", padx=5, pady=5)
        inner = ttk.Frame(grp)
        inner.pack(fill="x", padx=5, pady=5)

        def choose_patch(dry_run: bool) -> None:
            path = filedialog.askopenfilename(
                title="Wybierz patch",
                filetypes=[("WM patch", "*.wmpatch"), ("Patch", "*.patch"), ("Wszystkie", "*.*")],
                initialdir=str(Path(__file__).resolve().parent / "patches"),
            )
            if path:
                patcher.apply_patch(path, dry_run=dry_run)

        ttk.Button(
            inner,
            text="Sprawdź patch (dry-run)",
            command=lambda: choose_patch(True),
        ).pack(side="left", padx=2)
        ttk.Button(
            inner,
            text="Zastosuj patch",
            command=lambda: choose_patch(False),
        ).pack(side="left", padx=2)

        commits = patcher.get_commits()
        commit_var = tk.StringVar(value=commits[0] if commits else "")
        cb = ttk.Combobox(
            inner, values=commits, textvariable=commit_var, width=40, state="readonly"
        )
        cb.pack(side="left", padx=2)
        ttk.Button(
            inner,
            text="Cofnij do wersji",
            command=lambda: patcher.rollback_to(commit_var.get()),
        ).pack(side="left", padx=2)

    def _init_magazyn_tab(self) -> None:
        """Create subtabs for the 'magazyn' section on first use."""
        if self._magazyn_frame is None or self._magazyn_schema is None:
            return
        nb = ttk.Notebook(self._magazyn_frame)
        nb.pack(fill="both", expand=True)

        ustawienia_frame = ttk.Frame(nb)
        nb.add(ustawienia_frame, text="Ustawienia magazynu")
        print("[WM-DBG][SETTINGS][Magazyn] buduję sekcję 'Ustawienia magazynu'")
        self._populate_tab(ustawienia_frame, self._magazyn_schema)

        self._magazyn_initialized = True

    def _add_patch_manager_tab(self, base_dir: Path) -> None:
        """Zakładka 'Patche' - skanowanie/zastosowanie patchy i przywracanie kopii."""
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
        import os
        import sys
        import subprocess
        import shutil

        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Patche")

        ttk.Label(
            tab, text="Folder patchy (*.wmpatch):"
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        patches_var = tk.StringVar(value=os.path.join(base_dir, "patches"))
        entry = ttk.Entry(tab, textvariable=patches_var, width=60)
        entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 2))

        def _open_dir() -> None:
            path = patches_var.get()
            if os.name == "nt":
                os.startfile(path)  # type: ignore[arg-type]
            else:
                subprocess.Popen(["xdg-open", path])

        ttk.Button(tab, text="Otwórz folder", command=_open_dir).grid(
            row=0, column=2, padx=8, pady=(8, 2)
        )

        out = scrolledtext.ScrolledText(
            tab, height=18, width=100, state="disabled"
        )
        out.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)

        btns = ttk.Frame(tab)
        btns.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        run_btn = ttk.Button(btns, text="Skanuj (Dry-run)")
        apply_btn = ttk.Button(btns, text="Zastosuj (Apply)")
        run_btn.pack(side="left", padx=(0, 8))
        apply_btn.pack(side="left")

        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)

        def _append(text: str) -> None:
            out.configure(state="normal")
            out.insert("end", text + "\n")
            out.see("end")
            out.configure(state="disabled")

        def _run_patcher(do_apply: bool) -> None:
            patch_dir = patches_var.get().strip()
            if not os.path.isdir(patch_dir):
                _append(f"[WM-DBG] [PATCH] brak katalogu: {patch_dir}")
                messagebox.showwarning(
                    "Brak katalogu", f"Nie znaleziono: {patch_dir}", parent=tab
                )
                return
            _append(f"[WM-DBG] [PATCH] base={base_dir}")
            _append(f"[WM-DBG] [PATCH] patches={patch_dir}")
            _append(
                f"[WM-DBG] [PATCH] mode={'APPLY' if do_apply else 'DRY-RUN'}"
            )
            try:
                try:
                    from tools import patcher as _patcher  # type: ignore
                except Exception:
                    _patcher = None
                if _patcher is not None:
                    results: list[dict[str, Any]] = []
                    for name in sorted(os.listdir(patch_dir)):
                        if not name.lower().endswith((".wmpatch", ".patch")):
                            continue
                        full = os.path.join(patch_dir, name)
                        res = _patcher.apply_patch(full, dry_run=not do_apply)
                        details = res.stdout.strip().splitlines()
                        results.append(
                            {
                                "file": name,
                                "changed": res.returncode == 0 and do_apply,
                                "details": details,
                            }
                        )
                    changed = [r for r in results if r["changed"]]
                    for r in results:
                        status = "CHANGED" if r["changed"] else "OK"
                        _append(f"- {r['file']}: {status}")
                        for d in r["details"]:
                            _append(f"    • {d}")
                    messagebox.showinfo(
                        "Patche",
                        f"Zastosowano {len(results)} plików, zmian: {len(changed)}",
                        parent=tab,
                    )
                else:
                    exe = sys.executable
                    cmd = [
                        exe,
                        os.path.join(base_dir, "wm_patcher.py"),
                        "--base",
                        base_dir,
                        "--patches",
                        patch_dir,
                    ]
                    if do_apply:
                        cmd.append("--apply")
                    _append("[WM-DBG] uruchamiam: " + " ".join(cmd))
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, cwd=base_dir
                    )
                    if proc.stdout:
                        for line in proc.stdout.splitlines():
                            _append(line)
                    if proc.stderr:
                        _append("[STDERR] " + proc.stderr.strip())
                    messagebox.showinfo(
                        "Patche",
                        f"Zakończono (rc={proc.returncode}). Szczegóły powyżej.",
                        parent=tab,
                    )
            except Exception as e:  # pragma: no cover - debug output
                _append(f"[WM-DBG] [ERROR] {e}")
                messagebox.showerror("Błąd patchera", str(e), parent=tab)

        run_btn.configure(command=lambda: _run_patcher(False))
        apply_btn.configure(command=lambda: _run_patcher(True))

        ttk.Separator(tab).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=4
        )
        ttk.Label(
            tab, text="Kopie patchy (backup/patches):"
        ).grid(row=4, column=0, sticky="w", padx=8)

        backups = ttk.Treeview(tab, columns=("files",), show="tree")
        backups.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=8, pady=(2, 8))

        def _refresh_backups() -> None:
            root_dir = os.path.join(base_dir, "backup", "patches")
            for item in backups.get_children():
                backups.delete(item)
            if not os.path.isdir(root_dir):
                _append(f"[WM-DBG] brak folderu kopii: {root_dir}")
                return
            for name in sorted(os.listdir(root_dir)):
                d = os.path.join(root_dir, name)
                if not os.path.isdir(d):
                    continue
                files = [
                    f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))
                ]
                node = backups.insert(
                    "", "end", iid=name, text=name, values=(len(files),)
                )
                for f in sorted(files):
                    backups.insert(node, "end", text=f)

        def _restore_selected() -> None:
            sel = backups.selection()
            if not sel:
                messagebox.showinfo(
                    "Przywracanie",
                    "Wybierz katalog kopii (timestamp).",
                    parent=tab,
                )
                return
            ts = sel[0]
            root_dir = os.path.join(base_dir, "backup", "patches", ts)
            if not os.path.isdir(root_dir):
                messagebox.showerror(
                    "Błąd", f"Brak katalogu: {root_dir}", parent=tab
                )
                return
            if not messagebox.askyesno(
                "Potwierdź", f"Przywrócić kopię: {ts}?", parent=tab
            ):
                return
            restored = 0
            skipped = 0
            for fname in os.listdir(root_dir):
                src = os.path.join(root_dir, fname)
                if not os.path.isfile(src):
                    continue
                dst = os.path.join(base_dir, fname)
                if not os.path.exists(dst):
                    hit = None
                    for dirpath, _, filenames in os.walk(base_dir):
                        if fname in filenames:
                            cand = os.path.join(dirpath, fname)
                            if hit is None:
                                hit = cand
                            else:
                                hit = None
                                break
                    if hit:
                        dst = hit
                try:
                    shutil.copy2(src, dst)
                    restored += 1
                    _append(f"[WM-DBG] [RESTORE] {fname} -> {dst}")
                except Exception as ex:  # pragma: no cover - debug output
                    skipped += 1
                    _append(f"[WM-DBG] [RESTORE] SKIP {fname}: {ex}")
            messagebox.showinfo(
                "Przywracanie",
                f"Przywrócono: {restored}, pominięto: {skipped}",
                parent=tab,
            )

        ctrl = ttk.Frame(tab)
        ctrl.grid(row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        ttk.Button(
            ctrl, text="Odśwież kopie", command=_refresh_backups
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            ctrl, text="Przywróć zaznaczoną kopię", command=_restore_selected
        ).pack(side="left")

        _refresh_backups()
        _append("[WM-DBG] [SETTINGS] zakładka Patche: OK")

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
