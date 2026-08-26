# version: 1.0
"""Dodatkowy zapis historii przeglądów i napraw maszyny do pliku DOCX."""

from __future__ import annotations

import datetime as dt
import os
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class ServiceHistoryDocumentError(RuntimeError):
    """Błąd obsługi zewnętrznej karty historii maszyny."""


class InvalidDocumentFormatError(ServiceHistoryDocumentError):
    """Wybrany plik nie jest dokumentem DOCX."""


class HistoryTableNotFoundError(ServiceHistoryDocumentError):
    """W dokumencie nie znaleziono tabeli historii."""


def _normalize_text(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("\xa0", " ").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _classify_header(value: object) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    if "podpis" in text:
        return "signature"
    if "uwagi" in text or "opis" in text:
        return "notes"
    if "data" in text:
        return "date"
    if "typ" in text:
        return "type"
    return None


def _header_mapping_for_row(row) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row.cells):
        field = _classify_header(cell.text)
        if field and field not in mapping:
            mapping[field] = idx
    return mapping


def _find_history_table(document):
    required = {"type", "date", "signature", "notes"}
    for table in document.tables:
        rows = list(table.rows)
        if not rows:
            continue

        for row_idx, row in enumerate(rows[:8]):
            mapping = _header_mapping_for_row(row)
            if required.issubset(mapping):
                return table, row_idx, mapping

        max_header_rows = min(4, len(rows))
        max_columns = max((len(row.cells) for row in rows[:max_header_rows]), default=0)
        for end_idx in range(max_header_rows):
            mapping: dict[str, int] = {}
            for col_idx in range(max_columns):
                parts = []
                for row_idx in range(end_idx + 1):
                    row = rows[row_idx]
                    if col_idx < len(row.cells):
                        parts.append(row.cells[col_idx].text)
                field = _classify_header(" ".join(parts))
                if field and field not in mapping:
                    mapping[field] = col_idx
            if required.issubset(mapping):
                return table, end_idx, mapping

    raise HistoryTableNotFoundError(
        "Nie znaleziono tabeli z kolumnami TYP, DATA, PODPIS i UWAGI/OPIS."
    )


def _format_date(value: object) -> str:
    if isinstance(value, dt.datetime):
        return value.strftime("%d.%m.%y")
    if isinstance(value, dt.date):
        return value.strftime("%d.%m.%y")

    raw = str(value or "").strip()
    if not raw:
        return dt.date.today().strftime("%d.%m.%y")
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d.%m.%y")
    except Exception:
        pass
    try:
        parsed_date = dt.date.fromisoformat(raw[:10])
        return parsed_date.strftime("%d.%m.%y")
    except Exception:
        return raw


def _person_signature(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    words = [part for part in raw.replace("-", " ").split() if part]
    if len(words) >= 2:
        return "".join(word[0].upper() for word in words)
    return raw


def format_signatures(people: object) -> str:
    if isinstance(people, str):
        values = [part.strip() for part in people.split(",") if part.strip()]
    elif isinstance(people, Iterable):
        values = [str(item).strip() for item in people if str(item or "").strip()]
    else:
        values = [str(people).strip()] if str(people or "").strip() else []
    return ", ".join(_person_signature(value) for value in values)


def _row_is_empty(row, columns: Sequence[int]) -> bool:
    for idx in columns:
        if idx < len(row.cells) and str(row.cells[idx].text or "").strip():
            return False
    return True


def _set_cell_text_preserving_basic_format(cell, value: object) -> None:
    text = str(value or "")
    if not cell.paragraphs:
        cell.text = text
        return

    paragraph = cell.paragraphs[0]
    for current in cell.paragraphs:
        for run in current.runs:
            run.text = ""

    if paragraph.runs:
        paragraph.runs[0].text = text
    else:
        paragraph.add_run(text)


def _target_data_row(table, header_row_idx: int, columns: Sequence[int]):
    rows = list(table.rows)
    for row in rows[header_row_idx + 1 :]:
        if _row_is_empty(row, columns):
            return row
    return table.add_row()


def append_history_entry(
    path: str | os.PathLike[str],
    *,
    entry_type: str,
    performed_at: object,
    performed_by: object,
    description: object,
) -> None:
    """Dopisz jeden wpis P/N do tabeli historii w dokumencie DOCX."""

    target = Path(path)
    if target.suffix.casefold() != ".docx":
        raise InvalidDocumentFormatError("Karta historii musi być plikiem .docx.")
    if not target.is_file():
        raise ServiceHistoryDocumentError(f"Plik karty nie istnieje: {target}")

    typ = str(entry_type or "").strip().upper()
    if typ not in {"P", "N"}:
        raise ServiceHistoryDocumentError("Typ wpisu musi mieć wartość P albo N.")

    try:
        from docx import Document  # type: ignore
    except Exception as exc:
        raise ServiceHistoryDocumentError(
            "Brak biblioteki python-docx wymaganej do zapisu karty historii."
        ) from exc

    try:
        document = Document(str(target))
        table, header_idx, mapping = _find_history_table(document)
        columns = [mapping[key] for key in ("type", "date", "signature", "notes")]
        row = _target_data_row(table, header_idx, columns)

        values: Mapping[str, str] = {
            "type": typ,
            "date": _format_date(performed_at),
            "signature": format_signatures(performed_by),
            "notes": str(description or "").strip(),
        }
        for field, value in values.items():
            col_idx = mapping[field]
            if col_idx >= len(row.cells):
                raise ServiceHistoryDocumentError(
                    "Tabela historii ma niezgodną liczbę kolumn."
                )
            _set_cell_text_preserving_basic_format(row.cells[col_idx], value)

        temp_path = target.with_name(f".{target.stem}.wm_tmp{target.suffix}")
        try:
            document.save(str(temp_path))
            os.replace(temp_path, target)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
    except ServiceHistoryDocumentError:
        raise
    except PermissionError as exc:
        raise ServiceHistoryDocumentError(
            "Nie można zapisać karty. Zamknij dokument w Wordzie i spróbuj ponownie."
        ) from exc
    except Exception as exc:
        raise ServiceHistoryDocumentError(f"Nie udało się zapisać karty historii: {exc}") from exc


__all__ = [
    "ServiceHistoryDocumentError",
    "InvalidDocumentFormatError",
    "HistoryTableNotFoundError",
    "append_history_entry",
    "format_signatures",
]
