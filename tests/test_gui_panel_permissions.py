import pytest
import tkinter as tk
import gui_panel


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def test_brygadzista_side_panel_has_settings_button(root):
    gui_panel.uruchom_panel(root, "demo", "brygadzista")
    side = root.winfo_children()[0]
    texts = [w.cget("text") for w in side.winfo_children() if hasattr(w, "cget")]
    assert "Ustawienia" in texts
