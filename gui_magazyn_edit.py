"""Edytor pozycji magazynu – implementacja zastępcza."""

from tkinter import messagebox


def open_edit_dialog(parent, item_id, on_saved=None):
    """Tymczasowy edytor; wyświetla info i wywołuje on_saved."""
    root = parent.winfo_toplevel()
    messagebox.showinfo(
        "Edytor pozycji",
        f"Brak implementacji edytora dla {item_id}",
        parent=root,
    )
    if callable(on_saved):
        on_saved(item_id)
