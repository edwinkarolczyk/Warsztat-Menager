# version: 2.0
# Moduł: narzedzia_ui.editor_header_info_runtime
# 2.0:
# - Nowy edytor jest jedynym dostępnym edytorem NN/SN; stary wariant konfiguracji jest ignorowany.
# - Ustawienia nie pokazują wyboru Stary/Nowy widok.
# - Dane dashboardu są buforowane w jednej sesji edytora i odświeżane po zapisie.
# - Zakładka Informacje zapisuje historię wpisów (tekst, autor, data), zachowując stary opis.
# - Stary opis jest migrowany do historii jako wpis bez wymyślonego autora i daty.
# 1.0:
# - Nagłówek korzysta z tych samych żywych wartości co karta Podgląd.
# - Kanoniczny numer narzędzia ma pierwszeństwo przed placeholderem.
# - Zakładka "Opis" zmienia się na "Informacje".
#
# Stary formularz pozostaje wyłącznie technicznym backendem kompatybilności dla
# zapisu, zadań, wizyt, magazynu, DXF i uprawnień. Użytkownik ma jeden widoczny edytor.

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
import sys
import weakref
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant
from . import editor_lazy_media_runtime as _lazy


_EDITORS: "weakref.WeakSet[tk.Toplevel]" = weakref.WeakSet()


def _alive(widget: tk.Misc | None) -> bool:
    try:
        return widget is not None and bool(int(widget.winfo_exists()))
    except Exception:
        return False


def _widget_value(widget):
    if widget is None:
        return ""
    getter = getattr(widget, "get", None)
    if not callable(getter):
        return ""
    try:
        return str(getter() or "").strip()
    except Exception:
        return ""


def _dashboard(window):
    try:
        _main, _header, notebook = _variant._editor_parts(window)
    except Exception:
        return None
    if notebook is None:
        return None
    try:
        return _variant._tab_by_text(notebook, "Podgląd")
    except Exception:
        return None


def _dashboard_field(window, attr):
    dash = _dashboard(window)
    if dash is None:
        return ""
    return _widget_value(getattr(dash, attr, None))


def _norm_three(value):
    raw = str(value or "").strip()
    if not raw.isdigit():
        return ""
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return ""
    if not (1 <= number <= 999):
        return ""
    return f"{number:03d}"


def _window_number(window: tk.Toplevel) -> str:
    return (
        _norm_three(getattr(window, "_wm_tool_number", ""))
        or _norm_three(_dashboard_field(window, "_wm_nr_widget"))
        or _norm_three(_variant._entry_value_from_field(window, "Numer (3 cyfry)"))
    )


def _install_live_header_source():
    current = getattr(_lazy, "_paint_light_header", None)
    if not callable(current) or getattr(current, "_wm_live_header_source", False):
        return
    original = current

    def _paint_light_header_live(window, header, colors):
        nr_old, name_old, type_old, status_old, mode = original(window, header, colors)

        nr = (
            _norm_three(getattr(window, "_wm_tool_number", ""))
            or _norm_three(_dashboard_field(window, "_wm_nr_widget"))
            or _norm_three(nr_old)
            or "---"
        )
        name = (
            _dashboard_field(window, "_wm_name_widget")
            or ("" if name_old == "Bez nazwy" else str(name_old or "").strip())
            or "Bez nazwy"
        )
        tool_type = (
            _dashboard_field(window, "_wm_type_widget")
            or ("" if type_old == "—" else str(type_old or "").strip())
            or "—"
        )
        status = (
            _dashboard_field(window, "_wm_status_widget")
            or ("" if status_old == "—" else str(status_old or "").strip())
            or "—"
        )

        if header is not None:
            try:
                header._wm_number_badge.configure(text=f"#{nr}")
                header._wm_name_label.configure(text=name)
                header._wm_type_label.configure(text=f"Typ: {tool_type}")
                header._wm_status_badge.configure(
                    text=status,
                    bg=_variant._status_color(status, colors),
                )
            except Exception:
                pass

        try:
            window.title(f"Narzędzie {nr} — {name} [{mode}]")
        except Exception:
            pass

        if nr != "---":
            try:
                window._wm_tool_number = nr
            except Exception:
                pass

        return nr, name, tool_type, status, mode

    _paint_light_header_live._wm_live_header_source = True
    _paint_light_header_live._wm_live_header_original = original
    _lazy._paint_light_header = _paint_light_header_live


