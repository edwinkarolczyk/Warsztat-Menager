from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


path = Path("gui_dyspozycje_creator.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''# version: 1.1\n# Zmiany 1.1:\n# - Termin jest edytowany jako DD-MM-RR, z kalendarzem oraz skrótami +2 dni, +1 tydzień i +2 tygodnie.\n# - Do pliku termin nadal trafia jako YYYY-MM-DD; błędny format jest blokowany.\n# - Brak przypisanego użytkownika automatycznie ustawia Dyspozycję dla wszystkich.\n# - Autor zapisu jest pobierany z bieżącej sesji.\n''',
    '''# version: 1.2\n# Zmiany 1.2:\n# - Nowa Dyspozycja pokazuje od razu bieżącą datę w polu terminu.\n# - Termin jest tylko do odczytu; zmiana odbywa się przez kalendarz lub szybkie przyciski.\n# - Przy wyszukiwarce obiektu dodano etykietę „Wyszukaj:”.\n# Zmiany 1.1:\n# - Termin jest edytowany jako DD-MM-RR, z kalendarzem oraz skrótami +2 dni, +1 tydzień i +2 tygodnie.\n# - Do pliku termin nadal trafia jako YYYY-MM-DD; błędny format jest blokowany.\n# - Brak przypisanego użytkownika automatycznie ustawia Dyspozycję dla wszystkich.\n# - Autor zapisu jest pobierany z bieżącej sesji.\n''',
    "header",
)

text = replace_once(
    text,
    '''    var_object_search = tk.StringVar()\n    ent_object_search = ttk.Entry(frame, textvariable=var_object_search)\n    ent_object_search.grid(row=2, column=1, sticky="ew", pady=4)\n    ent_object_search.grid_remove()\n''',
    '''    var_object_search = tk.StringVar()\n    lbl_object_search = ttk.Label(frame, text="Wyszukaj:")\n    lbl_object_search.grid(row=2, column=0, sticky="w", pady=4)\n    lbl_object_search.grid_remove()\n    ent_object_search = ttk.Entry(frame, textvariable=var_object_search)\n    ent_object_search.grid(row=2, column=1, sticky="ew", pady=4)\n    ent_object_search.grid_remove()\n''',
    "search label",
)

text = replace_once(
    text,
    '''    ttk.Label(frame, text="Termin (DD-MM-RR):").grid(row=6, column=0, sticky="w", pady=4)\n    var_deadline = tk.StringVar(value=_deadline_to_display(ctx.get("termin") or ""))\n    deadline_frame = ttk.Frame(frame)\n    deadline_frame.grid(row=6, column=1, sticky="w", pady=4)\n    ent_deadline = ttk.Entry(deadline_frame, textvariable=var_deadline, width=14)\n    ent_deadline.pack(side="left")\n''',
    '''    ttk.Label(frame, text="Termin (DD-MM-RR):").grid(row=6, column=0, sticky="w", pady=4)\n    initial_deadline = _deadline_to_display(ctx.get("termin") or "")\n    if not initial_deadline:\n        initial_deadline = _dt.date.today().strftime("%d-%m-%y")\n    var_deadline = tk.StringVar(value=initial_deadline)\n    deadline_frame = ttk.Frame(frame)\n    deadline_frame.grid(row=6, column=1, sticky="w", pady=4)\n    ent_deadline = ttk.Entry(\n        deadline_frame,\n        textvariable=var_deadline,\n        width=14,\n        state="readonly",\n    )\n    ent_deadline.pack(side="left")\n''',
    "deadline readonly/current",
)

text = replace_once(
    text,
    '''        if source_key in {"narzedzia", "maszyny"}:\n            ent_object_search.grid()\n        else:\n            ent_object_search.grid_remove()\n''',
    '''        if source_key in {"narzedzia", "maszyny"}:\n            lbl_object_search.grid()\n            ent_object_search.grid()\n        else:\n            lbl_object_search.grid_remove()\n            ent_object_search.grid_remove()\n''',
    "search label visibility",
)

path.write_text(text, encoding="utf-8")
print("patched gui_dyspozycje_creator.py")
