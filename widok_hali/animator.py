"""Proste miejsce na przyszłą animację elementów hali."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, Iterable, List, Tuple


class Animator:
    """Szkielet klasy animatora – obecnie nie wykonuje żadnych akcji."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False


class RouteAnimator:
    """Prosta animacja przemieszczania się po trasie."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self._after_ids: List[str] = []

    def after(self, delay: int, callback: Callable[..., Any], *args: Any) -> str:
        """Zarejestruj ``after`` i zachowaj identyfikator."""
        job = self.canvas.after(delay, callback, *args)
        self._after_ids.append(job)
        return job

    def cancel_all(self) -> None:
        """Anuluj wszystkie zaplanowane zadania ``after``."""
        for job in self._after_ids:
            try:
                self.canvas.after_cancel(job)
            except Exception:
                pass
        self._after_ids.clear()

    def animate(
        self,
        path: Iterable[Tuple[int, int]],
        machine: Dict[str, Any] | None = None,
        overlay: Any | None = None,
        step_ms: int = 20,
        item_id: int | None = None,
    ) -> None:
        """Animuj przemieszczenie się po zadanej ścieżce.

        Po dotarciu na koniec ścieżki status maszyny zostanie ustawiony na
        ``"SERWIS"`` i wywołane zostanie ``overlay.refresh()`` (jeśli
        dostępne).
        """

        self.cancel_all()
        points: List[Tuple[int, int]] = list(path)

        if not points:
            if machine is not None:
                machine["status"] = "SERWIS"
            if overlay is not None:
                refresh = getattr(overlay, "refresh", None)
                if callable(refresh):
                    refresh()
            return

        def _step(index: int) -> None:
            if index >= len(points):
                if machine is not None:
                    machine["status"] = "SERWIS"
                if overlay is not None:
                    refresh = getattr(overlay, "refresh", None)
                    if callable(refresh):
                        refresh()
                return
            x, y = points[index]
            if item_id is not None:
                try:
                    self.canvas.moveto(item_id, x, y)
                except Exception:
                    pass
            self.after(step_ms, _step, index + 1)

        self.after(step_ms, _step, 0)
