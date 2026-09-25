# WM-VERSION: 0.1
# Plik: planista_auto_print_runtime.py
# version: 1.0
"""Przygotowanie i automatyczne wysłanie karty zlecenia do domyślnej drukarki Windows."""

from __future__ import annotations

import os
from pathlib import Path

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


def dispatch_work_order_print(order: dict) -> Path:
    """Wyślij kartę do domyślnej drukarki; karta zawsze pozostaje w WM_ROOT."""
    path = prepare_work_order_card(order)
    if os.name != "nt":
        raise AutoPrintError(
            f"Karta została zapisana: {path}. Automatyczny druk jest obsługiwany w Windows."
        )
    try:
        os.startfile(str(path), "print")
    except Exception as exc:
        raise AutoPrintError(
            f"Nie udało się wysłać zlecenia {order.get('id', '')} do domyślnej drukarki: {exc}"
        ) from exc
    return path
