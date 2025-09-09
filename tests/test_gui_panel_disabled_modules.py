import pytest
import tkinter as tk
import gui_panel
import profile_utils


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def test_disabled_modules_hide_buttons(root):
    user = profile_utils.get_user("dawid")
    assert user is not None
    backup = dict(user)
    try:
        profile_utils.set_module_visibility("dawid", "narzedzia", False)
        gui_panel.uruchom_panel(root, "dawid", user.get("rola"))
        side = root.winfo_children()[0]
        texts = [w.cget("text") for w in side.winfo_children() if hasattr(w, "cget")]
        assert "Narzędzia" not in texts
        assert "Zlecenia" in texts
    finally:
        profile_utils.save_user(backup)
