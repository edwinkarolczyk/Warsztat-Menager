# version: 1.0
# Moduł: narzedzia_ui.multistage_runtime
# Nowy edytor Narzędzi: opcjonalne powiązania wieloetapowe (maks. 6 etapów).
# Relacje są trzymane centralnie w data/narzedzia/powiazania_narzedzi.json.

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from . import editor_variant_runtime as _variant

_MAX_STAGES = 6
_REL_FILE = "powiazania_narzedzi.json"
_META_CACHE: dict[str, dict[str, Any]] | None = None


def _norm_nr(value: object) -> str:
    raw = str(value or "").strip()
    if raw.isdigit() and len(raw) <= 3:
        return raw.zfill(3)
    return raw


def _tools_dir() -> Path:
    try:
        import gui_narzedzia as tools_gui

        return Path(tools_gui._resolve_tools_dir())
    except Exception:
        return Path("data") / "narzedzia"


def _relations_path() -> Path:
    return _tools_dir() / _REL_FILE


def _read_relations() -> list[dict[str, Any]]:
    path = _relations_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        raw = {}

    groups = raw.get("groups") if isinstance(raw, dict) else []
    if not isinstance(groups, list):
        groups = []

    out: list[dict[str, Any]] = []
    for item in groups:
        if not isinstance(item, dict):
            continue
        tools_raw = item.get("tools")
        if not isinstance(tools_raw, list):
            continue
        tools: list[str] = []
        for value in tools_raw:
            nr = _norm_nr(value)
            if nr and nr not in tools:
                tools.append(nr)
            if len(tools) >= _MAX_STAGES:
                break
        if len(tools) < 2:
            continue
        group_id = str(item.get("id") or "").strip() or f"grp_{int(time.time() * 1000)}"
        out.append({"id": group_id, "tools": tools})
    return out


def _write_relations(groups: list[dict[str, Any]]) -> None:
    path = _relations_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "max_stages": _MAX_STAGES,
        "groups": groups,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _group_for(groups: list[dict[str, Any]], nr: str) -> dict[str, Any] | None:
    nr = _norm_nr(nr)
    for group in groups:
        tools = group.get("tools")
        if isinstance(tools, list) and nr in tools:
            return group
    return None