def _find_text_widget(tab):
    try:
        descendants = _variant._all_descendants(tab)
    except Exception:
        descendants = []
    for widget in descendants:
        if isinstance(widget, tk.Text):
            return widget
    return None


def _find_heading(tab):
    try:
        descendants = _variant._all_descendants(tab)
    except Exception:
        descendants = []
    for widget in descendants:
        if not isinstance(widget, (tk.Label, ttk.Label)):
            continue
        try:
            text = str(widget.cget("text") or "").strip()
        except Exception:
            continue
        if text in {"Opis narzędzia", "Opis", "OPIS NARZĘDZIA", "OPIS I UWAGI"}:
            return widget
    return None


def _hide_widget(widget: tk.Misc | None) -> None:
    if widget is None:
        return
    for method in ("grid_remove", "pack_forget", "place_forget"):
        try:
            getattr(widget, method)()
        except Exception:
            continue


def _session_cache_doc(window: tk.Toplevel) -> dict:
    cache = getattr(window, "_wm_single_editor_doc_cache", None)
    if not isinstance(cache, dict):
        return {}
    value = cache.get("doc")
    return value if isinstance(value, dict) else {}


def _install_session_state():
    current = getattr(_variant, "_current_doc", None)
    if not callable(current) or getattr(current, "_wm_single_editor_session", False):
        return
    original = current

    def _current_doc_session(window):
        nr = _window_number(window)
        cache = getattr(window, "_wm_single_editor_doc_cache", None)
        if isinstance(cache, dict) and cache.get("nr") == nr:
            doc = cache.get("doc")
            if isinstance(doc, dict):
                return doc

        try:
            doc = original(window)
        except Exception:
            doc = {}
        if not isinstance(doc, dict):
            doc = {}

        try:
            window._wm_single_editor_doc_cache = {
                "nr": nr,
                "doc": deepcopy(doc),
            }
        except Exception:
            pass

        if not getattr(window, "_wm_single_editor_cache_event", False):
            def _invalidate(_event=None, w=window):
                try:
                    w._wm_single_editor_doc_cache = None
                except Exception:
                    pass

            try:
                window.bind("<<ToolSaved>>", _invalidate, add="+")
                window._wm_single_editor_cache_event = True
            except Exception:
                pass

        return _session_cache_doc(window) or doc

    _current_doc_session._wm_single_editor_session = True
    _current_doc_session._wm_single_editor_original = original
    _variant._current_doc = _current_doc_session


def _normalize_info_entries(doc: dict) -> list[dict]:
    result: list[dict] = []
    raw = doc.get("informacje") if isinstance(doc, dict) else None

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    result.append({"text": text, "author": "", "ts": "", "legacy": True})
                continue
            if not isinstance(item, dict):
                continue
            text = str(
                item.get("text") or item.get("tekst") or item.get("opis") or ""
            ).strip()
            if not text:
                continue
            result.append(
                {
                    "text": text,
                    "author": str(
                        item.get("author") or item.get("autor") or item.get("user") or ""
                    ).strip(),
                    "ts": str(
                        item.get("ts") or item.get("timestamp") or item.get("data") or ""
                    ).strip(),
                    "legacy": bool(item.get("legacy", False)),
                }
            )
    elif isinstance(raw, str) and raw.strip():
        result.append({"text": raw.strip(), "author": "", "ts": "", "legacy": True})

    if not result and isinstance(doc, dict):
        old = str(doc.get("opis") or "").strip()
        if old:
            result.append({"text": old, "author": "", "ts": "", "legacy": True})
    return result


def _actor() -> str:
    attr_names = (
        "CURRENT_USER",
        "current_user",
        "CURRENT_LOGIN",
        "current_login",
        "ZALOGOWANY_UZYTKOWNIK",
        "zalogowany_uzytkownik",
        "LOGIN",
        "login",
    )
    for module_name in ("gui_panel", "gui_logowanie", "session_manager", "auth"):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for attr in attr_names:
            try:
                value = getattr(module, attr)
            except Exception:
                continue
            if isinstance(value, dict):
                value = (
                    value.get("imie_nazwisko")
                    or value.get("name")
                    or value.get("login")
                    or value.get("username")
                    or ""
                )
            text = str(value or "").strip()
            if text and not text.startswith("<"):
                return text
    return str(os.environ.get("USERNAME") or os.environ.get("USER") or "—").strip() or "—"


