# version: 1.0
"""Automatyczny wydruk kart nowych zleceń.

Wydruk jest niezależny od procesu akceptacji/synchronizacji WM.
Na Windows korzystamy z czasownika systemowego "print", a na Unix
z lp/lpr. Brak drukarki nie blokuje zapisania zlecenia.
"""

from __future__ import annotations

import html
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore


def _auto_print_enabled() -> bool:
    """Zwraca ustawienie automatycznego wydruku; domyślnie True."""
    try:
        if ConfigManager is None:
            return True
        cfg = ConfigManager().get("orders") or {}
        printing = cfg.get("printing") if isinstance(cfg, dict) else {}
        if isinstance(printing, dict) and "auto_new_orders" in printing:
            return bool(printing.get("auto_new_orders"))
    except Exception:
        pass
    return True


def _display_value(value: Any, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def _build_order_html(data: dict[str, Any]) -> str:
    kind = _display_value(data.get("rodzaj"))
    title = _display_value(data.get("opis"))
    order_id = _display_value(data.get("id"))
    status = _display_value(data.get("status"))
    created = _display_value(data.get("utworzono"))
    termin = _display_value(data.get("termin"))
    product = _display_value(data.get("produkt"))
    qty = _display_value(data.get("ilosc"))
    tool = _display_value(data.get("narzedzie_id"))
    machine = _display_value(data.get("maszyna_id"))
    material = _display_value(data.get("material"))
    supplier = _display_value(data.get("dostawca"))
    comment = _display_value(data.get("komentarz") or data.get("awaria"))

    rows = [
        ("Rodzaj", kind),
        ("Zlecenie", order_id),
        ("Status", status),
        ("Utworzono", created),
        ("Termin", termin),
    ]
    if data.get("produkt"):
        rows.extend([("Produkt", product), ("Ilość", qty)])
    if data.get("narzedzie_id"):
        rows.append(("Narzędzie", tool))
    if data.get("maszyna_id"):
        rows.append(("Maszyna", machine))
    if data.get("material"):
        rows.extend([("Materiał", material), ("Ilość", qty), ("Dostawca", supplier)])
    if comment != "—":
        rows.append(("Opis / komentarz", comment))

    body = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Zlecenie {html.escape(order_id)}</title>
<style>
@page {{ size: A5; margin: 10mm; }}
body {{ font-family: Arial, sans-serif; font-size: 11pt; color: #111; }}
h1 {{ font-size: 20pt; margin: 0 0 5mm; }}
h2 {{ font-size: 13pt; margin: 5mm 0 2mm; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #555; padding: 2.5mm; text-align: left; vertical-align: top; }}
th {{ width: 32%; }}
.footer {{ margin-top: 6mm; font-size: 8pt; }}
</style>
</head>
<body>
<h1>ZLECENIE DO WYKONANIA</h1>
<h2>{html.escape(title)}</h2>
<table>{body}</table>
<div class="footer">Warsztat Menager — automatyczny wydruk</div>
</body>
</html>"""


def _print_windows(path: Path) -> tuple[bool, str]:
    try:
        # Windows ShellExecute przez os.startfile z czasownikiem "print".
        # Nie otwieramy przeglądarki w trybie podglądu.
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
        return True, "Windows: wysłano do domyślnej drukarki"
    except Exception as exc:
        return False, str(exc)


def _print_posix(path: Path) -> tuple[bool, str]:
    for command in ("lp", "lpr"):
        executable = shutil.which(command)
        if not executable:
            continue
        try:
            subprocess.run(
                [executable, str(path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )
            return True, f"{command}: wysłano do domyślnej drukarki"
        except Exception as exc:
            return False, str(exc)
    return False, "Brak polecenia lp/lpr."


def drukuj_nowe_zlecenie(data: dict[str, Any], autor: str = "system") -> dict[str, Any]:
    """Generuje kartę i wysyła ją do drukarki bez udziału procesu akceptacji."""
    now = datetime.now().isoformat(timespec="seconds")
    previous = data.get("wydruk")
    if isinstance(previous, dict) and previous.get("status") == "wydrukowano":
        return previous

    if not _auto_print_enabled():
        return {
            "status": "pominieto",
            "kiedy": now,
            "kto": autor,
            "powod": "auto_new_orders=false",
        }

    out_dir = Path.cwd() / "wydruki" / "zlecenia"
    out_dir.mkdir(parents=True, exist_ok=True)
    order_id = str(data.get("id") or "UNKNOWN")
    path = out_dir / f"zlecenie_{order_id}.html"
    path.write_text(_build_order_html(data), encoding="utf-8")

    if os.name == "nt":
        ok, detail = _print_windows(path)
    else:
        ok, detail = _print_posix(path)

    if ok:
        print(f"[WM-DBG][DRUK] {order_id}: {detail}")
        return {
            "status": "wydrukowano",
            "kiedy": now,
            "kto": autor,
            "plik": str(path),
            "szczegoly": detail,
        }

    print(f"[WM-DBG][DRUK] {order_id}: BŁĄD: {detail}")
    return {
        "status": "blad",
        "kiedy": now,
        "kto": autor,
        "plik": str(path),
        "blad": detail,
    }