def _read_tool_doc(nr: str) -> dict[str, Any]:
    nr = _norm_nr(nr)
    try:
        import gui_narzedzia as tools_gui

        doc = tools_gui._read_tool(nr) or {}
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _load_tool_meta_cache(owner: tk.Misc | None = None, *, force: bool = False) -> dict[str, dict[str, Any]]:
    global _META_CACHE
    if _META_CACHE is not None and not force:
        return _META_CACHE

    wait = None
    progress = None
    if owner is not None:
        try:
            wait = tk.Toplevel(owner)
            wait.title("Ładowanie danych narzędzi")
            wait.transient(owner.winfo_toplevel())
            wait.resizable(False, False)
            frame = ttk.Frame(wait, padding=18, style="WM.Card.TFrame")
            frame.pack(fill="both", expand=True)
            ttk.Label(
                frame,
                text="Ładowanie danych narzędzi…\nProszę czekać.",
                justify="center",
                style="WM.Card.TLabel",
            ).pack(padx=20, pady=(4, 12))
            progress = ttk.Progressbar(frame, mode="indeterminate", length=280)
            progress.pack(fill="x", padx=8, pady=(0, 4))
            progress.start(12)
            wait.update_idletasks()
            width = max(360, wait.winfo_reqwidth())
            height = max(120, wait.winfo_reqheight())
            parent = owner.winfo_toplevel()
            x = max(0, parent.winfo_rootx() + (parent.winfo_width() - width) // 2)
            y = max(0, parent.winfo_rooty() + (parent.winfo_height() - height) // 2)
            wait.geometry(f"{width}x{height}+{x}+{y}")
            wait.lift(parent)
            wait.update()
        except Exception:
            wait = None
            progress = None

    cache: dict[str, dict[str, Any]] = {}
    base = _tools_dir()
    try:
        candidates = sorted(base.glob("*.json"))
    except Exception:
        candidates = []

    for path in candidates:
        stem = path.stem.strip()
        if not stem.isdigit() or len(stem) > 3:
            continue
        nr = stem.zfill(3)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        cache[nr] = {
            "nr": nr,
            "nazwa": str(raw.get("nazwa") or "").strip(),
            "typ": str(raw.get("typ") or "").strip(),
            "status": str(raw.get("status") or "").strip(),
            "tryb": str(raw.get("tryb") or raw.get("mode") or "").strip(),
            "obrazy": raw.get("obrazy") if isinstance(raw.get("obrazy"), list) else [],
            "obraz": str(raw.get("obraz") or "").strip(),
            "dxf_png": str(raw.get("dxf_png") or "").strip(),
        }

    _META_CACHE = cache

    if progress is not None:
        try:
            progress.stop()
        except Exception:
            pass
    if wait is not None:
        try:
            wait.destroy()
        except Exception:
            pass
    return cache


def _current_nr(window: tk.Toplevel) -> str:
    return _norm_nr(_variant._entry_value_from_field(window, "Numer (3 cyfry)"))


def _is_saved_tool(window: tk.Toplevel) -> bool:
    nr = _current_nr(window)
    if not nr:
        return False
    return bool(_read_tool_doc(nr))


def _tool_image_path(meta: dict[str, Any]) -> Path | None:
    base = _tools_dir()
    candidates: list[str] = []
    images = meta.get("obrazy")
    if isinstance(images, list):
        candidates.extend(str(x) for x in images if str(x or "").strip())
    legacy = str(meta.get("obraz") or "").strip()
    if legacy:
        candidates.append(legacy)
    dxf_png = str(meta.get("dxf_png") or "").strip()
    if dxf_png:
        candidates.append(dxf_png)

    for raw in candidates:
        path = Path(raw)
        checks = [path] if path.is_absolute() else [base / path, base / "media" / path.name]
        for candidate in checks:
            try:
                if candidate.is_file():
                    return candidate
            except OSError:
                continue
    return None


def _open_tool(nr: str) -> None:
    try:
        import gui_narzedzia as tools_gui

        opener = getattr(tools_gui, "_OPEN_TOOL_EDITOR_BY_ID", None)
        if callable(opener):
            opener(_norm_nr(nr))
    except Exception:
        pass


def _remove_tab(notebook: ttk.Notebook, tab: tk.Misc | None) -> None:
    if tab is None:
        return
    try:
        notebook.forget(tab)
    except Exception:
        pass
    try:
        tab.destroy()
    except Exception:
        pass


def _build_related_tab(
    window: tk.Toplevel,
    notebook: ttk.Notebook,
    group: dict[str, Any],
    current_nr: str,
) -> tk.Misc:
    colors = _variant._palette()
    tab = ttk.Frame(notebook, padding=12, style="WM.Card.TFrame")
    media = _variant._tab_by_text(notebook, "Pliki i zdjęcia")
    if media is not None:
        try:
            notebook.insert(notebook.index(media), tab, text="Powiązane narzędzia")
        except Exception:
            notebook.add(tab, text="Powiązane narzędzia")
    else:
        notebook.add(tab, text="Powiązane narzędzia")

    for col in range(3):
        tab.columnconfigure(col, weight=1, uniform="multistage")
    for row in range(2):
        tab.rowconfigure(row, weight=1)

    tools = [_norm_nr(x) for x in group.get("tools", [])][:_MAX_STAGES]
    cache = _load_tool_meta_cache(window)
    total = len(tools)

    for index, nr in enumerate(tools):
        meta = dict(cache.get(nr) or _read_tool_doc(nr))
        current = nr == current_nr
        card = tk.Frame(
            tab,
            bg=colors["card"],
            highlightthickness=2 if current else 1,
            highlightbackground=colors["accent"] if current else colors["line"],
            bd=0,
        )
        card.grid(
            row=index // 3,
            column=index % 3,
            sticky="nsew",
            padx=6,
            pady=6,
        )

        top = tk.Frame(card, bg=colors["card"])
        top.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(
            top,
            text=f"ETAP {index + 1} Z {total}",
            bg=colors["card"],
            fg=colors["accent"] if current else colors["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        if current:
            tk.Label(
                top,
                text="AKTUALNE",
                bg=colors["accent"],
                fg="#ffffff",
                font=("Segoe UI", 8, "bold"),
                padx=7,
                pady=2,
            ).pack(side="right")

        body = tk.Frame(card, bg=colors["card"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        thumb = tk.Label(
            body,
            text="Brak zdjęcia",
            bg=colors["panel"],
            fg=colors["muted"],
            width=22,
            height=7,
            justify="center",
            cursor="hand2" if not current else "arrow",
        )
        thumb.pack(side="left", padx=(0, 12))

        image_path = _tool_image_path(meta)
        if image_path is not None:
            try:
                photo = _variant._load_photo(image_path, thumb, (180, 105))
            except Exception:
                photo = None
            if photo is not None:
                thumb.configure(image=photo, text="")
                thumb._wm_multistage_photo = photo  # type: ignore[attr-defined]

        info = tk.Frame(body, bg=colors["card"])
        info.pack(side="left", fill="both", expand=True)
        tk.Label(
            info,
            text=nr,
            bg=colors["card"],
            fg=colors["text"],
            font=("Segoe UI", 26, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            info,
            text=str(meta.get("nazwa") or "Bez nazwy"),
            bg=colors["card"],
            fg=colors["text"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            wraplength=240,
            justify="left",
        ).pack(fill="x", pady=(2, 2))
        tk.Label(
            info,
            text=f"{meta.get('typ') or '—'}  •  {meta.get('status') or '—'}",
            bg=colors["card"],
            fg=colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=260,
            justify="left",
        ).pack(fill="x")

        if not current:
            ttk.Button(
                info,
                text="Otwórz narzędzie",
                command=lambda value=nr: _open_tool(value),
                style="WM.Side.TButton",
            ).pack(anchor="w", pady=(10, 0))
            thumb.bind("<Button-1>", lambda _event, value=nr: _open_tool(value))

    return tab


def _relation_label_text(group: dict[str, Any], nr: str) -> str:
    tools = [_norm_nr(x) for x in group.get("tools", [])][:_MAX_STAGES]
    try:
        stage = tools.index(_norm_nr(nr)) + 1
    except ValueError:
        return ""
    return f"Narzędzie wieloetapowe — etap {stage} z {len(tools)}"


def _relation_editor(window: tk.Toplevel, on_saved) -> None:
    current_nr = _current_nr(window)
    if not current_nr:
        messagebox.showwarning("Powiązane narzędzia", "Najpierw ustaw numer narzędzia.", parent=window)
        return
    if not _is_saved_tool(window):
        messagebox.showinfo(
            "Powiązane narzędzia",
            "Najpierw zapisz nowe narzędzie. Powiązania etapów można ustawić po pierwszym zapisie.",
            parent=window,
        )
        return

    cache = _load_tool_meta_cache(window, force=False)
    groups = _read_relations()
    current_group = _group_for(groups, current_nr)
    current_tools = list(current_group.get("tools", [])) if current_group else [current_nr]

    dialog = tk.Toplevel(window)
    dialog.title("Powiązane narzędzia — etapy")
    dialog.transient(window)
    dialog.resizable(False, False)
    try:
        from ui_theme import ensure_theme_applied

        ensure_theme_applied(dialog)
    except Exception:
        pass

    frame = ttk.Frame(dialog, padding=14, style="WM.Card.TFrame")
    frame.pack(fill="both", expand=True)
    ttk.Label(
        frame,
        text="Narzędzie wieloetapowe",
        style="WM.Card.TLabel",
        font=("Segoe UI", 14, "bold"),
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
    ttk.Label(
        frame,
        text=(
            "Ustaw kolejność narzędzi w procesie. Liczba etapów wynika z liczby wybranych narzędzi. "
            "Maksymalnie 6 etapów."
        ),
        style="WM.Muted.TLabel",
        wraplength=650,
        justify="left",
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

    def _label_for(nr: str) -> str:
        meta = cache.get(nr) or {}
        name = str(meta.get("nazwa") or "Bez nazwy").strip()
        return f"{nr} — {name}"

    numbers = sorted(cache.keys(), key=lambda x: int(x) if x.isdigit() else 9999)
    labels = ["— brak —"] + [_label_for(nr) for nr in numbers]
    label_to_nr = {_label_for(nr): nr for nr in numbers}
    vars_list: list[tk.StringVar] = []

    for idx in range(_MAX_STAGES):
        ttk.Label(frame, text=f"Etap {idx + 1}").grid(row=2 + idx, column=0, sticky="w", padx=(0, 10), pady=4)
        value = "— brak —"
        if idx < len(current_tools):
            nr = _norm_nr(current_tools[idx])
            if nr in cache:
                value = _label_for(nr)
        var = tk.StringVar(master=dialog, value=value)
        vars_list.append(var)
        combo = ttk.Combobox(frame, textvariable=var, values=labels, state="readonly", width=52)
        combo.grid(row=2 + idx, column=1, sticky="ew", pady=4)

    frame.columnconfigure(1, weight=1)

    def _selected_numbers() -> list[str]:
        selected: list[str] = []
        for var in vars_list:
            label = str(var.get() or "").strip()
            nr = label_to_nr.get(label, "")
            if nr:
                selected.append(nr)
        return selected

    def _save() -> None:
        selected = _selected_numbers()
        if len(selected) != len(set(selected)):
            messagebox.showwarning("Powiązane narzędzia", "To samo narzędzie nie może wystąpić w dwóch etapach.", parent=dialog)
            return
        if current_nr not in selected:
            messagebox.showwarning("Powiązane narzędzia", f"Bieżące narzędzie {current_nr} musi znajdować się na liście etapów.", parent=dialog)
            return
        if len(selected) < 2:
            messagebox.showinfo("Powiązane narzędzia", "Wybierz co najmniej dwa narzędzia albo użyj „Usuń powiązanie”.", parent=dialog)
            return
        if len(selected) > _MAX_STAGES:
            messagebox.showwarning("Powiązane narzędzia", "Maksymalnie 6 etapów.", parent=dialog)
            return

        current_id = str(current_group.get("id") or "") if current_group else ""
        for nr in selected:
            other = _group_for(groups, nr)
            if other is None:
                continue
            other_id = str(other.get("id") or "")
            if current_id and other_id == current_id:
                continue
            messagebox.showwarning(
                "Powiązane narzędzia",
                f"Narzędzie {nr} należy już do innego zestawu wieloetapowego. Najpierw usuń je z tamtego zestawu.",
                parent=dialog,
            )
            return

        remaining = []
        for group in groups:
            if current_group is not None and group is current_group:
                continue
            remaining.append(group)
        group_id = current_id or f"grp_{int(time.time() * 1000)}"
        remaining.append({"id": group_id, "tools": selected})
        try:
            _write_relations(remaining)
        except OSError as exc:
            messagebox.showerror("Powiązane narzędzia", f"Nie udało się zapisać powiązań:\n{exc}", parent=dialog)
            return
        dialog.destroy()
        on_saved()

    def _remove() -> None:
        if current_group is None:
            dialog.destroy()
            return
        if not messagebox.askyesno(
            "Usuń powiązanie",
            "Usunąć cały zestaw powiązań wieloetapowych dla tych narzędzi?",
            parent=dialog,
        ):
            return
        remaining = [group for group in groups if group is not current_group]
        try:
            _write_relations(remaining)
        except OSError as exc:
            messagebox.showerror("Powiązane narzędzia", f"Nie udało się zapisać zmian:\n{exc}", parent=dialog)
            return
        dialog.destroy()
        on_saved()

    buttons = ttk.Frame(frame, style="WM.TFrame")
    buttons.grid(row=2 + _MAX_STAGES, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    if current_group is not None:
        ttk.Button(buttons, text="Usuń powiązanie", command=_remove, style="WM.Side.TButton").pack(side="left")
    ttk.Button(buttons, text="Anuluj", command=dialog.destroy, style="WM.Side.TButton").pack(side="right", padx=(6, 0))
    ttk.Button(buttons, text="Zapisz etapy", command=_save, style="WM.Action.TButton").pack(side="right")

    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    try:
        dialog.update_idletasks()
        width = max(720, dialog.winfo_reqwidth())
        height = max(430, dialog.winfo_reqheight())
        x = max(0, window.winfo_rootx() + (window.winfo_width() - width) // 2)
        y = max(0, window.winfo_rooty() + (window.winfo_height() - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.lift(window)
        dialog.focus_force()
    except Exception:
        pass


def _decorate_multistage(window: tk.Toplevel) -> None:
    if getattr(window, "_wm_multistage_ready", False):
        return
    if not getattr(window, "_wm_editor_variant_ready", False):
        return

    _main, header, notebook = _variant._editor_parts(window)
    if header is None or notebook is None:
        return
    dashboard = _variant._tab_by_text(notebook, "Podgląd")
    if dashboard is None:
        return

    # Numer jest głównym identyfikatorem narzędzia — pokazujemy go znacznie większy.
    number_badge = getattr(header, "_wm_number_badge", None)
    if number_badge is not None:
        try:
            number_badge.configure(font=("Segoe UI", 22, "bold"), padx=15, pady=5)
        except Exception:
            pass

    identity = getattr(getattr(header, "_wm_name_label", None), "master", None)
    relation_label = None
    if identity is not None:
        colors = _variant._palette()
        relation_label = tk.Label(
            identity,
            text="",
            bg=colors["card"],
            fg=colors["accent"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )

    # Przy dodawaniu numer jest podpowiedzią kolejnego wolnego numeru, ale może być zmieniony.
    saved = _is_saved_tool(window)
    nr_widget = getattr(dashboard, "_wm_nr_widget", None)
    if nr_widget is not None and not saved:
        try:
            nr_widget.state(["!readonly", "!disabled"])
        except Exception:
            try:
                nr_widget.configure(state="normal")
            except Exception:
                pass

        details = getattr(nr_widget, "master", None)
        source_holder = _variant._field_value_widget(window, "Numer (3 cyfry)")
        source_free = _variant._find_button(source_holder, "Wolne numery")
        if details is not None and source_free is not None:
            try:
                details.columnconfigure(2, weight=0)
                ttk.Button(
                    details,
                    text="Wolne numery",
                    command=source_free.invoke,
                    style="WM.Side.TButton",
                ).grid(row=1, column=2, sticky="w", padx=(0, 12), pady=6)
                ttk.Label(
                    details,
                    text="Podpowiedź: wpisano kolejny wolny numer. Możesz wybrać inny wolny numer przed pierwszym zapisem.",
                    style="WM.Muted.TLabel",
                    wraplength=760,
                    justify="left",
                ).grid(row=5, column=0, columnspan=3, sticky="w", padx=12, pady=(2, 10))
            except Exception:
                pass

    action_bar = ttk.Frame(dashboard, style="WM.TFrame")
    action_bar.grid(row=2, column=0, columnspan=2, sticky="e", pady=(4, 0))

    def _refresh_relation() -> None:
        nr = _current_nr(window)
        groups = _read_relations()
        group = _group_for(groups, nr)
        signature = tuple(group.get("tools", [])) if group is not None else ()

        if relation_label is not None:
            try:
                if group is None:
                    relation_label.pack_forget()
                else:
                    relation_label.configure(text=_relation_label_text(group, nr))
                    if not relation_label.winfo_manager():
                        relation_label.pack(anchor="w", fill="x", pady=(4, 0))
            except Exception:
                pass

        old_tab = getattr(window, "_wm_multistage_tab", None)
        old_signature = getattr(window, "_wm_multistage_signature", None)
        if old_signature == signature:
            return
        if old_tab is not None:
            _remove_tab(notebook, old_tab)
            window._wm_multistage_tab = None  # type: ignore[attr-defined]

        if group is not None:
            new_tab = _build_related_tab(window, notebook, group, nr)
            window._wm_multistage_tab = new_tab  # type: ignore[attr-defined]
        window._wm_multistage_signature = signature  # type: ignore[attr-defined]

    def _edit_relation() -> None:
        _relation_editor(window, _refresh_relation)

    relation_button = ttk.Button(
        action_bar,
        text="Powiąż etapy" if not _group_for(_read_relations(), _current_nr(window)) else "Edytuj powiązane narzędzia",
        command=_edit_relation,
        style="WM.Side.TButton",
    )
    relation_button.pack(side="right")

    def _refresh_and_button(_event=None) -> None:
        _refresh_relation()
        try:
            has_group = _group_for(_read_relations(), _current_nr(window)) is not None
            relation_button.configure(text="Edytuj powiązane narzędzia" if has_group else "Powiąż etapy")
        except Exception:
            pass

    try:
        window.bind("<FocusIn>", _refresh_and_button, add="+")
    except Exception:
        pass
    _refresh_and_button()

    window._wm_multistage_ready = True  # type: ignore[attr-defined]
    window._wm_multistage_relation_label = relation_label  # type: ignore[attr-defined]


def install_multistage_runtime() -> None:
    if getattr(_variant, "_wm_multistage_runtime_installed", False):
        return

    original_decorate = _variant._decorate_editor

    def _decorate_with_multistage(window: tk.Toplevel) -> bool:
        result = original_decorate(window)
        if result:
            try:
                _decorate_multistage(window)
            except Exception:
                pass
        return result

    _variant._decorate_editor = _decorate_with_multistage
    _variant._wm_multistage_runtime_installed = True


__all__ = ["install_multistage_runtime"]
