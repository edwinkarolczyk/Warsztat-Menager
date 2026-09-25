# WM-VERSION: 0.1
# Plik: planista_auto_print_runtime.py
# version: 1.0
"""Przygotowanie i automatyczne wysłanie karty zlecenia do domyślnej drukarki Windows."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from gui_planista import _work_order_html, _work_order_output_path


class AutoPrintError(RuntimeError):
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
        return "win32api.ShellExecute(print)"
    except Exception as exc:
        errors.append(f"ShellExecute: {exc}")

    # 2. standardowy mechanizm Windows.
    try:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
        return "os.startfile(print)"
    except Exception as exc:
        errors.append(f"os.startfile: {exc}")

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
        return "PowerShell Start-Process -Verb Print"
    except Exception as exc:
        errors.append(f"PowerShell: {exc}")

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
        print(f"[WM-DBG][DRUK] {order.get('id', '')}: {method}")
    except AutoPrintError as exc:
        raise AutoPrintError(
            f"Nie udało się wysłać zlecenia {order.get('id', '')} do domyślnej drukarki. {exc}"
        ) from exc
    return path
