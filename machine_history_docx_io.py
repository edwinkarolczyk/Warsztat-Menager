# version: 1.0
"""Bezpieczny zapis dodatkowej historii maszyn do DOCX, także na udziałach sieciowych."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Mapping

from machine_history_doc import (
    InvalidDocumentFormatError,
    ServiceHistoryDocumentError,
    _find_history_table,
    _format_date,
    _set_cell_text_preserving_basic_format,
    _target_data_row,
    format_signatures,
)

logger = logging.getLogger(__name__)


def _replace_or_overwrite(temp_path: Path, target: Path) -> None:
    """Podmień plik atomowo, a na udziałach SMB użyj bezpośredniego nadpisania."""
    try:
        os.replace(temp_path, target)
        return
    except PermissionError as replace_exc:
        logger.warning(
            "[Maszyny][DOCX_HISTORY] os.replace() odrzucone dla %s; "
            "próba nadpisania zgodnego z udziałem sieciowym SMB.",
            target,
        )
        try:
            with temp_path.open("rb") as source, target.open("r+b") as destination:
                destination.seek(0)
                shutil.copyfileobj(source, destination, length=1024 * 1024)
                destination.truncate()
                destination.flush()
                try:
                    os.fsync(destination.fileno())
                except OSError:
                    pass
            return
        except PermissionError as write_exc:
            raise ServiceHistoryDocumentError(
                "Nie można zapisać karty DOCX. Plik jest zablokowany przez Worda "
                "albo użytkownik nie ma prawa zapisu do tego pliku."
            ) from write_exc
        except OSError as write_exc:
            raise ServiceHistoryDocumentError(
                f"Nie można nadpisać karty DOCX na dysku sieciowym: {write_exc}"
            ) from write_exc
        finally:
            _ = replace_exc


def append_history_entry(
    path: str | os.PathLike[str],
    *,
    entry_type: str,
    performed_at: object,
    performed_by: object,
    description: object,
) -> None:
    """Dopisz P/N do tabeli historii i zapisz DOCX także na dysku sieciowym."""
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

    temp_path = target.with_name(
        f".{target.stem}.wm_tmp_{os.getpid()}{target.suffix}"
    )
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

        document.save(str(temp_path))
        _replace_or_overwrite(temp_path, target)
    except ServiceHistoryDocumentError:
        raise
    except PermissionError as exc:
        raise ServiceHistoryDocumentError(
            "Nie można zapisać karty DOCX. Plik jest zablokowany przez Worda "
            "albo użytkownik nie ma prawa zapisu do tego pliku."
        ) from exc
    except Exception as exc:
        raise ServiceHistoryDocumentError(
            f"Nie udało się zapisać karty historii: {exc}"
        ) from exc
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


__all__ = ["append_history_entry"]
