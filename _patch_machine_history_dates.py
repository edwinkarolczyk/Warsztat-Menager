from pathlib import Path

path = Path("gui_maszyny.py")
text = path.read_text(encoding="utf-8")

old_header = '''# version: 1.3
# Zmiany 1.3:
'''
new_header = '''# version: 1.4
# Zmiany 1.4:
# - Start/Stop w historii statusów pokazują polski skrót dnia tygodnia oraz datę DD-MM-RR z godziną.
# Zmiany 1.3:
'''
if old_header not in text:
    raise SystemExit("Nie znaleziono nagłówka wersji 1.3")
text = text.replace(old_header, new_header, 1)

anchor = '''def _duration_minutes(started_at: object, ended_at: object) -> int:
'''
helper = '''_MACHINE_WEEKDAY_LABELS_PL = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")


def _format_machine_history_dt(value: object) -> str:
    parsed = _parse_machine_dt(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw.replace("T", " ")[:16] if raw else "—"
    weekday = _MACHINE_WEEKDAY_LABELS_PL[parsed.weekday()]
    return f"{weekday} {parsed.strftime('%d-%m-%y %H:%M')}"


'''
if anchor not in text:
    raise SystemExit("Nie znaleziono miejsca na helper dat historii")
text = text.replace(anchor, helper + anchor, 1)

old_closed = '''            start = str(item.get("started_at") or "—").replace("T", " ")[:16]
            stop = str(item.get("ended_at") or "—").replace("T", " ")[:16]
'''
new_closed = '''            start = _format_machine_history_dt(item.get("started_at"))
            stop = _format_machine_history_dt(item.get("ended_at"))
'''
if old_closed not in text:
    raise SystemExit("Nie znaleziono formatowania Start/Stop dla historii zamkniętej")
text = text.replace(old_closed, new_closed, 1)

old_current = '''                str(start_raw or "—").replace("T", " ")[:16],
                "w toku",
'''
new_current = '''                _format_machine_history_dt(start_raw),
                "w toku",
'''
if old_current not in text:
    raise SystemExit("Nie znaleziono formatowania Start dla bieżącego statusu")
text = text.replace(old_current, new_current, 1)

path.write_text(text, encoding="utf-8")
