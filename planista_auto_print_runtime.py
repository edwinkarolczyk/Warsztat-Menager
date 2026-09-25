# WM-VERSION: 0.1
# Plik: planista_auto_print_runtime.py
# version: 1.0
"""Przygotowanie i automatyczne wysłanie karty zlecenia do domyślnej drukarki Windows."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from datetime import datetime
import time
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


def _find_browser() -> Path | None:
    """Znajdź Edge/Chrome bez polegania na skojarzeniu plików HTML."""
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return candidate
    return None


def _browser_kiosk_print(path: Path) -> str:
    """Wydrukuj HTML przez Edge/Chrome z --kiosk-printing.
    
    To omija wadliwe skojarzenie Windows dla czasownika 'Print' plików HTML.
    Przeglądarka wywołuje window.print(), a kiosk-printing wybiera domyślną
    drukarkę bez pokazywania dialogu.
    """
    browser = _find_browser()
    if browser is None:
        raise AutoPrintError("Nie znaleziono Microsoft Edge ani Google Chrome.")

    # Osobny profil zapobiega kolizji z już uruchomioną przeglądarką.
    profile = path.parent / "_wm_print_profile"
    profile.mkdir(parents=True, exist_ok=True)
    url = path.resolve().as_uri()
    script = (
        "<script>"
        "window.addEventListener('load',()=>setTimeout(()=>window.print(),500));"
        "</script>"
    )
    html = path.read_text(encoding="utf-8")
    if "window.print()" not in html:
        html = html.replace("</body>", script + "</body>")
        path.write_text(html, encoding="utf-8")

    proc = subprocess.Popen(
        [
            str(browser),
            "--kiosk-printing",
            "--disable-print-preview",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _log_print(path, f"START browser kiosk print: {browser} pid={proc.pid}")
    # Daj przeglądarce czas na wyrenderowanie i wysłanie zadania.
    time.sleep(2.0)
    if proc.poll() not in (None, 0):
        raise AutoPrintError(f"Przeglądarka zakończyła się kodem {proc.returncode}.")
    return f"browser kiosk-printing: {browser.name}"


def _windows_print(path: Path) -> str:
    """Wyślij kartę do drukarki; nie wymagaj skojarzenia HTML w Windows."""
    errors: list[str] = []

    # 1. Preferowany mechanizm dla HTML: Edge/Chrome + kiosk-printing.
    try:
        return _browser_kiosk_print(path)
    except Exception as exc:
        errors.append(f"browser kiosk-printing: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL browser kiosk-printing: {traceback.format_exc()}")

    # 2. PyWin32 — jeśli jest dołączone do EXE.
    try:
        import win32api  # type: ignore
        win32api.ShellExecute(0, "print", str(path), None, str(path.parent), 0)
        _log_print(path, "OK win32api.ShellExecute(print)")
        return "win32api.ShellExecute(print)"
    except Exception as exc:
        errors.append(f"ShellExecute: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL ShellExecute: {traceback.format_exc()}")

    # 3. os.startfile — tylko gdy Windows ma poprawnie zarejestrowane 'Print'.
    try:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
        _log_print(path, "OK os.startfile(print)")
        return "os.startfile(print)"
    except Exception as exc:
        errors.append(f"os.startfile: {type(exc).__name__}: {exc}")
        _log_print(path, f"FAIL os.startfile: {traceback.format_exc()}")

    # 4. PowerShell z pełną ścieżką — PATH w EXE może nie zawierać powershell.exe.
    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if powershell.is_file():
        try:
            script = (
                "$p = Start-Process -FilePath "
                + repr(str(path))
                + " -Verb Print -PassThru; "
                + "if ($null -eq $p) { exit 1 }"
            )
            subprocess.run(
                [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
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
    else:
        errors.append(f"PowerShell: nie znaleziono {powershell}")

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
