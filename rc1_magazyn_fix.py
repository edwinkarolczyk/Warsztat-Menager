"""Narzędzia pomocnicze dla modułu magazynu (RC1 hotfix)."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable

_TOOLBAR_FLAG = "_rc1_magazyn_toolbar_initialized"


def _looks_like_toolbar(widget: Any) -> bool:
    module = getattr(widget.__class__, "__module__", "")
    return (
        hasattr(widget, "winfo_children")
        and hasattr(widget, "winfo_toplevel")
        and "tkinter" in module
    )


def _pick_toolbar(args: Iterable[Any], kwargs: dict[str, Any]) -> Any | None:
    """Wybierz obiekt toolbaru z argumentów funkcji."""

    args = list(args)
    if args and _looks_like_toolbar(args[0]):
        return args[0]

    for value in args[1:]:
        if _looks_like_toolbar(value):
            return value

    for value in kwargs.values():
        if _looks_like_toolbar(value):
            return value
    return None


def ensure_magazyn_toolbar_once(func: Callable[..., Any]) -> Callable[..., Any]:
    """Dekorator zapobiegający wielokrotnej inicjalizacji paska narzędzi.

    Funkcja dekorowana zostanie wykonana tylko raz dla danego obiektu toolbaru –
    kolejne wywołania z tym samym widżetem zostaną pominięte. Dzięki temu
    przypadkowe ponowne budowanie UI (np. przy resetowaniu widoku) nie doda
    duplikatów przycisków.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        toolbar = _pick_toolbar(args, kwargs)
        if toolbar is None:
            return func(*args, **kwargs)

        if getattr(toolbar, _TOOLBAR_FLAG, False):
            return toolbar

        result = func(*args, **kwargs)
        try:
            setattr(toolbar, _TOOLBAR_FLAG, True)
        except Exception:
            pass
        return result

    return wrapper
