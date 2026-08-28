# version: 1.1
"""Helpers for binding global keyboard shortcuts."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from wm.settings.util import get_conf


def _active_login(root: tk.Misc) -> str:
    candidates = [root]
    try:
        if hasattr(root, "winfo_toplevel"):
            candidates.append(root.winfo_toplevel())
    except Exception:
        pass
    for source in candidates:
        for attr in ("active_login", "current_user", "username", "_wm_login", "login"):
            try:
                value = str(getattr(source, attr, "") or "").strip()
            except Exception:
                value = ""
            if value and value.casefold() not in {"guest", "gość", "gosc", "niezalogowany"}:
                return value
    return "system"


def _creator_context(context: Optional[dict]) -> dict:
    ctx = dict(context or {})
    module = str(ctx.get("module") or ctx.get("modul_zrodlowy") or "").strip().casefold()
    if not str(ctx.get("typ_dyspozycji") or "").strip():
        if "narz" in module:
            ctx["typ_dyspozycji"] = "narzedzie"
            ctx.setdefault("modul_zrodlowy", "narzedzia")
        elif "maszyn" in module:
            ctx["typ_dyspozycji"] = "maszyna"
            ctx.setdefault("modul_zrodlowy", "maszyny")
    return ctx


def _open_current_creator(root: tk.Misc, context: Optional[dict]) -> None:
    from gui_dyspozycje_creator import open_dyspozycje_creator

    target = root
    try:
        if hasattr(root, "winfo_toplevel"):
            target = root.winfo_toplevel()
    except Exception:
        target = root

    open_dyspozycje_creator(
        target,
        autor=_active_login(target),
        context=_creator_context(context),
    )


def bind_ctrl_d(root: tk.Misc, *, context: Optional[dict] = None) -> None:
    """Bind Ctrl+D shortcut when enabled in the configuration."""

    conf = get_conf()
    enabled = (
        conf.get("dyspo", {})
        .get("shortcuts", {})
        .get("ctrlD", False)
    )
    if not enabled:
        return

    def _handler(event: tk.Event | None = None) -> str:
        try:
            _open_current_creator(root, context or {})
        except Exception:
            return "break"
        return "break"

    if not hasattr(root, "bind"):
        return
    for seq in ("<Control-d>", "<Control-D>"):
        try:
            root.bind(seq, _handler, add="+")
        except Exception:  # pragma: no cover - środowiska testowe bez tk
            return


__all__ = ["bind_ctrl_d"]
