import pytest
import tkinter as tk
from tkinter import ttk
from gui import panel as gui_panel


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


class DummyCM:
    def get(self, key, default=None):
        if key == "auth.session_timeout_min":
            return 2
        return default


def _parse_seconds(text: str) -> int:
    import re
    m = re.search(r"Wylogowanie za (?:(\d+) min )?(\d+) s", text)
    assert m
    minutes = int(m.group(1)) if m.group(1) else 0
    seconds = int(m.group(2))
    return minutes * 60 + seconds


def test_logout_timer_updates(root, monkeypatch):
    monkeypatch.setattr(gui_panel, "CONFIG_MANAGER", DummyCM())
    gui_panel.uruchom_panel(root, "demo", "user")
    main = root.winfo_children()[1]
    footer = main.winfo_children()[2]
    btns = footer.winfo_children()[1]
    label = [w for w in btns.winfo_children() if isinstance(w, ttk.Label)][0]
    start = _parse_seconds(label.cget("text"))
    # początek powinien odzwierciedlać wartość z konfiguracji (2 minuty)
    assert 118 <= start <= 120
    root.after(1100, root.quit)
    root.mainloop()
    after = _parse_seconds(label.cget("text"))
    assert after < start
