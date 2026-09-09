# version: 1.1
# Moduł: narzedzia_ui.editor_compact_history_runtime
# - Usuwa pusty kontener starego Opisu, który nadal zajmował miejsce w Informacjach.
# - Pole „Nowy wpis” ma maksymalnie 3 linie wysokości; historia wykorzystuje resztę zakładki.
# - Historia narzędzia grupuje zdarzenia z tej samej minuty w rozwijany wiersz drzewa.
# - Główne zdjęcie korzysta z jednego stałego callbacku „Dodaj zdjęcia” i odświeża się natychmiast.
# - Brak zdjęcia zawsze uruchamia dodawanie zdjęcia; podgląd DXF nie zastępuje tej akcji.
# - Zmiana historii dotyczy wyłącznie prezentacji; nie zmienia formatu historii ani sposobu zapisu danych.

from __future__ import annotations

from datetime import datetime
from typing import Any
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant
from . import editor_lazy_media_runtime as _lazy
from . import editor_polish_runtime as _polish


_HISTORY_COLUMNS = ("ts", "by", "action", "details")


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


def _hide(widget: tk.Misc | None) -> None:
    if widget is None:
        return
    for method in ("pack_forget", "grid_remove", "place_forget"):
        try:
            getattr(widget, method)()
        except Exception:
            continue


def _compact_information_tab(window: tk.Toplevel, notebook: ttk.Notebook) -> None:
    tab = _variant._tab_by_text(notebook, "Informacje")
    if tab is None:
        return

    host = None
    for child in list(tab.winfo_children()):
        if getattr(child, "_wm_information_history_ui", False):
            host = child
            break
    if host is None:
        return

    # Stary desc_frame pozostał spakowany jako fill/expand. Jego zawartość była
    # ukryta, ale sam pusty frame nadal zabierał większość wysokości zakładki.
    for child in list(tab.winfo_children()):
        if child is not host:
            _hide(child)

    try:
        host.pack_configure(fill="both", expand=True)
    except Exception:
        pass

    history = getattr(window, "_wm_information_history", None)
    for widget in _walk(host):
        if not isinstance(widget, tk.Text) or widget is history:
            continue
        try:
            widget.configure(height=3)
        except Exception:
            pass
        break


