from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# dyspozycje_store.py
path = Path("dyspozycje_store.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.1\n# Zmiany 1.1:\n",
    "# version: 1.2\n# Zmiany 1.2:\n"
    "# - Przy rozpoczęciu Dyspozycji zapisywany jest wykonawca i czas rozpoczęcia.\n"
    "# - Przypisanie pozostaje bez zmian; wykonawca jest osobnym polem rekordu.\n"
    "# Zmiany 1.1:\n",
    "store version",
)
text = replace_once(
    text,
    '        "utworzono": _now_iso(),\n        "wykonano": "",\n',
    '        "utworzono": _now_iso(),\n'
    '        "wykonuje": "",\n'
    '        "rozpoczal_at": "",\n'
    '        "wykonano": "",\n',
    "store new fields",
)
text = replace_once(
    text,
    '        "utworzono": str(src.get("utworzono") or _now_iso()).strip(),\n'
    '        "wykonano": str(src.get("wykonano") or "").strip(),\n',
    '        "utworzono": str(src.get("utworzono") or _now_iso()).strip(),\n'
    '        "wykonuje": _normalize_login(src.get("wykonuje")),\n'
    '        "rozpoczal_at": str(src.get("rozpoczal_at") or "").strip(),\n'
    '        "wykonano": str(src.get("wykonano") or "").strip(),\n',
    "store normalize fields",
)
text = replace_once(
    text,
    '    updates: dict[str, Any] = {\n'
    '        "status": target,\n'
    '        "meta": meta,\n'
    '    }\n'
    '    if target == "zamknieta":\n',
    '    updates: dict[str, Any] = {\n'
    '        "status": target,\n'
    '        "meta": meta,\n'
    '    }\n'
    '    if current == "nowa" and target == "w_toku":\n'
    '        updates["wykonuje"] = who\n'
    '        updates["rozpoczal_at"] = now\n'
    '    if target == "zamknieta":\n',
    "store start performer",
)
path.write_text(text, encoding="utf-8")


# gui_zlecenia.py
path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.3\n# Zmiany 1.3:\n",
    "# version: 1.4\n# Zmiany 1.4:\n"
    "# - Kolumna przypisania pokazuje osobno zleconego i faktycznego wykonawcę.\n"
    "# - Rozpoczęcie cudzej Dyspozycji wymaga potwierdzenia i nie zmienia przypisania.\n"
    "# - Dyspozycja dla wszystkich po rozpoczęciu pokazuje osobę, która ją podjęła.\n"
    "# Zmiany 1.3:\n",
    "gui version",
)
text = replace_once(
    text,
    'def _dysp_assigned_label(item: dict[str, Any]) -> str:\n'
    '    if item.get("dla_wszystkich") is True:\n'
    '        return "wszyscy"\n'
    '    return str(item.get("przypisane_do") or "—").strip() or "—"\n',
    'def _dysp_assigned_label(item: dict[str, Any]) -> str:\n'
    '    for_all = item.get("dla_wszystkich") is True\n'
    '    assigned = str(item.get("przypisane_do") or "").strip()\n'
    '    base = "wszyscy" if for_all else (assigned or "—")\n'
    '    performer = str(item.get("wykonuje") or "").strip()\n'
    '    if not performer:\n'
    '        return base\n'
    '    mismatch = bool(\n'
    '        not for_all\n'
    '        and assigned\n'
    '        and assigned.lower() != performer.lower()\n'
    '    )\n'
    '    prefix = "⚠ " if mismatch else ""\n'
    '    return f"{prefix}{base} → {performer}"\n',
    "gui assigned performer label",
)
text = replace_once(
    text,
    '            "przypisane": 135,\n',
    '            "przypisane": 190,\n',
    "gui assigned width",
)
text = replace_once(
    text,
    '    def _on_start(self) -> None:\n'
    '        self._change_status("w_toku")\n',
    '    def _on_start(self) -> None:\n'
    '        mapped = self._selected_row()\n'
    '        if not mapped:\n'
    '            messagebox.showinfo(\n'
    '                "Dyspozycje",\n'
    '                "Najpierw wybierz Dyspozycję.",\n'
    '                parent=self,\n'
    '            )\n'
    '            return\n'
    '        who = str(self._login_user or mapped.get("autor") or "").strip()\n'
    '        assigned = str(mapped.get("przypisane_do") or "").strip()\n'
    '        for_all = mapped.get("dla_wszystkich") is True\n'
    '        if (\n'
    '            not for_all\n'
    '            and assigned\n'
    '            and who\n'
    '            and assigned.lower() != who.lower()\n'
    '        ):\n'
    '            ok = messagebox.askyesno(\n'
    '                "Rozpocznij cudzą Dyspozycję",\n'
    '                f"Dyspozycja jest przypisana do: {assigned}.\\n"\n'
    '                f"Jesteś zalogowany jako: {who}.\\n\\n"\n'
    '                "Czy na pewno chcesz ją rozpocząć?",\n'
    '                parent=self,\n'
    '            )\n'
    '            if not ok:\n'
    '                return\n'
    '        self._change_status("w_toku")\n',
    "gui foreign start warning",
)
path.write_text(text, encoding="utf-8")

print("Dyspozycje stage 3.1 patch applied")
