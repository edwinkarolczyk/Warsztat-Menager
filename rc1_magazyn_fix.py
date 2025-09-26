# -*- coding: utf-8 -*-
# RC1: guard przed podwójnym przyciskiem 'Zamówienia' w Magazynie
_MAG_TOOLBAR_INIT = False
def ensure_magazyn_toolbar_once(build_fn):
    def wrapper(*args, **kwargs):
        global _MAG_TOOLBAR_INIT
        if _MAG_TOOLBAR_INIT:
            return
        _MAG_TOOLBAR_INIT = True
        return build_fn(*args, **kwargs)
    return wrapper
