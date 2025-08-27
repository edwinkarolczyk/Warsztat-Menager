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


def test_first_login_frame_has_height(root):
    gui_panel.uruchom_panel(root, "demo", "brygadzista")
    # main frame is second child of root; content is second child of main
    children = root.winfo_children()
    assert len(children) >= 2
    main = children[1]
    content = main.winfo_children()[1]
    assert content.winfo_height() > 0
