"""Prosta animacja tras techników po hali."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Iterable, List, Tuple


class RouteAnimator:
    """Animuje przesuwanie się po zadanej trasie."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self._after_ids: List[str] = []

    def cancel_all(self) -> None:
        """Anuluj wszystkie zaplanowane kroki animacji."""

        for job in self._after_ids:
            try:
                self.canvas.after_cancel(job)
            except Exception:  # pragma: no cover - defensywne
                pass
        self._after_ids.clear()

    def start(
        self,
        path: Iterable[Tuple[int, int]],
        *,
        machine: Any | None = None,
        overlay: Any | None = None,
        step_ms: int = 20,
        item_id: int | None = None,
    ) -> None:
        """Rozpocznij animację wzdłuż ``path``."""

        self.cancel_all()
        points: List[Tuple[int, int]] = list(path)

        if not points:
            if machine is not None:
                setattr(machine, "status", "SERWIS")
            if overlay is not None:
                refresh = getattr(overlay, "refresh", None)
                if callable(refresh):
                    refresh()
            return

        def _step(index: int) -> None:
            if index >= len(points):
                if machine is not None:
                    setattr(machine, "status", "SERWIS")
                if overlay is not None:
                    refresh = getattr(overlay, "refresh", None)
                    if callable(refresh):
                        refresh()
                return
            x, y = points[index]
            if item_id is not None:
                try:
                    self.canvas.moveto(item_id, x, y)
                except Exception:  # pragma: no cover - defensywne
                    pass
            job = self.canvas.after(step_ms, _step, index + 1)
            self._after_ids.append(job)

        job = self.canvas.after(step_ms, _step, 0)
        self._after_ids.append(job)


__all__ = ["RouteAnimator"]

