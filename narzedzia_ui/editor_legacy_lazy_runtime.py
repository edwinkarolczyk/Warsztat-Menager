# version: 1.1
# Moduł: narzedzia_ui.editor_legacy_lazy_runtime
# 1.1: po pierwszym wejściu zakładka pozostaje aktywna i kolejne odświeżenia
#      aktualizują ją normalnie także wtedy, gdy chwilowo jest w tle.
# Odkłada pierwsze wypełnianie ciężkich tabel klasycznego rdzenia edytora
# do chwili faktycznego wejścia w odpowiednią zakładkę nowego widoku.
# Nie zmienia modelu danych ani logiki zapisu.

from __future__ import annotations

import time
import weakref
from typing import Any
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant
from . import multistage_runtime as _multistage


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}
_DEFER_OUTER_TABS = {"Zadania", "Historia", "Wizyty"}
_DEFERRED_TREES: "weakref.WeakSet[ttk.Treeview]" = weakref.WeakSet()


def _tab_chain(widget: tk.Misc) -> list[tuple[ttk.Notebook, tk.Misc, str]]:
    chain: list[tuple[ttk.Notebook, tk.Misc, str]] = []
    node: tk.Misc | None = widget
    while node is not None:
        parent = getattr(node, "master", None)
        if isinstance(parent, ttk.Notebook):
            try:
                title = str(parent.tab(node, "text") or "").strip()
            except Exception:
                title = ""
            chain.append((parent, node, title))
        node = parent if isinstance(parent, tk.Misc) else None
    return chain


def _editor_window(widget: tk.Misc) -> tk.Toplevel | None:
    try:
        top = widget.winfo_toplevel()
    except Exception:
        return None
    if not isinstance(top, tk.Toplevel):
        return None
    try:
        title = str(top.title() or "").strip()
    except Exception:
        title = ""
    if title in _EDITOR_TITLES or getattr(widget, "_wm_legacy_lazy_tree", False):
        return top
    return None


def _eligible_tree(tree: ttk.Treeview) -> bool:
    if getattr(tree, "_wm_legacy_lazy_tree", False):
        return True
    if _editor_window(tree) is None:
        return False
    return any(title in _DEFER_OUTER_TABS for _nb, _tab, title in _tab_chain(tree))


def _chain_visible(tree: ttk.Treeview) -> bool:
    chain = _tab_chain(tree)
    if not chain:
        return False
    for notebook, tab, _title in chain:
        try:
            if str(notebook.select()) != str(tab):
                return False
        except Exception:
            return False
    return True


def _tab_path(tree: ttk.Treeview) -> str:
    titles = [title for _nb, _tab, title in reversed(_tab_chain(tree)) if title]
    return " > ".join(titles) or "?"


def _bind_notebook_flush(notebook: ttk.Notebook) -> None:
    if getattr(notebook, "_wm_legacy_lazy_bound", False):
        return

    def _on_tab_changed(_event: Any = None) -> None:
        for tree in list(_DEFERRED_TREES):
            try:
                if not tree.winfo_exists():
                    continue
            except Exception:
                continue
            _flush_tree_if_visible(tree)

    try:
        notebook.bind("<<NotebookTabChanged>>", _on_tab_changed, add="+")
        notebook._wm_legacy_lazy_bound = True  # type: ignore[attr-defined]
    except Exception:
        pass


def _mark_deferred(tree: ttk.Treeview) -> None:
    if getattr(tree, "_wm_legacy_lazy_tree", False):
        return
    tree._wm_legacy_lazy_tree = True  # type: ignore[attr-defined]
    tree._wm_legacy_lazy_loaded = False  # type: ignore[attr-defined]
    tree._wm_legacy_lazy_pending = []  # type: ignore[attr-defined]
    tree._wm_legacy_lazy_counter = 0  # type: ignore[attr-defined]
    _DEFERRED_TREES.add(tree)
    for notebook, _tab, _title in _tab_chain(tree):
        _bind_notebook_flush(notebook)


