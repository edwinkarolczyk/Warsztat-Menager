from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# Narzędzia — tylko aktywne listy Treeview.
p = Path("narzedzia_ui/list_panel.py")
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    '# version: 1.0\n',
    '# version: 1.1\n# Zmiany 1.1:\n# - Listy Narzędzi używają tej samej wielkości czcionki co Dyspozycje: Segoe UI 11, nagłówki 11 bold, wiersz 30 px.\n',
    'tools version',
)
anchor = 'REFRESH_INTERVAL_SECONDS = 30\n\n\nclass ToolsThreeTabsView(ttk.Frame):'
insert = '''REFRESH_INTERVAL_SECONDS = 30\n\n\ndef _apply_dysp_table_font(tree: ttk.Treeview) -> None:\n    \"\"\"Wyrównaj czytelność tabel Narzędzi do aktywnej tabeli Dyspozycji.\"\"\"\n    try:\n        style = ttk.Style(tree)\n        style.configure(\"Tools.Treeview\", font=(\"Segoe UI\", 11), rowheight=30)\n        style.configure(\"Tools.Treeview.Heading\", font=(\"Segoe UI\", 11, \"bold\"))\n        tree.configure(style=\"Tools.Treeview\")\n    except Exception:\n        pass\n\n\nclass ToolsThreeTabsView(ttk.Frame):'''
s = replace_once(s, anchor, insert, 'tools style helper')
for old, new, label in [
    ('        self.tv_inprog.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', '        _apply_dysp_table_font(self.tv_inprog)\n        self.tv_inprog.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', 'tools in progress'),
    ('        self.tv_all.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', '        _apply_dysp_table_font(self.tv_all)\n        self.tv_all.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', 'tools all'),
    ('        self.tv_tasks.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', '        _apply_dysp_table_font(self.tv_tasks)\n        self.tv_tasks.pack(fill="both", expand=True, padx=8, pady=(0, 8))\n', 'tools tasks'),
]:
    s = replace_once(s, old, new, label)
p.write_text(s, encoding="utf-8")


# Maszyny — tylko główna tabela listy.
p = Path("gui_maszyny.py")
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    '# version: 1.0\n',
    '# version: 1.1\n# Zmiany 1.1:\n# - Główna lista Maszyn używa tej samej wielkości czcionki co Dyspozycje: Segoe UI 11, nagłówki 11 bold, wiersz 30 px.\n',
    'machines version',
)
old = '''    _ensure_tree_columns(tree)\n    for r in rows:\n        _tree_insert_row(tree, r)\n'''
new = '''    _ensure_tree_columns(tree)\n    try:\n        style = ttk.Style(tree)\n        style.configure(\"Maszyny.Treeview\", font=(\"Segoe UI\", 11), rowheight=30)\n        style.configure(\"Maszyny.Treeview.Heading\", font=(\"Segoe UI\", 11, \"bold\"))\n        tree.configure(style=\"Maszyny.Treeview\")\n    except Exception:\n        pass\n    for r in rows:\n        _tree_insert_row(tree, r)\n'''
s = replace_once(s, old, new, 'machines tree style')
p.write_text(s, encoding="utf-8")
