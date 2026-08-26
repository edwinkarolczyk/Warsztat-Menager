from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected 1 exact match, got {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "gui_logowanie.py",
    "# version: 1.0\n# Plik: gui_logowanie.py (beta)\n# Zmiany 1.4.12.1:\n",
    "# version: 1.4.13\n# Plik: gui_logowanie.py (beta)\n# Zmiany 1.4.13:\n# - Tryby 121 i 212 przełączają zmianę naprzemiennie co tydzień; 111 i 222 pozostają stałe.\n# Zmiany 1.4.12.1:\n",
)

replace_once(
    "gui_logowanie.py",
    '''    # POPRAWKA: tryb zmian interpretujemy jako CYKL TYGODNIOWY (np. 121 / 212 / 111)\n    # a nie jako rozkład dni tygodnia\n    mode = _user_shift_mode(profile)\n    seq = [c for c in mode if c in ("1", "2")]\n    if not seq:\n        return None\n\n    # liczymy który to tydzień od startu rotacji\n    start = _global_rotation_start()\n    if not start:\n        week_idx = 0\n    else:\n        delta_days = (now.date() - start).days\n        week_idx = max(0, delta_days // 7)\n\n    # wybieramy zmianę dla całego tygodnia\n    c = seq[week_idx % len(seq)]\n    return "RANO" if c == "1" else "POPO"\n''',
    '''    # Tryb jest tygodniowy. 121/212 oznacza naprzemienną zmianę co tydzień,\n    # a 111/222 oznacza stałą zmianę. Inne starsze wzorce zachowują\n    # dotychczasowe cykliczne działanie.\n    mode = _user_shift_mode(profile)\n    seq = [c for c in mode if c in ("1", "2")]\n    if not seq:\n        return None\n\n    # liczymy który to tydzień od startu rotacji\n    start = _global_rotation_start()\n    if not start:\n        week_idx = 0\n    else:\n        delta_days = (now.date() - start).days\n        week_idx = max(0, delta_days // 7)\n\n    normalized_mode = "".join(seq)\n    if normalized_mode in {"111", "222"}:\n        c = normalized_mode[0]\n    elif normalized_mode in {"121", "212"}:\n        first = normalized_mode[0]\n        c = first if week_idx % 2 == 0 else ("2" if first == "1" else "1")\n    else:\n        c = seq[week_idx % len(seq)]\n    return "RANO" if c == "1" else "POPO"\n''',
)

replace_once(
    "grafiki/shifts_schedule.py",
    "# version: 1.0\n# Plik: grafiki/shifts_schedule.py\n# Zmiany:\n# - Silnik rotacji zmian oraz API\n",
    "# version: 1.1\n# Plik: grafiki/shifts_schedule.py\n# Zmiany 1.1:\n# - Tryby 121 i 212 przełączają zmianę naprzemiennie co tydzień; 111 i 222 pozostają stałe.\n# Zmiany:\n# - Silnik rotacji zmian oraz API\n",
)

replace_once(
    "grafiki/shifts_schedule.py",
    '''_DEFAULT_PATTERNS = {\n    "112": "112",\n    "111": "111",\n    "12": "12",\n    "121": "121",\n    "211": "211",\n    "1212": "1212",\n}\n''',
    '''_DEFAULT_PATTERNS = {\n    "112": "112",\n    "111": "111",\n    "222": "222",\n    "12": "12",\n    "121": "121",\n    "212": "212",\n    "211": "211",\n    "1212": "1212",\n}\n''',
)

replace_once(
    "grafiki/shifts_schedule.py",
    '''def _slot_for_mode(mode: str, week_idx: int) -> str:\n    patterns = _available_patterns()\n    pattern = patterns.get(mode, mode)\n    if not pattern:\n        pattern = "1"\n    idx = week_idx % len(pattern)\n    digit = pattern[idx]\n    return "RANO" if digit == "1" else "POPO"\n''',
    '''def _slot_for_mode(mode: str, week_idx: int) -> str:\n    patterns = _available_patterns()\n    pattern = patterns.get(mode, mode)\n    digits = [c for c in str(pattern or "1") if c in ("1", "2")]\n    if not digits:\n        digits = ["1"]\n\n    normalized_mode = "".join(digits)\n    if normalized_mode in {"111", "222"}:\n        digit = normalized_mode[0]\n    elif normalized_mode in {"121", "212"}:\n        first = normalized_mode[0]\n        digit = first if week_idx % 2 == 0 else ("2" if first == "1" else "1")\n    else:\n        digit = digits[week_idx % len(digits)]\n    return "RANO" if digit == "1" else "POPO"\n''',
)
