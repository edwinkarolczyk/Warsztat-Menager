# version: 1.0
# Moduł: settings_unused_runtime
# UI-only: ukrywa sekcje, których wartości nie są obecnie używane przez logikę WM.

from __future__ import annotations

from typing import Any


def _hide_unused_orders_settings(panel: Any) -> None:
    nb = getattr(panel, "_modules_nb", None)
    if nb is None:
        return
    for tab_id in list(nb.tabs()):
        try:
            title = str(nb.tab(tab_id, "text") or "").strip().lower()
        except Exception:
            continue
        if title == "zamówienia":
            try:
                nb.forget(tab_id)
            except Exception:
                pass
            break


def install_settings_unused_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_unused_runtime", False):
        return
    original = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original):
        return

    def _build_ui_without_dead_settings(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        _hide_unused_orders_settings(self)
        return result

    settings_panel_cls._build_ui = _build_ui_without_dead_settings
    settings_panel_cls._wm_settings_unused_runtime = True
