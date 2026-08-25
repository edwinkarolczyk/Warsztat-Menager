from pathlib import Path

p = Path("ui_theme.py")
s = p.read_text(encoding="utf-8")

old_header = '''# version: 1.0
"""Warstwa stylów Warsztat Menager.

Wersja 1.1.1 – dodano strażnika `ensure_theme_applied` z obsługą logowania
i importu wstecznie kompatybilnego.
"""'''
new_header = '''# version: 1.1.2
"""Warstwa stylów Warsztat Menager.

Wersja 1.1.2 – usunięto rekurencyjne, wielokrotne nakładanie motywu podczas
budowy GUI. `ensure_theme_applied` i `Toplevel` stosują motyw tylko raz na okno.

Wersja 1.1.1 – dodano strażnika `ensure_theme_applied` z obsługą logowania
i importu wstecznie kompatybilnego.
"""'''
if old_header not in s:
    raise SystemExit("header block not found")
s = s.replace(old_header, new_header, 1)

old_once = '''def apply_theme_once(
    target: tk.Misc | ttk.Style | None = None,
    *,
    scheme: str | None = None,
    config_path: Path | None = None,
) -> bool:
    """Apply a theme only if the target has not been themed yet.

    Returns True when the theme application was attempted or already applied,
    False otherwise.
    """

    try:
        if isinstance(target, tk.Misc):
            widget = target
        else:
            widget = getattr(target, "master", None)

        if widget is not None and getattr(widget, "_wm_theme_applied", False):
            return True

        fn = _get_apply_fn()
        if not fn:
            return False

        kwargs: dict[str, object] = {}
        if scheme is not None:
            kwargs["scheme"] = scheme
        if config_path is not None:
            kwargs["config_path"] = config_path

        try:
            fn(target, **kwargs)
        except TypeError:
            kwargs.pop("config_path", None)
            fn(target, **kwargs)

        if widget is not None:
            try:
                setattr(widget, "_wm_theme_applied", True)
            except Exception:
                pass
        return True
    except Exception:
        return False
'''
new_once = '''def apply_theme_once(
    target: tk.Misc | ttk.Style | None = None,
    *,
    scheme: str | None = None,
    config_path: Path | None = None,
) -> bool:
    """Zastosuj motyw najwyżej raz dla danego okna/widgetu głównego.

    Nie używa `_get_apply_fn()`, aby uniknąć wybrania samej siebie i rekurencji.
    """

    global _WM_THEME_APPLIED
    try:
        if isinstance(target, tk.Misc):
            widget = target
        else:
            widget = getattr(target, "master", None)

        if widget is not None and getattr(widget, "_wm_theme_applied", False):
            return True

        apply_theme_safe(target, scheme=scheme, config_path=config_path)
        _WM_THEME_APPLIED = True

        if widget is not None:
            try:
                setattr(widget, "_wm_theme_applied", True)
            except Exception:
                pass
        return True
    except Exception:
        logger.exception("apply_theme_once failed")
        return False
'''
if old_once not in s:
    raise SystemExit("apply_theme_once block not found")
s = s.replace(old_once, new_once, 1)

old_tree = '''def apply_theme_tree(
    widget: tk.Misc | None,
    scheme: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Zastosuj motyw dla podanego widgetu i całego jego drzewa potomków."""

    apply_theme_safe(widget, scheme=scheme, config_path=config_path)
    if hasattr(widget, "winfo_children"):
        for child in widget.winfo_children():
            apply_theme_tree(child, scheme=scheme, config_path=config_path)
'''
new_tree = '''def apply_theme_tree(
    widget: tk.Misc | None,
    scheme: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Zastosuj motyw raz dla okna.

    `apply_theme()` już obsługuje istniejące potomki, więc nie przechodzimy
    ponownie rekurencyjnie po każdym widżecie.
    """

    apply_theme_once(widget, scheme=scheme, config_path=config_path)
'''
if old_tree not in s:
    raise SystemExit("apply_theme_tree block not found")
s = s.replace(old_tree, new_tree, 1)

old_get = '''def _get_apply_fn():
    fn = (
        globals().get("apply_theme_once")
        or globals().get("apply_theme_safe")
        or globals().get("apply_theme")
    )
    return fn if callable(fn) else None
'''
new_get = '''def _get_apply_fn():
    # Nigdy nie zwracaj apply_theme_once z wnętrza mechanizmu "once".
    # W przeciwnym razie funkcja może wybrać samą siebie i wejść w rekurencję.
    fn = globals().get("apply_theme_safe") or globals().get("apply_theme")
    return fn if callable(fn) else None
'''
if old_get not in s:
    raise SystemExit("_get_apply_fn block not found")
s = s.replace(old_get, new_get, 1)

old_ensure = '''if "ensure_theme_applied" not in globals():

    def ensure_theme_applied(win):
        try:
            if not win:
                return False
            try:
                attach_fn = globals().get("attach_theme")
                if callable(attach_fn):
                    attach_fn(win)
            except Exception:
                pass
            if getattr(win, "_wm_theme_applied", False):
                return True
            fn = _get_apply_fn()
            if fn:
                try:
                    fn(win)
                except Exception as e:
                    _logger.warning("[THEME] apply_theme* wyjątek: %r", e)
            try:
                setattr(win, "_wm_theme_applied", True)
            except Exception:
                pass
            return True
        except Exception:
            return False
'''
new_ensure = '''if "ensure_theme_applied" not in globals():

    def ensure_theme_applied(win):
        """Idempotentnie zastosuj motyw raz dla danego okna."""
        try:
            if not win:
                return False
            if getattr(win, "_wm_theme_applied", False):
                return True
            return bool(apply_theme_once(win))
        except Exception:
            return False
'''
if old_ensure not in s:
    raise SystemExit("ensure_theme_applied block not found")
s = s.replace(old_ensure, new_ensure, 1)

p.write_text(s, encoding="utf-8")
print("ui_theme.py patched")
