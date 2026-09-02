# version: 1.1
"""Mały guard nowego edytora Narzędzi: martwe widgety Tk, media i autor informacji."""
from __future__ import annotations

from typing import Any
import tkinter as tk

from . import editor_variant_runtime as _variant


def _normalized_images(doc: dict[str, Any] | None) -> list[str]:
    if not isinstance(doc, dict):
        return []
    result: list[str] = []
    images = doc.get("obrazy")
    if isinstance(images, list):
        result.extend(str(item).strip() for item in images if str(item or "").strip())
    elif isinstance(images, str) and images.strip():
        result.append(images.strip())
    legacy = doc.get("obraz")
    if isinstance(legacy, str):
        legacy = legacy.strip()
        if legacy and legacy not in result:
            result.append(legacy)
    return result


def _logged_wm_actor() -> str:
    """Zwróć login aktywnej sesji WM; nigdy nie używaj loginu/nazwy Windows."""
    try:
        import gui_panel

        root = getattr(tk, "_default_root", None)
        getter = getattr(gui_panel, "wm_get_logged_login", None)
        if root is not None and callable(getter):
            login = str(getter(root) or "").strip()
            if login:
                return login
    except Exception:
        pass

    try:
        from services.profile_service import ProfileService

        login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        if login:
            return login
    except Exception:
        pass

    return "—"


def _install_information_actor_guard() -> None:
    """Podmień stary fallback USERNAME/USER na kanoniczną sesję Warsztat Menager."""
    try:
        from . import editor_header_info_runtime as _info
    except Exception:
        return
    current = getattr(_info, "_actor", None)
    if not callable(current) or getattr(current, "_wm_session_actor", False):
        return

    def _actor_from_wm_session() -> str:
        return _logged_wm_actor()

    _actor_from_wm_session._wm_session_actor = True  # type: ignore[attr-defined]
    _actor_from_wm_session._wm_actor_original = current  # type: ignore[attr-defined]
    _info._actor = _actor_from_wm_session


def install_editor_media_guard_runtime() -> None:
    """Zainstaluj zabezpieczenia nowego edytora zdjęć i autora informacji."""

    _install_information_actor_guard()

    current_descendants = getattr(_variant, "_all_descendants", None)
    if callable(current_descendants) and not getattr(
        current_descendants, "_wm_media_safe_descendants", False
    ):
        def _safe_all_descendants(widget: tk.Misc):
            try:
                children = widget.winfo_children()
            except (tk.TclError, RuntimeError):
                return
            except Exception:
                return
            for child in children:
                yield child
                yield from _safe_all_descendants(child)

        _safe_all_descendants._wm_media_safe_descendants = True  # type: ignore[attr-defined]
        _safe_all_descendants._wm_media_original = current_descendants  # type: ignore[attr-defined]
        _variant._all_descendants = _safe_all_descendants

    current_images = getattr(_variant, "_image_values", None)
    if not callable(current_images) or getattr(
        current_images, "_wm_media_json_fallback", False
    ):
        return

    original_images = current_images

    def _image_values_with_json_fallback(
        window: tk.Toplevel,
        doc: dict[str, Any] | None = None,
    ) -> list[str]:
        live_getter = getattr(window, "_wm_tool_images_get", None)
        if not callable(live_getter):
            return original_images(window, doc)

        try:
            raw_live = live_getter()
        except Exception:
            raw_live = []
        live = (
            [str(item).strip() for item in raw_live if str(item or "").strip()]
            if isinstance(raw_live, (list, tuple))
            else []
        )
        if live:
            return live

        json_doc = doc if isinstance(doc, dict) and doc else None
        if json_doc is None:
            try:
                json_doc = _variant._current_doc(window)
            except Exception:
                json_doc = {}
        fallback = _normalized_images(json_doc)

        try:
            nr = _variant._entry_value_from_field(window, "Numer (3 cyfry)") or "?"
        except Exception:
            nr = "?"
        token = (nr, len(live), len(fallback))
        if getattr(window, "_wm_media_guard_log_token", None) != token:
            print(
                "[WM-DBG][TOOLS_EDITOR][MEDIA] "
                f"nr={nr} json_obrazy={len(fallback)} live_images={len(live)} "
                f"fallback={'tak' if fallback else 'nie'}"
            )
            try:
                window._wm_media_guard_log_token = token  # type: ignore[attr-defined]
            except Exception:
                pass
        return fallback

    _image_values_with_json_fallback._wm_media_json_fallback = True  # type: ignore[attr-defined]
    _image_values_with_json_fallback._wm_media_original = original_images  # type: ignore[attr-defined]
    _variant._image_values = _image_values_with_json_fallback


__all__ = ["install_editor_media_guard_runtime"]
