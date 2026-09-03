# WM-VERSION: 0.1
# Plik: planista_excel_import.py
# version: 1.0
"""Odczyt zewnętrznego planu produkcji XLSX dla Planisty.

Moduł otwiera plik wyłącznie do odczytu. Nie zapisuje zmian ani do źródłowego
Excela, ani do zleceń WM; synchronizacja należy do kolejnych etapów.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS = {"m": _MAIN_NS, "r": _REL_NS, "p": _PKG_REL_NS}
_CELL_REF_RE = re.compile(r"^([A-Z]+)")


class PlanExcelError(ValueError):
    """Czytelny dla użytkownika błąd struktury/importu planu Excel."""


def _normalize_header(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _column_index(cell_ref: str) -> int:
    match = _CELL_REF_RE.match(str(cell_ref or "").upper())
    if not match:
        return -1
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - 64)
    return value - 1


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall("m:si", _NS):
        values.append("".join(node.text or "" for node in item.findall(".//m:t", _NS)))
    return values


def _sheet_xml_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_id = None
    for sheet in workbook.findall("m:sheets/m:sheet", _NS):
        if str(sheet.attrib.get("name") or "") == sheet_name:
            rel_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
            break
    if not rel_id:
        raise PlanExcelError(f"Brak arkusza „{sheet_name}” w wybranym pliku Excel.")

    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for rel in rels.findall("p:Relationship", _NS):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target")
            break
    if not target:
        raise PlanExcelError(f"Nie można odczytać arkusza „{sheet_name}”.")

    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def _cell_value(cell: ET.Element, shared: list[str]):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", _NS))

    value_node = cell.find("m:v", _NS)
    raw = value_node.text if value_node is not None else None
    if raw is None:
        return ""
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type in {"str", "e"}:
        return raw
    if cell_type == "b":
        return raw == "1"
    try:
        return float(raw)
    except ValueError:
        return raw


def _sheet_rows(archive: ZipFile, sheet_path: str, shared: list[str]) -> list[tuple[int, dict[int, object]]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows = []
    for row_node in root.findall(".//m:sheetData/m:row", _NS):
        try:
            row_no = int(row_node.attrib.get("r") or 0)
        except ValueError:
            row_no = 0
        cells: dict[int, object] = {}
        for cell in row_node.findall("m:c", _NS):
            col = _column_index(cell.attrib.get("r") or "")
            if col >= 0:
                cells[col] = _cell_value(cell, shared)
        rows.append((row_no, cells))
    return rows


def _header_columns(rows: list[tuple[int, dict[int, object]]]) -> tuple[int, dict[str, int]]:
    aliases = {
        "order": {"nr zlec", "nr zlecenia", "zlecenie", "zlec"},
        "product": {"produkt", "nazwa produktu", "oznaczenie", "wyrob", "wyrób"},
        "qty": {"ilosc", "ilość", "qty"},
        "date": {"data wysylki", "data wysyłki", "wysylka", "wysyłka"},
        "process": {"proces", "status procesu"},
    }
    normalized_aliases = {
        key: {_normalize_header(alias) for alias in values}
        for key, values in aliases.items()
    }

    best = None
    for row_no, cells in rows[:30]:
        found: dict[str, int] = {}
        for col, value in cells.items():
            normalized = _normalize_header(value)
            for key, values in normalized_aliases.items():
                if normalized in values:
                    found.setdefault(key, col)
        score = sum(key in found for key in ("order", "qty", "date", "process"))
        if "order" in found and "qty" in found and (best is None or score > best[0]):
            best = (score, row_no, found)

    if best is None:
        raise PlanExcelError(
            "Nie znaleziono nagłówków planu. Wymagane są co najmniej „Nr zlec.” i „Ilość”."
        )

    _score, header_row, columns = best
    if "product" not in columns:
        order_col = columns["order"]
        qty_col = columns["qty"]
        if order_col + 1 < qty_col:
            columns["product"] = order_col + 1
        else:
            raise PlanExcelError("Nie można ustalić kolumny produktu/oznaczenia w planie Excel.")

    missing = [key for key in ("order", "product", "qty", "date", "process") if key not in columns]
    if missing:
        labels = {
            "order": "Nr zlec.",
            "product": "Produkt",
            "qty": "Ilość",
            "date": "Data wysyłki",
            "process": "Proces",
        }
        raise PlanExcelError(
            "Brakuje wymaganych kolumn: " + ", ".join(labels[key] for key in missing) + "."
        )
    return header_row, columns


def _as_order_number(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _as_quantity(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).strip().replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _as_excel_date(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()
        except (OverflowError, ValueError):
            return str(value)

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def load_production_plan(path, sheet_name: str = "PLAN 2026") -> dict:
    """Wczytaj linie planu produkcji bez modyfikowania źródłowego pliku XLSX."""
    source = Path(path)
    if source.suffix.casefold() != ".xlsx":
        raise PlanExcelError("Wybierz plik Excel w formacie .xlsx.")
    if not source.is_file():
        raise PlanExcelError("Wybrany plik Excel nie istnieje.")

    try:
        with ZipFile(source, "r") as archive:
            shared = _shared_strings(archive)
            sheet_path = _sheet_xml_path(archive, sheet_name)
            rows = _sheet_rows(archive, sheet_path, shared)
    except PlanExcelError:
        raise
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise PlanExcelError(f"Nie można odczytać pliku Excel: {exc}") from exc

    header_row, columns = _header_columns(rows)
    result_rows = []
    current_order = ""
    current_date = ""

    for row_no, cells in rows:
        if row_no <= header_row:
            continue

        product = str(cells.get(columns["product"], "") or "").strip()
        if not product:
            continue

        explicit_order = _as_order_number(cells.get(columns["order"], ""))
        explicit_date = _as_excel_date(cells.get(columns["date"], ""))
        if explicit_order:
            current_order = explicit_order
            current_date = explicit_date
        elif explicit_date:
            current_date = explicit_date

        quantity = _as_quantity(cells.get(columns["qty"], ""))
        process = str(cells.get(columns["process"], "") or "").strip()
        result_rows.append(
            {
                "source_row": row_no,
                "nr_zlec": current_order,
                "produkt": product,
                "ilosc": quantity,
                "data_wysylki": current_date,
                "proces": process,
            }
        )

    if not result_rows:
        raise PlanExcelError(f"Arkusz „{sheet_name}” nie zawiera pozycji produkcyjnych.")

    return {
        "source_path": str(source.resolve()),
        "source_name": source.name,
        "sheet": sheet_name,
        "header_row": header_row,
        "rows": result_rows,
    }