def _minute_key(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    iso = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            continue

    # Dla starszych wpisów zachowaj zgodność bez zgadywania daty. Jeżeli zapis
    # wygląda jak ISO, sekundy są pomijane, bo widok historii i tak pokazuje minuty.
    if len(raw) >= 16 and raw[4:5] == "-" and raw[7:8] == "-":
        return raw[:16].replace("T", " ")
    return raw


def _event_count_label(count: int) -> str:
    if count == 1:
        return "1 zdarzenie"
    if 2 <= count <= 4:
        return f"{count} zdarzenia"
    return f"{count} zdarzeń"


def _actors_label(rows: list[tuple[Any, ...]]) -> str:
    actors: list[str] = []
    for row in rows:
        actor = str(row[1] if len(row) > 1 else "").strip()
        if actor and actor not in actors:
            actors.append(actor)
    if not actors:
        return "—"
    if len(actors) <= 2:
        return ", ".join(actors)
    return f"{len(actors)} osoby"


def _group_rows(rows: list[tuple[Any, ...]]):
    ordered: list[tuple[str, list[tuple[Any, ...]]]] = []
    positions: dict[str, int] = {}

    for index, row in enumerate(rows):
        values = tuple(row)
        key = _minute_key(values[0] if values else "")
        token = key if key else f"__wm_history_row_{index}"
        if key and token in positions:
            ordered[positions[token]][1].append(values)
            continue
        positions[token] = len(ordered)
        ordered.append((key, [values]))
    return ordered


def _emit_grouped_rows(
    tree: ttk.Treeview,
    insert_fn,
    rows: list[tuple[Any, ...]],
) -> None:
    group_no = 0
    for minute, grouped in _group_rows(rows):
        if len(grouped) <= 1:
            insert_fn("", "end", values=grouped[0])
            continue

        group_no += 1
        parent_iid = f"wm_hist_group_{id(tree):x}_{group_no}"
        summary = (
            minute or str(grouped[0][0] if grouped[0] else ""),
            _actors_label(grouped),
            _event_count_label(len(grouped)),
            "Rozwiń, aby zobaczyć szczegóły",
        )
        try:
            parent = insert_fn(
                "",
                "end",
                iid=parent_iid,
                text="",
                values=summary,
                tags=("wm_history_group",),
                open=False,
            )
        except Exception:
            parent = insert_fn(
                "",
                "end",
                text="",
                values=summary,
                tags=("wm_history_group",),
                open=False,
            )
        for values in grouped:
            insert_fn(parent, "end", text="", values=values)


def _history_tree(notebook: ttk.Notebook) -> ttk.Treeview | None:
    tab = _variant._tab_by_text(notebook, "Historia")
    if tab is None:
        return None
    for widget in _walk(tab):
        if not isinstance(widget, ttk.Treeview):
            continue
        try:
            columns = tuple(str(value) for value in widget.cget("columns"))
        except Exception:
            continue
        if columns == _HISTORY_COLUMNS:
            return widget
    return None


def _install_history_grouping(tree: ttk.Treeview) -> None:
    if getattr(tree, "_wm_history_grouping_ready", False):
        return

    try:
        tree.configure(show="tree headings")
        tree.heading("#0", text="")
        tree.column("#0", width=30, minwidth=30, stretch=False, anchor="center")
        tree.tag_configure("wm_history_group", font=("Segoe UI", 9, "bold"))
    except Exception:
        pass

    # Pobieramy metodę z klasy, a nie z instancji. Dzięki temu zachowujemy
    # istniejący lazy-load z editor_legacy_lazy_runtime.
    base_insert = ttk.Treeview.insert.__get__(tree, ttk.Treeview)
    base_delete = ttk.Treeview.delete.__get__(tree, ttk.Treeview)
    state: dict[str, Any] = {
        "collecting": False,
        "rows": [],
        "job": None,
        "counter": 0,
    }

    def _cancel_job() -> None:
        job = state.get("job")
        if not job:
            return
        try:
            tree.after_cancel(job)
        except Exception:
            pass
        state["job"] = None

    def _flush() -> None:
        state["job"] = None
        rows = list(state.get("rows") or [])
        state["rows"] = []
        state["collecting"] = False
        if rows and _alive(tree):
            _emit_grouped_rows(tree, base_insert, rows)

    def _delete_grouped(*items: str):
        _cancel_job()
        state["rows"] = []
        state["collecting"] = True
        return base_delete(*items)

    def _insert_grouped(
        parent: str,
        index: Any,
        iid: str | None = None,
        **kw: Any,
    ):
        if state.get("collecting") and str(parent or "") == "":
            values = tuple(kw.get("values") or ())
            state["rows"].append(values)
            state["counter"] = int(state.get("counter") or 0) + 1
            if not state.get("job"):
                try:
                    state["job"] = tree.after_idle(_flush)
                except Exception:
                    _flush()
            return iid or f"wm_hist_pending_{id(tree):x}_{state['counter']}"
        return base_insert(parent, index, iid=iid, **kw)

    # Pierwsze wypełnienie Historii może już czekać w buforze lazy-load.
    # Grupujemy ten bufor zanim zakładka zostanie pierwszy raz pokazana.
    pending = list(getattr(tree, "_wm_legacy_lazy_pending", []) or [])
    if pending and not getattr(tree, "_wm_legacy_lazy_loaded", False):
        rows = [
            tuple(kw.get("values") or ())
            for parent, _index, _iid, kw in pending
            if str(parent or "") == ""
        ]
        try:
            tree._wm_legacy_lazy_pending = []
        except Exception:
            pass
        if rows:
            _emit_grouped_rows(tree, base_insert, rows)
    else:
        try:
            top_rows = list(tree.get_children(""))
        except Exception:
            top_rows = []
        if top_rows:
            rows = [tuple(tree.item(iid, "values") or ()) for iid in top_rows]
            try:
                base_delete(*top_rows)
            except Exception:
                rows = []
            if rows:
                _emit_grouped_rows(tree, base_insert, rows)

    # repaint_hist() jest funkcją lokalną starego rdzenia. Przechwytując wyłącznie
    # insert/delete na tym konkretnym Treeview, każde kolejne odświeżenie nadal
    # korzysta z jego logiki, ale wynik jest automatycznie składany w grupy.
    try:
        tree.insert = _insert_grouped  # type: ignore[method-assign]
        tree.delete = _delete_grouped  # type: ignore[method-assign]
        tree._wm_history_grouping_ready = True
    except Exception:
        pass


def _find_button(root: tk.Misc | None, text: str) -> ttk.Button | None:
    if root is None:
        return None
    wanted = str(text or "").strip()
    widgets = [root, *_walk(root)]
    for widget in widgets:
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text") or "").strip() == wanted:
                return widget
        except Exception:
            continue
    return None


def _install_primary_photo_interaction(
    window: tk.Toplevel,
    header: tk.Misc | None,
    notebook: ttk.Notebook,
) -> None:
    if getattr(window, "_wm_primary_photo_interaction_ready", False):
        return
    if header is None:
        return

    thumb = getattr(header, "_wm_thumb", None)
    if thumb is None or not _alive(thumb):
        return

    media_tab = _variant._tab_by_text(notebook, "Pliki i zdjęcia")
    add_button = _find_button(media_tab, "Dodaj zdjęcia")
    if add_button is None:
        print(
            "[WM-ERR][TOOLS_EDITOR][MEDIA] nie znaleziono przycisku „Dodaj zdjęcia”"
        )
        return

    def _select_images() -> bool:
        if not _alive(add_button):
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] przycisk „Dodaj zdjęcia” nie istnieje"
            )
            return False
        before = tuple(_variant._image_values(window))
        print(
            "[WM-DBG][TOOLS_EDITOR][MEDIA] "
            f"PHOTO_ADD_CLICK before={len(before)}"
        )
        try:
            add_button.invoke()
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                f"PHOTO_ADD_FAIL {type(exc).__name__}: {exc}"
            )
            return False

        after = tuple(_variant._image_values(window))
        if after == before:
            print(
                "[WM-DBG][TOOLS_EDITOR][MEDIA] "
                "PHOTO_ADD_NOCHANGE"
            )
            return False

        print(
            "[WM-DBG][TOOLS_EDITOR][MEDIA] "
            f"PHOTO_SELECTED count={len(after)}"
        )
        try:
            _lazy._invalidate_media_cache(window)
            _lazy._refresh_primary_photo(window, header)
            print(
                "[WM-DBG][TOOLS_EDITOR][MEDIA] PHOTO_REFRESH immediate=1"
            )
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                f"PHOTO_REFRESH_FAIL {type(exc).__name__}: {exc}"
            )

        try:
            if media_tab is not None:
                media_tab._wm_polish_thumb_key = None  # type: ignore[attr-defined]
                if _lazy._selected_tab_title(window) == "Pliki i zdjęcia":
                    _polish._refresh_thumbnail_grid(window, media_tab)
        except Exception:
            pass
        try:
            _polish._schedule_dirty(window, delay_ms=0)
        except Exception:
            pass
        return True

    def _primary_click(_event: Any = None) -> None:
        try:
            images = tuple(_variant._image_values(window))
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                f"PHOTO_STATE_FAIL {type(exc).__name__}: {exc}"
            )
            images = ()

        # DXF nie jest zdjęciem głównym. Jeśli nie ma prawdziwego zdjęcia,
        # kliknięcie zawsze prowadzi do dodawania obrazu.
        if not images:
            _select_images()
            return

        try:
            window._wm_editor_gallery_index = 0  # type: ignore[attr-defined]
            _lazy._open_primary_only(window)
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                f"PHOTO_PREVIEW_FAIL {type(exc).__name__}: {exc}"
            )

    def _media_changed(_event: Any = None) -> None:
        if not _alive(window):
            return

        def _refresh() -> None:
            if not _alive(window):
                return
            try:
                _lazy._invalidate_media_cache(window)
                _lazy._refresh_primary_photo(window, header)
                print(
                    "[WM-DBG][TOOLS_EDITOR][MEDIA] PHOTO_REFRESH event=1"
                )
            except Exception as exc:
                print(
                    "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                    f"PHOTO_EVENT_REFRESH_FAIL {type(exc).__name__}: {exc}"
                )

        try:
            window.after_idle(_refresh)
        except Exception:
            _refresh()

    try:
        window._wm_tool_image_select = _select_images  # type: ignore[attr-defined]
        thumb.configure(cursor="hand2")
        # Bez add="+": ten finalny handler zastępuje wcześniejsze, kruche
        # wyszukiwanie ukrytego przycisku „Obraz → Wybierz...”.
        thumb.bind("<Button-1>", _primary_click)
        window.bind("<<ToolMediaChanged>>", _media_changed, add="+")
        window._wm_primary_photo_interaction_ready = True
    except Exception as exc:
        print(
            "[WM-ERR][TOOLS_EDITOR][MEDIA] "
            f"PHOTO_BIND_FAIL {type(exc).__name__}: {exc}"
        )


