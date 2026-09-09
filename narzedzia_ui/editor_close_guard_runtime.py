# version: 1.0
# Moduł: narzedzia_ui.editor_close_guard_runtime
# - Przywraca ostrzeżenie o niezapisanych zmianach po zmianie tytułu nowego edytora.
# - Nie traktuje samego leniwego wczytania tabel jako zmiany użytkownika.
# - Usuwa przycisk „Anuluj”; pozostawia „Zapisz” i „Zamknij okno”.
# - Przypina dolny pasek akcji do dołu okna.

from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from . import editor_runtime as _runtime


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}


def _alive(widget: tk.Misc | None) -> bool:
    try:
        return widget is not None and bool(int(widget.winfo_exists()))
    except Exception:
        return False


def _walk(widget: tk.Misc):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _walk(child)


def _button_texts(parent: tk.Misc) -> set[str]:
    result: set[str] = set()
    try:
        children = parent.winfo_children()
    except Exception:
        return result
    for child in children:
        if not isinstance(child, ttk.Button):
            continue
        try:
            result.add(str(child.cget("text") or "").strip())
        except Exception:
            pass
    return result


def _is_tool_editor(dlg: tk.Toplevel) -> bool:
    try:
        title = str(dlg.title() or "").strip()
    except Exception:
        title = ""

    if title in _EDITOR_TITLES:
        return True
    if bool(getattr(dlg, "_wm_editor_variant_ready", False)):
        return True

    upper = title.upper()
    return title.startswith("Narzędzie ") and ("[NN]" in upper or "[SN]" in upper)


def _lazy_tree_rows(tree: ttk.Treeview) -> list[tuple[str, tuple[Any, ...], tuple[Any, ...]]]:
    pending = list(getattr(tree, "_wm_legacy_lazy_pending", []) or [])
    rows: list[tuple[str, tuple[Any, ...], tuple[Any, ...]]] = []
    for item in pending:
        try:
            parent, _index, iid, kw = item
        except (TypeError, ValueError):
            continue
        if str(parent or ""):
            continue
        if not isinstance(kw, dict):
            kw = {}
        values = kw.get("values") or ()
        if not isinstance(values, (list, tuple)):
            values = (values,)
        tags = kw.get("tags") or ()
        if isinstance(tags, str):
            tags = (tags,)
        elif not isinstance(tags, (list, tuple)):
            tags = (tags,)
        rows.append((str(iid), tuple(values), tuple(tags)))
    return rows


def _snapshot(dlg: tk.Toplevel) -> tuple:
    """Stan edytowalnych danych; samo lazy-load nie może tworzyć fałszywej zmiany."""
    state: list[tuple[Any, ...]] = []

    for widget in _walk(dlg):
        path = str(widget)
        try:
            if isinstance(widget, ttk.Entry):
                state.append(("entry", path, widget.get()))
                continue

            if isinstance(widget, ttk.Combobox):
                state.append(("combo", path, widget.get()))
                continue

            if isinstance(widget, tk.Text):
                state.append(("text", path, widget.get("1.0", "end-1c")))
                continue

            if isinstance(widget, ttk.Treeview):
                if (
                    getattr(widget, "_wm_legacy_lazy_tree", False)
                    and not getattr(widget, "_wm_legacy_lazy_loaded", False)
                ):
                    rows = _lazy_tree_rows(widget)
                else:
                    rows = []
                    for iid in widget.get_children(""):
                        rows.append(
                            (
                                str(iid),
                                tuple(widget.item(iid, "values") or ()),
                                tuple(widget.item(iid, "tags") or ()),
                            )
                        )
                state.append(("tree", path, tuple(rows)))
                continue

            if isinstance(widget, tk.Listbox):
                state.append(("list", path, tuple(widget.get(0, "end"))))
                continue

            if isinstance(widget, ttk.Checkbutton):
                text = str(widget.cget("text") or "").strip()
                if text.startswith("Numer stały"):
                    continue
                variable = str(widget.cget("variable") or "")
                value = widget.tk.globalgetvar(variable) if variable else ""
                state.append(("check", path, text, str(value)))
                continue

            if isinstance(widget, ttk.Radiobutton):
                text = str(widget.cget("text") or "").strip()
                variable = str(widget.cget("variable") or "")
                value = widget.tk.globalgetvar(variable) if variable else ""
                state.append(("radio", path, text, str(value)))
                continue

            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text") or "")
                parent_buttons = _button_texts(widget.master)
                if parent_buttons.intersection({"Wybierz...", "Wyczyść"}):
                    state.append(("media-label", path, text))
        except Exception:
            continue

    return tuple(state)


def _request_close(dlg: tk.Toplevel) -> str:
    if not _alive(dlg):
        return "break"

    try:
        saved = getattr(dlg, "_wm_close_saved_snapshot", None)
        current = _snapshot(dlg)
        changed = saved is not None and current != saved
    except Exception:
        changed = True

    if changed:
        try:
            close_anyway = messagebox.askyesno(
                "Niezapisane zmiany",
                "Masz niezapisane zmiany.\nZamknąć bez zapisywania?",
                parent=dlg,
            )
        except Exception:
            close_anyway = False
        if not close_anyway:
            return "break"

    try:
        dlg.destroy()
    except Exception:
        pass
    return "break"


