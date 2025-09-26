"""RC1 hotfix dla widoku magazynu – pilnowanie przycisku "Zamówienia"."""

from __future__ import annotations

from typing import Any, Callable

from tkinter import messagebox

CanCheck = Callable[[Any, str], bool]
OrdersHandler = Callable[[Any], Any]


def _can_access_orders(owner: Any, can_check: CanCheck) -> bool:
    try:
        return bool(can_check(owner, "to_orders"))
    except Exception:
        return False


def build_orders_command(
    owner: Any,
    handler: OrdersHandler | None,
    can_check: CanCheck,
) -> Callable[[], None]:
    """Tworzy komendę dla przycisku Zamówienia z dodatkowymi komunikatami."""

    def _cmd() -> None:
        if not _can_access_orders(owner, can_check):
            messagebox.showwarning(
                "Uprawnienia",
                "Brak uprawnień do modułu Zamówienia.",
            )
            return
        if not callable(handler):
            messagebox.showinfo(
                "Zamówienia",
                "Moduł Zamówienia jest chwilowo niedostępny.",
            )
            return
        try:
            handler(owner)
        except Exception as exc:  # pragma: no cover - defensywne okno
            messagebox.showerror(
                "Zamówienia",
                f"Nie udało się otworzyć modułu Zamówienia: {exc}",
            )

    return _cmd


def should_disable_orders_button(
    owner: Any,
    handler: OrdersHandler | None,
    can_check: CanCheck,
) -> bool:
    """Zwraca True jeśli przycisk Zamówienia powinien być wyłączony."""

    if not _can_access_orders(owner, can_check):
        return True
    if not callable(handler):
        return True
    return False


__all__ = [
    "build_orders_command",
    "should_disable_orders_button",
]
