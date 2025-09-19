# -*- coding: utf-8 -*-
"""Seed file for generating simplified machine data set from maintenance schedule."""

import csv
import json
import os
from datetime import datetime

# ──────────────────────────────────────────────────────────────
# KONFIGURACJA: ustaw ścieżki zgodnie z repo
INPUT_CSV = "data/import/Harmonogram przeglądów i napraw na 2025.csv"
INPUT_XLSM = "data/import/Harmonogram przeglądów i napraw na 2025.xlsm"  # opcjonalnie
OUTPUT_DIR = "data/maszyny"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "maszyny.json")

# Auto-rozmieszczenie (jak chciałeś: luźne po różnych współrzędnych)
START_X, START_Y = 100, 100
STEP_X, STEP_Y = 150, 130
COLS = 10
SIZE_W, SIZE_H = 100, 60
ROMAN_MONTHS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"}


# ──────────────────────────────────────────────────────────────
def log(info):
    """Display a short info message."""
    print(f"[INFO] {info}")


def dbg(info):
    """Display a debug message."""
    print(f"[WM-DBG] {info}")


def err(info):
    """Display an error message."""
    print(f"[ERROR] {info}")


def fix_pl(value):
    """Replace incorrectly decoded Polish characters."""
    if not isinstance(value, str):
        return value
    replacements = {
        "¹": "ą",
        "³": "ł",
        "¿": "ż",
        "\u009c": "ś",
        "\u009f": "ź",
        "ê": "ę",
        "ñ": "ń",
        "\u008f": "ń",
        "\u0085": "ą",
        "\u0082": "ł",
        "\u0087": "ć",
        "\u009b": "ś",
        "\u009e": "ż",
    }
    for src, dest in replacements.items():
        value = value.replace(src, dest)
    return value


def _read_csv_without_pandas(path):
    errors = []
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            with open(path, "r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                    reader = csv.reader(handle, dialect)
                except csv.Error:
                    reader = csv.reader(handle, delimiter=";")
                rows = [list(row) for row in reader]
            return rows[1:] if rows else []
        except UnicodeDecodeError as exc:
            errors.append(exc)
    if errors:
        raise errors[-1]
    return []


def _read_csv_table(path):
    try:
        import pandas as pd
    except ImportError:
        return _read_csv_without_pandas(path)

    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        if last_error is not None:
            raise last_error
        raise RuntimeError("Nie udało się odczytać pliku CSV w żadnym z obsługiwanych kodowań.")

    df = df.fillna("")
    return df.astype(str).values.tolist()


def _read_xlsm_table(path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Obsługa plików XLSM wymaga zainstalowanego pakietu pandas.") from exc

    workbook = pd.ExcelFile(path)
    df = workbook.parse(workbook.sheet_names[0])
    df = df.fillna("")
    return df.astype(str).values.tolist()


def _load_source():
    """Return schedule data as a list of rows (header rows included)."""
    if os.path.isfile(INPUT_CSV):
        log(f"Czytam CSV: {INPUT_CSV}")
        return _read_csv_table(INPUT_CSV)
    if os.path.isfile(INPUT_XLSM):
        log(f"Czytam XLSM: {INPUT_XLSM}")
        return _read_xlsm_table(INPUT_XLSM)
    raise FileNotFoundError(
        "Brak pliku wejściowego. Dodaj CSV lub XLSM do repo (data/import/...).",
    )


def _prepare_rows(table):
    """Return cleaned rows and header metadata."""
    if len(table) < 2:
        return [], []

    header_row2 = table[1] if len(table) > 1 else []
    columns = ["Hala", "Nr ewid.", "Maszyna", "Typ"] + list(header_row2[4:])
    columns = [col if isinstance(col, str) else "" for col in columns]

    # Remove duplicate columns while keeping the first occurrence
    unique_columns = []
    unique_indices = []
    for idx, col in enumerate(columns):
        if not col or col in unique_columns:
            continue
        unique_columns.append(col)
        unique_indices.append(idx)

    data_rows = table[2:]
    processed_rows = []
    max_index = max(unique_indices, default=-1)

    for row in data_rows:
        row_list = list(row)
        if len(row_list) <= max_index:
            row_list.extend([""] * (max_index + 1 - len(row_list)))
        record = {}
        for col_name, col_idx in zip(unique_columns, unique_indices):
            raw_value = row_list[col_idx] if col_idx < len(row_list) else ""
            text_value = fix_pl(str(raw_value)).strip()
            record[col_name] = text_value
        processed_rows.append(record)

    # Forward-fill missing hall identifiers
    last_hall = ""
    for record in processed_rows:
        hall_value = record.get("Hala", "").strip()
        if hall_value and hall_value.lower() != "nan":
            last_hall = hall_value
        else:
            record["Hala"] = last_hall

    month_columns = [col for col in unique_columns if col.strip() in ROMAN_MONTHS]
    return processed_rows, month_columns


def build_machines(table):
    """Build the machine payload using the simplified WM layout."""
    rows, month_columns = _prepare_rows(table)

    machines = []
    per_hall_counter = {}

    for index, source in enumerate(rows, start=1):
        name = source.get("Typ", "").strip()
        model = source.get("Maszyna", "").strip()
        if name == "" and model == "":
            continue

        hall_raw = source.get("Hala", "").strip()
        try:
            hall = int(float(hall_raw)) if hall_raw not in ("", "nan") else 1
        except Exception:
            hall = 1

        przeglady = []
        for month in month_columns:
            value = source.get(month, "").strip()
            if value and value.lower() != "nan":
                przeglady.append(value)

        hall_index = per_hall_counter.get(hall, 0)
        row_idx, col_idx = divmod(hall_index, COLS)
        x_pos = START_X + col_idx * STEP_X
        y_pos = START_Y + row_idx * STEP_Y
        per_hall_counter[hall] = hall_index + 1

        machines.append(
            {
                "id": str(index),
                "nazwa": name if name else (model if model else "MASZYNA"),
                "typ": model,
                "hala": hall,
                "pozycja": {"x": x_pos, "y": y_pos},
                "rozmiar": {"w": SIZE_W, "h": SIZE_H},
                "status": "sprawna",
                "nastepne_zadanie": None,
                "przeglady": przeglady,
            },
        )

    return machines


def main():
    try:
        table = _load_source()
    except Exception as exc:  # pragma: no cover - diagnostic output
        err(f"Nie mogę wczytać źródła: {exc}")
        raise

    log("Buduję listę maszyn…")
    try:
        machines = build_machines(table)
    except Exception as exc:  # pragma: no cover - diagnostic output
        err(f"Błąd budowy listy: {exc}")
        raise

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "plik": OUTPUT_JSON,
        "wersja_pliku": "1.0.0",
        "wygenerowano": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "liczba_maszyn": len(machines),
        "opis": "Startowy zbiór maszyn z harmonogramem 2025 (format uproszczony WM).",
        "maszyny": machines,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    log(f"Zapisano: {OUTPUT_JSON}")
    dbg(f"Maszyny: {len(machines)}")


if __name__ == "__main__":
    main()
