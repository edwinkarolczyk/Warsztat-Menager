import tkinter as tk
import pytest

from ustawienia_systemu import _lines_from_text


def test_lines_from_text_normal():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    try:
        root.withdraw()
        txt = tk.Text(root)
        txt.insert("1.0", "one\n\ntwo\n")
        assert _lines_from_text(txt) == ["one", "two"]
    finally:
        txt.destroy()
        root.destroy()


def test_lines_from_text_destroyed_widget():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    try:
        root.withdraw()
        txt = tk.Text(root)
        txt.insert("1.0", "one\ntwo\n")
        txt.destroy()
        assert _lines_from_text(txt) == []
    finally:
        root.destroy()