def _find_footer(dlg: tk.Toplevel) -> tk.Misc | None:
    for widget in _walk(dlg):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text") or "").strip() != "Zapisz":
                continue
        except Exception:
            continue
        parent = getattr(widget, "master", None)
        if not isinstance(parent, tk.Misc):
            continue
        texts = _button_texts(parent)
        if "Zamknij okno" in texts:
            return parent
    return None


def _pin_footer_and_remove_cancel(dlg: tk.Toplevel) -> bool:
    footer = _find_footer(dlg)
    if footer is None:
        return False

    # Usuwamy tylko Anuluj z paska, w którym są też Zapisz i Zamknij okno.
    for child in list(footer.winfo_children()):
        if not isinstance(child, ttk.Button):
            continue
        try:
            text = str(child.cget("text") or "").strip()
        except Exception:
            continue
        if text == "Anuluj":
            try:
                child.destroy()
            except Exception:
                pass
        elif text == "Zamknij okno":
            try:
                child.configure(command=lambda d=dlg: _request_close(d))
            except Exception:
                pass

    # Pasek akcji ma dostać miejsce jako pierwszy, a środek edytora resztę.
    if getattr(footer, "master", None) is dlg:
        try:
            packed = [item for item in dlg.pack_slaves() if item is not footer]
            footer.pack_forget()
            if packed:
                footer.pack(side="bottom", fill="x", before=packed[0])
            else:
                footer.pack(side="bottom", fill="x")
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][FOOTER] "
                f"nie udało się przypiąć paska: {type(exc).__name__}: {exc}"
            )

    return True


def _wrap_save_button(dlg: tk.Toplevel) -> None:
    for widget in _walk(dlg):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text") or "").strip() != "Zapisz":
                continue
            if getattr(widget, "_wm_close_save_wrapped", False):
                return
            command_name = str(widget.cget("command") or "").strip()
        except Exception:
            continue
        if not command_name:
            continue

        def _invoke(*, button=widget, command=command_name, dialog=dlg):
            before = int(getattr(_runtime, "_SAVE_COUNTER", 0) or 0)
            try:
                return button.tk.call(command)
            finally:
                def _refresh_snapshot() -> None:
                    if not _alive(dialog):
                        return
                    after = int(getattr(_runtime, "_SAVE_COUNTER", 0) or 0)
                    if after > before:
                        try:
                            dialog._wm_close_saved_snapshot = _snapshot(dialog)  # type: ignore[attr-defined]
                        except Exception:
                            pass

                try:
                    dialog.after(0, _refresh_snapshot)
                except Exception:
                    pass

        try:
            widget.configure(command=_invoke)
            widget._wm_close_save_wrapped = True  # type: ignore[attr-defined]
            dlg.bind("<Control-s>", lambda _event, b=widget: (b.invoke(), "break")[1])
        except Exception:
            pass
        return


def _instrument(dlg: tk.Toplevel) -> bool:
    if not _alive(dlg) or getattr(dlg, "_wm_close_guard_ready", False):
        return bool(getattr(dlg, "_wm_close_guard_ready", False))
    if not _is_tool_editor(dlg):
        return False
    if not _pin_footer_and_remove_cancel(dlg):
        return False

    try:
        _runtime._install_save_guard()
    except Exception:
        pass
    try:
        _runtime._EDITORS.add(dlg)
    except Exception:
        pass

    _wrap_save_button(dlg)

    try:
        dlg.protocol("WM_DELETE_WINDOW", lambda d=dlg: _request_close(d))
        dlg.bind("<Escape>", lambda _event, d=dlg: _request_close(d))
        dlg.bind("<Control-w>", lambda _event, d=dlg: _request_close(d))
    except Exception:
        pass

    try:
        dlg._wm_close_saved_snapshot = _snapshot(dlg)  # type: ignore[attr-defined]
        dlg._wm_close_guard_ready = True  # type: ignore[attr-defined]
        dlg._wm_tools_editor_runtime = True  # type: ignore[attr-defined]
    except Exception:
        return False

    print("[WM-DBG][TOOLS_EDITOR] ochrona niezapisanych zmian + stały footer aktywne")
    return True


def _install_toplevel_hook() -> None:
    if getattr(tk.Toplevel, "_wm_tools_close_guard_hook", False):
        return

    original_init = tk.Toplevel.__init__

    def _init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        def _try(attempt: int = 0) -> None:
            if not _alive(self):
                return
            if _instrument(self):
                return
            if attempt < 10:
                try:
                    self.after(80, lambda: _try(attempt + 1))
                except Exception:
                    pass

        try:
            self.after(180, _try)
        except Exception:
            pass

    tk.Toplevel.__init__ = _init
    tk.Toplevel._wm_tools_close_guard_hook = True  # type: ignore[attr-defined]
    tk.Toplevel._wm_tools_close_guard_original_init = original_init  # type: ignore[attr-defined]


def install_editor_close_guard_runtime() -> None:
    if getattr(tk.Toplevel, "_wm_tools_close_guard_installed", False):
        return

    # Jeśli wcześniejszy strażnik zdążył się podpiąć, jego callbacki też mają
    # korzystać z wersji odpornej na lazy-load.
    try:
        _runtime._editor_snapshot = _snapshot
        _runtime._request_close = _request_close
    except Exception:
        pass

    _install_toplevel_hook()
    tk.Toplevel._wm_tools_close_guard_installed = True  # type: ignore[attr-defined]


__all__ = ["install_editor_close_guard_runtime"]
