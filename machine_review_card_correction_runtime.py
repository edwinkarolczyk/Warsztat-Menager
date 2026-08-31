# version: 1.0
"""Przycisk Korekta wpisu w karcie serwisowej maszyny dla Brygadzisty.

Runtime jest celowo wąski: przechwytuje wyłącznie komunikat
``Karta serwisowa maszyny`` w module Maszyny. Pozostałe messageboxy są
przekazywane bez zmian do oryginalnego tkinter.messagebox.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_CARD_TITLE = "Karta serwisowa maszyny"


def _selected_tree_state(parent: Any) -> tuple[Any | None, tuple[str, ...]]:
    tree = getattr(parent, "_wm_review_correction_tree", None)
    if tree is None:
        return None, ()
    try:
        selected = tuple(str(item) for item in (tree.selection() or ()))
    except Exception:
        return None, ()
    return tree, selected


def _restore_selected_tree(parent: Any, tree: Any, selected: tuple[str, ...]) -> None:
    if tree is None or not selected:
        return
    try:
        valid = [item for item in selected if bool(tree.exists(item))]
        if not valid:
            return
        tree.selection_set(valid)
        tree.focus(valid[0])
        parent._wm_review_correction_tree = tree
    except Exception:
        logger.exception("[Maszyny][CARD_CORRECTION] Nie udało się odtworzyć zaznaczenia.")


def _show_foreman_card(
    parent: Any,
    gui_module: Any,
    original_box: Any,
    message: str,
) -> str:
    """Pokaż kartę z przyciskiem korekty i zachowaj dokładne zaznaczenie wpisu."""
    try:
        from machine_review_correction_runtime import (
            _active_role,
            _open_correction_dialog,
            _selected_review_context,
        )
    except Exception:
        logger.exception("[Maszyny][CARD_CORRECTION] Brak runtime korekty.")
        return original_box.showinfo(_CARD_TITLE, message, parent=parent)

    try:
        if _active_role(parent) != "brygadzista":
            return original_box.showinfo(_CARD_TITLE, message, parent=parent)
        if _selected_review_context(parent) is None:
            return original_box.showinfo(_CARD_TITLE, message, parent=parent)
    except Exception:
        logger.exception("[Maszyny][CARD_CORRECTION] Nie udało się potwierdzić kontekstu.")
        return original_box.showinfo(_CARD_TITLE, message, parent=parent)

    ttk = getattr(gui_module, "ttk", None)
    tk_module = getattr(gui_module, "tk", None)
    if ttk is None or tk_module is None:
        return original_box.showinfo(_CARD_TITLE, message, parent=parent)

    base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
    real_toplevel = getattr(base_tk, "Toplevel", None)
    if real_toplevel is None:
        return original_box.showinfo(_CARD_TITLE, message, parent=parent)

    tree, selected = _selected_tree_state(parent)
    action = {"correct": False}

    try:
        card = real_toplevel(parent)
        card.title(_CARD_TITLE)
        card.resizable(False, False)
        card.transient(parent)

        outer = ttk.Frame(card, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=str(message or ""),
            justify="left",
            anchor="nw",
            wraplength=520,
        ).pack(fill="both", expand=True)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(14, 0))

        def _correct() -> None:
            action["correct"] = True
            card.destroy()

        ttk.Button(
            buttons,
            text="Korekta wpisu",
            command=_correct,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Zamknij",
            command=card.destroy,
        ).pack(side="right")

        card.protocol("WM_DELETE_WINDOW", card.destroy)
        card.update_idletasks()
        try:
            width = max(520, int(card.winfo_reqwidth()))
            height = max(360, int(card.winfo_reqheight()))
            px = int(parent.winfo_rootx()) + max(0, (int(parent.winfo_width()) - width) // 2)
            py = int(parent.winfo_rooty()) + max(0, (int(parent.winfo_height()) - height) // 2)
            card.geometry(f"{width}x{height}+{px}+{py}")
        except Exception:
            pass

        try:
            card.grab_set()
            card.focus_set()
        except Exception:
            pass

        card.wait_window()
    except Exception:
        logger.exception("[Maszyny][CARD_CORRECTION] Nie udało się pokazać karty.")
        return original_box.showinfo(_CARD_TITLE, message, parent=parent)

    if action["correct"]:
        _restore_selected_tree(parent, tree, selected)
        try:
            if parent.winfo_exists():
                _open_correction_dialog(parent, gui_module)
        except Exception as exc:
            logger.exception("[Maszyny][CARD_CORRECTION] Nie udało się otworzyć korekty.")
            try:
                original_box.showerror(
                    "Korekta wpisu",
                    f"Nie udało się otworzyć korekty:\n{exc}",
                    parent=parent,
                )
            except Exception:
                pass
    return "ok"


class _MessageboxProxy:
    _wm_review_card_proxy = True

    def __init__(self, original: Any, gui_module: Any) -> None:
        self._original = original
        self._gui_module = gui_module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)

    def showinfo(self, title: str, message: str, *args: Any, **kwargs: Any):
        parent = kwargs.get("parent")
        if str(title or "") == _CARD_TITLE and parent is not None:
            try:
                return _show_foreman_card(
                    parent,
                    self._gui_module,
                    self._original,
                    str(message or ""),
                )
            except Exception:
                logger.exception("[Maszyny][CARD_CORRECTION] Błąd adaptera karty.")
        return self._original.showinfo(title, message, *args, **kwargs)


def install_machine_review_card_correction(gui_module: Any) -> bool:
    """Dodaj Korekta wpisu tylko do karty serwisowej oglądanej przez Brygadzistę."""
    if gui_module is None:
        return False
    original = getattr(gui_module, "messagebox", None)
    if original is None:
        return False
    if getattr(original, "_wm_review_card_proxy", False):
        return True
    gui_module.messagebox = _MessageboxProxy(original, gui_module)
    return True


__all__ = ["install_machine_review_card_correction"]
