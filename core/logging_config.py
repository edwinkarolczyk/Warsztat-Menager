from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from logging import StreamHandler

_LOG_CREATED = False


def setup_logging(log_dir: str = "logs", filename: str = "wm.log") -> None:
    global _LOG_CREATED
    if _LOG_CREATED:
        return
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    fh = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    logging.getLogger(__name__).info("[LOGCFG] Logging initialized → %s", log_path)
    _LOG_CREATED = True
