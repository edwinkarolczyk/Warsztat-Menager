# Plik: machine_card_pdf.py
# version: 1.0
"""Generowanie karty maszyny A4 do wydruku."""

from __future__ import annotations

import html
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


MONTHS_PL = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}


def _first_value(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _machine_number(machine: dict[str, Any]) -> str:
    raw = _first_value(machine, "id", "nr_ewid", "numer", default="---")
    raw = str(raw or "").strip()
    if raw.isdigit():
        return raw
    return raw or "---"


def _safe_filename(value: str) -> str:
    out = []
    for char in str(value):
        if char.isalnum() or char in {"-", "_"}:
            out.append(char)
    return "".join(out) or "maszyna"


def _open_file(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    try:
        subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _register_reportlab_unicode_fonts() -> tuple[str, str]:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return ("Helvetica", "Helvetica-Bold")

    candidates = [
        (
            "WMArial",
            "WMArial-Bold",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ),
        (
            "WMCalibri",
            "WMCalibri-Bold",
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
        ),
        (
            "WMSegoeUI",
            "WMSegoeUI-Bold",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
        ),
    ]

    for regular_name, bold_name, regular_path, bold_path in candidates:
        if not (os.path.exists(regular_path) and os.path.exists(bold_path)):
            continue
        try:
            pdfmetrics.registerFont(TTFont(regular_name, regular_path))
            pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            return (regular_name, bold_name)
        except Exception:
            continue

    return ("Helvetica", "Helvetica-Bold")


def _draw_wrapped_line(canvas_obj, text: str, x: float, y: float, max_chars: int):
    rest = str(text or "")
    if not rest:
        rest = "—"
    while rest:
        canvas_obj.drawString(x, y, rest[:max_chars])
        rest = rest[max_chars:]
        y -= 14
    return y


def _format_months(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return str(value)
    out = []
    for item in value:
        try:
            nr = int(item)
            out.append(MONTHS_PL.get(nr, str(item)))
        except Exception:
            out.append(str(item))
    return ", ".join(out) if out else "—"


def _format_list(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or "—"
    return str(value)


def _generate_pdf_reportlab(machine: dict[str, Any], output_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    font_regular, font_bold = _register_reportlab_unicode_fonts()

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    left = 16 * mm
    right = width - 16 * mm
    y = height - 16 * mm

    nr = _machine_number(machine)
    rows = [
        ("Nazwa", _first_value(machine, "nazwa", "name")),
        ("Typ", _first_value(machine, "typ", "type")),
        ("Status", _first_value(machine, "status")),
        ("Lokalizacja", _first_value(machine, "lokalizacja", "hala")),
        ("Domyślny typ przeglądu", _first_value(machine, "default_review_type")),
        ("Miesiące przeglądu", _format_months(machine.get("review_months"))),
        ("Sugerowani serwisanci", _format_list(machine.get("review_workers"))),
        ("Zdjęcie", _first_value(machine, "image", "obraz")),
    ]

    c.setFont(font_bold, 28)
    c.drawString(left, y, f"NR MASZYNY: {nr}")
    c.setFont(font_bold, 18)
    c.drawRightString(right, y, "KARTA MASZYNY")
    y -= 34

    c.setLineWidth(1)
    c.line(left, y, right, y)
    y -= 28

    c.setFont(font_bold, 12)
    c.drawString(left, y, "DANE MASZYNY")
    y -= 22

    for label, value in rows:
        c.setFont(font_bold, 10)
        c.drawString(left, y, f"{label}:")
        c.setFont(font_regular, 10)
        y = _draw_wrapped_line(c, value or "—", left + 120, y, 80)
        y -= 4

    y -= 12
    c.setFont(font_bold, 12)
    c.drawString(left, y, "PRZEGLĄDY / SERWIS")
    y -= 24

    reviews = machine.get("reviews") or machine.get("zadania") or []
    if not isinstance(reviews, list) or not reviews:
        reviews = ["Brak wpisów przeglądów / serwisu"]

    c.setFont(font_regular, 10)
    for idx, item in enumerate(reviews, start=1):
        if y < 170:
            c.showPage()
            y = height - 18 * mm
            c.setFont(font_bold, 18)
            c.drawString(left, y, f"NR MASZYNY: {nr}")
            c.drawRightString(right, y, "KARTA MASZYNY - SERWIS")
            y -= 34
            c.setFont(font_regular, 10)
        if isinstance(item, dict):
            text = (
                item.get("data")
                or item.get("date")
                or item.get("typ_zadania")
                or item.get("type")
                or item.get("opis")
                or item.get("notes")
                or str(item)
            )
        else:
            text = str(item)
        y = _draw_wrapped_line(c, f"{idx}. {text}", left, y, 105)
        y -= 2

    y -= 18
    if y < 190:
        c.showPage()
        y = height - 18 * mm

    c.setFont(font_bold, 12)
    c.drawString(left, y, "UWAGI")
    y -= 24
    for _ in range(5):
        c.line(left, y, right, y)
        y -= 24

    y -= 10
    c.setFont(font_bold, 11)
    c.drawString(left, y, "DATA / PODPIS:")
    c.line(left + 95, y, right, y)

    c.setFont(font_regular, 8)
    c.drawRightString(
        right,
        10 * mm,
        f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    c.save()
    return output_path


def _generate_html_fallback(machine: dict[str, Any], output_path: Path) -> Path:
    html_path = output_path.with_suffix(".html")
    nr = html.escape(_machine_number(machine))
    rows = [
        ("Nazwa", _first_value(machine, "nazwa", "name")),
        ("Typ", _first_value(machine, "typ", "type")),
        ("Status", _first_value(machine, "status")),
        ("Lokalizacja", _first_value(machine, "lokalizacja", "hala")),
        ("Domyślny typ przeglądu", _first_value(machine, "default_review_type")),
        ("Miesiące przeglądu", _format_months(machine.get("review_months"))),
        ("Sugerowani serwisanci", _format_list(machine.get("review_workers"))),
    ]
    rows_html = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value or '—')}</td></tr>"
        for label, value in rows
    )
    content = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Karta maszyny {nr}</title>
<style>
@page {{ size: A4; margin: 16mm; }}
body {{ font-family: Arial, sans-serif; color: #111; }}
.top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
.nr {{ font-size: 34px; font-weight: 700; }}
.title {{ font-size: 22px; font-weight: 700; }}
hr {{ margin: 18px 0; }}
table {{ border-collapse: collapse; margin-bottom: 22px; }}
th {{ text-align: left; padding: 5px 20px 5px 0; }}
td {{ padding: 5px 0; }}
h2 {{ font-size: 17px; margin-top: 22px; }}
.line {{ border-bottom: 1px solid #222; height: 30px; }}
.footer {{ position: fixed; bottom: 8mm; right: 16mm; font-size: 10px; }}
</style>
</head>
<body>
<div class="top">
  <div class="nr">NR MASZYNY: {nr}</div>
  <div class="title">KARTA MASZYNY</div>
</div>
<hr>
<h2>DANE MASZYNY</h2>
<table>{rows_html}</table>
<h2>UWAGI</h2>
<div class="line"></div>
<div class="line"></div>
<div class="line"></div>
<div class="line"></div>
<div class="line"></div>
<h2>DATA / PODPIS</h2>
<div class="line"></div>
<div class="footer">Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body>
</html>
"""
    html_path.write_text(content, encoding="utf-8")
    return html_path


def generate_machine_card(
    machine: dict[str, Any],
    output_dir: str | Path,
    *,
    open_after: bool = True,
) -> Path:
    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    nr = _safe_filename(_machine_number(machine))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_base / f"karta_maszyny_{nr}_{stamp}.pdf"

    try:
        generated = _generate_pdf_reportlab(machine, output_path)
    except Exception:
        generated = _generate_html_fallback(machine, output_path)

    if open_after:
        _open_file(generated)

    return generated
