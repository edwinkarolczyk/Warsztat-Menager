# -*- coding: utf-8 -*-
"""Ograniczenia RC1 dla modułu Magazyn."""

from __future__ import annotations

from typing import Any, Callable, TypeVar, cast

_MAG_TOOLBAR_INIT = False
_MAG_TOOLBAR_IDS: set[int] = set()
_F = TypeVar("_F", bound=Callable[..., Any])


def ensure_magazyn_toolbar_once(build_fn: _F) -> _F:
    """Zwraca dekorator chroniący przed duplikacją przycisku w toolbarze.

    Funkcja ``build_fn`` zostanie wykonana maksymalnie raz dla danego widgetu
    paska narzędzi.  Jeżeli nie uda się ustalić widgetu (np. dekorator użyty
    bez argumentów), chroni globalnie – wywoła ``build_fn`` tylko przy pierwszym
    wywołaniu.
    """

    marker = "_wm_magazyn_toolbar_orders"

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        global _MAG_TOOLBAR_INIT

        toolbar = args[0] if args else None
        if toolbar is not None:
            toolbar_id = id(toolbar)
            if toolbar_id in _MAG_TOOLBAR_IDS:
                return None

            _MAG_TOOLBAR_IDS.add(toolbar_id)

            try:
                if getattr(toolbar, marker):
                    return None
            except AttributeError:
                pass

            try:
                setattr(toolbar, marker, True)
            except Exception:
                pass

            return build_fn(*args, **kwargs)

        if _MAG_TOOLBAR_INIT:
            return None
        _MAG_TOOLBAR_INIT = True
        return build_fn(*args, **kwargs)

    return cast(_F, wrapper)
