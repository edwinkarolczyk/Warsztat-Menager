# -*- coding: utf-8 -*-
# RC1: poprawa kontrastu napisów w przyciskach (motyw default)

from __future__ import annotations


def apply_theme_fixes() -> None:
    try:
        import tkinter as tk
        from tkinter import ttk

        _root = tk._get_default_root() or tk.Tk()
        style = ttk.Style()
        style.configure("TButton", foreground="#FFFFFF")
        style.map(
            "TButton",
            foreground=[("active", "#FFFFFF"), ("disabled", "#AAAAAA")],
        )
        for style_name in ("WM.Side.TButton", "WM.Toolbar.TButton"):
            try:
                style.configure(style_name, foreground="#FFFFFF")
                style.map(
                    style_name,
                    foreground=[("active", "#FFFFFF"), ("disabled", "#AAAAAA")],
                )
            except Exception:
                pass
    except Exception:
        pass


apply_theme_fixes()
