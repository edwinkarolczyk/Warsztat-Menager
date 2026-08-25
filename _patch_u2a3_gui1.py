from pathlib import Path

P = Path('gui_planowanie.py')
s = P.read_text(encoding='utf-8')


def once(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1, got {n}')
    s = s.replace(old, new, 1)


def block(start, end, new, label):
    global s
    if s.count(start) != 1 or s.count(end) != 1:
        raise RuntimeError(f'{label}: marker mismatch')
    i = s.index(start)
    j = s.index(end, i)
    s = s[:i] + new + s[j:]


once('# version: 1.3\n', '# version: 1.4\n', 'version')
once(
    '# =========================================================\n# Zmiany 1.3:\n',
    '# =========================================================\n# Zmiany 1.4:\n'
    '# - U2A-3: zlecenie wybiera produkt i pokazuje wyliczone zapotrzebowanie.\n'
    '# - Duplikaty numerów dostają automatycznie sufiks _2, _3, ... bez prefiksu ZL.\n'
    '# - Wyliczenie nie wykonuje ruchów magazynowych ani nie tworzy Dyspozycji.\n'
    '# Zmiany 1.3:\n',
    'changelog',
)
once(
    'from gui_planowanie_bom import BomEditorPanel, SemiProductsPanel\n',
    'from gui_planowanie_bom import BomEditorPanel, SemiProductsPanel\n'
    'from planowanie_zapotrzebowanie import RequirementCalculator, RequirementError, unique_order_number\n',
    'import',
)
once(
    '        self.product_catalog = ProductCatalog()\n',
    '        self.product_catalog = ProductCatalog()\n        self.requirement_calculator = RequirementCalculator(self.product_catalog)\n',
    'calculator init',
)
once('self.orders_tree.heading("symbol", text="Symbol")', 'self.orders_tree.heading("symbol", text="Produkt")', 'product heading')
once(
'''        self.detail_text = tk.Text(detail, height=12)
        self.detail_text.pack(fill="both", expand=True)

        stats = ttk.LabelFrame(tab, text="Statystyki")
''',
'''        self.detail_text = tk.Text(detail, height=8)
        self.detail_text.pack(fill="both", expand=True)

        req = ttk.LabelFrame(tab, text="Zapotrzebowanie zlecenia — podgląd bez stanów magazynowych")
        req.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        req_cols = ("typ", "kod", "nazwa", "ilosc", "jednostka", "zrodlo")
        self.requirements_tree = ttk.Treeview(req, columns=req_cols, show="headings", height=8)
        for key, label, width in (
            ("typ", "Typ", 90), ("kod", "Kod", 150), ("nazwa", "Nazwa", 180),
            ("ilosc", "Potrzeba", 100), ("jednostka", "Jedn.", 70), ("zrodlo", "Wynika z", 260),
        ):
            self.requirements_tree.heading(key, text=label)
            self.requirements_tree.column(key, width=width, anchor="w")
        self.requirements_tree.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        self.requirements_status_var = tk.StringVar(value="Wybierz zlecenie.")
        ttk.Label(req, textvariable=self.requirements_status_var, wraplength=1050).pack(anchor="w", padx=6, pady=(2, 6))

        stats = ttk.LabelFrame(tab, text="Statystyki")
''',
'requirement UI',
)
once(
'''                str(o.get("number", "")),
                str(o.get("client", "")),
''',
'''                str(o.get("number", "")),
                str(o.get("product_code") or o.get("symbol") or ""),
                str(o.get("client", "")),
''',
'search product',
)
once(
'            self.orders_tree.insert("", "end", iid=order["id"], values=(order.get("number"), order.get("symbol"), order.get("client"), order.get("qty"), order.get("ship_date"), order.get("status", "aktywne")))\n',
'            product_code = order.get("product_code") or order.get("symbol") or ""\n            self.orders_tree.insert("", "end", iid=order["id"], values=(order.get("number"), product_code, order.get("client"), order.get("qty"), order.get("ship_date"), order.get("status", "aktywne")))\n',
'order list',
)

new_form = '''    def _open_order_form(self, order=None, day_date=None):
        if not self.access.can_edit:
            return None
        win = tk.Toplevel(self.root)
        win.title("Dodaj/Edytuj zlecenie")
        win.transient(self.root)
        default_date = day_date.isoformat() if day_date else _today()
        values = order or {}
        form = ttk.Frame(win, padding=8)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        number_var = tk.StringVar(value=str(values.get("number") or ""))
        client_var = tk.StringVar(value=str(values.get("client") or ""))
        qty_var = tk.StringVar(value=str(values.get("qty") or "1"))
        ship_var = tk.StringVar(value=str(values.get("ship_date") or default_date))
        start_var = tk.StringVar(value=str(values.get("start_date") or default_date))

        product_labels, product_by_label = [], {}
        current_code = str(values.get("product_code") or values.get("symbol") or "").strip()
        try:
            products = self.product_catalog.list_products()
        except Exception as exc:
            products = []
            messagebox.showerror("Zlecenie", f"Nie udało się wczytać produktów:\\n{exc}", parent=win)
        for product in sorted(products, key=lambda p: str(p.get("kod") or "").casefold()):
            code = str(product.get("kod") or "").strip()
            if not code:
                continue
            label = f"{code} — {product.get('nazwa','')}"
            product_labels.append(label)
            product_by_label[label] = code
        selected = next((label for label, code in product_by_label.items() if code.casefold() == current_code.casefold()), "")
        if current_code and not selected:
            selected = current_code
            product_labels.append(selected)
            product_by_label[selected] = current_code
        product_var = tk.StringVar(value=selected)

        rows = (
            (0, "Nr zlecenia:", number_var),
            (2, "Klient:", client_var),
            (3, "Ilość produktu:", qty_var),
            (4, "Termin wysyłki:", ship_var),
            (5, "Data startu:", start_var),
        )
        for row, label, var in rows:
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(form, textvariable=var, width=40).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Produkt:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=product_var, values=product_labels, state="readonly", width=48).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Button(form, text="📅", command=lambda: ship_var.set(_today())).grid(row=4, column=2, padx=4)
        ttk.Button(form, text="📅", command=lambda: start_var.set(_today())).grid(row=5, column=2, padx=4)
        ttk.Label(form, text="Opis jest stały: Zlecenie + nadany nr. Duplikat dostanie _2, _3 itd.", wraplength=560).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 2))

        result = {"value": None}
        def save_form():
            number = number_var.get().strip()
            if not number:
                messagebox.showerror("Zlecenie", "Podaj nr zlecenia.", parent=win)
                return
            product_code = product_by_label.get(product_var.get().strip(), "")
            if not product_code:
                messagebox.showerror("Zlecenie", "Wybierz produkt z katalogu produktów.", parent=win)
                return
            try:
                qty = int(qty_var.get().strip())
            except ValueError:
                messagebox.showerror("Zlecenie", "Ilość produktu musi być liczbą całkowitą.", parent=win)
                return
            if qty <= 0:
                messagebox.showerror("Zlecenie", "Ilość produktu musi być większa od zera.", parent=win)
                return
            result["value"] = {
                "number": number, "product_code": product_code, "client": client_var.get().strip(),
                "qty": qty, "ship_date": ship_var.get().strip(), "start_date": start_var.get().strip(),
            }
            win.destroy()
        ttk.Button(form, text="Zapisz", command=save_form).grid(row=7, column=1, sticky="e", pady=8)
        win.grab_set()
        win.wait_window()
        return result["value"]

'''
block('    def _open_order_form(self, order=None, day_date=None):\n', '    def _build_stages(self, base_stages=None):\n', new_form, 'order form')
P.write_text(s, encoding='utf-8')
print('U2A-3 GUI part 1 prepared')
