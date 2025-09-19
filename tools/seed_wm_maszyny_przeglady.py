# -*- coding: utf-8 -*-
# Wersja: 1.0.1 (pure-Python, bez pandas)
# Czyta: data/import/Harmonogram przeglądów i napraw na 2025.csv
# Tworzy: data/maszyny/maszyny.json (format WM uproszczony)

import csv
import json
import os
from datetime import datetime

INPUT_CSV = "data/import/Harmonogram przeglądów i napraw na 2025.csv"
OUTPUT_DIR = "data/maszyny"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "maszyny.json")

# Rozmieszczenie
START_X, START_Y = 100, 100
STEP_X, STEP_Y = 150, 130
COLS = 10
SIZE_W, SIZE_H = 100, 60

MONTHS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def fix_pl(text):
    if not isinstance(text, str):
        return text
    replacements = {
        "¹": "ą",
        "³": "ł",
        "¿": "ż",
        "\u009c": "ś",
        "\u009f": "ź",
        "ê": "ę",
        "ñ": "ń",
        "\u008f": "ń",
        "\u0084": "ą",
        "\u0082": "ł",
        "\u0087": "ć",
        "\u009b": "ś",
        "\u009e": "ż",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def read_csv_latin1_auto_delim(path):
    with open(path, "r", encoding="latin1", newline="") as file_obj:
        sample = file_obj.read(4096)
        file_obj.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
        except Exception:
            class Simple(csv.Dialect):
                delimiter = ";"
                quotechar = '"'
                doublequote = True
                skipinitialspace = True
                lineterminator = "\n"
                quoting = csv.QUOTE_MINIMAL

            dialect = Simple()
        reader = csv.reader(file_obj, dialect)
        rows = [[fix_pl(cell) for cell in row] for row in reader]
    return rows


def build_machines_from_rows(rows):
    if len(rows) < 3:
        raise ValueError(
            "Za mało wierszy w CSV (spodziewane: 2 wiersze nagłówka + dane)."
        )

    header1 = rows[0]
    header2 = rows[1]
    data_rows = rows[2:]

    # Docelowe kolumny: "Hala","Nr ewid.","Maszyna","Typ" + miesiące z header2 (od index 4)
    columns = ["Hala", "Nr ewid.", "Maszyna", "Typ"] + header2[4:]
    # Mapowanie indeks->nazwa
    colmap = {
        idx: (columns[idx] if idx < len(columns) and columns[idx] else f"col{idx}")
        for idx in range(len(columns))
    }

    # Forward-fill Hala: zbierz najpierw surowe rekordy
    raw = []
    for row in data_rows:
        if all((cell is None or str(cell).strip() == "") for cell in row):
            continue
        item = {}
        for idx, value in enumerate(row[: len(columns)]):
            item[colmap[idx]] = (value or "").strip()
        raw.append(item)

    # FFill "Hala"
    last_hala = ""
    for item in raw:
        if item.get("Hala", ""):
            last_hala = item["Hala"]
        else:
            item["Hala"] = last_hala

    # Wydobądź przeglądy
    machines_rows = []
    for item in raw:
        name = (item.get("Typ", "") or "").strip()
        model = (item.get("Maszyna", "") or "").strip()
        if not name and not model:
            continue

        # miesiące obecne w header2 od index 4
        przeglady = []
        for idx in range(4, len(columns)):
            colname = columns[idx] if idx < len(columns) else None
            if colname and colname.strip() in MONTHS:
                raw_value = (item.get(colname, "") or "").strip()
                if raw_value and raw_value.lower() != "nan":
                    przeglady.append(raw_value)

        # hala -> int
        hall_raw = (item.get("Hala", "") or "").strip()
        try:
            hall = int(float(hall_raw)) if hall_raw else 1
        except Exception:
            hall = 1

        machines_rows.append(
            {
                "nazwa": name if name else (model if model else "MASZYNA"),
                "typ": model,
                "hala": hall,
                "przeglady": przeglady,
            }
        )

    # Pozycje
    machines = []
    per_hall_counter = {}
    for idx, row in enumerate(machines_rows, start=1):
        hall = row["hala"]
        hall_index = per_hall_counter.get(hall, 0)
        row_i, col_i = divmod(hall_index, COLS)
        x_pos = START_X + col_i * STEP_X
        y_pos = START_Y + row_i * STEP_Y
        per_hall_counter[hall] = hall_index + 1

        machines.append(
            {
                "id": str(idx),
                "nazwa": row["nazwa"],
                "typ": row["typ"],
                "hala": hall,
                "pozycja": {"x": x_pos, "y": y_pos},
                "rozmiar": {"w": SIZE_W, "h": SIZE_H},
                "status": "sprawna",
                "nastepne_zadanie": None,
                "przeglady": row["przeglady"],
            }
        )
    return machines


def main():
    if not os.path.isfile(INPUT_CSV):
        raise SystemExit(
            f"[ERROR] Brak pliku: {INPUT_CSV} (wrzuć CSV do data/import/)"
        )

    rows = read_csv_latin1_auto_delim(INPUT_CSV)
    machines = build_machines_from_rows(rows)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "plik": OUTPUT_JSON,
        "wersja_pliku": "1.0.0",
        "wygenerowano": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "liczba_maszyn": len(machines),
        "opis": (
            "Startowy zbiór maszyn z harmonogramem 2025 "
            "(format WM uproszczony, seeder pure-python)."
        ),
        "maszyny": machines,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8", newline="\n") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")

    print("[INFO] Zapisano:", OUTPUT_JSON)
    print("[INFO] Maszyny:", len(machines))


if __name__ == "__main__":
    main()
