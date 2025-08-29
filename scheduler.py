# Plik: scheduler.py
# Wysyłanie powiadomień o nadchodzących zdarzeniach.

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timedelta

try:
    from tkinter import messagebox, TclError
except Exception:  # pragma: no cover - tkinter may be absent
    class TclError(Exception):
        pass

    class messagebox:  # pragma: no cover - fallback
        @staticmethod
        def showinfo(title: str, message: str) -> None:
            logging.info("%s: %s", title, message)

try:  # pragma: no cover - optional dependency
    from plyer import notification as _plyer_notify
except Exception:  # pragma: no cover
    _plyer_notify = None

logger = logging.getLogger(__name__)

EVENTS_FILE = os.path.join("data", "events.json")


def _read_events(path: str = EVENTS_FILE) -> list[dict]:
    """Load events from JSON file."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning("[SCHED] read error %s: %s", path, e)
    return []


def _notify(title: str, msg: str, method: str) -> None:
    """Show notification using toast or messagebox."""
    if method == "toast" and _plyer_notify:
        try:
            _plyer_notify.notify(title=title, message=msg)
            return
        except Exception:
            logger.debug("[SCHED] plyer notify failed", exc_info=True)
    messagebox.showinfo(title, msg)


def schedule_events(root, cfg: dict) -> None:
    """Schedule notifications for events from EVENTS_FILE.

    Args:
        root: Tk root for scheduling via ``after``.
        cfg: configuration dictionary with ``notifications`` section.
    """
    if not root:
        return
    notif_cfg = cfg.get("notifications", {})
    if not notif_cfg.get("enabled", True):
        return
    method = notif_cfg.get("method", "messagebox")
    notified: set[str] = set()

    def _tick() -> None:
        try:
            now = datetime.now()
            events = _read_events()
            for ev in events:
                name = ev.get("name") or ""
                when = ev.get("time")
                if not name or not when:
                    continue
                try:
                    evt_time = datetime.fromisoformat(when)
                except ValueError:
                    continue
                key = f"{name}_{when}"
                if key in notified:
                    continue
                if timedelta(0) <= evt_time - now <= timedelta(minutes=5):
                    _notify("Wydarzenie", f"{name} o {evt_time.strftime('%H:%M')}", method)
                    notified.add(key)
        except Exception:
            logger.error("[SCHED] tick error: %s", traceback.format_exc())
        finally:
            try:
                root.after(60000, _tick)
            except TclError:
                logger.info("[SCHED] scheduling stopped")

    _tick()
