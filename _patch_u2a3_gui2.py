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


preview = '''    @staticmethod
    def _format_requirement_qty(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value or "")
        if number.is_integer():
            return str(int(number))
        return f"{number:.3f}".rstrip("0").rstrip(".")

    def _refresh_requirement_preview(self, order):
        if not hasattr(self, "requirements_tree"):
            return
        self.requirements_tree.delete(*self.requirements_tree.get_children())
        product_code = str(order.get("product_code") or order.get("symbol") or "").strip()
        qty = order.get("qty", 0)
        try:
            result = self.requirement_calculator.calculate(product_code, qty)
        except RequirementError as exc:
            self.requirements_status_var.set(str(exc))
            return
        except Exception as exc:
            self.requirements_status_var.set(f"Nie udało się policzyć zapotrzebowania: {exc}")
            return
        for idx, row in enumerate(result.get("rows") or []):
            self.requirements_tree.insert("", "end", iid=f"req-{idx}", values=(
                row.get("typ", ""), row.get("kod", ""), row.get("nazwa", ""),
                self._format_requirement_qty(row.get("ilosc")), row.get("jednostka", ""), row.get("zrodlo", ""),
            ))
        warnings = result.get("warnings") or []
        text = (
            f"Produkt {result.get('product_code','')} × {self._format_requirement_qty(result.get('product_qty'))} "
            f"| rewizja składu {result.get('composition_revision', 1)}"
        )
        if warnings:
            text += " | UWAGI: " + " ; ".join(str(x) for x in warnings[:4])
            if len(warnings) > 4:
                text += f" ; +{len(warnings) - 4} kolejnych"
        self.requirements_status_var.set(text)

'''
once('    def _refresh_stats(self):\n', preview + '    def _refresh_stats(self):\n', 'preview methods')

new_add = '''    def _add_order(self, day_date=None):
        payload = self._open_order_form(day_date=day_date)
        if not payload:
            return
        requested = payload.get("number") or ""
        try:
            number = unique_order_number(requested, self.store.data.get("orders", []))
        except RequirementError as exc:
            messagebox.showerror("Zlecenie", str(exc), parent=self.root)
            return
        if number != requested:
            messagebox.showinfo("Nr zlecenia", f"Nr '{requested}' już istnieje. Nadano nr '{number}'.", parent=self.root)
        product_code = str(payload.get("product_code") or "").strip()
        order = {
            "id": f"ord-{int(datetime.now().timestamp() * 1000)}",
            "opis": "Zlecenie",
            "number": number,
            "product_code": product_code,
            "symbol": product_code,
            "client": payload.get("client"),
            "qty": int(payload.get("qty") or 0),
            "start_date": payload.get("start_date") or _today(),
            "ship_date": payload.get("ship_date") or _today(),
            "status": "aktywne",
            "attachments": [],
            "stages": self._build_stages(),
            "history": [],
        }
        _build_schedule(order, set(self.store.data.get("working_saturdays", [])))
        self.store.data.setdefault("orders", []).append(order)
        self._persist_or_warn()
        self._refresh_orders_list()

'''
block('    def _add_order(self, day_date=None):\n', '    def _show_order_detail(self):\n', new_add, 'add order')

new_detail = '''    def _show_order_detail(self):
        sel = self.orders_tree.selection()
        if not sel:
            return
        order = next((o for o in self.store.data.get("orders", []) if o["id"] == sel[0]), None)
        if not order:
            return
        self.detail_text.delete("1.0", "end")
        number = str(order.get("number") or "")
        product_code = str(order.get("product_code") or order.get("symbol") or "")
        self.detail_text.insert("end", f"Zlecenie {number}\\nProdukt: {product_code}\\nIlość: {order.get('qty', '')}\\n\\n")
        self.detail_text.insert("end", json.dumps(order, ensure_ascii=False, indent=2))
        self._refresh_requirement_preview(order)

'''
block('    def _show_order_detail(self):\n', '    def _block_day(self):\n', new_detail, 'detail')

new_edit = '''    def _edit_selected_order(self):
        order = self._selected_order()
        if not order or not self.access.can_edit:
            return
        payload = self._open_order_form(order=order)
        if not payload:
            return
        requested = payload.get("number") or order.get("number") or ""
        try:
            number = unique_order_number(requested, self.store.data.get("orders", []), exclude_id=str(order.get("id") or ""))
        except RequirementError as exc:
            messagebox.showerror("Zlecenie", str(exc), parent=self.root)
            return
        if number != requested:
            messagebox.showinfo("Nr zlecenia", f"Nr '{requested}' już istnieje. Nadano nr '{number}'.", parent=self.root)
        product_code = str(payload.get("product_code") or "").strip()
        order.update({
            "opis": "Zlecenie",
            "number": number,
            "product_code": product_code,
            "symbol": product_code,
            "client": payload.get("client"),
            "qty": int(payload.get("qty") or order.get("qty") or 0),
            "ship_date": payload.get("ship_date") or order.get("ship_date"),
            "start_date": payload.get("start_date") or order.get("start_date"),
        })
        order["stages"] = self._build_stages(order.get("stages", []))
        _build_schedule(order, set(self.store.data.get("working_saturdays", [])))
        self._persist_or_warn()
        self._refresh_orders_list()

'''
block('    def _edit_selected_order(self):\n', '    def _delete_selected_order(self):\n', new_edit, 'edit order')

P.write_text(s, encoding='utf-8')
print('U2A-3 GUI part 2 prepared')
