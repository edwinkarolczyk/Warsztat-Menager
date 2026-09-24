# WM-VERSION: 0.1
# Plik: planista_editor_runtime.py
# version: 1.2
# 1.2: opcja kontrolowanej nadprodukcji przy dodawaniu i edycji zlecenia.
# 1.1: jeden edytor zlecenia po dwukliku: dane, realizacja, półprodukty, zapotrzebowanie, druk i usuwanie.
"""Dodawanie/edycja zleceń oraz edycja słowników Planisty."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk


def _fmt(value) -> str:
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _install_order_editor() -> None:
    import gui_planista_panel as GPP
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP
    from ui_context_help import SearchableCombobox, add_help_button

    Panel = GPP.PlanistaPanel
    old_build = Panel._build_orders
    if getattr(old_build, "_wm_order_editor", False):
        return

    def product_values():
        rows = []
        for rec in ZL.list_produkty():
            code = str(rec.get("kod") or "").strip()
            if not code:
                continue
            name = str(rec.get("nazwa") or code).strip()
            display = f"{name}  [{code}]"
            rows.append((display, rec))
        return rows

    def add_order(self):
        rows = product_values()
        if not rows:
            messagebox.showinfo("Planista", "Najpierw dodaj produkt w zakładce Produkty.", parent=self)
            return
        by_display = {display: rec for display, rec in rows}

        dlg = tk.Toplevel(self.root)
        dlg.title("Dodaj zlecenie")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        product = tk.StringVar()
        qty = tk.StringVar(value="1")
        term = tk.StringVar(value=date.today().strftime("%d-%m-%y"))
        cut = tk.StringVar(value=_fmt(ZL.DEFAULT_CUT_MM))
        internal = tk.StringVar()
        notes = tk.StringVar()
        reserve = tk.BooleanVar(value=True)
        allow_overproduction = tk.BooleanVar(value=False)

        labels = (
            ("Produkt", 0),
            ("Ilość", 1),
            ("Termin", 2),
            ("Rzaz [mm]", 3),
            ("Zlecenie wewnętrzne", 4),
            ("Uwagi", 5),
        )
        for text, row in labels:
            ttk.Label(frm, text=text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)

        combo = SearchableCombobox(frm, textvariable=product, state="normal")
        combo.set_values([display for display, _ in rows])
        combo.grid(row=0, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Wybierz produkt z kartoteki Produkty. Zlecenie zapisze aktualną wersję produktu i na jej podstawie policzy półprodukty oraz surowce.", row=0, column=2, padx=(4, 0))
        ttk.Entry(frm, textvariable=qty).grid(row=1, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Podaj liczbę sztuk produktu do wykonania. Planista automatycznie wyliczy zapotrzebowanie wynikające z BOM.", row=1, column=2, padx=(4, 0))
        tk.Entry(frm, textvariable=term, state="readonly", readonlybackground="#2e7d32", fg="white", justify="center").grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Button(frm, text="📅", command=lambda: GPP._open_date_calendar(dlg, term), width=3).grid(row=2, column=2, sticky="w", padx=(4, 0))
        ttk.Entry(frm, textvariable=cut).grid(row=3, column=1, sticky="ew", pady=3)
        add_help_button(frm, "Rzaz jest doliczany do materiału dla każdej wykonywanej sztuki półproduktu liniowego.", row=3, column=2, padx=(4, 0))
        ttk.Entry(frm, textvariable=internal).grid(row=4, column=1, sticky="ew", pady=3)
        ttk.Entry(frm, textvariable=notes).grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Checkbutton(frm, text="Rezerwuj dostępny materiał", variable=reserve).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 3))
        add_help_button(frm, "Po zapisaniu WM zarezerwuje dostępne półprodukty i surowce dla tego zlecenia. Braki pozostaną widoczne jako zapotrzebowanie.", row=6, column=2, padx=(4, 0))
        ttk.Checkbutton(
            frm,
            text="Zezwól na nadprodukcję (Magazyn po potwierdzeniu)",
            variable=allow_overproduction,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=3)
        add_help_button(
            frm,
            "Pozwala zgłosić dodatkowe sztuki. Nadwyżka półproduktu czeka na osobne potwierdzenie przekazania do Magazynu.",
            row=7,
            column=2,
            padx=(4, 0),
        )

        def save():
            rec = by_display.get(product.get().strip())
            if not rec:
                messagebox.showerror("Dodaj zlecenie", "Wybierz produkt z listy.", parent=dlg)
                return
            try:
                qty_value = float(qty.get().replace(",", "."))
                cut_value = float(cut.get().replace(",", "."))
                if qty_value <= 0:
                    raise ValueError("Ilość musi być większa od zera.")
                if cut_value < 0:
                    raise ValueError("Rzaz nie może być ujemny.")
                ZL.create_zlecenie(
                    str(rec.get("kod")),
                    qty_value,
                    uwagi=notes.get().strip(),
                    autor=self.login or "system",
                    zlec_wew=internal.get().strip() or None,
                    reserve=bool(reserve.get()),
                    version=rec.get("version"),
                    termin=GPP._iso_date(term.get()),
                    rzaz_mm=cut_value,
                    allow_overproduction=bool(allow_overproduction.get()),
                )
            except Exception as exc:
                messagebox.showerror("Dodaj zlecenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        buttons = ttk.Frame(frm)
        buttons.grid(row=8, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Anuluj", command=dlg.destroy).pack(side="right")
        ttk.Button(buttons, text="Dodaj zlecenie", command=save).pack(side="right", padx=(0, 6))
        frm.columnconfigure(1, weight=1)

    def edit_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie do edycji.", parent=self)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edycja zlecenia {order.get('id')}")
        dlg.transient(self.root)
        dlg.geometry("1120x720")
        dlg.minsize(900, 600)
        dlg.grab_set()

        # Wizualna karta z zaokrąglonym obrysem. Zewnętrzna ramka okna pozostaje
        # systemowa; zaokrąglenie dotyczy właściwego edytora WM.
        canvas = tk.Canvas(dlg, bg="#111418", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        card = tk.Frame(canvas, bg="#1b1f24", bd=0, highlightthickness=0)
        card_window = canvas.create_window(28, 28, anchor="nw", window=card)
        card_shape = {"id": None}

        def redraw_card(_event=None):
            width = max(160, canvas.winfo_width())
            height = max(160, canvas.winfo_height())
            x1, y1, x2, y2 = 16, 16, width - 16, height - 16
            radius = 18
            points = (
                x1 + radius, y1, x2 - radius, y1, x2, y1,
                x2, y1 + radius, x2, y2 - radius, x2, y2,
                x2 - radius, y2, x1 + radius, y2, x1, y2,
                x1, y2 - radius, x1, y1 + radius, x1, y1,
            )
            if card_shape["id"] is None:
                card_shape["id"] = canvas.create_polygon(
                    points,
                    smooth=True,
                    splinesteps=24,
                    fill="#1b1f24",
                    outline="#3a414b",
                    width=1,
                )
                canvas.tag_lower(card_shape["id"])
            else:
                canvas.coords(card_shape["id"], *points)
            canvas.coords(card_window, 28, 28)
            canvas.itemconfigure(
                card_window,
                width=max(80, width - 56),
                height=max(80, height - 56),
            )

        canvas.bind("<Configure>", redraw_card)
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        header = ttk.Frame(card)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 10))
        title_var = tk.StringVar()
        subtitle_var = tk.StringVar()
        ttk.Label(header, textvariable=title_var, font=("Arial", 14, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=subtitle_var).pack(anchor="w", pady=(3, 0))

        notebook = ttk.Notebook(card)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10)

        basic_tab = ttk.Frame(notebook, padding=16)
        realization_tab = ttk.Frame(notebook, padding=16)
        semis_tab = ttk.Frame(notebook, padding=16)
        requirements_tab = ttk.Frame(notebook, padding=16)
        notebook.add(basic_tab, text="Dane podstawowe")
        notebook.add(realization_tab, text="Realizacja")
        notebook.add(semis_tab, text="Półprodukty")
        notebook.add(requirements_tab, text="Zapotrzebowanie")

        qty = tk.StringVar()
        term = tk.StringVar()
        cut = tk.StringVar()
        internal = tk.StringVar()
        notes = tk.StringVar()
        status_var = tk.StringVar()
        ordered_var = tk.StringVar()
        done_total_var = tk.StringVar()
        remaining_var = tk.StringVar()
        done_input = tk.StringVar()
        allow_overproduction = tk.BooleanVar(value=False)

        summary = ttk.Frame(header)
        summary.pack(fill="x", pady=(10, 0))
        for index, (caption, variable) in enumerate((
            ("PLAN PRODUKTU", ordered_var),
            ("WYKONANO", done_total_var),
            ("POZOSTAŁO", remaining_var),
        )):
            cell = ttk.Frame(summary, padding=(12, 8))
            cell.grid(row=0, column=index, sticky="ew", padx=(0, 8))
            ttk.Label(cell, text=caption, font=("Arial", 9, "bold")).pack(anchor="w")
            ttk.Label(cell, textvariable=variable, font=("Arial", 18, "bold")).pack(anchor="w")
            summary.columnconfigure(index, weight=1)

        basic_tab.columnconfigure(1, weight=1)
        ttk.Label(basic_tab, text="Zlecenie warsztatowe").grid(row=0, column=0, sticky="w", pady=4)
        order_id_label = ttk.Label(basic_tab)
        order_id_label.grid(row=0, column=1, sticky="w", pady=4)
        add_help_button(
            basic_tab,
            "Stały numer warsztatowy zlecenia. Nie jest tym samym co numer zlecenia wewnętrznego.",
            row=0,
            column=2,
            padx=(6, 0),
        )

        ttk.Label(basic_tab, text="Produkt").grid(row=1, column=0, sticky="w", pady=4)
        product_label = ttk.Label(basic_tab)
        product_label.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(basic_tab, text="Wersja BOM").grid(row=2, column=0, sticky="w", pady=4)
        version_label = ttk.Label(basic_tab)
        version_label.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(basic_tab, text="Zlecenie wewnętrzne").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(basic_tab, textvariable=internal).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(basic_tab, text="Ilość").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(basic_tab, textvariable=qty).grid(row=4, column=1, sticky="ew", pady=4)
        add_help_button(
            basic_tab,
            "Zmiana ilości przelicza pozostałą część zlecenia, BOM i rezerwacje. Już rozliczone wykonanie nie jest cofane.",
            row=4,
            column=2,
            padx=(6, 0),
        )

        ttk.Label(basic_tab, text="Termin").grid(row=5, column=0, sticky="w", pady=4)
        tk.Entry(
            basic_tab,
            textvariable=term,
            state="readonly",
            readonlybackground="#2e7d32",
            fg="white",
            justify="center",
        ).grid(row=5, column=1, sticky="ew", pady=4)
        ttk.Button(
            basic_tab,
            text="📅",
            width=3,
            command=lambda: GPP._open_date_calendar(dlg, term),
        ).grid(row=5, column=2, sticky="w", padx=(6, 0))

        ttk.Label(basic_tab, text="Rzaz [mm]").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(basic_tab, textvariable=cut).grid(row=6, column=1, sticky="ew", pady=4)
        add_help_button(
            basic_tab,
            "Rzaz wpływa na zapotrzebowanie materiałowe półproduktów liniowych. Zapis przeliczy plan i rezerwacje.",
            row=6,
            column=2,
            padx=(6, 0),
        )

        ttk.Label(basic_tab, text="Uwagi").grid(row=7, column=0, sticky="w", pady=4)
        ttk.Entry(basic_tab, textvariable=notes).grid(row=7, column=1, sticky="ew", pady=4)

        ttk.Label(basic_tab, text="Status").grid(row=8, column=0, sticky="w", pady=4)
        ttk.Label(basic_tab, textvariable=status_var).grid(row=8, column=1, sticky="w", pady=4)

        ttk.Checkbutton(
            basic_tab,
            text="Zezwól na nadprodukcję (Magazyn po potwierdzeniu)",
            variable=allow_overproduction,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 4))
        add_help_button(
            basic_tab,
            "Pozwala zgłosić dodatkowe półprodukty. O ich przekazaniu do Magazynu decydujesz osobno.",
            row=9,
            column=2,
            padx=(6, 0),
        )

        ttk.Label(realization_tab, text="Zamówiono", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 40)
        )
        ttk.Label(realization_tab, text="Wykonano", font=("Arial", 10, "bold")).grid(
            row=0, column=1, sticky="w", padx=(0, 40)
        )
        ttk.Label(realization_tab, text="Pozostało", font=("Arial", 10, "bold")).grid(
            row=0, column=2, sticky="w"
        )
        ttk.Label(realization_tab, textvariable=ordered_var, font=("Arial", 16, "bold")).grid(
            row=1, column=0, sticky="w", pady=(4, 18)
        )
        ttk.Label(realization_tab, textvariable=done_total_var, font=("Arial", 16, "bold")).grid(
            row=1, column=1, sticky="w", pady=(4, 18)
        )
        ttk.Label(realization_tab, textvariable=remaining_var, font=("Arial", 16, "bold")).grid(
            row=1, column=2, sticky="w", pady=(4, 18)
        )
        ttk.Separator(realization_tab).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 14))
        ttk.Label(realization_tab, text="Nowa łączna ilość wykonana").grid(row=3, column=0, sticky="w")
        ttk.Entry(realization_tab, textvariable=done_input, width=16).grid(
            row=3, column=1, sticky="w", padx=(8, 4)
        )
        add_help_button(
            realization_tab,
            "Wpisz łączną liczbę wykonanych sztuk. WM zapisze przyrost bez zmiany magazynu.",
            row=3,
            column=2,
            padx=(4, 0),
        )

        # WM 1.0: proposal only; never accept a BOM set without a user action.
        from planista_semi_progress_runtime import proposed_product_completion

        proposal_var = tk.StringVar(value="")
        ttk.Label(realization_tab, textvariable=proposal_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

        def apply_proposal():
            proposal = proposed_product_completion(load_order())
            if not proposal["available"] or proposal["additional"] <= 0:
                messagebox.showinfo(
                    "Komplety półproduktów",
                    proposal["reason"] or "Brak nowych kompletnych zestawów.",
                    parent=dlg,
                )
                return
            done_input.set(_fmt(proposal["complete_sets"]))
            messagebox.showinfo(
                "Potwierdź produkt",
                "Uzupełniono proponowaną ilość. Użyj «Zapisz wykonanie», "
                "aby potwierdzić faktycznie gotowe produkty.",
                parent=dlg,
            )

        ttk.Button(
            realization_tab, text="Wstaw liczbę kompletów z BOM", command=apply_proposal
        ).grid(row=4, column=3, sticky="w", padx=(10, 0))

        semi_cols = ("nazwa", "potrzeba", "magazyn", "do_wyk", "wykonano", "pozostalo", "id")
        ttk.Label(
            semis_tab, text="1. Wybierz półprodukt",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            semis_tab,
            text="Wybierz wiersz, aby zobaczyć operację do wykonania. "
                 "Plan półproduktu możesz zmienić osobno poniżej.",
            wraplength=880, justify="left",
        ).pack(anchor="w", pady=(0, 9))
        semi_tree = ttk.Treeview(semis_tab, columns=semi_cols, show="headings", height=6)
        semi_labels = {
            "nazwa": "Półprodukt",
            "potrzeba": "Do zlecenia",
            "magazyn": "Z magazynu",
            "do_wyk": "Do wykonania",
            "wykonano": "Wykonano",
            "pozostalo": "Pozostało",
            "id": "ID",
        }
        semi_widths = {
            "nazwa": 240,
            "potrzeba": 100,
            "magazyn": 100,
            "do_wyk": 110,
            "wykonano": 100,
            "pozostalo": 100,
            "id": 90,
        }
        for col in semi_cols:
            semi_tree.heading(col, text=semi_labels[col])
            semi_tree.column(col, width=semi_widths[col], anchor="w")
        semi_tree.pack(fill="x", expand=False)
        ttk.Separator(semis_tab).pack(fill="x", pady=(14, 10))
        ttk.Label(
            semis_tab, text="2. Zgłoś wykonanie",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        selected_semi_var = tk.StringVar(value="Wybierz półprodukt z listy powyżej.")
        ttk.Label(
            semis_tab, textvariable=selected_semi_var,
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        step_var = tk.StringVar(value="")
        ttk.Label(
            semis_tab, textvariable=step_var,
            wraplength=880, justify="left",
        ).pack(anchor="w", pady=(0, 6))

        semi_edit = ttk.Frame(semis_tab)
        semi_target = tk.StringVar()
        semi_done = tk.StringVar()
        operation_name = tk.StringVar()
        operation_qty = tk.StringVar()
        ttk.Label(semi_edit, text="Plan półproduktu:").pack(side="left")
        ttk.Entry(semi_edit, textvariable=semi_target, width=10).pack(side="left", padx=(6, 14))
        ttk.Label(semi_edit, text="Ręczne wykonanie:").pack(side="left")
        ttk.Entry(semi_edit, textvariable=semi_done, width=10).pack(side="left", padx=(6, 6))

        operation_frame = ttk.Frame(semis_tab)
        operation_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(operation_frame, text="Bieżąca operacja:").pack(side="left")
        operation_combo = ttk.Combobox(
            operation_frame, textvariable=operation_name, state="readonly", width=24,
        )
        operation_combo.pack(side="left", padx=(6, 10))
        ttk.Label(operation_frame, text="Łącznie wykonano:").pack(side="left")
        ttk.Entry(operation_frame, textvariable=operation_qty, width=10).pack(side="left", padx=(6, 8))

        req_text = tk.Text(
            requirements_tab,
            wrap="word",
            relief="flat",
            bg="#171a1f",
            fg="#e9eef3",
            insertbackground="#e9eef3",
            padx=10,
            pady=10,
        )
        req_text.pack(fill="both", expand=True)
        req_text.configure(state="disabled")

        def load_order():
            return ZL._read_json(ZL._order_path(order["id"]))

        def requirements_text(current):
            lines = []
            for code, rec in (current.get("plan_polprodukty") or {}).items():
                if not isinstance(rec, dict):
                    continue
                lines.append(
                    f"{rec.get('nazwa') or code}: potrzeba {_fmt(rec.get('potrzeba', 0))} | "
                    f"z magazynu {_fmt(rec.get('z_magazynu', 0))} | "
                    f"do wykonania {_fmt(rec.get('do_wykonania', 0))}"
                )
            raw = current.get("zapotrzebowanie_surowce") or {}
            if raw:
                lines += ["", "SUROWIEC:"]
                for code, rec in raw.items():
                    if isinstance(rec, dict):
                        lines.append(
                            f"{code}: {GPP._fmt_amount(rec.get('ilosc', 0), rec.get('jednostka', ''))}"
                        )
            shortages = current.get("braki") or []
            if shortages:
                lines += ["", "BRAKI SUROWCA:"]
                for rec in shortages:
                    lines.append(
                        f"{rec.get('nazwa') or rec.get('kod')}: brakuje "
                        f"{GPP._fmt_amount(rec.get('brakuje', 0), rec.get('jednostka', ''))}"
                    )
            return "\n".join(lines) if lines else "Brak danych."

        def semi_rows(current):
            try:
                import planista_semi_progress_runtime as PS

                return PS.semi_progress_rows(current)
            except Exception:
                rows = []
                progress = current.get("wykonano_polprodukty") or {}
                for code, rec in (current.get("plan_polprodukty") or {}).items():
                    if not isinstance(rec, dict):
                        continue
                    need = float(rec.get("potrzeba", 0) or 0)
                    from_stock = float(rec.get("z_magazynu", 0) or 0)
                    to_make = float(rec.get("do_wykonania", max(0.0, need - from_stock)) or 0)
                    done = float(progress.get(code, 0) or 0)
                    rows.append(
                        {
                            "kod": str(code),
                            "nazwa": str(rec.get("nazwa") or code),
                            "potrzeba": need,
                            "z_magazynu": from_stock,
                            "do_wykonania": to_make,
                            "wykonano": done,
                            "pozostalo": max(0.0, to_make - done),
                        }
                    )
                return rows

        def refresh_main_selection():
            self.refresh()
            oid = str(order.get("id") or "")
            if oid and self.tree.exists(oid):
                self.tree.selection_set(oid)
                self.tree.focus(oid)
                self.tree.see(oid)

        def refresh_editor(*, reset_inputs=False):
            nonlocal order
            try:
                order = load_order()
            except Exception:
                dlg.destroy()
                self.refresh()
                return

            qty_value = float(order.get("ilosc", 0) or 0)
            done_value = float(order.get("wykonano", 0) or 0)
            title_var.set(f"Edycja zlecenia {order.get('id')}")
            subtitle_var.set(
                f"Produkt: {order.get('produkt', '')}   |   Status: {order.get('status', '')}   |   "
                f"Wersja BOM: {order.get('version') or '—'}"
            )
            order_id_label.configure(text=str(order.get("id") or ""))
            product_label.configure(text=str(order.get("produkt") or ""))
            version_label.configure(text=str(order.get("version") or "—"))
            status_var.set(str(order.get("status") or ""))

            if reset_inputs:
                qty.set(_fmt(qty_value))
                term.set(GPP._display_date(order.get("termin")) or date.today().strftime("%d-%m-%y"))
                cut.set(_fmt(order.get("rzaz_mm", ZL.DEFAULT_CUT_MM)))
                internal.set(str(order.get("zlec_wew") or ""))
                notes.set(str(order.get("uwagi") or ""))
                allow_overproduction.set(bool(order.get("zezwol_nadprodukcja")))

            ordered_var.set(_fmt(qty_value))
            done_total_var.set(_fmt(done_value))
            remaining_var.set(_fmt(max(0.0, qty_value - done_value)))
            done_input.set(_fmt(done_value))

            proposal = proposed_product_completion(order)
            if proposal["available"]:
                proposal_var.set(
                    f"Kompletne zestawy: {_fmt(proposal['complete_sets'])} / "
                    f"{_fmt(proposal['planned'])} | nowe do potwierdzenia: "
                    f"{_fmt(proposal['additional'])}"
                )
            else:
                proposal_var.set(proposal["reason"])

            old_selection = semi_tree.selection()
            preferred_code = old_selection[0] if old_selection else ""
            semi_tree.delete(*semi_tree.get_children())
            for row in semi_rows(order):
                semi_tree.insert(
                    "",
                    "end",
                    iid=row["kod"],
                    values=(
                        row["nazwa"],
                        _fmt(row["potrzeba"]),
                        _fmt(row["z_magazynu"]),
                        _fmt(row["do_wykonania"]),
                        _fmt(row["wykonano"]),
                        _fmt(row["pozostalo"]),
                        row["kod"],
                    ),
                )
            available_codes = semi_tree.get_children()
            if available_codes:
                picked = preferred_code if preferred_code in available_codes else available_codes[0]
                semi_tree.selection_set(picked)
                semi_tree.focus(picked)
                semi_tree.see(picked)
            on_semi_select()

            req_text.configure(state="normal")
            req_text.delete("1.0", "end")
            req_text.insert("1.0", requirements_text(order))
            req_text.configure(state="disabled")

        def save_basic():
            nonlocal order
            try:
                qty_value = float(qty.get().replace(",", "."))
                cut_value = float(cut.get().replace(",", "."))
                if qty_value < 0 or cut_value < 0:
                    raise ValueError("Ilość i rzaz nie mogą być ujemne.")
                order = ZP.update_zlecenie(
                    order["id"],
                    ilosc=qty_value,
                    termin=GPP._iso_date(term.get()),
                    rzaz_mm=cut_value,
                    zlec_wew=internal.get().strip(),
                    uwagi=notes.get().strip(),
                    allow_overproduction=bool(allow_overproduction.get()),
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Edytuj zlecenie", str(exc), parent=dlg)
                return False
            refresh_main_selection()
            refresh_editor(reset_inputs=True)
            return True

        def offer_closure_after_settlement():
            from planista_dispatch_runtime import (
                closure_readiness, close_completed_planista_dispatch,
            )

            fresh = load_order()
            state = closure_readiness(fresh)
            if not state["ready"]:
                if state["dispatch"] is not None and state["reason"]:
                    messagebox.showinfo("Dyspozycja", state["reason"], parent=dlg)
                return
            if not messagebox.askyesno(
                "Zamknięcie dyspozycji",
                f"Zlecenie {fresh['id']} jest wykonane i ma rozliczony materiał.\n"
                "Czy zamknąć powiązaną dyspozycję produkcyjną?\n"
                "Materiał NIE zostanie pobrany ponownie.",
                parent=dlg,
            ):
                return
            try:
                close_completed_planista_dispatch(
                    fresh["id"], who=self.login or "system", role=self.rola
                )
            except Exception as exc:
                messagebox.showerror("Dyspozycja", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)

        def offer_settlement_and_closure():
            nonlocal order
            fresh = load_order()
            qty = float(fresh.get("ilosc", 0) or 0)
            done = float(fresh.get("wykonano", 0) or 0)
            settled = float(fresh.get("materialy_rozliczono_do", 0) or 0)
            if qty <= 0 or done + 1e-9 < qty:
                return
            if settled + 1e-9 < done:
                if not messagebox.askyesno(
                    "Rozliczenie materiału",
                    f"Wykonano {_fmt(done)} / {_fmt(qty)} produktów.\n"
                    f"Najpierw rozliczyć materiał od {_fmt(settled)} do {_fmt(done)} szt.?",
                    parent=dlg,
                ):
                    return
                try:
                    order = ZP.rozlicz_material(fresh["id"], kto=self.login or "system")
                except Exception as exc:
                    messagebox.showerror("Rozliczenie materiału", str(exc), parent=dlg)
                    return
                refresh_main_selection()
                refresh_editor(reset_inputs=True)
            offer_closure_after_settlement()

        def save_done():
            nonlocal order
            try:
                new_value = float(done_input.get().replace(",", "."))
                allow = False
                try:
                    import planista_semi_progress_runtime as PS

                    shortages = PS.semi_shortages_for_completion(order, new_value)
                except Exception:
                    shortages = []
                if shortages:
                    details = "\n".join(
                        f"• {row['nazwa']}: brakuje zgłosić {_fmt(row['brakuje'])} szt."
                        for row in shortages
                    )
                    allow = messagebox.askyesno(
                        "Brak postępu półproduktów",
                        "Zgłoszony postęp półproduktów jest za mały dla tej liczby gotowych produktów:\n\n"
                        + details
                        + "\n\nZatwierdzić wykonanie produktu mimo to?",
                        parent=dlg,
                    )
                    if not allow:
                        return
                try:
                    order = ZP.report_wykonano(
                        order["id"],
                        new_value,
                        kto=self.login or "system",
                        allow_incomplete_semis=allow,
                    )
                except TypeError as exc:
                    # Retry only legacy signature mismatch, never an internal
                    # TypeError after a partial write or warehouse side effect.
                    if "allow_incomplete_semis" not in str(exc):
                        raise
                    order = ZP.report_wykonano(
                        order["id"],
                        new_value,
                        kto=self.login or "system",
                    )
            except Exception as exc:
                messagebox.showerror("Rozliczenie", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)
            offer_settlement_and_closure()

        ttk.Button(realization_tab, text="Potwierdź wykonanie produktu", command=save_done).grid(
            row=3, column=3, sticky="w", padx=(10, 0)
        )
        def settle_material():
            nonlocal order
            # Ponownie odczytaj dane: inne okno mogło zapisać wykonanie.
            try:
                fresh = load_order()
                done = float(fresh.get("wykonano", 0) or 0)
                settled = float(fresh.get("materialy_rozliczono_do", 0) or 0)
                if done <= settled:
                    messagebox.showinfo(
                        "Rozliczenie materiału",
                        "Nie ma nowego wykonania do rozliczenia.",
                        parent=dlg,
                    )
                    refresh_editor(reset_inputs=True)
                    return
                if not messagebox.askyesno(
                    "Rozliczenie materiału",
                    f"Rozliczyć materiał dla wykonania od {_fmt(settled)} do {_fmt(done)} szt.?\n"
                    "Ta operacja zmieni stan i rezerwacje magazynu.",
                    parent=dlg,
                ):
                    return
                order = ZP.rozlicz_material(fresh["id"], kto=self.login or "system")
            except Exception as exc:
                messagebox.showerror("Rozliczenie materiału", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)
            offer_closure_after_settlement()

        ttk.Button(realization_tab, text="Rozlicz materiał", command=settle_material).grid(
            row=5, column=3, sticky="w", padx=(10, 0), pady=(8, 0)
        )
        add_help_button(
            realization_tab,
            "Rozlicza wyłącznie wykonane, jeszcze nierozliczone sztuki. Zmienia stan i rezerwacje magazynu.",
            row=5,
            column=2,
            padx=(4, 0),
        )

        def on_semi_select(_event=None):
            selection = semi_tree.selection()
            if not selection:
                semi_target.set("")
                semi_done.set("")
                update_semi_controls()
                return
            code = selection[0]
            row = next((item for item in semi_rows(order) if item["kod"] == code), None)
            if row:
                semi_target.set(_fmt(row["potrzeba"]))
                semi_done.set(_fmt(row["wykonano"]))
            import planista_semi_progress_runtime as PS
            targets = PS._full_semi_targets(order)
            operations = [
                str(x) for x in (targets.get(code) or {}).get("czynnosci") or []
            ]
            operation_combo.configure(values=operations)
            operation_name.set(operations[0] if operations else "")
            on_operation_select()
            update_semi_controls()

        def on_operation_select(_event=None):
            selection = semi_tree.selection()
            code = selection[0] if selection else ""
            progress = (order.get("postep_operacji_polproduktow") or {}).get(code) or {}
            operation_qty.set(_fmt(progress.get(operation_name.get(), 0)))
            update_semi_controls()

        operation_combo.bind("<<ComboboxSelected>>", on_operation_select)

        def save_operation():
            nonlocal order
            selection = semi_tree.selection()
            if not selection:
                messagebox.showinfo("Operacje", "Wybierz półprodukt.", parent=dlg)
                return
            if not operation_name.get():
                messagebox.showinfo(
                    "Operacje", "Ten półprodukt nie ma zdefiniowanych operacji.", parent=dlg
                )
                return
            import planista_semi_progress_runtime as PS
            try:
                order = PS.report_polprodukt_operation(
                    order["id"], selection[0], operation_name.get(),
                    float(operation_qty.get().replace(",", ".")),
                    kto=self.login or "system",
                )
                pending = PS.pending_semi_surplus(order, selection[0])
                if pending > 1e-9 and messagebox.askyesno(
                    "Nadwyżka półproduktu",
                    f"Zgłoszono {_fmt(pending)} szt. nadwyżki po ostatniej operacji.\\n"
                    "Przekazać ją teraz do Magazynu?",
                    parent=dlg,
                ):
                    order = PS.transfer_polprodukt_surplus(
                        order["id"], selection[0], kto=self.login or "system",
                    )
            except Exception as exc:
                messagebox.showerror("Postęp operacji", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)

        operation_save_button = ttk.Button(
            operation_frame, text="Zapisz wykonanie operacji",
            command=save_operation,
        )
        operation_save_button.pack(side="left", padx=(6, 0))

        def save_semi_target():
            nonlocal order
            selection = semi_tree.selection()
            if not selection:
                messagebox.showinfo("Półprodukty", "Wybierz półprodukt.", parent=dlg)
                return
            try:
                selected_code = selection[0]
                new_target = float(semi_target.get().replace(",", "."))
                rows = semi_rows(order)
                overrides = {row["kod"]: float(row["potrzeba"]) for row in rows}
                overrides[selected_code] = new_target
                if any(value < 0 for value in overrides.values()):
                    raise ValueError("Ilość półproduktu nie może być ujemna.")
                order = ZP.update_zlecenie(
                    order["id"],
                    korekty_polproduktow=overrides,
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Półprodukty", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)

        def save_semi_done():
            nonlocal order
            selection = semi_tree.selection()
            if not selection:
                messagebox.showinfo("Półprodukty", "Wybierz półprodukt.", parent=dlg)
                return
            try:
                import planista_semi_progress_runtime as PS
                operations = (PS._full_semi_targets(order).get(selection[0]) or {}).get("czynnosci") or []
                requested = float(semi_done.get().replace(",", "."))
                current = float((order.get("wykonano_polprodukty") or {}).get(selection[0], 0) or 0)
                if operations and requested > current + 1e-9:
                    raise ValueError(
                        "Ten półprodukt wymaga zakończenia ostatniej operacji. "
                        "Zgłoś postęp przez «Zapisz operację»."
                    )
                order = PS.report_polprodukt_wykonano(
                    order["id"],
                    selection[0],
                    float(semi_done.get().replace(",", ".")),
                    kto=self.login or "system",
                )
                pending = PS.pending_semi_surplus(order, selection[0])
                if pending > 1e-9 and messagebox.askyesno(
                    "Nadwyżka półproduktu",
                    f"Zgłoszono {_fmt(pending)} szt. nadwyżki. "
                    "Przekazać ją teraz do Magazynu?\n"
                    "Wybranie Nie pozostawi nadwyżkę przy zleceniu.",
                    parent=dlg,
                ):
                    order = PS.transfer_polprodukt_surplus(
                        order["id"], selection[0], kto=self.login or "system"
                    )
            except Exception as exc:
                messagebox.showerror("Postęp półproduktów", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)

        def transfer_pending_semi():
            nonlocal order
            selection = semi_tree.selection()
            if not selection:
                messagebox.showinfo("Nadwyżka", "Wybierz półprodukt.", parent=dlg)
                return
            import planista_semi_progress_runtime as PS
            current = load_order()
            pending = PS.pending_semi_surplus(current, selection[0])
            if pending <= 1e-9:
                messagebox.showinfo("Nadwyżka", "Brak nadwyżki oczekującej na przekazanie.", parent=dlg)
                return
            if not messagebox.askyesno(
                "Przekaż nadwyżkę",
                f"Przekazać {_fmt(pending)} szt. półproduktu do Magazynu?",
                parent=dlg,
            ):
                return
            try:
                order = PS.transfer_polprodukt_surplus(
                    current["id"], selection[0], kto=self.login or "system"
                )
            except Exception as exc:
                messagebox.showerror("Przekazanie nadwyżki", str(exc), parent=dlg)
                return
            refresh_main_selection()
            refresh_editor(reset_inputs=True)

        add_help_button(
            operation_frame,
            "Zgłaszaj wykonanie operacji po kolei. Dopiero ostatnia operacja "
            "zaliczy gotowy półprodukt. Liczba jest łączna dla tego zlecenia.",
            command_only=False,
        ).pack(side="left", padx=(6, 0))

        semi_tree.bind("<<TreeviewSelect>>", on_semi_select)
        ttk.Button(semi_edit, text="Zapisz plan", command=save_semi_target).pack(side="left", padx=(6, 4))
        add_help_button(
            semi_edit,
            "Zmienia docelową ilość zaznaczonego półproduktu i ponownie przelicza zapotrzebowanie.",
            command_only=False,
        ).pack(side="left", padx=(0, 14))
        manual_save_button = ttk.Button(semi_edit, text="Zapisz wykonanie półproduktu", command=save_semi_done)
        manual_save_button.pack(side="left", padx=(6, 4))
        surplus_button = ttk.Button(semi_edit, text="Przekaż nadwyżkę", command=transfer_pending_semi)
        surplus_button.pack(side="left", padx=(6, 4))
        add_help_button(
            semi_edit,
            "Zapisuje łączny postęp. Przy nadwyżce pyta osobno o jej przekazanie; odmowa zachowuje ją przy zleceniu.",
            command_only=False,
        ).pack(side="left")

        # UI only: plan correction and manual fallback are secondary actions.
        advanced_open = tk.BooleanVar(value=False)
        advanced_toggle = ttk.Button(semis_tab)
        advanced_toggle.pack(anchor="w", pady=(12, 0))

        def update_semi_controls():
            selection = semi_tree.selection()
            code = selection[0] if selection else ""
            import planista_semi_progress_runtime as PS

            targets = PS._full_semi_targets(order) if code else {}
            operations = [
                str(value) for value in (targets.get(code) or {}).get("czynnosci") or []
            ]
            pending = PS.pending_semi_surplus(order, code) if code else 0
            if code:
                row = next((item for item in semi_rows(order) if item["kod"] == code), None)
                if row:
                    selected_semi_var.set(
                        f"{row['nazwa']} [{code}]  •  "
                        f"{_fmt(row['wykonano'])} / {_fmt(row['do_wykonania'])} szt."
                    )
                if operations:
                    current_op = operation_name.get()
                    current_idx = operations.index(current_op) if current_op in operations else 0
                    step_var.set(
                        f"Operacja {current_idx + 1} z {len(operations)}. "
                        "Po ostatniej operacji WM zaliczy gotowy półprodukt."
                    )
                else:
                    step_var.set(
                        "Brak operacji technologicznych. Zgłoś ręcznie wykonaną "
                        "ilość półproduktu poniżej."
                    )
            else:
                selected_semi_var.set("Wybierz półprodukt z listy powyżej.")
                step_var.set("")

            if operations:
                operation_frame.pack(fill="x", pady=(4, 0), before=advanced_toggle)
            else:
                operation_frame.pack_forget()
            if pending > 1e-9:
                surplus_button.pack(side="left", padx=(6, 4))
            else:
                surplus_button.pack_forget()
            if advanced_open.get() or (bool(code) and not operations):
                semi_edit.pack(fill="x", pady=(8, 0), before=advanced_toggle)
            else:
                semi_edit.pack_forget()
            advanced_toggle.configure(
                text=(
                    "Ukryj korektę planu i zapis ręczny ▴"
                    if advanced_open.get()
                    else "Korekta planu / zapis ręczny ▾"
                )
            )

        def toggle_advanced():
            advanced_open.set(not advanced_open.get())
            update_semi_controls()

        advanced_toggle.configure(command=toggle_advanced)

        ttk.Separator(semis_tab).pack(fill="x", pady=(12, 7))
        ttk.Label(
            semis_tab, text="3. Gotowy produkt",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            semis_tab, textvariable=proposal_var,
            wraplength=880, justify="left",
        ).pack(anchor="w", pady=(4, 6))
        ttk.Button(
            semis_tab, text="Przejdź do potwierdzenia produktu →",
            command=lambda: notebook.select(realization_tab),
        ).pack(anchor="w")
        ttk.Label(
            semis_tab,
            text="WM wylicza kompletne zestawy, ale wykonanie produktu "
                 "potwierdzasz osobno w zakładce Realizacja.",
            wraplength=880, justify="left",
        ).pack(anchor="w", pady=(5, 0))

        footer = ttk.Frame(card)
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(12, 8))

        def delete_order():
            nonlocal order
            oid = str(order.get("id") or "")
            if not messagebox.askyesno(
                "Usuń zlecenie",
                f"Czy na pewno usunąć zlecenie {oid}?\n\n"
                "Zostaną zwolnione jego rezerwacje i usunięte powiązane dyspozycje.",
                parent=dlg,
            ):
                return
            try:
                if not ZL.delete_zlecenie(oid, kto=self.login or "system"):
                    raise RuntimeError("Zlecenie już nie istnieje.")
            except Exception as exc:
                messagebox.showerror("Usuń zlecenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        def print_current():
            oid = str(order.get("id") or "")
            if oid and self.tree.exists(oid):
                self.tree.selection_set(oid)
                self.tree.focus(oid)
            self.print_work_order()

        ttk.Button(footer, text="Usuń zlecenie", command=delete_order).pack(side="left")
        add_help_button(
            footer,
            "Usuwa zlecenie po potwierdzeniu. WM zwalnia jego rezerwacje i usuwa powiązane dyspozycje.",
            command_only=False,
        ).pack(side="left", padx=(4, 0))
        ttk.Button(footer, text="Zamknij", command=dlg.destroy).pack(side="right")
        ttk.Button(footer, text="Drukuj", command=print_current).pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="Zapisz dane zlecenia", command=save_basic).pack(side="right", padx=(0, 6))

        refresh_editor(reset_inputs=True)

    def build_orders(self, parent):
        old_build(self, parent)
        frames = [child for child in parent.winfo_children() if isinstance(child, ttk.Frame)]
        if not frames:
            return
        bar = frames[-1]

        # Operacje na pojedynczym zleceniu są w jednym edytorze otwieranym dwuklikiem.
        # Excel ma własny pasek i zostaje poza edycją pojedynczego zlecenia.
        for child in list(bar.winfo_children()):
            child.destroy()

        ttk.Button(bar, text="Dodaj zlecenie", command=self.add_order).pack(side="left")
        add_help_button(
            bar,
            "Tworzy nowe zlecenie na podstawie wybranego produktu i jego aktualnego BOM. Planista wyliczy półprodukty, surowce oraz rezerwacje.",
            command_only=False,
        ).pack(side="left", padx=(4, 0))

        self.tree.bind("<Double-1>", lambda _e: self.edit_order())

    Panel.add_order = add_order
    Panel.edit_order = edit_order
    build_orders._wm_order_editor = True
    build_orders._wm_original = old_build
    Panel._build_orders = build_orders


def _install_operations_editor() -> None:
    import gui_magazyn_bom as GMB
    import planista_operations_runtime as POR
    from ui_context_help import add_help_button

    UI = GMB.MagazynBOM
    old_build = UI._build_operations_dictionary
    if getattr(old_build, "_wm_edit_operation", False):
        return

    def select_operation(self, _event=None):
        selection = self.tree_operations.selection()
        if not selection:
            return
        values = POR._load_operations()
        idx = int(selection[0])
        if 0 <= idx < len(values):
            self._editing_operation_original = values[idx]
            self.operation_name.set(values[idx])

    def edit_operation(self):
        old_name = str(getattr(self, "_editing_operation_original", "") or "").strip()
        new_name = self.operation_name.get().strip()
        if not old_name:
            GMB._msg_error(self, "Operacje technologiczne", "Zaznacz operację do edycji.")
            return
        if not new_name:
            GMB._msg_error(self, "Operacje technologiczne", "Nazwa operacji nie może być pusta.")
            return
        values = POR._load_operations()
        if old_name not in values:
            GMB._msg_error(self, "Operacje technologiczne", "Operacja została zmieniona w innym miejscu. Odśwież listę.")
            return
        if new_name.casefold() != old_name.casefold() and any(x.casefold() == new_name.casefold() for x in values):
            GMB._msg_error(self, "Operacje technologiczne", "Taka operacja już istnieje.")
            return
        values[values.index(old_name)] = new_name
        fresh = GMB.WarehouseModel()
        for code, rec in list(fresh.polprodukty.items()):
            if not isinstance(rec, dict):
                continue
            operations = list(rec.get("czynnosci") or [])
            changed = False
            for idx, value in enumerate(operations):
                if str(value).casefold() == old_name.casefold():
                    operations[idx] = new_name
                    changed = True
            if changed:
                updated = dict(rec)
                updated["czynnosci"] = operations
                fresh.add_or_update_polprodukt(updated)
        POR._save_operations(values)
        self.model.polprodukty = fresh.polprodukty
        self._editing_operation_original = ""
        self.operation_name.set("")
        self._refresh_operations_tree()
        self._refresh_pp_operations()
        if hasattr(self, "_load_polprodukty"):
            self._load_polprodukty()

    def build_operations(self, parent):
        old_build(self, parent)
        self._editing_operation_original = ""
        self.tree_operations.bind("<<TreeviewSelect>>", self._select_operation_for_edit, add="+")
        top = next((child for child in parent.winfo_children() if isinstance(child, ttk.Frame)), None)
        if top is not None:
            ttk.Button(top, text="Zapisz zmianę", command=self._edit_operation).grid(row=1, column=3, padx=(8, 0))
            add_help_button(top, "Zmienia nazwę zaznaczonej operacji i aktualizuje wszystkie półprodukty, które jej używają. Powiązania technologiczne nie zostaną utracone.", row=1, column=4, padx=(4, 0))

    UI._select_operation_for_edit = select_operation
    UI._edit_operation = edit_operation
    build_operations._wm_edit_operation = True
    UI._build_operations_dictionary = build_operations


def _install_raw_kind_editor() -> None:
    import gui_magazyn_bom as GMB
    from ui_context_help import add_help_button

    UI = GMB.MagazynBOM
    old_build = UI._build_raw_kinds
    if getattr(old_build, "_wm_edit_raw_kind", False):
        return

    def select_kind(self, _event=None):
        selection = self.tree_raw_kinds.selection()
        if not selection:
            return
        idx = int(selection[0])
        if not (0 <= idx < len(self.model.raw_kinds)):
            return
        rec = self.model.raw_kinds[idx]
        self._editing_raw_kind_original = str(rec.get("nazwa") or "")
        self.raw_kind_name.set(self._editing_raw_kind_original)
        self.raw_kind_mode.set("Fi" if str(rec.get("pole") or "").casefold() == "fi" else "Wymiar")

    def edit_kind(self):
        old_name = str(getattr(self, "_editing_raw_kind_original", "") or "").strip()
        new_name = self.raw_kind_name.get().strip()
        mode = "fi" if self.raw_kind_mode.get() == "Fi" else "wymiar"
        if not old_name:
            GMB._msg_error(self, "Rodzaje surowców", "Zaznacz rodzaj surowca do edycji.")
            return
        if not new_name:
            GMB._msg_error(self, "Rodzaje surowców", "Nazwa rodzaju nie może być pusta.")
            return

        fresh = GMB.WarehouseModel()
        target = next((item for item in fresh.raw_kinds if str(item.get("nazwa") or "").casefold() == old_name.casefold()), None)
        if target is None:
            GMB._msg_error(self, "Rodzaje surowców", "Rodzaj został zmieniony w innym miejscu. Odśwież listę.")
            return
        if new_name.casefold() != old_name.casefold() and any(str(item.get("nazwa") or "").casefold() == new_name.casefold() for item in fresh.raw_kinds):
            GMB._msg_error(self, "Rodzaje surowców", "Taki rodzaj surowca już istnieje.")
            return

        records = []
        for item in fresh.raw_kinds:
            if item is target:
                records.append({"nazwa": new_name, "pole": mode})
            else:
                records.append(dict(item))
        fresh.save_raw_kinds(records)

        for code, rec in list(fresh.surowce.items()):
            if not isinstance(rec, dict) or str(rec.get("rodzaj") or "").casefold() != old_name.casefold():
                continue
            updated = dict(rec)
            updated["rodzaj"] = new_name
            size = str(updated.get("rozmiar") or updated.get("wymiar") or updated.get("fi") or "").strip()
            updated.pop("fi", None)
            updated.pop("wymiar", None)
            updated.update(GMB._raw_dimension_fields(new_name, size, mode))
            fresh.add_or_update_surowiec(updated)

        self.model.raw_kinds = fresh.raw_kinds
        self.model.surowce = fresh.surowce
        self._kind_dimension_modes = {
            str(item["nazwa"]): str(item.get("pole") or "wymiar").casefold()
            for item in fresh.raw_kinds
            if isinstance(item, dict) and item.get("nazwa")
        }
        self.s_kind_combo.configure(values=tuple(self._kind_dimension_modes))
        self._editing_raw_kind_original = ""
        self.raw_kind_name.set("")
        self._refresh_raw_kinds_tree()
        self._load_surowce()
        self._refresh_raw_selector()

    def build_raw_kinds(self, parent):
        old_build(self, parent)
        self._editing_raw_kind_original = ""
        self.tree_raw_kinds.bind("<<TreeviewSelect>>", self._select_raw_kind_for_edit, add="+")
        top = next((child for child in parent.winfo_children() if isinstance(child, ttk.Frame)), None)
        if top is not None:
            ttk.Button(top, text="Zapisz zmianę", command=self._edit_raw_kind).grid(row=1, column=4, padx=(8, 0))
            add_help_button(top, "Zmienia nazwę lub typ wymiaru zaznaczonego rodzaju. Surowce używające tego rodzaju zostaną automatycznie zaktualizowane.", row=1, column=5, padx=(4, 0))

    UI._select_raw_kind_for_edit = select_kind
    UI._edit_raw_kind = edit_kind
    build_raw_kinds._wm_edit_raw_kind = True
    UI._build_raw_kinds = build_raw_kinds


def install_planista_editor_runtime() -> None:
    _install_order_editor()
    _install_operations_editor()
    _install_raw_kind_editor()


__all__ = ["install_planista_editor_runtime"]
