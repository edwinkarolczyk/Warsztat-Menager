from __future__ import annotations
import os
import json
import time
from typing import List

from config.paths import get_path, join_path, ensure_core_tree

def _exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)

def run() -> dict:
    """
    Wykonuje prosty audyt środowiska WM:
      - sprawdza istnienie podstawowych katalogów/plików,
      - zapisuje raport do logs/audyt_wm-{timestamp}.txt,
      - zwraca {ok, msg, path}.
    """
    ensure_core_tree()

    checks = []
    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "ok": ok, "detail": detail})

    # Katalogi kluczowe
    data_root = get_path("paths.data_root")
    logs_dir  = get_path("paths.logs_dir")
    backup_dir= get_path("paths.backup_dir")
    add("data_root", _exists(data_root), data_root)
    add("logs_dir",  _exists(logs_dir),  logs_dir)
    add("backup_dir",_exists(backup_dir),backup_dir)

    # Pliki i źródła
    stock_src = get_path("warehouse.stock_source")
    bom_file  = get_path("bom.file")
    types_f   = get_path("tools.types_file")
    statuses_f= get_path("tools.statuses_file")
    tasks_f   = get_path("tools.task_templates_file")
    machines_f= get_path("hall.machines_file")
    bg_img    = get_path("hall.background_image", "")

    add("warehouse.stock_source", _exists(stock_src), stock_src)
    add("bom.file",               _exists(bom_file),  bom_file)
    add("tools.types_file",       _exists(types_f),   types_f)
    add("tools.statuses_file",    _exists(statuses_f),statuses_f)
    add("tools.task_templates_file", _exists(tasks_f),tasks_f)
    add("hall.machines_file",     _exists(machines_f),machines_f)
    if bg_img:
        add("hall.background_image", _exists(bg_img), bg_img)
    else:
        add("hall.background_image", True, "(nie ustawiono — opcjonalne)")

    # Podsumowanie
    failed = [c for c in checks if not c["ok"]]
    ok_all = len(failed) == 0
    summary = f"OK: {len(checks)-len(failed)} / {len(checks)}; FAIL: {len(failed)}"

    # Zapis raportu
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = join_path("paths.logs_dir", f"audyt_wm-{ts}.txt")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines: List[str] = [
        f"Audyt WM — {ts}",
        "=" * 40,
        f"data_root: {data_root}",
        f"logs_dir : {logs_dir}",
        f"backup_dir: {backup_dir}",
        "-" * 40,
    ]
    for c in checks:
        lines.append(f"[{ 'OK' if c['ok'] else 'FAIL' }] {c['name']}: {c['detail']}")
    lines.append("-" * 40)
    lines.append(summary)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"ok": ok_all, "msg": summary, "path": out_path}