def _install_editor_postprocess() -> None:
    current = getattr(_variant, "_decorate_editor", None)
    if not callable(current) or getattr(current, "_wm_compact_history_runtime", False):
        return
    original = current

    def _decorate_compact_history(window: tk.Toplevel) -> bool:
        result = original(window)
        if not result:
            return result
        try:
            _main, header, notebook = _variant._editor_parts(window)
        except Exception:
            header = None
            notebook = None
        if notebook is None:
            return result

        try:
            _compact_information_tab(window, notebook)
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][INFO_LAYOUT] "
                f"{type(exc).__name__}: {exc}"
            )
        try:
            tree = _history_tree(notebook)
            if tree is not None:
                _install_history_grouping(tree)
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][HISTORY_GROUP] "
                f"{type(exc).__name__}: {exc}"
            )
        try:
            _install_primary_photo_interaction(window, header, notebook)
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MEDIA] "
                f"PHOTO_SETUP_FAIL {type(exc).__name__}: {exc}"
            )
        return result

    _decorate_compact_history._wm_compact_history_runtime = True
    _decorate_compact_history._wm_compact_history_original = original
    _variant._decorate_editor = _decorate_compact_history


def install_editor_compact_history_runtime() -> None:
    if getattr(_variant, "_wm_editor_compact_history_installed", False):
        return
    _install_editor_postprocess()
    _variant._wm_editor_compact_history_installed = True
    print(
        "[WM-DBG][TOOLS_EDITOR] kompaktowe Informacje + grupowanie Historii "
        "+ stabilne kliknięcie zdjęcia aktywne"
    )


__all__ = ["install_editor_compact_history_runtime"]