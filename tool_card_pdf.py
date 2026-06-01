# Plik: tool_card_pdf.py
# version: 1.0
# Zmiany:
# - Generowanie karty narzędzia A4 do wydruku.
# - Duży numer narzędzia w lewym górnym rogu.
# - Lista zadań z polami [ ] do zaznaczania długopisem.

from __future__ import annotations

import html
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _first_value(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _tool_number(tool: dict[str, Any]) -> str:
    raw = _first_value(tool, "numer", "nr", "id", default="---")
    raw = str(raw or "").strip()
    if raw.isdigit():
        return raw.zfill(3)
    return raw or "---"


def _task_title(task: Any) -> str:
    if isinstance(task, dict):
        return str(
            task.get("tytul")
            or task.get("title")
            or task.get("text")
            or task.get("nazwa")
            or ""
        ).strip()
    if isinstance(task, str):
        return task.strip()
    return ""


def _task_done(task: Any) -> bool:
    if isinstance(task, dict):
        return bool(task.get("done"))
    return False


def _extract_tasks(tool: dict[str, Any]) -> list[Any]:
    raw = tool.get("zadania")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        out: list[Any] = []
        for value in raw.values():
            if isinstance(value, dict):
                for key, done in value.items():
                    out.append({"tytul": str(key), "done": bool(done)})
            elif isinstance(value, list):
                out.extend(value)
            elif isinstance(value, str) and value.strip():
                out.append(value.strip())
        return out
    if isinstance(raw, str) and raw.strip():
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return []


def _safe_filename(value: str) -> str:
    out = []
    for char in str(value):
        if char.isalnum() or char in {"-", "_"}:
            out.append(char)
    return "".join(out) or "narzedzie"


def _open_file(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    try:
        subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _draw_wrapped_line(canvas_obj, text: str, x: float, y: float, max_chars: int):
    chunks = []
    rest = text
    while rest:
        chunks.append(rest[:max_chars])
        rest = rest[max_chars:]
    for chunk in chunks:
        canvas_obj.drawString(x, y, chunk)
        y -= 14
    return y


def _register_reportlab_unicode_fonts() -> tuple[str, str]:
    """
    Rejestruje fonty TTF z polskimi znakami dla ReportLab.

    Domyślne PDF-owe Helvetica/Helvetica-Bold nie gwarantują poprawnych znaków PL.
    Na Windows najczęściej dostępne są Arial, Calibri albo Segoe UI.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

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


def _generate_pdf_reportlab(tool: dict[str, Any], output_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    font_regular, font_bold = _register_reportlab_unicode_fonts()

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    left = 16 * mm
    right = width - 16 * mm
    y = height - 16 * mm

    nr = _tool_number(tool)
    rows = [
        ("Nazwa", _first_value(tool, "nazwa", "name")),
        ("Typ", _first_value(tool, "typ", "type")),
        ("Tryb", _first_value(tool, "tryb", "mode")),
        ("Status", _first_value(tool, "status")),
        ("Pracownik", _first_value(tool, "pracownik", "assigned_to", "owner")),
        ("Data dodania", _first_value(tool, "data_dodania", "date_added", "created_at")),
    ]

    c.setFont(font_bold, 28)
    c.drawString(left, y, f"NR NARZĘDZIA: {nr}")
    c.setFont(font_bold, 18)
    c.drawRightString(right, y, "KARTA NARZĘDZIA")
    y -= 34

    c.setLineWidth(1)
    c.line(left, y, right, y)
    y -= 28

    c.setFont(font_bold, 12)
    c.drawString(left, y, "DANE NARZĘDZIA")
    y -= 22

    for label, value in rows:
        c.setFont(font_bold, 10)
        c.drawString(left, y, f"{label}:")
        c.setFont(font_regular, 10)
        c.drawString(left + 95, y, value or "—")
        y -= 18

    y -= 12
    c.setFont(font_bold, 12)
    c.drawString(left, y, "ZADANIA DO WYKONANIA")
    y -= 24

    tasks = _extract_tasks(tool)
    if not tasks:
        tasks = ["Brak zadań przypisanych do narzędzia"]

    c.setFont(font_regular, 10)
    for idx, task in enumerate(tasks, start=1):
        if y < 170:
            c.showPage()
            y = height - 18 * mm
            c.setFont(font_bold, 18)
            c.drawString(left, y, f"NR NARZĘDZIA: {nr}")
            c.drawRightString(right, y, "KARTA NARZĘDZIA - ZADANIA")
            y -= 34
            c.setFont(font_regular, 10)

        box = "[x]" if _task_done(task) else "[ ]"
        title = _task_title(task) or f"Zadanie {idx}"
        line = f"{box} {idx}. {title}"
        y = _draw_wrapped_line(c, line, left, y, 105)
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


def _generate_html_fallback(tool: dict[str, Any], output_path: Path) -> Path:
    html_path = output_path.with_suffix(".html")
    nr = html.escape(_tool_number(tool))
    rows = [
        ("Nazwa", _first_value(tool, "nazwa", "name")),
        ("Typ", _first_value(tool, "typ", "type")),
        ("Tryb", _first_value(tool, "tryb", "mode")),
        ("Status", _first_value(tool, "status")),
        ("Pracownik", _first_value(tool, "pracownik", "assigned_to", "owner")),
        ("Data dodania", _first_value(tool, "data_dodania", "date_added", "created_at")),
    ]
    tasks = _extract_tasks(tool)
    if not tasks:
        tasks = ["Brak zadań przypisanych do narzędzia"]

    rows_html = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value or '—')}</td></tr>"
        for label, value in rows
    )
    tasks_html = "\n".join(
        "<li>"
        + html.escape("[x]" if _task_done(task) else "[ ]")
        + " "
        + html.escape(str(idx))
        + ". "
        + html.escape(_task_title(task) or f"Zadanie {idx}")
        + "</li>"
        for idx, task in enumerate(tasks, start=1)
    )

    content = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Karta narzędzia {nr}</title>
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
li {{ margin: 8px 0; font-size: 14px; }}
.line {{ border-bottom: 1px solid #222; height: 30px; }}
.footer {{ position: fixed; bottom: 8mm; right: 16mm; font-size: 10px; }}
</style>
</head>
<body>
<div class="top">
  <div class="nr">NR NARZĘDZIA: {nr}</div>
  <div class="title">KARTA NARZĘDZIA</div>
</div>
<hr>
<h2>DANE NARZĘDZIA</h2>
<table>{rows_html}</table>
<h2>ZADANIA DO WYKONANIA</h2>
<ol>{tasks_html}</ol>
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


def generate_tool_card(
    tool: dict[str, Any],
    output_dir: str | Path,
    *,
    open_after: bool = True,
) -> Path:
    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    nr = _safe_filename(_tool_number(tool))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_base / f"karta_narzedzia_{nr}_{stamp}.pdf"

    try:
        generated = _generate_pdf_reportlab(tool, output_path)
    except Exception:
        generated = _generate_html_fallback(tool, output_path)

    if open_after:
        _open_file(generated)

    return generated
