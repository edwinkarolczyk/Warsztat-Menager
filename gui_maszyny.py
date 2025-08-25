# Wersja pliku: 1.1.0
# Plik: gui_maszyny.py
# Zmiany 1.1.0:
# - Rozbudowa panelu maszyn: listowanie maszyn oraz możliwość oznaczenia najbliższego zadania jako wykonane
# - Korzysta z modułu maszyny_logika.next_task oraz complete_task

import tkinter as tk
from tkinter import ttk, messagebox
import maszyny_logika as ML


def panel_maszyny(root, frame, login=None, rola=None):
    """Prosty panel maszyn z obsługą zadań."""
    for widget in frame.winfo_children():
        widget.destroy()

    tk.Label(frame, text="🛠️ Panel maszyn", font=("Arial", 16), bg="#333", fg="white").pack(fill="x")

    tree = ttk.Treeview(frame, columns=("id", "nazwa", "zadanie"), show="headings")
    tree.heading("id", text="Nr ewid")
    tree.heading("nazwa", text="Nazwa")
    tree.heading("zadanie", text="Najbliższe zadanie")
    tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _load():
        tree.delete(*tree.get_children())
        machines = ML.load_machines()
        for m in machines:
            idx, task = ML.next_task(m)
            if task:
                txt = f"{task.get('data')} {task.get('typ_zadania')}"
            else:
                txt = "brak"
            tree.insert("", "end", iid=str(m.get("nr_ewid")), values=(m.get("nr_ewid"), m.get("nazwa"), txt))
        tree._machines = {str(m.get("nr_ewid")): m for m in machines}

    def _mark_done():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Maszyny", "Wybierz maszynę")
            return
        mid = sel[0]
        m = tree._machines.get(mid)
        idx, task = ML.next_task(m)
        if idx is None:
            messagebox.showinfo("Maszyny", "Brak zaplanowanych zadań")
            return
        try:
            ML.complete_task(mid, idx, user=login or "system")
            messagebox.showinfo("Maszyny", "Zadanie oznaczone jako wykonane")
            _load()
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    ttk.Button(frame, text="Oznacz zadanie jako wykonane", command=_mark_done).pack(pady=(0,8))

    _load()

# Zmiany w wersji 1.0.1:
# - Dodano obsługę login i rola jako opcjonalne parametry
# - Umożliwia prawidłowe wywołanie z gui_panel
