from pathlib import Path

path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    text = text.replace(old, new, 1)


replace_once(
    "# version: 1.8\n# Zmiany 1.8:\n",
    "# version: 1.9\n# Zmiany 1.9:\n"
    "# - Termin w tabeli Dyspozycji jest wyświetlany w formacie jak w Maszynach: dzień tygodnia + DD-MM-RR.\n"
    "# - Zapis terminu w danych pozostaje bez zmian (ISO), zmienia się wyłącznie prezentacja.\n"
    "# Zmiany 1.8:\n",
    "version header",
)

anchor = '''def _dysp_due_in_label(item: dict[str, Any]) -> str:\n'''
formatter = '''_DYSP_WEEKDAY_LABELS_PL = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")\n\n\ndef _format_dysp_deadline(value: Any) -> str:\n    raw = str(value or "").strip()\n    if not raw:\n        return "—"\n    try:\n        parsed_date = _dt.date.fromisoformat(raw[:10])\n    except Exception:\n        return raw\n\n    weekday = _DYSP_WEEKDAY_LABELS_PL[parsed_date.weekday()]\n    date_text = parsed_date.strftime("%d-%m-%y")\n\n    time_text = ""\n    if len(raw) >= 16 and ("T" in raw[:16] or " " in raw[:16]):\n        candidate = raw[11:16]\n        if len(candidate) == 5 and candidate[2] == ":":\n            time_text = candidate\n\n    return f"{weekday} {date_text}" + (f" {time_text}" if time_text else "")\n\n\n'''
replace_once(anchor, formatter + anchor, "deadline formatter anchor")

replace_once(
    '                        str(order.get("termin") or "—"),\n',
    '                        _format_dysp_deadline(order.get("termin") or order.get("deadline")),\n',
    "deadline table display",
)

path.write_text(text, encoding="utf-8")