def _display_ts(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "bez daty"
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%H:%M %d.%m.%y")
        except ValueError:
            continue
    return text


def _info_signature(entries: list[dict]) -> str:
    normalized = [
        {
            "text": str(item.get("text") or ""),
            "author": str(item.get("author") or ""),
            "ts": str(item.get("ts") or ""),
            "legacy": bool(item.get("legacy", False)),
        }
        for item in entries
        if isinstance(item, dict)
    ]
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _render_info_history(window: tk.Toplevel) -> None:
    history = getattr(window, "_wm_information_history", None)
    entries = getattr(window, "_wm_information_entries", None)
    signature_var = getattr(window, "_wm_information_signature_var", None)
    if not isinstance(history, tk.Text) or not isinstance(entries, list):
        return

    try:
        history.configure(state="normal")
        history.delete("1.0", "end")
        if not entries:
            history.insert("end", "Brak zapisanych wpisów.")
        else:
            for index, item in enumerate(reversed(entries)):
                text = str(item.get("text") or "").strip()
                author = str(item.get("author") or "").strip()
                ts = str(item.get("ts") or "").strip()
                legacy = bool(item.get("legacy", False))
                if not text:
                    continue
                history.insert("end", text + "\n")
                if legacy and not author and not ts:
                    meta = "Starszy opis • bez autora i daty"
                else:
                    meta = f"{author or '—'} • {_display_ts(ts)}"
                history.insert("end", meta + "\n")
                if index < len(entries) - 1:
                    history.insert("end", "\n" + ("─" * 46) + "\n\n")
        history.configure(state="disabled")
    except Exception:
        pass

    if signature_var is not None:
        try:
            signature_var.set(_info_signature(entries))
        except Exception:
            pass


def _matching_editor(data: dict) -> tk.Toplevel | None:
    raw = ""
    if isinstance(data, dict):
        raw = data.get("numer") or data.get("nr") or data.get("id") or ""
    nr = _norm_three(raw)
    candidates = [window for window in list(_EDITORS) if _alive(window)]
    if nr:
        for window in reversed(candidates):
            try:
                if _window_number(window) == nr:
                    return window
            except Exception:
                continue
    return candidates[-1] if len(candidates) == 1 else None


def _ensure_info_save_wrapper() -> None:
    module = sys.modules.get("gui_narzedzia")
    current = getattr(module, "_save_tool", None) if module is not None else None
    if not callable(current) or getattr(current, "_wm_information_history_save", False):
        return
    original = current

    def _save_with_information(data):
        window = _matching_editor(data if isinstance(data, dict) else {})
        if window is not None and isinstance(data, dict):
            entries = getattr(window, "_wm_information_entries", None)
            if isinstance(entries, list):
                data["informacje"] = deepcopy(entries)
        result = original(data)
        if window is not None and isinstance(data, dict):
            try:
                window._wm_single_editor_doc_cache = {
                    "nr": _window_number(window),
                    "doc": deepcopy(data),
                }
            except Exception:
                pass
        return result

    _save_with_information._wm_information_history_save = True
    _save_with_information._wm_information_history_original = original
    module._save_tool = _save_with_information


def _decorate_information_tab(window, notebook):
    tab = _variant._tab_by_text(notebook, "Informacje")
    if tab is None or getattr(tab, "_wm_information_history_ready", False):
        return

    _ensure_info_save_wrapper()
    _EDITORS.add(window)

    old_text = _find_text_widget(tab)
    heading = _find_heading(tab)
    colors = _variant._palette()

    if old_text is not None:
        _hide_widget(old_text)
        parent = getattr(old_text, "master", None)
        if parent is not None and parent is not tab:
            _hide_widget(parent)
    if heading is not None:
        _hide_widget(heading)

    for child in list(tab.winfo_children()):
        if child is old_text:
            continue
        try:
            if getattr(child, "_wm_information_history_ui", False):
                continue
        except Exception:
            pass
        if isinstance(child, (tk.Label, ttk.Label)):
            _hide_widget(child)

    host = ttk.Frame(tab, padding=(12, 10), style="WM.Card.TFrame")
    host.pack(fill="both", expand=True)
    host._wm_information_history_ui = True

    ttk.Label(host, text="NOWY WPIS", style="WM.Muted.TLabel").pack(anchor="w")

    editor = tk.Text(
        host,
        height=4,
        wrap="word",
        font=("Segoe UI", 11),
        bg=colors["panel"],
        fg=colors["text"],
        insertbackground=colors["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=colors["line"],
        highlightcolor=colors["blue"],
        padx=10,
        pady=8,
    )
    editor.pack(fill="x", pady=(5, 8))

    actions = ttk.Frame(host, style="WM.TFrame")
    actions.pack(fill="x", pady=(0, 12))
    ttk.Label(
        actions,
        text="Ctrl+Enter = dodaj wpis",
        style="WM.Muted.TLabel",
    ).pack(side="left")

    ttk.Separator(host, orient="horizontal").pack(fill="x", pady=(0, 10))
    ttk.Label(host, text="HISTORIA INFORMACJI", style="WM.Muted.TLabel").pack(anchor="w")

    history_frame = ttk.Frame(host, style="WM.TFrame")
    history_frame.pack(fill="both", expand=True, pady=(6, 0))

    history = tk.Text(
        history_frame,
        wrap="word",
        state="disabled",
        font=("Segoe UI", 10),
        bg=colors["panel"],
        fg=colors["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=colors["line"],
        padx=12,
        pady=10,
    )
    history.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(history_frame, orient="vertical", command=history.yview)
    scroll.pack(side="right", fill="y")
    history.configure(yscrollcommand=scroll.set)

    doc = _variant._current_doc(window)
    entries = _normalize_info_entries(doc)
    window._wm_information_entries = entries
    window._wm_information_history = history

    signature_var = tk.StringVar(master=host, value=_info_signature(entries))
    signature_entry = ttk.Entry(host, textvariable=signature_var)
    signature_entry.pack_forget()
    window._wm_information_signature_var = signature_var
    window._wm_information_signature_entry = signature_entry

    def _add_entry(_event=None):
        text = editor.get("1.0", "end-1c").strip()
        if not text:
            return "break"
        entries.append(
            {
                "text": text,
                "author": _actor(),
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "legacy": False,
            }
        )
        editor.delete("1.0", "end")
        _render_info_history(window)
        try:
            window.event_generate("<<ToolInfoChanged>>", when="tail")
        except Exception:
            pass
        return "break"

    ttk.Button(
        actions,
        text="Dodaj wpis",
        command=_add_entry,
        style="WM.Side.TButton",
    ).pack(side="right")

    editor.bind("<Control-Return>", _add_entry)
    _render_info_history(window)

    try:
        tab._wm_information_history_ready = True
    except Exception:
        pass


def _install_information_tab():
    current = getattr(_variant, "_rename_tabs", None)
    if not callable(current) or getattr(current, "_wm_information_tab", False):
        return
    original = current

    def _rename_tabs_information(notebook):
        original(notebook)

        for tab_id in notebook.tabs():
            try:
                text = str(notebook.tab(tab_id, "text") or "").strip()
            except Exception:
                continue
            if text in {"Opis", "Opis narzędzia"}:
                try:
                    notebook.tab(tab_id, text="Informacje")
                except Exception:
                    pass
                break

        try:
            top = notebook.winfo_toplevel()
        except Exception:
            top = None
        if isinstance(top, tk.Toplevel):
            _decorate_information_tab(top, notebook)

    _rename_tabs_information._wm_information_tab = True
    _rename_tabs_information._wm_information_original = original
    _variant._rename_tabs = _rename_tabs_information


def _install_single_editor_mode() -> None:
    def _always_new() -> bool:
        return True

    _always_new._wm_single_editor_mode = True
    _variant._new_variant_enabled = _always_new

    try:
        import settings_tools_runtime as settings_runtime
    except Exception:
        settings_runtime = None

    if settings_runtime is not None:
        def _no_variant_selector(panel):
            try:
                root = settings_runtime._module_tab(panel, "Narzędzia")
                if root is None:
                    return
                box = settings_runtime._label_frame(root, "Okna edycji")
                if box is not None:
                    settings_runtime._hide(box)
                setattr(root, "_wm_editor_variant_selector", True)
            except Exception:
                pass

        _no_variant_selector._wm_single_editor_mode = True
        settings_runtime._editor_variant_selector = _no_variant_selector


def install_editor_header_info_runtime():
    if getattr(_variant, "_wm_editor_header_info_installed", False):
        return

    _install_single_editor_mode()
    _install_session_state()
    _install_live_header_source()
    _install_information_tab()

    _variant._wm_editor_header_info_installed = True
    print(
        "[WM-DBG][TOOLS_EDITOR] jeden edytor aktywny + jedna sesja danych "
        "+ historia Informacji"
    )


__all__ = ["install_editor_header_info_runtime"]
