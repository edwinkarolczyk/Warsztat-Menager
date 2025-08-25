# Wersja pliku: 1.0.1
# Plik: gui_maszyny.py

def panel_maszyny(root, frame, login=None, rola=None):
    for widget in frame.winfo_children():
        widget.destroy()

    import tkinter as tk
    tk.Label(frame, text="🛠️ Panel maszyn", font=("Arial", 16), bg="#333", fg="white").pack(pady=20)

# Zmiany w wersji 1.0.1:
# - Dodano obsługę login i rola jako opcjonalne parametry
# - Umożliwia prawidłowe wywołanie z gui_panel
