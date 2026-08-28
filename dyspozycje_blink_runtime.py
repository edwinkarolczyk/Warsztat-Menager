# version: 1.0
"""Miganie zaległych Dyspozycji pomiędzy czerwonym a kolorem ich statusu."""

from __future__ import annotations

from typing import Any


_BASE_TAG_BY_LABEL = {
    "nowa": "dysp_new",
    "w toku": "dysp_in_progress",
    "wstrzymana": "dysp_paused",
}


def install_dyspozycje_status_blink(gui_module: Any) -> None:
    """Podmień wyłącznie Treeview modułu Dyspozycji.

    Zaległa Dyspozycja miga:
    - Nowa: czerwony <-> żółty,
    - W toku: czerwony <-> niebieski,
    - Wstrzymana: czerwony <-> pomarańczowy.

    Pozostałe Treeview i logika statusów nie są zmieniane.
    """

    if gui_module is None or getattr(gui_module, "_wm_status_blink_installed", False):
        return

    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None:
        return

    base_treeview = getattr(ttk_module, "Treeview", None)
    if base_treeview is None or getattr(base_treeview, "_wm_status_blink_proxy", False):
        gui_module._wm_status_blink_installed = True
        return

    class _StatusBlinkTreeview(base_treeview):
        _wm_status_blink_proxy = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._wm_overdue_base_tags: dict[str, str] = {}
            self._wm_logical_tags: dict[str, tuple[str, ...]] = {}

        def insert(self, parent, index, iid=None, **kw):
            values = tuple(kw.get("values") or ())
            tags = tuple(kw.get("tags") or ())
            created_iid = super().insert(parent, index, iid=iid, **kw)
            key = str(created_iid)
            self._wm_logical_tags[key] = tags

            if "dysp_overdue" in tags:
                status_label = str(values[2] if len(values) > 2 else "").strip().casefold()
                base_tag = _BASE_TAG_BY_LABEL.get(status_label)
                if base_tag:
                    self._wm_overdue_base_tags[key] = base_tag
            return created_iid

        def item(self, item, option=None, **kw):
            key = str(item)

            if option == "tags" and not kw:
                logical = self._wm_logical_tags.get(key)
                if logical is not None:
                    return logical
                return super().item(item, option)

            if "tags" in kw:
                proposed = tuple(kw.get("tags") or ())
                self._wm_logical_tags[key] = proposed
                base_tag = self._wm_overdue_base_tags.get(key)
                if base_tag:
                    proposed_set = set(proposed)
                    if "dysp_overdue_blink" in proposed_set:
                        # Faza alarmowa: czerwony kolor zaległości.
                        kw["tags"] = ("dysp_overdue",)
                    elif "dysp_overdue" in proposed_set:
                        # Druga faza: normalny kolor aktualnego statusu.
                        kw["tags"] = (base_tag,)

            return super().item(item, option, **kw)

        def delete(self, *items):
            for item in items:
                key = str(item)
                self._wm_overdue_base_tags.pop(key, None)
                self._wm_logical_tags.pop(key, None)
            return super().delete(*items)

    ttk_module.Treeview = _StatusBlinkTreeview
    gui_module._wm_status_blink_installed = True
