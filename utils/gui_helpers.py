import tkinter as tk


def clear_frame(frame: tk.Widget) -> None:
    """Destroy all child widgets of the given frame."""
    for widget in list(frame.winfo_children()):
        widget.destroy()
