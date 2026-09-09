# version: 1.0
"""Podłączenie Narzędzi do aktywnego kreatora Dyspozycji.

Nie zmienia logiki Narzędzi. Podmienia jedynie punkt wejścia starego
``wm.dyspo_wizard`` na ten sam ``gui_dyspozycje_creator`` którego używają Maszyny.
"""

from __future__ import annotations

import logging
import sys
from typing import Any
from tkinter import messagebox

logger = logging.getLogger(__name__)


def _active_login(root) -> str:
    candidates = [root]
    try:
        if root is not None and hasattr(root, "winfo_toplevel"):
            candidates.append(root.winfo_toplevel())
    except Exception:
        pass

    for source in candidates:
        if source is None:
            continue
        for attr in ("active_login", "current_user", "username", "_wm_login", "login"):
            try:
                value = str(getattr(source, attr, "") or "").strip()
            except Exception:
                value = ""
            if value and value.casefold() not in {"guest", "gość", "gosc", "niezalogowany"}:
                return value
    return "system"


def _normalized_context(context: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(context or {})
    ctx: dict[str, Any] = {
        "typ_dyspozycji": "narzedzie",
        "modul_zrodlowy": "narzedzia",
    }
    ctx.update(incoming)

    # Zgodność z kontekstami używanymi przez starszy wizard.
    if not str(ctx.get("obiekt_id") or "").strip():
        for key in (
            "narzedzie_id",
            "tool_id",
            "nr_narzedzia",
            "nr",
            "numer",
            "id_obiektu",
            "object_id",
        ):
            value = str(ctx.get(key) or "").strip()
            if value:
                ctx["obiekt_id"] = value
                break

    ctx["typ_dyspozycji"] = "narzedzie"
    ctx["modul_zrodlowy"] = "narzedzia"
    return ctx


def install_tools_dysp_creator(gui_module=None) -> bool:
    """Podmień wyłącznie funkcję otwierającą kreator z modułu Narzędzia."""

    module = gui_module or sys.modules.get("gui_narzedzia")
    if module is None:
        return False
    if getattr(module, "_wm_current_dysp_creator_runtime", False):
        return True

    def _open_current_creator(root, context=None):
        try:
            from gui_dyspozycje_creator import open_dyspozycje_creator
        except Exception as exc:
            logger.exception("[NARZEDZIA][DYSP] Brak aktywnego kreatora Dyspozycji.")
            try:
                messagebox.showerror(
                    "Narzędzia",
                    f"Nie udało się otworzyć kreatora Dyspozycji:\n{exc}",
                    parent=root if getattr(root, "tk", None) is not None else None,
                )
            except Exception:
                pass
            return None

        target = root
        if hasattr(root, "winfo_toplevel"):
            try:
                target = root.winfo_toplevel()
            except Exception:
                target = root

        try:
            return open_dyspozycje_creator(
                target,
                autor=_active_login(target),
                context=_normalized_context(context),
            )
        except Exception as exc:
            logger.exception("[NARZEDZIA][DYSP] Błąd otwierania aktywnego kreatora.")
            try:
                messagebox.showerror(
                    "Narzędzia",
                    f"Nie udało się otworzyć kreatora Dyspozycji:\n{exc}",
                    parent=target if getattr(target, "tk", None) is not None else None,
                )
            except Exception:
                pass
            return None

    # Główny helper używany przez bieżące GUI Narzędzi.
    module._maybe_open_dyspo = _open_current_creator

    # Zostawiamy alias dla ewentualnych starszych miejsc wywołujących nazwę
    # open_dyspo_wizard bezpośrednio. Nie importujemy starego wizarda.
    module.open_dyspo_wizard = lambda root, context=None: _open_current_creator(root, context)
    module._wm_current_dysp_creator_runtime = True
    return True


__all__ = ["install_tools_dysp_creator"]
