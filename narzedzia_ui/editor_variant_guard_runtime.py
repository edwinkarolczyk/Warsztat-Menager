# version: 1.0
# Moduł: narzedzia_ui.editor_variant_guard_runtime
# Zachowuje techniczny tytuł głównego edytora, którego używają starsze runtime'y
# do rozpoznawania okna. Widoczne dane narzędzia są prezentowane w nowym nagłówku.

from __future__ import annotations

from typing import Any


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}


def install_editor_variant_guard_runtime() -> None:
    try:
        from . import editor_variant_runtime as variant
    except Exception:
        return

    current = getattr(variant, "_sync_new_view", None)
    if not callable(current):
        return
    if getattr(current, "_wm_editor_variant_guard", False):
        return

    original = current

    def _sync_guarded(window, *args: Any, **kwargs: Any):
        try:
            title = str(window.title() or "").strip()
        except Exception:
            title = ""

        canonical = getattr(window, "_wm_tools_editor_canonical_title", "")
        if not canonical and title in _EDITOR_TITLES:
            canonical = title
            try:
                window._wm_tools_editor_canonical_title = canonical
            except Exception:
                pass

        if canonical:
            try:
                window.title(canonical)
            except Exception:
                pass

        try:
            return original(window, *args, **kwargs)
        finally:
            if canonical:
                try:
                    window.title(canonical)
                except Exception:
                    pass

    _sync_guarded._wm_editor_variant_guard = True
    _sync_guarded._wm_editor_variant_original = original
    variant._sync_new_view = _sync_guarded


__all__ = ["install_editor_variant_guard_runtime"]
