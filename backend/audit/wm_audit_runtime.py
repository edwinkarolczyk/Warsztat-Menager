"""Narzędzia runtime audytu WM zapisujące logi i raport w katalogu logów."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List

from config.paths import join_path

LOG_FILENAME = "audyt_wm.log"
REPORT_FILENAME = "audyt_wm.txt"


def _ensure_logs_dir() -> str:
    """Zwraca istniejący katalog logów (paths.logs_dir)."""
    logs_dir = join_path("paths.logs_dir")
    if not logs_dir:
        raise RuntimeError("Brak ustawionej ścieżki paths.logs_dir.")
    logs_dir = logs_dir.replace("\\", os.sep)
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def _setup_logger(log_path: str) -> logging.Logger:
    """Konfiguruje logger zapisujący do podanej ścieżki."""
    logger = logging.getLogger("wm_audit_runtime")
    while logger.handlers:
        handler = logger.handlers.pop()
        try:
            handler.close()
        except Exception:
            pass
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _collect_basic_stats(root: str, logger: logging.Logger) -> List[str]:
    """Zwraca proste statystyki o projekcie wykorzystywane w raporcie."""
    py_files = 0
    json_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        parts = dirpath.split(os.sep)
        if any(part.startswith(".") for part in parts if part):
            continue
        if "__pycache__" in parts:
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                py_files += 1
            elif filename.endswith(".json"):
                json_files += 1
    logger.info(
        "Zebrane statystyki plików: %s plików .py, %s plików .json.",
        py_files,
        json_files,
    )
    return [
        f"Liczba plików .py: {py_files}",
        f"Liczba plików .json: {json_files}",
    ]


def make_report(logger: logging.Logger) -> str:
    """Buduje tekstowy raport audytu."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    logger.info("Rozpoczynam generowanie raportu audytu WM.")
    stats = _collect_basic_stats(os.getcwd(), logger)
    report_lines: List[str] = [
        "=== Raport audytu Warsztat Menager ===",
        f"Czas wygenerowania: {timestamp}",
        "",
    ]
    report_lines.extend(stats)
    report_lines.append("")
    report_lines.append(f"Logi audytu: {LOG_FILENAME}")
    logger.info("Raport audytu WM wygenerowany.")
    return "\n".join(report_lines)


def run_audit() -> str:
    """Generuje raport audytu i zapisuje logi oraz raport w katalogu logów."""
    logs_dir = _ensure_logs_dir()
    log_path = os.path.join(logs_dir, LOG_FILENAME)
    report_path = os.path.join(logs_dir, REPORT_FILENAME)

    logger = _setup_logger(log_path)
    logger.info("Uruchomiono audyt WM.")

    report = make_report(logger)

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write(report)
    logger.info("Raport audytu zapisano do %s.", report_path)

    return report