def _flush_tree_if_visible(tree: ttk.Treeview) -> None:
    if not getattr(tree, "_wm_legacy_lazy_tree", False):
        return
    if getattr(tree, "_wm_legacy_lazy_loaded", False):
        return
    window = _editor_window(tree)
    if window is None or not getattr(window, "_wm_editor_variant_ready", False):
        return
    if not _chain_visible(tree):
        return

    pending = list(getattr(tree, "_wm_legacy_lazy_pending", []) or [])
    tree._wm_legacy_lazy_pending = []  # type: ignore[attr-defined]
    tree._wm_legacy_lazy_loaded = True  # type: ignore[attr-defined]

    started = time.perf_counter()
    inserted = 0
    original_insert = getattr(ttk.Treeview, "_wm_legacy_lazy_original_insert", None)
    if not callable(original_insert):
        return

    for parent, index, iid, kw in pending:
        try:
            original_insert(tree, parent, index, iid=iid, **kw)
            inserted += 1
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][LAZY] "
                f"tab={_tab_path(tree)!r} insert={type(exc).__name__}: {exc}"
            )
    elapsed = (time.perf_counter() - started) * 1000.0
    print(
        "[WM-PERF][TOOLS_EDITOR][LAZY] "
        f"tab={_tab_path(tree)!r} rows={inserted} materialize={elapsed:.1f}ms"
    )


def _install_treeview_lazy_rows() -> None:
    if getattr(ttk.Treeview, "_wm_legacy_lazy_installed", False):
        return

    original_insert = ttk.Treeview.insert
    original_delete = ttk.Treeview.delete
    ttk.Treeview._wm_legacy_lazy_original_insert = original_insert  # type: ignore[attr-defined]
    ttk.Treeview._wm_legacy_lazy_original_delete = original_delete  # type: ignore[attr-defined]

    def _insert_lazy(
        self: ttk.Treeview,
        parent: str,
        index: Any,
        iid: str | None = None,
        **kw: Any,
    ):
        if not _eligible_tree(self):
            return original_insert(self, parent, index, iid=iid, **kw)

        _mark_deferred(self)
        if getattr(self, "_wm_legacy_lazy_loaded", False):
            return original_insert(self, parent, index, iid=iid, **kw)

        window = _editor_window(self)
        if (
            window is not None
            and getattr(window, "_wm_editor_variant_ready", False)
            and _chain_visible(self)
        ):
            _flush_tree_if_visible(self)
            return original_insert(self, parent, index, iid=iid, **kw)

        if iid is None:
            counter = int(getattr(self, "_wm_legacy_lazy_counter", 0) or 0) + 1
            self._wm_legacy_lazy_counter = counter  # type: ignore[attr-defined]
            iid = f"wm_lazy_{id(self):x}_{counter}"

        pending = getattr(self, "_wm_legacy_lazy_pending", None)
        if not isinstance(pending, list):
            pending = []
            self._wm_legacy_lazy_pending = pending  # type: ignore[attr-defined]
        pending.append((parent, index, iid, dict(kw)))
        return iid

    def _delete_lazy(self: ttk.Treeview, *items: str):
        if _eligible_tree(self):
            _mark_deferred(self)
            if not getattr(self, "_wm_legacy_lazy_loaded", False):
                pending = getattr(self, "_wm_legacy_lazy_pending", None)
                if isinstance(pending, list):
                    pending.clear()
                return None
        return original_delete(self, *items)

    ttk.Treeview.insert = _insert_lazy  # type: ignore[assignment]
    ttk.Treeview.delete = _delete_lazy  # type: ignore[assignment]
    ttk.Treeview._wm_legacy_lazy_installed = True  # type: ignore[attr-defined]


def _install_pending_task_counts() -> None:
    current = getattr(_variant, "_task_counts", None)
    if not callable(current) or getattr(current, "_wm_legacy_lazy_counts", False):
        return
    original = current

    def _task_counts_lazy(
        window: tk.Toplevel,
        doc: dict[str, Any],
    ) -> tuple[int, int, int]:
        try:
            tree = _variant._find_tasks_tree(window)
        except Exception:
            tree = None
        if (
            isinstance(tree, ttk.Treeview)
            and getattr(tree, "_wm_legacy_lazy_tree", False)
            and not getattr(tree, "_wm_legacy_lazy_loaded", False)
        ):
            pending = list(getattr(tree, "_wm_legacy_lazy_pending", []) or [])
            top_rows = [row for row in pending if str(row[0] or "") == ""]
            total = len(top_rows)
            done = 0
            for _parent, _index, _iid, kw in top_rows:
                values = kw.get("values")
                if isinstance(values, (list, tuple)) and len(values) > 2:
                    marker = str(values[2] or "").strip().lower()
                    if marker in {"✔", "✓", "tak", "true", "1"}:
                        done += 1
            return total, done, max(0, total - done)
        return original(window, doc)

    _task_counts_lazy._wm_legacy_lazy_counts = True  # type: ignore[attr-defined]
    _task_counts_lazy._wm_legacy_lazy_original = original  # type: ignore[attr-defined]
    _variant._task_counts = _task_counts_lazy


