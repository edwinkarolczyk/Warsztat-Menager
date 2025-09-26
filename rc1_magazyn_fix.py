# -*- coding: utf-8 -*-
# RC1: guard przed podwójnym przyciskiem 'Zamówienia' w Magazynie

from __future__ import annotations

_MAG_TOOLBAR_INIT = False


def ensure_magazyn_toolbar_once(build_fn):
    """Dekorator: wywoła build_fn tylko raz (chroni przed duplikatami przycisków)."""

    def wrapper(*args, **kwargs):
        global _MAG_TOOLBAR_INIT
        if _MAG_TOOLBAR_INIT:
            return None
        _MAG_TOOLBAR_INIT = True
        return build_fn(*args, **kwargs)

    return wrapper
