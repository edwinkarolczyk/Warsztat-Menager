from __future__ import annotations
import os
import time
from typing import List

from config.paths import get_path, join_path, ensure_core_tree
from wm_log import dbg as wm_dbg, info as wm_info, err as wm_err

import json
from pathlib import Path


def wm_warn(where: str, msg: str, exc: BaseException | None = None, **kv: object) -> None:
    if exc is not None:
        kv = {**kv, "exc": repr(exc)}
    wm_info(where, msg, **kv)


_AUDIT_DATA_CANDIDATES = [
    Path("data") / "audyt.json",
    Path("config") / "audit_points.json",
]


def _load_extended_audit_data() -> dict | None:
    """Czyta rozszerzony audyt (Roadmapa) z pliku danych. Zwraca dict z 'groups' albo None."""
    for p in _AUDIT_DATA_CANDIDATES:
        try:
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("groups"), list):
                    wm_info("audit.run", "extended_loaded", path=str(p))
                    return data
        except Exception as e:
            wm_warn("audit.run", "extended_read_failed", e, path=str(p))
    return None


def _flatten_extended_audit_rows(data: dict) -> list[tuple[str, str, str, bool, str]]:
    """Spłaszcza groups/items do wierszy: (group, id, label, done, notes)."""
    rows: list[tuple[str, str, str, bool, str]] = []
    try:
        for g in data.get("groups", []):
            gname = str(g.get("name", ""))
            for it in g.get("items", []):
                rid = str(it.get("id", ""))
                label = str(it.get("label", ""))
                done = bool(it.get("done", False))
                notes = str(it.get("notes", ""))
                rows.append((gname, rid, label, done, notes))
    except Exception as e:
        wm_warn("audit.run", "extended_flatten_failed", e)
    return rows

__all__ = ["run", "run_audit"]

def _exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)

def run() -> dict:
    """
    Wykonuje prosty audyt środowiska WM:
      - sprawdza istnienie podstawowych katalogów/plików,
      - zapisuje raport do logs/audyt_wm-{timestamp}.txt,
      - zwraca {ok, msg, path}.
    """
    wm_dbg("audit.run", "enter")
    try:
        ensure_core_tree()

        checks = []

        def add(name: str, ok: bool, detail: str = ""):
            checks.append({"name": name, "ok": ok, "detail": detail})

        # Katalogi kluczowe
        data_root = get_path("paths.data_root")
        logs_dir = get_path("paths.logs_dir")
        backup_dir = get_path("paths.backup_dir")
        add("data_root", _exists(data_root), data_root)
        add("logs_dir", _exists(logs_dir), logs_dir)
        add("backup_dir", _exists(backup_dir), backup_dir)

        # Pliki i źródła
        stock_src = get_path("warehouse.stock_source")
        bom_file = get_path("bom.file")
        types_f = get_path("tools.types_file")
        statuses_f = get_path("tools.statuses_file")
        tasks_f = get_path("tools.task_templates_file")
        machines_f = get_path("hall.machines_file")
        bg_img = get_path("hall.background_image", "")

        add("warehouse.stock_source", _exists(stock_src), stock_src)
        add("bom.file", _exists(bom_file), bom_file)
        add("tools.types_file", _exists(types_f), types_f)
        add("tools.statuses_file", _exists(statuses_f), statuses_f)
        add("tools.task_templates_file", _exists(tasks_f), tasks_f)
        add("hall.machines_file", _exists(machines_f), machines_f)
        if bg_img:
            add("hall.background_image", _exists(bg_img), bg_img)
        else:
            add("hall.background_image", True, "(nie ustawiono — opcjonalne)")

        # Podsumowanie
        failed = [c for c in checks if not c["ok"]]
        ok_all = len(failed) == 0
        summary = (
            f"OK: {len(checks) - len(failed)} / {len(checks)}; FAIL: {len(failed)}"
        )

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
            lines.append(
                f"[{ 'OK' if c['ok'] else 'FAIL' }] {c['name']}: {c['detail']}"
            )
        lines.append("-" * 40)
        lines.append(summary)

        # --- BEGIN EXTENDED AUDIT APPEND ---
        try:
            _ext = _load_extended_audit_data()
            if _ext:
                _rows = _flatten_extended_audit_rows(_ext)
                if _rows:
                    lines.append("")  # odstęp
                    lines.append("---- ROADMAP AUDYT (data/audyt.json) ----")
                    total = len(_rows)
                    done = sum(1 for r in _rows if r[3] is True)
                    lines.append(f"Pozycje: {total} | Wykonane: {done} | Otwarte: {total-done}")
                    lines.append("")  # odstęp

                    # format jednej linii: [OK|TODO] Grupa :: ID – Opis  (notatka)
                    for (grp, rid, label, ok, notes) in _rows:
                        status = "OK" if ok else "TODO"
                        # skracanie bardzo długich notatek do czytelnego raportu
                        nshort = notes.strip()
                        if len(nshort) > 120:
                            nshort = nshort[:117] + "..."
                        line = f"[{status}] {grp} :: {rid} – {label}"
                        if nshort:
                            line += f"  ({nshort})"
                        lines.append(line)

                    lines.append("---- /ROADMAP AUDYT ----")
                    wm_info("audit.run", "extended_appended", count=total, done=done)
        except Exception as _e:
            wm_warn("audit.run", "extended_append_failed", _e)
        # --- END EXTENDED AUDIT APPEND ---

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        wm_info("audit.run", "written", path=out_path, summary=summary)
        return {"ok": ok_all, "msg": summary, "path": out_path}
    except Exception as e:  # pragma: no cover - logowanie błędów
        wm_err("audit.run", "exception", e)
        return {"ok": False, "msg": "Błąd audytu – szczegóły w logu."}


def run_audit() -> str:
    """Uruchamia audyt i zwraca treść raportu jako tekst."""
    result = run()
    report_path = result.get("path") if isinstance(result, dict) else None
    if report_path and os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as handle:
                report = handle.read()
        except Exception as exc:  # pragma: no cover - logowanie błędów
            wm_err("audit.run_audit", "read_failed", exc, path=report_path)
        else:
            wm_info("audit.run_audit", "report_ready", path=report_path)
            return report

    summary = ""
    if isinstance(result, dict):
        summary = result.get("msg") or ""
        try:
            serialized = json.dumps(result, ensure_ascii=False, indent=2)
        except Exception:
            serialized = summary or str(result)
    else:
        serialized = str(result)

    wm_info("audit.run_audit", "fallback", summary=summary)
    return serialized