def _install_lazy_multistage_tab() -> None:
    current = getattr(_multistage, "_build_related_tab", None)
    if not callable(current) or getattr(current, "_wm_legacy_lazy_multistage", False):
        return
    original = current

    def _build_related_tab_lazy(
        window: tk.Toplevel,
        notebook: ttk.Notebook,
        group: dict[str, Any],
        current_nr: str,
    ) -> tk.Misc:
        if getattr(window, "_wm_multistage_lazy_materializing", False):
            return original(window, notebook, group, current_nr)

        tab = ttk.Frame(notebook, padding=12, style="WM.Card.TFrame")
        media = _variant._tab_by_text(notebook, "Pliki i zdjęcia")
        if media is not None:
            try:
                notebook.insert(
                    notebook.index(media),
                    tab,
                    text="Powiązane narzędzia",
                )
            except Exception:
                notebook.add(tab, text="Powiązane narzędzia")
        else:
            notebook.add(tab, text="Powiązane narzędzia")

        ttk.Label(
            tab,
            text="Powiązane narzędzia zostaną wczytane po wejściu w tę zakładkę.",
            style="WM.Muted.TLabel",
            anchor="center",
        ).pack(fill="both", expand=True, padx=24, pady=24)

        state = {"loaded": False, "bind_id": None}

        def _materialize(_event: Any = None) -> None:
            if state["loaded"]:
                return
            try:
                if str(notebook.select()) != str(tab):
                    return
                if not tab.winfo_exists():
                    return
            except Exception:
                return

            state["loaded"] = True
            started = time.perf_counter()
            try:
                notebook.forget(tab)
            except Exception:
                pass
            try:
                tab.destroy()
            except Exception:
                pass

            try:
                window._wm_multistage_lazy_materializing = True  # type: ignore[attr-defined]
                new_tab = original(window, notebook, group, current_nr)
                window._wm_multistage_tab = new_tab  # type: ignore[attr-defined]
                try:
                    notebook.select(new_tab)
                except Exception:
                    pass
            finally:
                try:
                    window._wm_multistage_lazy_materializing = False  # type: ignore[attr-defined]
                except Exception:
                    pass

            elapsed = (time.perf_counter() - started) * 1000.0
            print(
                "[WM-PERF][TOOLS_EDITOR][LAZY] "
                f"tab='Powiązane narzędzia' first_load={elapsed:.1f}ms"
            )
            bind_id = state.get("bind_id")
            if bind_id:
                try:
                    notebook.unbind("<<NotebookTabChanged>>", bind_id)
                except Exception:
                    pass

        try:
            state["bind_id"] = notebook.bind(
                "<<NotebookTabChanged>>",
                _materialize,
                add="+",
            )
        except Exception:
            state["bind_id"] = None
        return tab

    _build_related_tab_lazy._wm_legacy_lazy_multistage = True  # type: ignore[attr-defined]
    _build_related_tab_lazy._wm_legacy_lazy_original = original  # type: ignore[attr-defined]
    _multistage._build_related_tab = _build_related_tab_lazy


def _install_primary_photo_box_finish() -> None:
    current = getattr(_variant, "_decorate_editor", None)
    if not callable(current) or getattr(current, "_wm_legacy_lazy_photo_box", False):
        return
    original = current

    def _decorate_with_large_primary(window: tk.Toplevel) -> bool:
        result = original(window)
        if not result:
            return result
        try:
            _main, header, _notebook = _variant._editor_parts(window)
            thumb = getattr(header, "_wm_thumb", None) if header is not None else None
            if thumb is not None:
                box = getattr(thumb, "master", None)
                if box is not None:
                    box.configure(width=380, height=250)
                    box.pack_propagate(False)
                # width/height=0 pozwala obrazowi 360x230 użyć jego naturalnego rozmiaru.
                thumb.configure(width=0, height=0)
                thumb.pack_configure(
                    fill="both",
                    expand=True,
                    padx=6,
                    pady=6,
                )
        except Exception:
            pass
        return result

    _decorate_with_large_primary._wm_legacy_lazy_photo_box = True  # type: ignore[attr-defined]
    _decorate_with_large_primary._wm_legacy_lazy_original = original  # type: ignore[attr-defined]
    _variant._decorate_editor = _decorate_with_large_primary


def install_editor_legacy_lazy_runtime() -> None:
    if getattr(_variant, "_wm_editor_legacy_lazy_installed", False):
        return
    _install_treeview_lazy_rows()
    _install_pending_task_counts()
    _install_lazy_multistage_tab()
    _install_primary_photo_box_finish()
    _variant._wm_editor_legacy_lazy_installed = True
    print("[WM-DBG][TOOLS_EDITOR] legacy tab rows lazy-load aktywny")


__all__ = ["install_editor_legacy_lazy_runtime"]
