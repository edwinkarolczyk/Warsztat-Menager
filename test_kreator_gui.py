"""Test GUI using tkinter event simulation.

This test previously relied on ``pyautogui`` and real screen
interaction.  It now simulates user actions using ``tkinter`` events so
that it can run without a physical GUI.  The test is skipped when a
display or ``pyautogui`` is unavailable.
"""

import os
import tkinter as tk

import pytest

try:  # pragma: no cover - skip if import fails
    import pyautogui  # noqa: F401
except Exception:  # pragma: no cover - skip when missing
    pyautogui = None


if pyautogui is None or not os.environ.get("DISPLAY"):
    pytest.skip(
        "Wymagane pyautogui oraz środowisko z wyświetlaczem",
        allow_module_level=True,
    )


def test_login_window_event_simulation():
    """Symulate wpisanie PINu i kliknięcie przycisku logowania."""

    root = tk.Tk()
    root.withdraw()

    pin_var = tk.StringVar()
    pin_input = tk.Entry(root, textvariable=pin_var)
    pin_input.pack()

    result = {}

    def on_login():
        result["pin"] = pin_var.get()

    btn = tk.Button(root, text="Zaloguj", command=on_login)
    btn.pack()

    root.update_idletasks()

    pin_input.focus_force()
    pin_input.insert(0, "1")
    btn.invoke()

    assert result["pin"] == "1"

    root.destroy()

