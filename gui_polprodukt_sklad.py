# version: 1.0
# Moduł: gui_polprodukt_sklad
# Edytor wielopoziomowego składu półproduktu.

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from polprodukty_store import SemiProductCatalog, SemiProductCatalogError


def open_semiproduct_composition(master, catalog: SemiProductCatalog, item: dict, on_saved=None):
    code = str(item.get('kod') or '').strip()
    win = tk.Toplevel(master)
    win.title(f"Skład półproduktu — {code}")
    win.geometry('820x520')
    win.transient(master.winfo_toplevel())
    win.grab_set()

    entries = copy.deepcopy(item.get('sklad') or [])
    rows: dict[str, dict] = {}

    top = ttk.Frame(win, padding=10)
    top.pack(fill='x')
    ttk.Label(top, text=f"Półprodukt: {code} — {item.get('nazwa','')}", font=('Segoe UI', 11, 'bold')).pack(side='left')

    btns = ttk.Frame(top)
    btns.pack(side='right')

    tree = ttk.Treeview(win, columns=('kod', 'nazwa', 'ilosc'), show='headings', height=16)
    tree.heading('kod', text='Półprodukt składowy')
    tree.heading('nazwa', text='Nazwa')
    tree.heading('ilosc', text='Ilość na 1 szt.')
    tree.column('kod', width=220, anchor='w')
    tree.column('nazwa', width=360, anchor='w')
    tree.column('ilosc', width=120, anchor='center')
    tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    status_var = tk.StringVar(value='Skład półproduktu może mieć kolejne poziomy. Silnik zapotrzebowania wykrywa pętle.')
    ttk.Label(win, textvariable=status_var, wraplength=780).pack(fill='x', padx=10, pady=(0, 8))

    def catalog_map():
        try:
            return {str(x.get('kod') or ''): x for x in catalog.list_items()}
        except Exception:
            return {}

    def refresh():
        tree.delete(*tree.get_children())
        rows.clear()
        cmap = catalog_map()
        for idx, entry in enumerate(entries):
            child = str(entry.get('kod') or '').strip()
            child_item = cmap.get(child, {})
            iid = f'sklad-{idx}'
            rows[iid] = entry
            tree.insert('', 'end', iid=iid, values=(child, child_item.get('nazwa', ''), entry.get('ilosc_na_szt', 1)))

    def selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0].split('-', 1)[1])
        except Exception:
            return None

    def edit_entry(idx=None):
        cmap = catalog_map()
        choices = [k for k in sorted(cmap, key=str.casefold) if k and k.casefold() != code.casefold()]
        existing = entries[idx] if idx is not None else {}
        child_var = tk.StringVar(value=str(existing.get('kod') or ''))
        qty_var = tk.StringVar(value=str(existing.get('ilosc_na_szt') or 1))
        dlg = tk.Toplevel(win)
        dlg.title('Pozycja składu półproduktu')
        dlg.transient(win)
        dlg.grab_set()
        form = ttk.Frame(dlg, padding=12)
        form.pack(fill='both', expand=True)
        ttk.Label(form, text='Półprodukt:').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Combobox(form, textvariable=child_var, values=choices, state='normal', width=44).grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Ilość na 1 szt.:').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=qty_var).grid(row=1, column=1, sticky='ew', pady=4)
        form.columnconfigure(1, weight=1)

        def accept():
            child = child_var.get().strip()
            if not child:
                messagebox.showerror('Skład półproduktu', 'Wybierz półprodukt.', parent=dlg)
                return
            if child.casefold() == code.casefold():
                messagebox.showerror('Skład półproduktu', 'Półprodukt nie może zawierać samego siebie.', parent=dlg)
                return
            try:
                qty = float(qty_var.get().replace(',', '.'))
            except ValueError:
                messagebox.showerror('Skład półproduktu', 'Ilość musi być liczbą.', parent=dlg)
                return
            if qty <= 0:
                messagebox.showerror('Skład półproduktu', 'Ilość musi być większa od zera.', parent=dlg)
                return
            if qty.is_integer():
                qty = int(qty)
            row = {'kod': child, 'ilosc_na_szt': qty}
            if idx is None:
                entries.append(row)
            else:
                entries[idx] = row
            dlg.destroy()
            refresh()

        controls = ttk.Frame(form)
        controls.grid(row=2, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(controls, text='Anuluj', command=dlg.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(controls, text='OK', command=accept).pack(side='right')

    def remove():
        idx = selected_index()
        if idx is None:
            return
        del entries[idx]
        refresh()

    def save():
        try:
            saved = catalog.save_sklad(item, entries)
        except SemiProductCatalogError as exc:
            messagebox.showerror('Skład półproduktu', str(exc), parent=win)
            return
        except Exception as exc:
            messagebox.showerror('Skład półproduktu', f'Nie udało się zapisać:\n{exc}', parent=win)
            return
        if callable(on_saved):
            try:
                on_saved(saved)
            except Exception:
                pass
        win.destroy()

    ttk.Button(btns, text='Dodaj', command=lambda: edit_entry(None)).pack(side='left', padx=3)
    ttk.Button(btns, text='Edytuj', command=lambda: edit_entry(selected_index()) if selected_index() is not None else None).pack(side='left', padx=3)
    ttk.Button(btns, text='Usuń', command=remove).pack(side='left', padx=3)
    ttk.Button(btns, text='Zapisz skład', command=save).pack(side='left', padx=(12, 3))
    tree.bind('<Double-1>', lambda _e: edit_entry(selected_index()) if selected_index() is not None else None)
    refresh()
    return win
