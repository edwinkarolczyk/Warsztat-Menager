# WM-VERSION: 0.1
# Plik: planista_auto_print_runtime.py
# version: 1.0
"""Przygotowanie i automatyczne wysłanie karty zlecenia do domyślnej drukarki Windows."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from datetime import datetime
import traceback

from gui_planista import _work_order_html, _work_order_output_path


class AutoPrintError(RuntimeError):
    pass


def _print_log_path(path: Path) -> Path:
    log_path = path.parent / "auto_print.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def _log_print(path: Path, message: str) -> None:
    try:
        with _print_log_path(path).open("a", encoding="utf-8") as handle:
            handle.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] "
                f"{message}\\n"
            )
    except Exception:
        pass


def prepare_work_order_card(order: dict) -> Path:
    path = _work_order_output_path(order)
    html = _work_order_html(order)
    # Przy automatycznym wydruku używamy systemowego polecenia Print, więc
    # usuwamy skrypt window.print(), żeby nie otworzyć drugiego dialogu.
    html = html.replace(
        "<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),250));</script>",
        "",
    )
    path.write_text(html, encoding="utf-8")
    return path


def _windows_print(path: Path) -> str:
    """Wyślij plik do drukarki, próbując kilku mechanizmów Windows."""
    errors: list[str] = []

    # 1. pywin32: jawne ShellExecute("print") — działa na części konfiguracji,
    # na których os.startfile nie udostępnia czasownika Print dla HTML.
    try:
        import win32api  # type: ignore
        win32api.ShellExecute(0, "print", str(path), None, str(path.parent), 0)
        _log_print(path, "OK win32api.ShellExecute(print)")
        return "win32api.ShellExecute(print)"
    except Exception as exc:
        errors.append(f"ShellExecute: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL ShellExecute: {traceback.format_exc()}")

    # 2. standardowy mechanizm Windows.
    try:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
        _log_print(path, "OK os.startfile(print)")
        return "os.startfile(print)"
    except Exception as exc:
        errors.append(f"os.startfile: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL os.startfile: {traceback.format_exc()}")

    # 3. PowerShell Start-Process -Verb Print jako fallback.
    try:
        script = (
            "$p = Start-Process -FilePath "
            + repr(str(path))
            + " -Verb Print -PassThru; "
            + "if ($null -eq $p) { exit 1 }"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        _log_print(path, "OK PowerShell Start-Process -Verb Print")
        return "PowerShell Start-Process -Verb Print"
    except Exception as exc:
        errors.append(f"PowerShell: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL PowerShell: {traceback.format_exc()}")

    _log_print(path, "ALL PRINT METHODS FAILED: " + " | ".join(errors))
    raise AutoPrintError("; ".join(errors))


def dispatch_work_order_print(order: dict) -> Path:
    """Wyślij kartę do domyślnej drukarki; karta zawsze pozostaje w WM_ROOT."""
    path = prepare_work_order_card(order)
    if os.name != "nt":
        raise AutoPrintError(
            f"Karta została zapisana: {path}. Automatyczny druk jest obsługiwany w Windows."
        )
    try:
        method = _windows_print(path)
        msg = f"[WM-DBG][DRUK] {order.get('id', '')}: {method}"
        print(msg, flush=True)
        _log_print(path, msg)
    except AutoPrintError as exc:
        _log_print(path, f"[WM-DBG][DRUK] ERROR {order.get('id', '')}: {exc}")
        raise AutoPrintError(
            f"Nie udało się wysłać zlecenia {order.get('id', '')} do domyślnej drukarki. {exc}"
        ) from exc
    return path
