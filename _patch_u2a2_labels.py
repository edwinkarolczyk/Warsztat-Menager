from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected exactly {expected} matches, got {count}")
    return text.replace(old, new)


plan_path = Path("gui_planowanie.py")
plan = plan_path.read_text(encoding="utf-8")
plan = replace_once(plan, "# version: 1.2\n", "# version: 1.3\n", "plan version")
plan = replace_once(
    plan,
    "# =========================================================\n# Zmiany 1.2:\n",
    "# =========================================================\n# Zmiany 1.3:\n"
    "# - Nazwa widoczna BOM została zmieniona na Skład produktu; dane wewnętrzne pozostają bez zmian.\n"
    "# - W Planowaniu doprecyzowano Nr zlecenia oraz nazewnictwo rewizji/składu.\n"
    "# Zmiany 1.2:\n",
    "plan changelog",
)
plan = replace_once(plan, 'notebook.add(tab_bom, text="BOM")', 'notebook.add(tab_bom, text="SKŁAD PRODUKTU")', "planning tab")
plan = replace_once(plan, 'self.orders_tree.heading("number", text="Nr")', 'self.orders_tree.heading("number", text="Nr zlecenia")', "order number heading")
plan = replace_once(plan, '("bom_revision", "Rewizja BOM", 100),', '("bom_revision", "Rewizja składu", 110),', "products revision heading")
plan = replace_once(plan, '("bom_count", "Pozycji BOM", 100),', '("bom_count", "Pozycji składu", 110),', "products count heading")
plan = replace_once(
    plan,
    '"Ta zakładka zarządza metadanymi produktów. Istniejący BOM produktu "\n            "nie jest tu przepisywany ani usuwany; osobny edytor BOM zostanie "\n            "podpięty w kolejnym etapie."',
    '"Ta zakładka zarządza metadanymi produktów. Istniejący skład produktu "\n            "nie jest tu przepisywany ani usuwany; edycja składu jest dostępna "\n            "w zakładce Skład produktu."',
    "products info",
)
plan = replace_once(plan, '("Rewizja BOM:", revision_var),', '("Rewizja składu:", revision_var),', "product form revision")
plan_path.write_text(plan, encoding="utf-8")

bom_path = Path("gui_planowanie_bom.py")
bom = bom_path.read_text(encoding="utf-8")
bom = replace_once(bom, "# version: 1.0\n", "# version: 1.1\n", "bom ui version")
bom = replace_once(
    bom,
    "# U2A-2: Półprodukty i edytor BOM w Planowaniu.\n",
    "# U2A-2: Półprodukty i edytor BOM w Planowaniu.\n"
    "# Zmiany 1.1:\n"
    "# - W interfejsie BOM nazwano Składem produktu, a materiał Surowcem.\n"
    "# - Nazwy wewnętrzne pozostają bez zmian dla zgodności danych.\n",
    "bom ui changelog",
)
replacements = [
    ("('material', 'Materiał', 150)", "('material', 'Surowiec', 150)", "semi heading"),
    ("('Kod materiału:', 'material_kod')", "('Kod surowca:', 'material_kod')", "semi material code"),
    ("('Ilość materiału na szt.:', 'material_ilosc')", "('Ilość surowca na szt.:', 'material_ilosc')", "semi material qty"),
    ("text='Zapisz BOM'", "text='Zapisz skład'", "save button"),
    ("('material', 'Materiał z półproduktu', 220)", "('material', 'Surowiec z półproduktu', 220)", "composition material heading"),
    ("messagebox.askyesno('BOM', 'Masz niezapisane zmiany BOM. Odrzucić je?'", "messagebox.askyesno('Skład produktu', 'Masz niezapisane zmiany składu produktu. Odrzucić je?'", "discard refresh"),
    ("messagebox.showerror('BOM', f'Nie udało się wczytać produktów:\\n{exc}'", "messagebox.showerror('Skład produktu', f'Nie udało się wczytać produktów:\\n{exc}'", "load products error"),
    ("messagebox.askyesno('BOM', 'Masz niezapisane zmiany BOM. Odrzucić je i przejść do innego produktu?'", "messagebox.askyesno('Skład produktu', 'Masz niezapisane zmiany składu produktu. Odrzucić je i przejść do innego produktu?'", "discard switch"),
    ("self.status_var.set(f\"BOM produktu {product.get('kod','')} | rewizja {product.get('bom_revision', 1)}\")", "self.status_var.set(f\"Skład produktu {product.get('kod','')} | rewizja {product.get('bom_revision', 1)}\")", "composition status"),
    ("win.title('Pozycja BOM')", "win.title('Pozycja składu produktu')", "entry title"),
    ("text='Czynności BOM (opcjonalne):'", "text='Czynności składu (opcjonalne):'", "entry ops label"),
    ("text='Materiał nie jest kopiowany do BOM — pochodzi z definicji półproduktu.'", "text='Surowiec nie jest kopiowany do składu produktu — pochodzi z definicji półproduktu.'", "entry source note"),
    ("messagebox.showerror('BOM', 'Wybierz lub wpisz kod półproduktu.'", "messagebox.showerror('Skład produktu', 'Wybierz lub wpisz kod półproduktu.'", "entry code error"),
    ("messagebox.showerror('BOM', 'Ilość musi być liczbą.'", "messagebox.showerror('Skład produktu', 'Ilość musi być liczbą.'", "entry qty error"),
    ("messagebox.showerror('BOM', 'Ilość musi być większa od zera.'", "messagebox.showerror('Skład produktu', 'Ilość musi być większa od zera.'", "entry qty positive"),
    ("messagebox.showerror('BOM', str(exc), parent=self)", "messagebox.showerror('Skład produktu', str(exc), parent=self)", "save error title"),
    ("messagebox.showerror('BOM', f'Nie udało się zapisać BOM:\\n{exc}', parent=self)", "messagebox.showerror('Skład produktu', f'Nie udało się zapisać składu produktu:\\n{exc}', parent=self)", "save exception"),
    ("self.status_var.set(f\"Zapisano BOM | rewizja {saved.get('bom_revision', 1)}\")", "self.status_var.set(f\"Zapisano skład produktu | rewizja {saved.get('bom_revision', 1)}\")", "saved status"),
    ("'Nie można usunąć — półprodukt jest używany w BOM: '", "'Nie można usunąć — półprodukt jest używany w składzie produktu: '", "delete used message"),
]
for old, new, label in replacements:
    bom = replace_once(bom, old, new, label)
bom = replace_exact(
    bom,
    "self.status_var.set('Niezapisane zmiany BOM.')",
    "self.status_var.set('Niezapisane zmiany składu produktu.')",
    2,
    "dirty statuses",
)
bom_path.write_text(bom, encoding="utf-8")

print("Terminology patch prepared")
