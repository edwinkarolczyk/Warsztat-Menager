# version: 1.0
"""PDF z aktywnym planem przeglądów i serwisów maszyn."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


def _output_dir() -> Path:
    try:
        from core import root_paths as wm_root_paths

        root = Path(wm_root_paths.get_root_anchor())
    except Exception:
        raw = str(os.environ.get("WM_ROOT") or "").strip()
        root = Path(raw) if raw else Path.cwd()
    target = root / "wydruki" / "maszyny"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _font_names() -> tuple[str, str]:
    """Zarejestruj dostępny font Unicode; fallback do Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return "Helvetica", "Helvetica-Bold"

    candidates = [
        (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if not regular.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("WMPlan", str(regular)))
            pdfmetrics.registerFont(
                TTFont("WMPlanBold", str(bold if bold.is_file() else regular))
            )
            return "WMPlan", "WMPlanBold"
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


def _machine_id(machine: Mapping[str, Any]) -> str:
    return str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or ""
    ).strip()


def _machine_name(machine: Mapping[str, Any]) -> str:
    return str(machine.get("nazwa") or machine.get("name") or "").strip()


def _parse_date(value: object) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        return dt.date.fromisoformat(raw[:10])
    except Exception:
        return None


def _status_key(value: object) -> str:
    raw = str(value or "").strip().casefold().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    if raw in {"done", "wykonany", "wykonane", "completed", "zamkniety", "zamknięty"}:
        return "done"
    if raw in {"cancelled", "canceled", "anulowany", "anulowane"}:
        return "cancelled"
    if raw in {"in progress", "in_progress", "w toku", "rozpoczety", "rozpoczęty"}:
        return "in_progress"
    return "planned"


def _people_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Iterable):
        return ", ".join(str(item).strip() for item in value if str(item or "").strip())
    return str(value or "").strip()


def _entries_for_machine(machine: Mapping[str, Any], gui_module=None) -> list[dict[str, Any]]:
    if gui_module is not None:
        combiner = getattr(gui_module, "_combined_machine_review_entries", None)
        if callable(combiner):
            try:
                return [dict(item) for item in combiner(dict(machine)) if isinstance(item, dict)]
            except Exception:
                pass
    reviews = machine.get("reviews")
    if isinstance(reviews, list):
        return [dict(item) for item in reviews if isinstance(item, dict)]
    return []


def _collect_plan(rows: Iterable[Mapping[str, Any]], gui_module=None) -> list[dict[str, Any]]:
    today = dt.date.today()
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for machine in rows or []:
        if not isinstance(machine, Mapping):
            continue
        machine_id = _machine_id(machine)
        machine_name = _machine_name(machine)
        if not machine_id and not machine_name:
            continue

        for entry in _entries_for_machine(machine, gui_module=gui_module):
            state = _status_key(entry.get("status"))
            if state in {"done", "cancelled"}:
                continue

            date_value = _parse_date(
                entry.get("planned_date")
                or entry.get("date")
                or entry.get("data")
                or entry.get("completed_at")
            )
            if date_value is None:
                continue

            typ = str(entry.get("type") or entry.get("typ") or "Przegląd / serwis").strip()
            source = str(entry.get("source") or "").strip().casefold()
            if source == "cycle" and "cyklic" not in typ.casefold():
                typ = f"{typ} (cykliczny)"

            key = (machine_id, date_value.isoformat(), typ.casefold())
            if key in seen:
                continue
            seen.add(key)

            if state == "in_progress":
                status_label = "W toku"
            elif date_value < today:
                status_label = "Po terminie"
            elif date_value == today:
                status_label = "Dzisiaj"
            elif (date_value - today).days <= 7:
                status_label = f"Za {(date_value - today).days} dni"
            else:
                status_label = "Planowany"

            people = (
                entry.get("suggested_workers")
                or entry.get("suggested_people")
                or entry.get("responsible")
                or entry.get("completed_by")
                or []
            )
            notes = str(
                entry.get("description")
                or entry.get("notes")
                or entry.get("uwagi")
                or ""
            ).strip()

            result.append(
                {
                    "date": date_value,
                    "machine": f"{machine_id} — {machine_name}" if machine_name else machine_id,
                    "type": typ,
                    "status": status_label,
                    "people": _people_text(people),
                    "notes": notes,
                }
            )

    result.sort(key=lambda item: (item["date"], item["machine"], item["type"]))
    return result


def generate_machine_service_plan_pdf(
    rows: Iterable[Mapping[str, Any]], *, gui_module=None
) -> tuple[Path, int]:
    """Utwórz PDF z niewykonanymi przeglądami/serwisami i zwróć (ścieżka, liczba)."""

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise RuntimeError("Brak biblioteki reportlab wymaganej do wydruku PDF.") from exc

    plan = _collect_plan(rows, gui_module=gui_module)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _output_dir() / f"plan_przegladow_maszyn_{stamp}.pdf"

    regular_font, bold_font = _font_names()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "WMTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "WMMeta",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=8,
        leading=10,
        spaceAfter=8,
    )
    cell_style = ParagraphStyle(
        "WMCell",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=7.5,
        leading=9,
    )
    head_style = ParagraphStyle(
        "WMHead",
        parent=cell_style,
        fontName=bold_font,
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Plan przeglądów i serwisów maszyn",
        author="Warsztat Menager",
    )

    story = [
        Paragraph("Plan przeglądów i serwisów maszyn", title_style),
        Paragraph(
            f"Wygenerowano: {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} | "
            f"Liczba pozycji: {len(plan)}",
            meta_style,
        ),
        Spacer(1, 2 * mm),
    ]

    if not plan:
        story.append(Paragraph("Brak aktywnych pozycji do wydruku.", cell_style))
    else:
        table_data = [
            [
                Paragraph("Termin", head_style),
                Paragraph("Maszyna", head_style),
                Paragraph("Typ", head_style),
                Paragraph("Status", head_style),
                Paragraph("Osoby", head_style),
                Paragraph("Zakres / uwagi", head_style),
            ]
        ]
        for item in plan:
            table_data.append(
                [
                    Paragraph(item["date"].strftime("%d.%m.%Y"), cell_style),
                    Paragraph(str(item["machine"]), cell_style),
                    Paragraph(str(item["type"]), cell_style),
                    Paragraph(str(item["status"]), cell_style),
                    Paragraph(str(item["people"] or "—"), cell_style),
                    Paragraph(str(item["notes"] or "—"), cell_style),
                ]
            )

        table = Table(
            table_data,
            colWidths=[24 * mm, 46 * mm, 40 * mm, 28 * mm, 38 * mm, 76 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9CA3AF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return path, len(plan)


__all__ = ["generate_machine_service_plan_pdf"]
