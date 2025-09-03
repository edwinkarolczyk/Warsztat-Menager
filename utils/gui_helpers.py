import tkinter as tk


def destroy_safe(widget: tk.Widget) -> None:
    """Destroy widget ignoring any exceptions."""
    try:
        widget.destroy()
    except Exception:
        pass


def clear_frame(frame: tk.Widget) -> None:
    """Destroy all child widgets of the given frame safely."""
    for widget in list(frame.winfo_children()):
        destroy_safe(widget)
