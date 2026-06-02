# Plik: gui_narzedzia.py
# version: 1.0
# Zmiany 1.5.31:
# - [NARZĘDZIA] Przywrócono kompatybilność ze starymi plikami JSON (listy i klucz "items").
#
# Zmiany 1.5.30:
# - [MAGAZYN] Zwrot materiałów przy cofnięciu oznaczenia zadania jako wykonane
#
# Zmiany 1.5.29:
# - [MAGAZYN] Integracja z magazynem: przy oznaczeniu zadania jako wykonane zużywamy materiały (consume_for_task)
# - [MAGAZYN] Dodano import logika_zadan jako LZ
#
# Zmiany 1.5.28:
# - Dodano ręczny przełącznik (checkbox) „Przenieś do SN przy zapisie” dla narzędzi NN (001–499).
#   Widoczny tylko dla NOWE; aktywny jedynie dla roli uprawnionej (wg config narzedzia.uprawnienia.zmiana_klasy).
# - Opcja co zrobić z listą zadań przy konwersji: „pozostaw”, „podmień na serwis wg typu” (domyślnie), „dodaj serwis do istniejących”.
# - Usunięto dawny auto-prompt NN→SN przy statusie „sprawne” — teraz decyzja jest wyłącznie „ptaszkiem”.
# - Zachowano: sumowanie zadań po zmianie statusu (produkcja/serwis), blokada duplikatów, fix dublowania okienek.
#
# Uwaga: Historia dopisuje wpis o zmianie trybu: [tryb] NOWE -> [tryb] STARE.

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import time
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog
from tkinter import ttk, messagebox, simpledialog

from narzedzia_ui import STATE
from narzedzia_ui.list_panel import ToolsThreeTabsView, open_tools_window
from ui_theme import ensure_theme_applied, get_theme_color
from tool_data_bridge import ToolDataBridge

try:  # pragma: no cover - moduł kreatora dyspozycji opcjonalny
    from wm.dyspo_wizard import open_dyspo_wizard
except ImportError as exc:  # pragma: no cover - brak modułu w starszych instalacjach
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł wm.dyspo_wizard (ImportError: %s)",
        exc,
    )
    open_dyspo_wizard = None  # type: ignore

try:  # pragma: no cover - skróty opcjonalne
    from wm.gui.shortcuts import bind_ctrl_d
except ImportError as exc:  # pragma: no cover - fallback
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł wm.gui.shortcuts (ImportError: %s)",
        exc,
    )

    def bind_ctrl_d(*_args, **_kwargs):  # type: ignore
        return None


class ToolsBatchLoader:
    """
    Loader do Treeview bez freeza:
    - czyta pliki narzędzi batchami (np. 10 szt)
    - po każdym batchu oddaje sterowanie do UI (after)
    - można przerwać (cancel)
    """

    def __init__(
        self,
        tk_root: tk.Misc,
        tool_paths: list[str],
        read_tool_min_fn,
        insert_row_fn,
        set_progress_fn=None,
        batch_size: int = 10,
        tick_ms: int = 100,
        dbg_prefix: str = "[WM-PERF][TOOLS-BATCH]",
    ):
        self.tk_root = tk_root
        self.tool_paths = list(tool_paths)
        self.read_tool_min_fn = read_tool_min_fn
        self.insert_row_fn = insert_row_fn
        self.set_progress_fn = set_progress_fn
        self.batch_size = int(batch_size)
        self.tick_ms = int(tick_ms)
        self.dbg_prefix = dbg_prefix

        self._i = 0
        self._after_id = None
        self._started_ts = None
        self._cancelled = False

    def start(self):
        self._cancelled = False
        self._i = 0
        self._started_ts = time.perf_counter()
        self._schedule_next(0)

    def cancel(self):
        self._cancelled = True
        if self._after_id is not None:
            try:
                self.tk_root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _schedule_next(self, delay_ms: int):
        self._after_id = self.tk_root.after(delay_ms, self._tick)

    def _tick(self):
        if self._cancelled:
            return

        total = len(self.tool_paths)
        start_i = self._i
        end_i = min(self._i + self.batch_size, total)

        for idx in range(start_i, end_i):
            path = self.tool_paths[idx]
            try:
                row = self.read_tool_min_fn(path)
                if row:
                    self.insert_row_fn(row)
            except Exception:
                continue

        self._i = end_i

        if self.set_progress_fn:
            try:
                self.set_progress_fn(self._i, total)
            except Exception:
                pass

        if self._i < total:
            self._schedule_next(self.tick_ms)
        else:
            dt = (time.perf_counter() - self._started_ts) * 1000.0
            perf(f"{self.dbg_prefix} DONE total={total} dt={dt:.2f}ms")
            self._after_id = None


def _wm_widget_alive(widget: tk.Misc | None) -> bool:
    try:
        if widget is None:
            return False
        exists = getattr(widget, "winfo_exists", None)
        if callable(exists):
            return bool(exists())
        return True
    except Exception:
        return False


# === NOWA FUNKCJA POMOCNICZA ===
def _normalize_path(path: str | Path) -> Path:
    """
    Zwraca znormalizowaną ścieżkę do użycia jako klucz w cache.
    Bezpieczna na Windows (case-insensitive, absolutna ścieżka).
    """
    return Path(os.path.normcase(os.path.abspath(str(path))))


def _maybe_open_dyspo(root, context):
    if open_dyspo_wizard is None:
        return
    target = root
    if hasattr(root, "winfo_toplevel"):
        try:
            target = root.winfo_toplevel()
        except Exception:
            target = root
    if getattr(target, "tk", None) is None:
        local_tk = globals().get("tk")
        local_ttk = globals().get("ttk")
        dialog = None
        if hasattr(local_tk, "Toplevel"):
            try:
                dialog = local_tk.Toplevel(target)
                try:
                    ensure_theme_applied(dialog)
                except Exception:
                    pass
            except Exception:
                dialog = None
        proceed = None
        if hasattr(local_ttk, "Button"):
            try:
                def _proceed() -> None:
                    new_dialog = None
                    if hasattr(local_tk, "Toplevel"):
                        try:
                            new_dialog = local_tk.Toplevel(target)
                            try:
                                ensure_theme_applied(new_dialog)
                            except Exception:
                                pass
                        except Exception:
                            new_dialog = None
                    if hasattr(local_ttk, "Button"):
                        try:
                            save_cmd = lambda: None
                            local_ttk.Button(
                                new_dialog or target, text="Zapisz", command=save_cmd
                            )
                            if new_dialog is not None and hasattr(new_dialog, "bind"):
                                new_dialog.bind("<Return>", save_cmd)
                        except Exception:
                            pass
                proceed = _proceed
                local_ttk.Button(
                    dialog or target, text="Dalej", command=proceed
                )
            except Exception:
                proceed = None
        if dialog is not None and hasattr(dialog, "bind") and proceed is not None:
            try:
                dialog.bind("<Return>", proceed)
            except Exception:
                pass
        return
    open_dyspo_wizard(target, context=context)


def _wm_humanize_duration_seconds(seconds: float | int | None) -> str:
    """Zwraca czytelny czas wizyty: godziny -> dni -> miesiące -> lata."""

    try:
        total_seconds = float(seconds or 0)
    except (TypeError, ValueError):
        total_seconds = 0.0

    if total_seconds <= 0:
        return "0h"

    total_minutes = int(total_seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours < 24:
        if minutes:
            return f"{max(0, hours)}h {minutes}m"
        return f"{max(1, hours)}h"

    days = hours // 24
    rem_hours = hours % 24

    if days < 30:
        if rem_hours:
            return f"{days}d {rem_hours}h"
        return f"{days}d"

    months = days // 30
    rem_days = days % 30

    if months < 12:
        if rem_days:
            return f"{months} mies. {rem_days}d"
        return f"{months} mies."

    years = months // 12
    rem_months = months % 12

    if rem_months:
        return f"{years}r {rem_months} mies."
    return f"{years}r"


def _wm_humanize_duration_text(value: object) -> str:
    """Konwertuje stare teksty typu '29h 29m' / '29h' na czytelny format."""

    raw = str(value or "").strip()
    if not raw or raw == "—":
        return raw or "—"
    if "w toku" in raw.lower():
        return raw

    import re

    hours = 0
    minutes = 0

    match_h = re.search(r"(\d+)\s*h", raw, re.IGNORECASE)
    match_m = re.search(r"(\d+)\s*m", raw, re.IGNORECASE)
    if match_h:
        hours = int(match_h.group(1))
    if match_m:
        minutes = int(match_m.group(1))

    if not match_h and not match_m:
        return raw

    return _wm_humanize_duration_seconds(hours * 3600 + minutes * 60)


try:
    from utils.tool_mode_helpers import infer_mode_from_id, validate_number
except ImportError as exc:  # pragma: no cover - fallback przy brakującym helperze
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł utils.tool_mode_helpers (ImportError: %s)",
        exc,
    )

    def validate_number(nr, mode, *, is_new, keep_number):
        if is_new or not keep_number:
            if (mode == "NN" and not (1 <= nr <= 499)) or (
                mode == "SN" and not (500 <= nr <= 1000)
            ):
                return False, "Numer poza dozwolonym zakresem dla trybu."
        else:
            if not (1 <= nr <= 1000):
                return False, "Dozwolone numery 001–1000."
        return True, None

    def infer_mode_from_id(tool_id):
        try:
            n = int(str(tool_id).lstrip("0") or "0")
        except Exception:
            n = 0
        return "NN" if 1 <= n <= 499 else "SN"

_theme_guard_spec = importlib.util.find_spec("ui_theme_guard")
if _theme_guard_spec is not None:
    _theme_guard_module = importlib.import_module("ui_theme_guard")
    ensure_theme_applied = getattr(
        _theme_guard_module, "ensure_theme_applied", lambda _widget: None
    )
else:
    def ensure_theme_applied(_widget):
        return None

try:
    from utils_json import (
        normalize_tools_doc,
        normalize_tools_index,
        safe_read_json as _safe_read_json,
        safe_write_json as _safe_write_json,
    )
except ImportError as exc:
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł utils_json (ImportError: %s)",
        exc,
    )

    import json as _json

    def _safe_read_json(path: str, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return default

    def _safe_write_json(path: str, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)

    def normalize_tools_doc(doc):
        """
        Normalizuje strukturę dokumentu narzędzi:
        - list -> {"narzedzia": list}   (wsteczna kompatybilność)
        - dict z różnymi możliwymi kluczami -> mapuje na "narzedzia"
        - dict pojedynczego wpisu -> opakuj w listę pod "narzedzia"
        """
        if doc is None:
            return {"narzedzia": []}

        if isinstance(doc, list):
            return {"narzedzia": [row for row in doc if isinstance(row, dict)]}

        if isinstance(doc, dict):
            aliases = ("narzedzia", "narzędzia", "tools", "items")
            for k in aliases:
                if k in doc and isinstance(doc[k], list):
                    return {"narzedzia": [row for row in doc[k] if isinstance(row, dict)]}
            # pojedynczy wpis jako dict
            return {"narzedzia": [doc]}

        return {"narzedzia": []}

    def normalize_tools_index(doc):
        normalized = {"items": []}

        if isinstance(doc, list):
            normalized["items"] = [row for row in doc if isinstance(row, dict)]
            return normalized

        if isinstance(doc, dict):
            meta = {
                k: v
                for k, v in doc.items()
                if k not in {"items", "narzedzia", "narzędzia", "tools"}
            }
            normalized.update(meta)

            for key in ("items", "narzedzia", "narzędzia", "tools"):
                raw = doc.get(key)
                if isinstance(raw, list):
                    normalized["items"] = [row for row in raw if isinstance(row, dict)]
                    if normalized["items"]:
                        break

            if not normalized["items"]:
                keys = ("nr", "numer", "id", "nazwa", "status", "typ", "zadania")
                if any(key in doc for key in keys):
                    normalized["items"] = [dict(meta)]

            return normalized

        return normalized
try:
    import logika_zadan as LZ  # [MAGAZYN] zużycie materiałów dla zadań
except ImportError as exc:  # pragma: no cover - moduł opcjonalny
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł logika_zadan (ImportError: %s)",
        exc,
    )
    LZ = None
import logika_magazyn as LM  # [MAGAZYN] zwrot materiałów
from utils.path_utils import cfg_path
import ui_hover
import zadania_assign_io
import profile_utils
from services import profile_service
from services.profile_service import ProfileService, load_assign_tools, save_assign_tool
from config_manager import ConfigManager, resolve_rel

try:
    from config_manager import get_config  # type: ignore
except ImportError:  # pragma: no cover - fallback dla starszych wersji
    def get_config():
        try:
            return ConfigManager().load()
        except Exception:
            return {}
from config.paths import (
    get_path,
    p_profiles,
    p_tools_defs,
    p_users,
)
from utils_tools import (
    ensure_tools_sample_if_empty,
    load_tools_rows_with_fallback,
    migrate_tools_scattered_to_root,
    save_tool_item,
    save_tools_rows,
)
from utils_paths import tools_dir
from tools_config_loader import (
    load_config,
    get_tasks_for_status,
    get_types,
    find_type,
)
from wm_tools_helpers import (
    iter_tools_json,
    is_valid_tool_record,
    ensure_task_shape as ensure_task_shape_helper,
    is_pending_task as is_pending_task_helper,
    assign_task_any,
    save_tool_json,
    merge_tasks_with_status_templates,
    tool_task_id,
)
from wm_perf import perf, perf_span

try:
    from narzedzia_history import append_tool_history
except ImportError as exc:  # pragma: no cover - historia opcjonalna
    getLogger(__name__).debug(
        "[WM-DBG][narzedzia] pomijam opcjonalny moduł narzedzia_history (ImportError: %s)",
        exc,
    )

    def append_tool_history(*_args, **_kwargs):
        return None

# ===================== MOTYW (użytkownika) =====================
from ui_theme import apply_theme_safe as apply_theme
from utils.gui_helpers import clear_frame
from utils import error_dialogs
import logger as app_logger


_ACTIVE_TOOL_EDITOR_OPENER = None
_ACTIVE_TOOL_EDITOR_ROOT = None


def _external_tool_id_variants(tool_id: str) -> set[str]:
    """Warianty ID narzędzia do porównania: 42 / 042."""
    raw = str(tool_id or "").strip()
    variants = {raw}
    if raw.isdigit():
        variants.add(raw.zfill(3))
        variants.add(str(int(raw)))
    return {item for item in variants if item}


def _external_get_tool_id(tool: Mapping[str, Any]) -> str:
    return str(tool.get("id") or tool.get("nr") or tool.get("numer") or "").strip()


def _external_load_tools_rows() -> list[Mapping[str, Any]]:
    """
    Ładuje narzędzia dla wejścia z Dyspozycji.

    Ma być odporne na różne sygnatury load_tools_rows_with_fallback()
    i nie może wymagać wcześniej otwartego modułu Narzędzia.
    """
    print("[WM-DBG][DYSPO->NARZ] _external_load_tools_rows start")
    attempts = []

    try:
        cfg = get_config()
        attempts.append(
            (
                "[WM-DBG][DYSPO->NARZ] próba "
                "load_tools_rows_with_fallback(cfg, resolve_rel)",
                lambda: load_tools_rows_with_fallback(cfg, resolve_rel),
            )
        )
    except Exception as exc:
        print(f"[WM-DBG][DYSPO->NARZ][ERR] próba ładowania narzędzi nieudana: {exc}")

    attempts.append(
        (
            "[WM-DBG][DYSPO->NARZ] próba load_tools_rows_with_fallback()",
            lambda: load_tools_rows_with_fallback(),
        )
    )

    for diagnostic, attempt in attempts:
        print(diagnostic)
        try:
            result = attempt()
        except Exception as exc:
            print(f"[WM-DBG][DYSPO->NARZ][ERR] próba ładowania narzędzi nieudana: {exc}")
            continue

        if isinstance(result, tuple):
            rows = result[0] if result else []
        else:
            rows = result

        if isinstance(rows, list):
            print(f"[WM-DBG][DYSPO->NARZ] załadowano rows={len(rows)} typ={type(result)}")
            return [row for row in rows if isinstance(row, Mapping)]

    rows: list[Mapping[str, Any]] = []
    print("[WM-DBG][DYSPO->NARZ] fallback iter_tools_json()")
    try:
        for idx, entry in enumerate(iter_tools_json()):
            if isinstance(entry, tuple):
                path, data = entry
            else:
                path = entry
                try:
                    data = _safe_read_json(str(path), {})
                except Exception:
                    data = {}
            if idx < 10:
                print(f"[WM-DBG][DYSPO->NARZ] iter_tools_json[{idx}] path={path}")
            if isinstance(data, Mapping):
                row = dict(data)
                row.setdefault("_path", str(path))
                if not _external_get_tool_id(row):
                    stem = Path(str(path)).stem
                    row.setdefault("id", stem)
                    row.setdefault("nr", stem)
                    row.setdefault("numer", stem)
                rows.append(row)
    except Exception:
        pass

    print(f"[WM-DBG][DYSPO->NARZ] _external_load_tools_rows koniec rows={len(rows)}")
    return rows


def _external_find_tool_by_id(tool_id: str) -> dict[str, Any] | None:
    """Znajduje narzędzie po ID bez wymagania otwartego modułu Narzędzia."""
    variants = _external_tool_id_variants(tool_id)
    print(f"[WM-DBG][DYSPO->NARZ] szukam narzędzia tool_id={tool_id!r}, variants={variants}")

    rows = _external_load_tools_rows()

    for idx, row in enumerate(rows or []):
        if not isinstance(row, Mapping):
            continue
        row_id = _external_get_tool_id(row)
        if idx < 10:
            print(f"[WM-DBG][DYSPO->NARZ] row[{idx}] id={row_id!r}")
        if row_id in variants:
            print(f"[WM-DBG][DYSPO->NARZ] znaleziono narzędzie row_id={row_id!r}")
            return dict(row)
        if row_id.isdigit() and str(int(row_id)) in variants:
            print(f"[WM-DBG][DYSPO->NARZ] znaleziono narzędzie row_id={row_id!r}")
            return dict(row)

    print(f"[WM-DBG][DYSPO->NARZ][WARN] nie znaleziono narzędzia tool_id={tool_id!r}")
    return None


def _external_find_tool_path(tool: Mapping[str, Any]) -> str:
    """Zwraca ścieżkę pliku narzędzia dla pełnego edytora."""
    path = str(tool.get("_path") or tool.get("path") or tool.get("plik") or "").strip()
    if path:
        return path

    tool_id = _external_get_tool_id(tool)
    if not tool_id:
        return ""

    candidates: list[Path] = []
    try:
        base = Path(_resolve_tools_dir())
        candidates.extend(
            [
                base / f"{tool_id}.json",
                base / f"{tool_id.zfill(3)}.json"
                if tool_id.isdigit()
                else base / f"{tool_id}.json",
            ]
        )
    except Exception:
        pass

    try:
        for entry in iter_tools_json():
            if isinstance(entry, tuple):
                candidate_path = Path(str(entry[0]))
            else:
                candidate_path = Path(str(entry))
            if candidate_path.stem in _external_tool_id_variants(tool_id):
                candidates.append(candidate_path)
    except Exception:
        pass

    for candidate in candidates:
        try:
            if candidate.exists():
                return str(candidate)
        except Exception:
            continue
    return ""


def _active_tool_editor_available() -> bool:
    root = globals().get("_ACTIVE_TOOL_EDITOR_ROOT")
    opener = globals().get("_ACTIVE_TOOL_EDITOR_OPENER")
    if not callable(opener):
        return False
    try:
        if root is not None and hasattr(root, "winfo_exists"):
            return bool(root.winfo_exists())
    except Exception:
        return False
    return root is not None


def open_tool_from_external_context(master: tk.Misc | None, tool_id: str) -> bool:
    """
    Publiczny helper dla Dyspozycji.
    Otwiera pełny edytor narzędzia z modułu Narzędzia.
    """
    print(f"[WM-DBG][DYSPO->NARZ] open_tool_from_external_context tool_id={tool_id!r}")
    print(f"[WM-DBG][DYSPO->NARZ] _OPEN_TOOL_EDITOR_BY_ID callable={callable(_OPEN_TOOL_EDITOR_BY_ID)}")
    print(f"[WM-DBG][DYSPO->NARZ] moduł Narzędzia aktywny={_active_tool_editor_available()}")
    tool = _external_find_tool_by_id(tool_id)
    if not tool:
        return False

    opener = globals().get("_ACTIVE_TOOL_EDITOR_OPENER")
    if callable(opener) and _active_tool_editor_available():
        opener(tool)
        return True

    raise RuntimeError(
        "Pełny edytor narzędzia jest dostępny dopiero po otwarciu modułu Narzędzia. "
        "Otwórz moduł Narzędzia raz, potem wróć do Dyspozycji."
    )


logger = getLogger(__name__)
if not hasattr(logger, "log_akcja"):
    setattr(logger, "log_akcja", getattr(app_logger, "log_akcja", lambda *args, **kwargs: None))
LOG = logger


def _parse_any_date(value: Any) -> datetime | None:
    """Parse a variety of legacy date formats into :class:`datetime`."""

    if isinstance(value, datetime):
        return value
    if value in (None, "", " "):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    iso_candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y.%m.%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _format_display_date(value: Any) -> str:
    """Format *value* to ``DD-MM-YYYY`` when possible."""

    parsed = _parse_any_date(value)
    if parsed is not None:
        return parsed.strftime("%d-%m-%Y")
    if isinstance(value, str):
        return value.strip()
    return ""


def _task_identifier(nr: str, key: Any) -> str | None:
    """Return identifier for task ``key`` belonging to tool ``nr``."""

    if isinstance(key, int):
        return tool_task_id(nr, key)
    return None


def _lookup_assignment(assignments: dict[str, Any], nr: str, key: Any) -> str:
    """Return login assigned to ``(nr, key)`` using override mapping."""

    candidates: list[str] = []
    task_id = _task_identifier(nr, key)
    if task_id:
        candidates.append(task_id)
    if isinstance(key, int):
        base_nr = str(nr).strip()
        plain = f"NARZ-{base_nr}-{key + 1}"
        candidates.append(plain)
        stripped = base_nr.lstrip("0") or base_nr
        if stripped != base_nr:
            if task_id:
                suffix = task_id.rsplit("-", 1)[-1]
                candidates.append(f"NARZ-{stripped}-{suffix}")
            candidates.append(f"NARZ-{stripped}-{key + 1}")
    for candidate in candidates:
        if candidate in assignments:
            value = assignments.get(candidate)
            if value is not None:
                return str(value)
    return ""


def _auto_archive_for_sprawne(
    tasks: list[dict[str, Any]], login: str | None
) -> list[tuple[str, str]]:
    """Mark all tasks as done when tool status switches to ``sprawne``."""

    completed: list[tuple[str, str]] = []
    iso_now = _now_iso()
    for idx, entry in enumerate(tasks):
        shaped = ensure_task_shape(entry)
        if not shaped:
            continue
        if shaped.get("archived") or shaped.get("done"):
            continue
        if login:
            shaped["by"] = login
        shaped["done"] = True
        shaped["state"] = "done"
        shaped["status"] = _clean_status(shaped.get("status"), "done")
        if not shaped.get("date_added"):
            shaped["date_added"] = iso_now
        shaped["date_done"] = _normalize_date_value(shaped.get("date_done")) or iso_now
        shaped["archived"] = True
        shaped["archived_at"] = (
            _normalize_date_value(shaped.get("archived_at"))
            or shaped["date_done"]
            or iso_now
        )
        tasks[idx] = shaped
        completed.append((shaped.get("tytul") or shaped.get("title") or "", shaped["date_done"]))
    return completed


def _task_dates_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    """Return display and sort helpers for the task date column."""

    if not isinstance(task, dict):
        return {"display": "", "sort_token": "", "has_date": False, "added": "", "done": ""}

    order = ["date_added", "data", "termin", "deadline", "date"]
    display = ""
    sort_token = ""
    sort_dt = None
    for key in order:
        candidate = task.get(key)
        display_candidate = _format_display_date(candidate)
        if not display_candidate:
            continue
        display = display_candidate
        parsed = _parse_any_date(candidate)
        if parsed is not None:
            sort_dt = parsed.replace(microsecond=0)
            sort_token = sort_dt.isoformat()
        else:
            sort_token = display_candidate
        break

    added_display = _format_display_date(task.get("date_added"))
    done_display = _format_display_date(task.get("date_done") or task.get("ts_done"))

    return {
        "display": display,
        "sort_token": sort_token,
        "has_date": bool(display),
        "added": added_display,
        "done": done_display,
        "sort_dt": sort_dt,
    }

def _var_to_bool(value: Any) -> bool:
    """Coerce Tkinter variable values to ``bool`` reliably."""

    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off"}
    return bool(value)


def _is_archived_view() -> bool:
    """Return ``True`` when the archived-only toggle is active."""

    if STATE.tasks_archived_var is None:
        return False
    try:
        raw = STATE.tasks_archived_var.get()
    except Exception:
        return False
    return _var_to_bool(raw)


def _now_iso() -> str:
    """Return current timestamp in ISO format without microseconds."""

    return datetime.now().replace(microsecond=0).isoformat()


def _normalize_date_value(value: Any) -> str:
    """Return sanitized ISO-like string for *value* or empty string."""

    parsed: datetime | None = None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = _parse_any_date(text)
        if parsed is None:
            return text
    else:
        return ""

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed.replace(microsecond=0).isoformat()


def _clean_status(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return fallback


def _prepare_new_task(payload: Dict[str, Any], *, now_iso: str | None = None) -> Dict[str, Any]:
    """Create a task dict with fresh metadata for new entries."""

    shaped = ensure_task_shape(payload)
    stamp = now_iso or _now_iso()

    source_value = str(shaped.get("source") or "").strip()
    shaped["source"] = source_value or "unknown"

    if source_value:
        source_lower = source_value.lower()
        if source_lower in {"preset", "status_default", "status_template", "visit_template"}:
            shaped["done"] = False
            shaped["by"] = None
            shaped["ts_done"] = None
    elif shaped.get("done") is False:
        shaped["by"] = None
        shaped["ts_done"] = None

    existing_added = _normalize_date_value(shaped.get("date_added"))
    shaped["date_added"] = existing_added or stamp

    if shaped.get("done"):
        status_clean = _clean_status(shaped.get("status"), "done")
        shaped["state"] = "done"
        shaped["status"] = "done" if status_clean.lower() in {"done", "active"} else status_clean
        existing_done = _normalize_date_value(shaped.get("date_done") or shaped.get("ts_done"))
        shaped["date_done"] = existing_done or stamp
        archived_at = _normalize_date_value(shaped.get("archived_at")) or shaped["date_done"]
        shaped["archived_at"] = archived_at or stamp
        shaped["archived"] = True
    else:
        status_clean = _clean_status(shaped.get("status"), "active")
        shaped["state"] = "active"
        shaped["status"] = "active" if status_clean.lower() in {"done", "active"} else status_clean
        shaped["date_done"] = _normalize_date_value(shaped.get("date_done")) or ""
        shaped.pop("archived_at", None)
        if shaped.get("archived"):
            shaped.pop("archived", None)

    return shaped


def _log_tool_history(tool_id: str, user: str | None, action: str, **extra: Any) -> None:
    """Best-effort wrapper for :func:`append_tool_history`."""

    tool_clean = (tool_id or "").strip()
    if not tool_clean:
        return
    try:
        append_tool_history(tool_clean, (user or "system") or "system", action, **extra)
    except Exception:
        LOG.debug("[TOOLS][HIST] Nie udało się zapisać historii (%s)", action)

def _as_tool_dict(doc: Any) -> Dict[str, Any]:
    """Return a dictionary representation of a tool document."""

    keys_hint = ("nr", "numer", "id", "nazwa", "status", "typ", "zadania")

    if isinstance(doc, dict):
        if any(key in doc for key in keys_hint):
            return dict(doc)
        for key in ("narzedzia", "narzędzia", "items", "tools"):
            nested = doc.get(key)
            if isinstance(nested, dict):
                return dict(nested)
            if isinstance(nested, list):
                for entry in nested:
                    if isinstance(entry, dict):
                        return dict(entry)
                return {}
        return {}
    if isinstance(doc, list):
        for el in doc:
            if isinstance(el, dict):
                return dict(el)
    return {}


def _task_date_str(task: Dict[str, Any]) -> str:
    """Return a human-friendly task date string (DD-MM-YYYY)."""

    if not isinstance(task, dict):
        return ""

    summary = _task_dates_summary(task)
    return summary.get("display", "")


def _norm_tasks(tasks: Any) -> List[Dict[str, Any]]:
    """Return a list of normalized task dictionaries regardless of the representation."""

    if isinstance(tasks, list):
        return [ensure_task_shape(t) for t in tasks if isinstance(t, dict)]
    if isinstance(tasks, str):
        try:
            legacy = _legacy_parse_tasks(tasks)
        except Exception:
            return []
        return [ensure_task_shape(t) for t in legacy if isinstance(t, dict)]
    return []


def _normalize_image_list(value: Any) -> List[str]:
    """Return a sanitized list of relative image paths."""

    paths: List[str] = []
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            paths.append(candidate)
        return paths

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if not isinstance(item, str):
                continue
            candidate = item.strip()
            if candidate and candidate not in paths:
                paths.append(candidate)
    return paths


def _normalized_tool_images(data: Dict[str, Any]) -> List[str]:
    """Merge legacy ``obraz`` and new ``obrazy`` representations."""

    images: List[str] = []
    for key in ("obrazy", "obraz"):
        value = data.get(key)
        for candidate in _normalize_image_list(value):
            if candidate not in images:
                images.append(candidate)
    return images


def _apply_image_normalization(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure ``obrazy`` (list) and ``obraz`` (first item) fields are in sync."""

    images = _normalized_tool_images(data)
    data["obrazy"] = images
    data["obraz"] = images[0] if images else ""
    return data


def ensure_task_shape(task: Any) -> Dict[str, Any]:
    """Normalize *task* dictionary ensuring required keys exist and are typed correctly."""

    base_source = task if isinstance(task, dict) else {}
    base = dict(ensure_task_shape_helper(base_source))

    title = base.get("tytul") or base_source.get("title") or base_source.get("text") or ""
    base["tytul"] = str(title).strip()
    base["done"] = bool(base.get("done"))
    base["by"] = str(base_source.get("by") or base.get("by") or "")
    ts_done = (
        base_source.get("ts_done")
        or base_source.get("ts")
        or base_source.get("timestamp")
        or base.get("ts_done")
        or ""
    )
    base["ts_done"] = str(ts_done) if ts_done else ""

    assigned = (
        base_source.get("assigned_to")
        or base_source.get("assigned")
        or base_source.get("owner")
        or base_source.get("login")
        or base.get("assigned_to")
    )
    if assigned in ("", " ", None):
        base["assigned_to"] = None
    else:
        base["assigned_to"] = str(assigned).strip()

    assigned_ts = (
        base_source.get("assigned_ts")
        or base_source.get("ts_assigned")
        or base_source.get("assignedAt")
        or base.get("assigned_ts")
    )
    if assigned_ts:
        base["assigned_ts"] = str(assigned_ts)
    elif "assigned_ts" in base:
        base.pop("assigned_ts", None)

    if "date_added" in base_source or "date_added" in base:
        normalized_added = _normalize_date_value(
            base_source.get("date_added") or base.get("date_added")
        )
        if normalized_added:
            base["date_added"] = normalized_added
        else:
            base.pop("date_added", None)
    else:
        base.pop("date_added", None)

    if "date_done" in base_source or "date_done" in base:
        normalized_done = _normalize_date_value(
            base_source.get("date_done") or base.get("date_done")
        )
        if normalized_done:
            base["date_done"] = normalized_done
        else:
            base.pop("date_done", None)
    else:
        base.pop("date_done", None)

    if "status" in base_source or "status" in base:
        status_value = base_source.get("status") or base.get("status")
        status_clean = _clean_status(status_value, "")
        if status_clean:
            base["status"] = status_clean
        else:
            base.pop("status", None)
    else:
        base.pop("status", None)

    if "state" in base_source or "state" in base:
        state_raw = base_source.get("state") or base.get("state")
        state_clean = str(state_raw).strip().lower() if state_raw else ""
        if state_clean:
            base["state"] = state_clean
        else:
            base.pop("state", None)
    else:
        base.pop("state", None)

    source_value = None
    if isinstance(base_source, dict):
        source_value = base_source.get("source")
    if source_value is None:
        source_value = base.get("source")
    if source_value is not None:
        cleaned_source = str(source_value).strip()
        base["source"] = cleaned_source or "unknown"
    else:
        base["source"] = "unknown"

    archived_flag = base_source.get("archived")
    if archived_flag is None:
        archived_flag = base.get("archived")
    archived_bool = bool(archived_flag) or bool(base.get("done"))
    if archived_bool:
        base["archived"] = True
    elif "archived" in base:
        base.pop("archived", None)

    if "archived_at" in base_source or "archived_at" in base:
        normalized_archived = _normalize_date_value(
            base_source.get("archived_at") or base.get("archived_at")
        )
        if normalized_archived:
            base["archived_at"] = normalized_archived
        else:
            base.pop("archived_at", None)
    elif base.get("archived"):
        normalized_archived = _normalize_date_value(
            base.get("date_done") or base_source.get("date_done")
        )
        if normalized_archived:
            base["archived_at"] = normalized_archived
        else:
            base.pop("archived_at", None)
    else:
        base.pop("archived_at", None)

    return base


def _safe_tool_doc(path: str) -> Dict[str, Any]:
    """Safely load and normalize a tool JSON document."""

    raw = normalize_tools_doc(_safe_read_json(path, {}))
    data = dict(_as_tool_dict(raw))
    data["zadania"] = _norm_tasks(data.get("zadania"))
    return data


def _save_tool_doc(path: str, tool: Dict[str, Any]) -> None:
    """Persist a tool document ensuring normalized structure."""

    data = dict(tool) if isinstance(tool, dict) else {}
    data["zadania"] = _norm_tasks(data.get("zadania"))
    try:
        _safe_write_json(path, data)
    except Exception as exc:
        logger.exception("[Narzędzia] Nie udało się zapisać JSON narzędzia: %s", path)
        messagebox.showerror(
            "Zapis narzędzia",
            f"Nie udało się zapisać pliku narzędzia:\n{path}\n\nSzczegóły: {exc}",
        )
        raise

_TOOLS_CFG_CACHE: dict | None = None
_TOOLS_PRIMARY_PATH: str | None = None
_TOOLS_MIGRATED = False
_TOOLS_BRIDGE = ToolDataBridge()


def _init_tools_data(cfg: dict | None = None) -> tuple[dict, list[dict], str, bool]:
    """Initialise tools data paths, performing lightweight migration if needed."""

    global _TOOLS_CFG_CACHE, _TOOLS_PRIMARY_PATH, _TOOLS_MIGRATED

    if cfg is None:
        try:
            cfg = get_config()
        except Exception:
            cfg = {}
    if cfg is None:
        cfg = {}

    _TOOLS_CFG_CACHE = cfg

    if not _TOOLS_MIGRATED:
        try:
            moved = migrate_tools_scattered_to_root(cfg)
            if moved:
                tools_root = resolve_rel(cfg, "tools.dir") or "<root>"
                logger.info(
                    "[TOOLS] Migrowano pliki narzędzi: %d → %s", moved, tools_root
                )
        except Exception:
            pass
        _TOOLS_MIGRATED = True

    rows_raw, primary = load_tools_rows_with_fallback(cfg, resolve_rel)
    try:
        from gui_panel import wm_set_module_source
        wm_set_module_source(root, "Narzędzia", primary)
    except Exception:
        pass
    had_rows = bool(rows_raw)
    rows = ensure_tools_sample_if_empty(rows_raw, primary)
    _TOOLS_PRIMARY_PATH = primary
    return cfg, rows, primary, had_rows

# ===================== STAŁE / USTALENIA (domyślne) =====================
CONFIG_PATH = cfg_path("config.json")
DEFAULT_CONFIG_PATH = CONFIG_PATH
STATUSY_NOWE_DEFAULT  = ["projekt", "w budowie", "próby narzędzia", "odbiór", "sprawne"]
STATUSY_STARE_DEFAULT = ["sprawne", "do ostrzenia", "w ostrzeniu", "po ostrzeniu", "w naprawie", "uszkodzone", "wycofane"]

_CFG_CACHE: dict | None = None
CONFIG_MTIME: float | None = None
_CFG_CACHE_PATH: str | None = None

TASK_TEMPLATES_DEFAULT = [
    "zadanie testowe",
    "zadanie testowe1",
    "zadanie testowe2",
    "zadanie testowe3",
    "zadanie testowe4",
    "zadanie testowe5",
    "zadanie testowe6",
    "zadanie testowe7",
    "zadanie testowe8",
    "zadanie testowe9",
]
STARE_CONVERT_TEMPLATES_DEFAULT = [
    "zadanie testowe",
    "zadanie testowe1",
    "zadanie testowe2",
    "zadanie testowe3",
    "zadanie testowe4",
    "zadanie testowe5",
    "zadanie testowe6",
    "zadanie testowe7",
    "zadanie testowe8",
    "zadanie testowe9",
]

TYPY_NARZEDZI_DEFAULT = ["Tłoczące", "Wykrawające", "Postępowe", "Giętarka"]

# Statusy NN uznawane za fazę "produkcja" (lower)
NN_PROD_STATES = {
    "projekt","w budowie","1 próba","1 proba","2 próba","2 proba","próby narzędzia","proby narzedzia","odbiór","odbior"
}

# Obsługa załączników do narzędzi
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".dxf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _open_tools_panel():
    """
    Otwiera panel 'Narzędzia' ZAWSZE.
    Gdy plik pusty/niepoprawny – pokazuje pustą listę i informację,
    bez crashy i bez file-dialogów.
    """

    try:
        from start import CONFIG_MANAGER  # type: ignore

        cfg_candidate = CONFIG_MANAGER.load() if hasattr(CONFIG_MANAGER, "load") else {}
    except Exception:
        cfg_candidate = {}

    if not cfg_candidate:
        try:
            cfg_candidate = get_config()
        except Exception:
            logger.exception(
                "[Narzędzia] Nie udało się uzyskać konfiguracji przez get_config()."
            )
            cfg_candidate = {}

    cfg, rows, primary_path, had_rows = _init_tools_data(cfg_candidate)

    win = open_tools_window(rows, had_rows=had_rows, path=primary_path, cfg=cfg_candidate)
    logger.info("[Narzędzia] Panel otwarty; rekordów: %d; plik=%s", len(rows), primary_path)
    return win



# Współdzielony stan panelu przechowywany w ``narzedzia_ui.STATE``


def _resolve_path_candidate(path: str | None, default: str) -> str:
    """Return an absolute filesystem path for *path* with *default* fallback."""

    candidate = str(path or "").strip()
    if not candidate:
        candidate = default
    if not os.path.isabs(candidate):
        try:
            candidate = cfg_path(candidate)
        except Exception:
            candidate = default
    return candidate


def _default_tools_tasks_file() -> str:
    """Return the default path to ``zadania_narzedzia.json`` using settings."""

    default = ""
    cfg_mgr = None
    try:
        cfg_mgr = ConfigManager()
        default = str(p_tools_defs(cfg_mgr))
    except Exception:
        default = str(Path("zadania_narzedzia.json").resolve())
    candidate = get_path("tools.definitions_path", default)
    return _resolve_path_candidate(candidate, default)


def _profiles_usernames(cmb_user=None) -> list[str]:
    """Return list of all usernames from profiles.

    If ``cmb_user`` is provided, it will have its ``values`` configured with the
    retrieved usernames.  This mirrors the behaviour of the legacy variant
    which updated the combobox in-place.
    """
    try:
        default = getattr(profile_utils, "_DEFAULT_USERS_FILE", profile_utils.USERS_FILE)
        profile_utils.USERS_FILE = default
        users = profile_utils.read_users()
        profile_utils.USERS_FILE = default
        logins = [u.get("login", "") for u in users]
    except Exception:
        logins = []
    if cmb_user is not None:
        try:
            cmb_user.config(values=logins)
        except Exception:
            pass
    return logins


def _tools_editor_user_choices() -> list[str]:
    """Collect display names of users for the tools editor combobox."""

    seen: set[str] = set()
    users: list[str] = []

    def add(value: str) -> None:
        value = (value or "").strip()
        if not value:
            return
        lower = value.lower()
        if lower in seen:
            return
        seen.add(lower)
        users.append(value)

    # 1) services.profile_service.get_all_users
    try:
        from services.profile_service import get_all_users  # type: ignore

        for entry in get_all_users() or []:
            if isinstance(entry, dict):
                add(
                    entry.get("display_name")
                    or entry.get("name")
                    or entry.get("login")
                    or ""
                )
            elif isinstance(entry, str):
                add(entry)
    except Exception:
        pass

    # 2) profiles.json (prefer ścieżkę z konfiguracji, następnie fallbacki)
    profile_candidates: list[str] = []
    cfg_mgr = None
    try:
        cfg_mgr = ConfigManager()
    except Exception:
        cfg_mgr = None

    preferred_profiles = ""
    if cfg_mgr is not None:
        try:
            preferred_profiles = str(p_profiles(cfg_mgr))
            if preferred_profiles:
                profile_candidates.append(preferred_profiles)
        except Exception:
            preferred_profiles = ""
        configured_profiles = str(
            get_path("profiles.file", preferred_profiles)
        ).strip()
        if configured_profiles and configured_profiles not in profile_candidates:
            profile_candidates.append(configured_profiles)

    if not profile_candidates:
        fallback_profiles = str(Path("profiles.json").resolve())
        profile_candidates.append(fallback_profiles)

    for path in profile_candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    add(
                        value.get("display_name")
                        or value.get("name")
                        or value.get("login")
                        or key
                    )
                elif isinstance(value, str):
                    add(value)
                else:
                    add(str(key))
        elif isinstance(data, list):
            for value in data:
                if isinstance(value, dict):
                    add(
                        value.get("display_name")
                        or value.get("name")
                        or value.get("login")
                        or ""
                    )
                elif isinstance(value, str):
                    add(value)
                else:
                    add(str(value))

    # 3) uzytkownicy.json (prefer ścieżkę z konfiguracji + fallbacki)
    users_candidates: list[str] = []
    preferred_users = ""
    if cfg_mgr is not None:
        try:
            preferred_users = str(p_users(cfg_mgr))
            if preferred_users:
                users_candidates.append(preferred_users)
        except Exception:
            preferred_users = ""
        configured_users = str(
            get_path("profiles.users_file", preferred_users)
        ).strip()
        if configured_users and configured_users not in users_candidates:
            users_candidates.append(configured_users)

    if not users_candidates:
        fallback_users = str(Path("uzytkownicy.json").resolve())
        users_candidates.append(fallback_users)

    for path_users in users_candidates:
        if not os.path.exists(path_users):
            continue
        try:
            with open(path_users, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue

        if isinstance(data, list):
            for value in data:
                if isinstance(value, dict):
                    add(
                        value.get("name")
                        or value.get("login")
                        or value.get("id")
                        or ""
                    )
                else:
                    add(str(value))
            break
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    add(
                        value.get("name")
                        or value.get("login")
                        or value.get("id")
                        or key
                    )
                else:
                    add(str(key))
            break

    # 4) Legacy fallback – ensure previous behaviour still works
    if not users:
        for login in _profiles_usernames():
            add(login)

    excluded = {"NN", "SN"}
    filtered = [
        value
        for value in users
        if (value or "").strip() and (value or "").strip().upper() not in excluded
    ]
    return sorted(filtered, key=str.lower)


def _current_user() -> tuple[str | None, str | None]:
    """Return current login and role as tuple."""
    return STATE.current_login, STATE.current_role


def _selected_task() -> tuple[str | None, str]:
    """Return ``(task_id, context)`` of selected assignment."""
    if STATE.assign_tree is None:
        return None, ""
    try:
        sel = STATE.assign_tree.focus()
    except Exception:
        return None, ""
    if not sel:
        return None, ""
    rec = STATE.assign_row_data.get(sel)
    if not rec:
        return None, ""
    return rec.get("task"), rec.get("context", "")


def _owner_login(owner) -> str | None:
    login = getattr(owner, "login", None)
    if login:
        return login
    active = getattr(owner, "active_profile", None)
    if callable(getattr(active, "get", None)):
        login = active.get("login")
    elif isinstance(active, dict):
        login = active.get("login")
    return login


def _filter_my(owner, tools: List[tuple[Path, Dict[str, Any]]]):
    login = _owner_login(owner)
    if not login:
        return tools
    out: List[tuple[Path, Dict[str, Any]]] = []
    for path, doc in tools:
        if doc.get("pracownik") == login:
            out.append((path, doc))
            continue
        for key, z in merge_tasks_with_status_templates(doc):
            if not is_pending_task_helper(z):
                continue
            task = ensure_task_shape(z)
            if task.get("assigned_to") == login:
                out.append((path, doc))
                break
    return out


class _TreeviewTooltip:
    """Minimal tooltip helper displaying text near the mouse pointer."""

    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self._tip: tk.Toplevel | None = None
        self._label: ttk.Label | None = None
        self._current_item: str | None = None
        self._current_text: str | None = None
        self._data: dict[str, str] = {}

    def update(self, mapping: dict[str, str]) -> None:
        self._data = dict(mapping)

    def _ensure_tip(self) -> None:
        if self._tip is not None and getattr(self._tip, "winfo_exists", lambda: False)():
            return
        self._tip = tk.Toplevel(self.tree)
        ensure_theme_applied(self._tip)
        self._tip.wm_overrideredirect(True)
        try:
            self._tip.withdraw()
        except Exception:
            pass
        self._label = ttk.Label(self._tip, text="", style="WM.Tooltip.TLabel", padding=(6, 3))
        self._label.pack()

    def show_for(self, item: str, text: str, x: int, y: int) -> None:
        if not text:
            self.hide()
            return
        self._ensure_tip()
        if self._tip is None or self._label is None:
            return
        if self._current_item == item and self._current_text == text:
            return
        self._current_item = item
        self._current_text = text
        self._label.configure(text=text)
        self._tip.geometry(f"+{x + 16}+{y + 16}")
        self._tip.deiconify()
        try:
            self._tip.lift()
        except Exception:
            pass

    def hide(self, destroy: bool = False) -> None:
        if self._tip is not None:
            try:
                self._tip.withdraw()
            except Exception:
                pass
            if destroy:
                try:
                    self._tip.destroy()
                except Exception:
                    pass
                self._tip = None
                self._label = None
        self._current_item = None
        self._current_text = None

    def on_motion(self, event: tk.Event) -> None:
        column = self.tree.identify_column(event.x)
        if column != "#3":
            self.hide()
            return
        item = self.tree.identify_row(event.y)
        if not item:
            self.hide()
            return
        text = self._data.get(item, "")
        if not text:
            self.hide()
            return
        self.show_for(item, text, event.x_root, event.y_root)

    def on_leave(self, _event: tk.Event | None = None) -> None:
        self.hide()

    def on_destroy(self, _event: tk.Event | None = None) -> None:
        self.hide(destroy=True)
        if STATE.tasks_tooltip_helper is self:
            STATE.tasks_tooltip_helper = None


def _ensure_tasks_tooltip(tree: ttk.Treeview | None) -> None:
    if tree is None:
        return
    helper = STATE.tasks_tooltip_helper
    if helper is None or getattr(helper, "tree", None) is not tree:
        helper = _TreeviewTooltip(tree)
        STATE.tasks_tooltip_helper = helper
        for event, handler in (
            ("<Motion>", helper.on_motion),
            ("<Leave>", helper.on_leave),
            ("<Destroy>", helper.on_destroy),
        ):
            try:
                tree.bind(event, handler, add="+")
            except TypeError:
                tree.bind(event, handler)
    helper.update(STATE.tasks_tooltips)


class TasksBatchLoader:
    def __init__(
        self,
        tree: ttk.Treeview,
        entries: list[tuple[Path, Dict[str, Any]]],
        *,
        batch_size: int = 5,
        delay: int = 200,
        status_label: tk.Label | None = None,
        show_history: bool = False,
        archived_only: bool = False,
        assign_overrides: dict[str, str] | None = None,
        mine_only: bool = False,
        current_login_norm: str | None = None,
        highlight_checker=None,
    ) -> None:
        self.tree = tree
        self.entries = list(entries)
        self.batch_size = batch_size
        self.delay = delay
        self.status_label = status_label
        self.show_history = show_history
        self.archived_only = archived_only
        self.assign_overrides = assign_overrides or {}
        self.mine_only = mine_only
        self.current_login_norm = current_login_norm
        self.highlight_checker = highlight_checker
        self._job: str | None = None
        self._processed_entries = 0
        self._first_highlight: str | None = None

    def start(self) -> None:
        self._load_batch()

    def _load_batch(self) -> None:
        rows: list[dict[str, Any]] = []
        chunk_size = min(self.batch_size, len(self.entries))
        for _ in range(chunk_size):
            path, doc = self.entries.pop(0)
            if not isinstance(doc, dict):
                try:
                    doc = _safe_read_json(str(path), default={})
                except Exception:
                    doc = {}
            doc = dict(doc or {})
            doc["zadania"] = _norm_tasks(doc.get("zadania"))
            nr_val = str(
                doc.get("nr")
                or doc.get("numer")
                or doc.get("id")
                or path.stem
                or ""
            ).strip()
            if not nr_val:
                nr_val = path.stem
            STATE.tasks_docs_cache[path] = doc
            for key, task in merge_tasks_with_status_templates(doc):
                shaped = ensure_task_shape(task)
                title_raw = shaped.get("tytul") or shaped.get("title") or ""
                title = str(title_raw).strip()
                assigned_raw = shaped.get("assigned_to")
                assigned = "" if assigned_raw in (None, "") else str(assigned_raw).strip()
                override_assigned = _lookup_assignment(
                    self.assign_overrides, nr_val, key
                )
                effective_assigned = override_assigned or assigned
                if self.mine_only and self.current_login_norm:
                    if (effective_assigned or "").strip().lower() != self.current_login_norm:
                        continue
                assigned = effective_assigned
                src = shaped.get("source") or ("own" if isinstance(key, int) else "status")
                display_src = "status" if src == "status" else "własne"
                status_field = (
                    (shaped.get("state") or shaped.get("status") or "")
                    .strip()
                    .lower()
                )
                archived = bool(shaped.get("archived")) or bool(shaped.get("done"))
                if not archived and status_field in {"done", "zrobione"}:
                    archived = True
                pending = is_pending_task_helper(shaped)
                if self.archived_only:
                    if not archived:
                        continue
                elif not self.show_history and archived:
                    continue
                if not archived and not pending:
                    continue
                date_info = _task_dates_summary(shaped)
                sort_value = date_info.get("sort_token") or (
                    date_info.get("display", "").lower()
                    if date_info.get("has_date")
                    else ""
                )
                tooltip_text = ""
                added_txt = date_info.get("added") or ""
                done_txt = date_info.get("done") or ""
                if added_txt:
                    tooltip_text = f"Dodano: {added_txt}"
                    if archived and done_txt:
                        tooltip_text += f" • Zakończono: {done_txt}"
                task_id = _task_identifier(nr_val, key)
                rows.append(
                    {
                        "nr": nr_val,
                        "title": title,
                        "title_sort": title.lower(),
                        "path": path,
                        "key": key,
                        "values": (
                            nr_val,
                            title,
                            date_info.get("display", ""),
                            display_src,
                            assigned,
                        ),
                        "assigned": assigned,
                        "archived": archived,
                        "date_has": bool(date_info.get("has_date")),
                        "date_sort": sort_value,
                        "tooltip": tooltip_text,
                        "task_id": task_id,
                    }
                )

        rows.sort(
            key=lambda item: (
                0 if not item.get("archived") else 1,
                0 if item.get("date_has") else 1,
                item.get("date_sort") or "",
                item["nr"],
                item["title_sort"],
            )
        )

        highlight_tag = "selected_tool"
        for row in rows:
            tags_list = []
            if callable(self.highlight_checker) and self.highlight_checker(
                row["nr"], row["path"]
            ):
                tags_list.append(highlight_tag)
            if not row.get("assigned"):
                tags_list.append("unassigned")
            if row.get("archived"):
                tags_list.append("arch")
            iid = self.tree.insert("", "end", values=row["values"], tags=tuple(tags_list))
            STATE.tasks_rows_meta[iid] = {
                "path": row["path"],
                "key": row["key"],
                "nr": row["nr"],
                "archived": row.get("archived", False),
                "task_id": row.get("task_id"),
            }
            tooltip_text = row.get("tooltip") or ""
            if tooltip_text:
                STATE.tasks_tooltips[iid] = tooltip_text
            if highlight_tag in tags_list and self._first_highlight is None:
                self._first_highlight = iid

        if self._first_highlight:
            try:
                self.tree.selection_set(self._first_highlight)
                self.tree.focus(self._first_highlight)
                self.tree.see(self._first_highlight)
            except Exception:
                pass

        self._processed_entries += chunk_size
        if self.status_label is not None:
            try:
                total = self._processed_entries + len(self.entries)
                self.status_label.config(
                    text=f"Załadowano: {self._processed_entries}/{total}"
                )
            except Exception:
                pass

        if self.entries:
            self._job = self.tree.after(self.delay, self._load_batch)

    def cancel(self) -> None:
        if self._job:
            try:
                self.tree.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


TASKS_LOADER: TasksBatchLoader | None = None


def _refresh_tasks(tree: ttk.Treeview | None, status_label: tk.Label | None = None) -> None:
    """Populate the task list with pending tasks batchowo."""

    global TASKS_LOADER

    if tree is None:
        return

    if TASKS_LOADER is not None:
        TASKS_LOADER.cancel()

    tree.delete(*tree.get_children())
    STATE.tasks_rows_meta.clear()
    STATE.tasks_docs_cache.clear()
    STATE.tasks_tooltips.clear()

    selected_nr = (STATE.tasks_selected_nr or "").strip()
    selected_path = STATE.tasks_selected_path

    entries: list[tuple[Path, Dict[str, Any]]] = []
    try:
        entries = [
            (Path(path), dict(doc))
            for path, doc in iter_tools_json()
            if isinstance(doc, dict)
        ]
    except Exception:
        entries = []

    if not entries:
        base_dir = Path(_resolve_tools_dir() or "")
        for raw in _load_all_tools():
            if not isinstance(raw, dict):
                continue
            nr_raw = str(
                raw.get("nr")
                or raw.get("numer")
                or raw.get("id")
                or ""
            ).strip()
            fake_path = base_dir / f"{nr_raw}.json" if nr_raw else base_dir / "narzedzie.json"
            entries.append((fake_path, dict(raw)))

    def _should_highlight(nr: str, path: Path) -> bool:
        if selected_nr and nr == selected_nr:
            return True
        if selected_path is None:
            return False
        try:
            return path.resolve() == selected_path.resolve()
        except Exception:
            return str(path) == str(selected_path)

    raw_history = False
    if STATE.tasks_history_var is not None:
        try:
            raw_history = STATE.tasks_history_var.get()
        except Exception:
            raw_history = False
    archived_only = _is_archived_view()
    show_history = _var_to_bool(raw_history)
    if archived_only:
        show_history = True

    try:
        raw_assignments = load_assign_tools()
    except Exception:
        raw_assignments = {}
    assign_overrides = {
        str(key): str(value)
        for key, value in (raw_assignments or {}).items()
        if key is not None
    }

    mine_only = False
    current_login_norm: str | None = None
    if STATE.var_filter_mine is not None:
        try:
            mine_only = bool(STATE.var_filter_mine.get())
        except Exception:
            mine_only = False
    if mine_only:
        login, _role = _current_user()
        if login:
            current_login_norm = login.strip().lower()

    highlight_tag = "selected_tool"
    try:
        tree.tag_configure(
            highlight_tag,
            background=get_theme_color("selection_soft", fallback="#e9f2ff"),
        )
    except Exception:
        pass

    tree.tag_configure("unassigned", background="#2b2b2b", foreground="#a0a0a0")
    tree.tag_configure("arch", foreground="#9aa0a6")

    style_cls = getattr(ttk, "Style", None)
    if style_cls is not None:
        try:
            ensure_theme_applied(tree.winfo_toplevel())
        except Exception:
            pass
        style = style_cls()
        style_name = tree.cget("style") or "Treeview"
        style.configure(style_name, rowheight=20)

        for target in {style_name, "Treeview"}:
            style.map(
                target,
                background=[
                    ("selected", "#404040"),
                    ("active", "#404040"),
                ],
                foreground=[
                    ("selected", "#ffffff"),
                    ("active", "#ffffff"),
                ],
            )

        try:
            tree.update_idletasks()
        except Exception:
            pass

    loader = TasksBatchLoader(
        tree,
        entries,
        batch_size=5,
        delay=200,
        status_label=status_label,
        show_history=show_history,
        archived_only=archived_only,
        assign_overrides=assign_overrides,
        mine_only=mine_only,
        current_login_norm=current_login_norm,
        highlight_checker=_should_highlight,
    )
    TASKS_LOADER = loader
    loader.start()

    _ensure_tasks_tooltip(tree)


def _set_tasks_context(
    owner,
    tree: ttk.Treeview | None,
    path: Path | None,
    tool_doc: Dict[str, Any] | None,
    *,
    status_label: tk.Label | None = None,
    auto_refresh: bool = True,
):
    STATE.tasks_tree = tree
    STATE.tasks_owner = owner
    STATE.tasks_selected_path = path
    if isinstance(tool_doc, dict):
        nr_val = str(
            tool_doc.get("nr")
            or tool_doc.get("numer")
            or tool_doc.get("id")
            or ""
        ).strip()
        STATE.tasks_selected_nr = nr_val or (path.stem if path else None)
    else:
        STATE.tasks_selected_nr = (path.stem if isinstance(path, Path) else None)
    if auto_refresh:
        _refresh_tasks(tree, status_label=status_label)


def _selected_task_meta(tree: ttk.Treeview | None) -> Dict[str, Any] | None:
    if tree is None:
        return None
    try:
        iid = tree.selection()[0]
    except Exception:
        try:
            iid = tree.focus()
        except Exception:
            return None
        if not iid:
            return None
    return STATE.tasks_rows_meta.get(iid)


def _assign_login_to_task(tree: ttk.Treeview | None, login: str | None):
    if tree is None:
        return False
    meta = _selected_task_meta(tree)
    if not meta:
        return False
    if meta.get("archived") or _is_archived_view():
        return False
    path = meta.get("path")
    key = meta.get("key")
    if not isinstance(path, Path) or key is None:
        return False
    login_clean = str(login or "").strip()
    clear_assignment = login_clean == ""
    doc = STATE.tasks_docs_cache.get(path)
    if not isinstance(doc, dict):
        doc = _safe_tool_doc(str(path))
    else:
        doc = dict(doc)
    if not isinstance(doc, dict):
        return False
    doc["zadania"] = _norm_tasks(doc.get("zadania"))
    created = isinstance(key, tuple)
    assign_target = login_clean if not clear_assignment else ""
    ok, idx = assign_task_any(doc, key, assign_target)
    if not ok:
        return False
    tasks = doc.setdefault("zadania", []) if isinstance(doc, dict) else []
    if isinstance(idx, int) and 0 <= idx < len(tasks):
        if created:
            tasks[idx] = _prepare_new_task(dict(tasks[idx]))
        else:
            tasks[idx] = ensure_task_shape(tasks[idx])
        if clear_assignment:
            shaped = ensure_task_shape(tasks[idx])
            shaped["assigned_to"] = None
            shaped.pop("assigned_ts", None)
            tasks[idx] = shaped
    doc["zadania"] = tasks
    _ensure_folder()
    save_tool_json(path, doc)
    task_id = meta.get("task_id")
    nr_meta = str(meta.get("nr", "") or "").strip()
    if isinstance(idx, int):
        if not task_id:
            task_id = _task_identifier(nr_meta, idx)
        if task_id:
            try:
                save_assign_tool(task_id, None if clear_assignment else assign_target)
            except Exception:
                pass
    if created and isinstance(idx, int) and 0 <= idx < len(tasks):
        task_obj = ensure_task_shape(tasks[idx])
        _log_tool_history(
            str(path.stem),
            login,
            "task_added",
            task=task_obj.get("tytul") or task_obj.get("title"),
            ts=task_obj.get("date_added") or _now_iso(),
        )
    _refresh_tasks(tree)
    _refresh_assignments_view()
    return True


def _mark_done(owner, tree: ttk.Treeview | None):
    if tree is None:
        return
    meta = _selected_task_meta(tree)
    if not meta:
        return
    if meta.get("archived") or _is_archived_view():
        messagebox.showinfo("Zadania", "Zadania archiwalne są tylko do podglądu.")
        return
    path = meta.get("path")
    key = meta.get("key")
    if not isinstance(path, Path) or key is None:
        return
    login = _owner_login(owner) or ""
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    iso_now = _now_iso()
    doc = STATE.tasks_docs_cache.get(path)
    if not isinstance(doc, dict):
        doc = _safe_tool_doc(str(path))
    else:
        doc = dict(doc)
    if not isinstance(doc, dict):
        return
    doc["zadania"] = _norm_tasks(doc.get("zadania"))
    if isinstance(key, tuple):
        ok, idx = assign_task_any(doc, key, login)
        if not ok or idx is None:
            return
        key = idx
    tasks = doc.setdefault("zadania", [])
    if not isinstance(key, int) or key < 0 or key >= len(tasks):
        return
    task = ensure_task_shape(tasks[key])
    task["done"] = True
    if login:
        task["by"] = login
    task["ts_done"] = now_ts
    if not task.get("date_added"):
        task["date_added"] = iso_now
    task["date_done"] = _normalize_date_value(task.get("date_done")) or iso_now
    task["status"] = _clean_status(task.get("status"), "done")
    task["state"] = "done"
    task["archived"] = True
    archived_at = _normalize_date_value(task.get("archived_at")) or task.get("date_done")
    task["archived_at"] = archived_at or iso_now
    tasks[key] = task
    doc["zadania"] = tasks
    _ensure_folder()
    save_tool_json(path, doc)
    if task.get("assigned_to"):
        task_id = task.get("id")
        if task_id:
            profile_service.save_assign_tool(task_id, None)
    _log_tool_history(
        str(path.stem),
        login,
        "task_done",
        task=task.get("tytul") or task.get("title"),
        ts=task.get("date_done") or iso_now,
    )
    _refresh_tasks(tree)
    doc["postep"] = _compute_postep_from_tasks(doc)
    _update_main_tools_progress_for_path(path, doc)


def _assign_me(owner, tree: ttk.Treeview | None):
    login = _owner_login(owner)
    if not login:
        login = ProfileService.get_active_user()
    if not login:
        try:
            import getpass

            login = getpass.getuser()
        except Exception:
            login = ""
    login = (login or "").strip()
    if not login:
        messagebox.showerror(
            "Przypisanie", "Nie udało się ustalić aktualnego loginu użytkownika."
        )
        return
    meta = _selected_task_meta(tree) or {}
    if _is_archived_view() or meta.get("archived"):
        messagebox.showinfo("Przypisanie", "Nie można przypisywać zadań z archiwum.")
        return
    if not _assign_login_to_task(tree, login):
        messagebox.showwarning("Przypisanie", "Nie udało się przypisać zadania.")


def _assign_to_user(owner, tree: ttk.Treeview | None):
    user = simpledialog.askstring("Przypisz", "Podaj login użytkownika:")
    if user is None:
        return
    login = user.strip()
    if not login:
        messagebox.showwarning("Przypisanie", "Login nie może być pusty.")
        return
    meta = _selected_task_meta(tree) or {}
    if _is_archived_view() or meta.get("archived"):
        messagebox.showinfo("Przypisanie", "Nie można przypisywać zadań z archiwum.")
        return
    if not _assign_login_to_task(tree, login):
        messagebox.showwarning("Przypisanie", "Nie udało się przypisać zadania.")


def _refresh_assignments_view() -> None:
    """Refresh assignments list using ``zadania_assign_io``."""
    if STATE.assign_tree is None:
        return
    ctx = "narzedzia"
    data = zadania_assign_io.list_in_context(ctx)
    if STATE.var_filter_mine is not None and STATE.var_filter_mine.get():
        login, _ = _current_user()
        data = [d for d in data if d.get("user") == login]
    STATE.assign_tree.delete(*STATE.assign_tree.get_children())
    STATE.assign_row_data.clear()
    for rec in data:
        iid = STATE.assign_tree.insert("", "end", values=(rec.get("task"), rec.get("user")))
        STATE.assign_row_data[iid] = rec


def _asgn_assign() -> bool:
    """Assign selected task to user from combobox."""
    login, role = _current_user()
    allowed_roles = profile_utils.ADMIN_ROLE_NAMES | {"brygadzista"}
    if (role or "").lower() not in allowed_roles:
        return False
    task_id, ctx = _selected_task()
    if not task_id:
        return False
    user = STATE.cmb_user_var.get().strip() if STATE.cmb_user_var else ""
    if not user:
        return False
    zadania_assign_io.assign(task_id, user, ctx or "narzedzia")
    _refresh_assignments_view()
    return True

# ===================== CONFIG / DEBUG =====================
def _load_config():
    global _CFG_CACHE, CONFIG_MTIME, _CFG_CACHE_PATH
    if _CFG_CACHE_PATH != CONFIG_PATH:
        _CFG_CACHE = None
        CONFIG_MTIME = None
        _CFG_CACHE_PATH = CONFIG_PATH
    if not os.path.exists(CONFIG_PATH):
        _CFG_CACHE = {}
        CONFIG_MTIME = None
        return {}
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if _CFG_CACHE is not None and CONFIG_MTIME == mtime:
            return _CFG_CACHE
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = "\n".join(
                line for line in f if not line.lstrip().startswith("#")
            )
            _CFG_CACHE = json.loads(content) if content.strip() else {}
        CONFIG_MTIME = mtime
        _CFG_CACHE_PATH = CONFIG_PATH
        return _CFG_CACHE
    except (OSError, json.JSONDecodeError) as e:
        logger.log_akcja(f"Błąd wczytywania {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd wczytywania {CONFIG_PATH}: {e}")
        return _CFG_CACHE or {}

def _save_config(cfg: dict) -> bool:
    global _CFG_CACHE, CONFIG_MTIME, _CFG_CACHE_PATH
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        _CFG_CACHE = cfg
        try:
            CONFIG_MTIME = os.path.getmtime(CONFIG_PATH)
        except (OSError, AttributeError):
            CONFIG_MTIME = None
        _CFG_CACHE_PATH = CONFIG_PATH
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.log_akcja(f"Błąd zapisu {CONFIG_PATH}: {e}")
        error_dialogs.show_error_dialog("Config", f"Błąd zapisu {CONFIG_PATH}: {e}")
        return False

DEBUG = bool(os.environ.get("WM_DEBUG") or _load_config().get("tryb_testowy"))

def _dbg(*args):
    if DEBUG:
        LOG.debug("[narzedzia] %s", " ".join(str(a) for a in args))

_MISSING_CONFIGURATION_NOTIFIED: set[str] = set()


try:  # pragma: no cover - repozytorium zadań może nie być dostępne w testach
    import tasks_repo  # type: ignore
except Exception:  # pragma: no cover - tolerancja środowiska
    tasks_repo = None  # type: ignore


def _notify_missing_configuration(category: str, message: str) -> None:
    """Show one-time warning for missing configuration pieces."""

    key = category.strip().lower()
    if not key:
        key = message.strip().lower()
    if key in _MISSING_CONFIGURATION_NOTIFIED:
        return
    _MISSING_CONFIGURATION_NOTIFIED.add(key)
    try:
        messagebox.showwarning("Konfiguracja narzędzi", message)
    except Exception:
        _dbg("Brak konfiguracji:", message)


def _list_production_tasks() -> list:
    """Return production tasks from the repository if available."""

    if tasks_repo and hasattr(tasks_repo, "list_production_tasks"):
        try:
            return list(tasks_repo.list_production_tasks())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensywnie loguj
            _dbg("Błąd repozytorium zadań (produkcja):", exc)

    try:
        collections = LZ.get_collections() if LZ else []
    except Exception as exc:  # pragma: no cover - defensywnie loguj
        _dbg("Błąd pobierania kolekcji zadań:", exc)
        collections = []

    tasks: list = []
    for collection in collections:
        coll_id = str(collection.get("id") or collection.get("name") or "").strip()
        if not coll_id:
            continue
        try:
            types = LZ.get_tool_types(collection=coll_id) if LZ else []
        except Exception as exc:  # pragma: no cover - defensywnie loguj
            _dbg("Błąd pobierania typów zadań:", exc)
            continue
        for typ in types:
            type_id = typ.get("id") or typ.get("name")
            if not type_id:
                continue
            try:
                statuses = LZ.get_statuses(type_id, coll_id) if LZ else []
            except Exception as exc:  # pragma: no cover - defensywnie loguj
                _dbg("Błąd pobierania statusów zadań:", exc)
                continue
            for status in statuses:
                status_id = status.get("id") or status.get("name")
                if not status_id:
                    continue
                try:
                    tasks.extend(LZ.get_tasks(type_id, status_id, coll_id) if LZ else [])
                except Exception as exc:  # pragma: no cover - defensywnie loguj
                    _dbg("Błąd pobierania listy zadań:", exc)
    return tasks


def _maybe_seed_config_templates():
    """Check for missing tool templates/types and warn the user instead of seeding."""

    try:
        cfg = _load_config()
    except (OSError, json.JSONDecodeError, TypeError) as e:
        _dbg("Błąd odczytu config podczas sprawdzania braków:", e)
        return

    missing: list[str] = []
    zadania_dane = _list_production_tasks()
    if not zadania_dane:
        missing.append("zadania (produkcja)")
    else:
        _dbg("[WM-DBG][narzedzia] pomijam warning 'zadania (produkcja)' – dane istnieją")
    if not _clean_list(cfg.get("szablony_zadan_narzedzia_stare")):
        missing.append("zadania (serwis)")
    if not _clean_list(cfg.get("typy_narzedzi")):
        try:
            default_collection = getattr(LZ, "get_default_collection", lambda: "")()
        except Exception:
            default_collection = ""
        if not _type_names_for_collection(default_collection):
            missing.append("typy narzędzi")

    if missing:
        details = ", ".join(missing)
        _notify_missing_configuration(
            "config-missing",
            (
                "Brakuje ustawień dla: "
                f"{details}. Uzupełnij je w module Ustawienia → Narzędzia."
            ),
        )

def _clean_list(lst):
    out, seen = [], set()
    if isinstance(lst, list):
        for x in lst:
            s = str(x).strip()
            sl = s.lower()
            if s and sl not in seen:
                seen.add(sl); out.append(s)
    return out


def _load_tools_list_from_file(
    path_key: str,
    candidate_keys: Iterable[str] = (),
    *,
    dict_value_keys: Iterable[str] = ("name", "title", "label", "value", "id"),
) -> list[str]:
    """Load a list of strings from a JSON file resolved via :func:`get_path`."""

    path = get_path(path_key)
    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(
            "[WM-DBG][NARZ][STATUS] Błąd odczytu pliku listy narzędzi %s: %s",
            path,
            exc,
        )
        _dbg("Błąd odczytu pliku listy narzędzi:", path, exc)
        return []

    collected: list[str] = []

    def _append_from(value: object) -> None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                collected.append(stripped)
            return
        if isinstance(value, list):
            for item in value:
                _append_from(item)
            return
        if isinstance(value, dict):
            for key in dict_value_keys:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    collected.append(candidate.strip())
                    return
            for inner in value.values():
                _append_from(inner)

    if isinstance(data, dict):
        matched_specific = False
        for key in candidate_keys:
            if key is None:
                continue
            if key in data:
                matched_specific = True
                _append_from(data.get(key))
                if collected:
                    break
        if not collected and not matched_specific:
            for generic_key in ("values", "items", "list"):
                if generic_key in data:
                    _append_from(data.get(generic_key))
                    if collected:
                        break
        if not collected and not matched_specific:
            for value in data.values():
                _append_from(value)
    else:
        _append_from(data)

    return collected

def _task_templates_from_config():
    """
    Zwraca listę szablonów zadań. Preferuje config['tools']['task_templates'].
    Zgodność wsteczna: stare klucze w configu oraz domyślne stałe.
    """
    try:
        cfg_mgr = ConfigManager()
        templates = cfg_mgr.get("tools.task_templates", None)
        if isinstance(templates, list) and templates:
            clean = [str(x).strip() for x in templates if str(x).strip()]
            # usuwamy duplikaty z zachowaniem kolejności
            out, seen = [], set()
            for t in clean:
                tl = t.lower()
                if tl not in seen:
                    seen.add(tl)
                    out.append(t)
            return out
        # fallback: stary config + plik zewnętrzny
        cfg = _load_config()
        lst = _clean_list(cfg.get("szablony_zadan_narzedzia"))
        if lst:
            return lst
        file_templates = _clean_list(
            _load_tools_list_from_file(
                "tools.task_templates_file",
                ("NOWE", "nowe", "templates", "zadania", "tasks", "list"),
            )
        )
        return file_templates
    except Exception:
        return []

def _stare_convert_templates_from_config():
    """
    Zwraca alternatywne szablony (tryb 'stare').
    Preferuje tools.task_templates, a jeśli pusto – stary klucz lub stałą
    STARE_CONVERT_TEMPLATES_DEFAULT.
    """

    try:
        cfg_mgr = ConfigManager()
        templates = cfg_mgr.get("tools.task_templates", None)
        if isinstance(templates, list) and templates:
            clean = [str(x).strip() for x in templates if str(x).strip()]
            out, seen = [], set()
            for t in clean:
                tl = t.lower()
                if tl not in seen:
                    seen.add(tl)
                    out.append(t)
            return out
        cfg = _load_config()
        lst = _clean_list(cfg.get("szablony_zadan_narzedzia_stare"))
        if lst:
            return lst
        file_templates = _clean_list(
            _load_tools_list_from_file(
                "tools.task_templates_file",
                ("STARE", "stare", "templates", "zadania", "tasks", "list"),
            )
        )
        return file_templates
    except Exception:
        return []

def _types_from_config():
    """
    Zwraca listę typów narzędzi. Preferuje config['tools']['types'].
    Fallback: kolekcja domyślna/loader, następnie stare klucze, na końcu stała.
    """
    use_config_manager = CONFIG_PATH == DEFAULT_CONFIG_PATH

    # 1) nowe ustawienia (tylko gdy korzystamy z domyślnej ścieżki configu)
    if use_config_manager:
        try:
            cfg_mgr = ConfigManager()
            types = cfg_mgr.get("tools.types", None)
            if (
                isinstance(types, list)
                and types
                and not cfg_mgr.is_schema_default("tools.types")
            ):
                clean = [str(x).strip() for x in types if str(x).strip()]
                return clean
        except Exception:
            pass

    # 2) loader kolekcji (jeśli istnieje)
    if use_config_manager:
        try:
            cfg_mgr = ConfigManager()
            default_collection = cfg_mgr.get("tools.default_collection", "NN") or "NN"
        except Exception:
            default_collection = "NN"
    else:
        default_collection = "NN"
    names = _type_names_for_collection(str(default_collection).strip() or "NN")
    if names:
        return names
    # 3) plik typów narzędzi
    if use_config_manager:
        file_types = _clean_list(
            _load_tools_list_from_file(
                "tools.types_file",
                ("types", "typy", "list", "items"),
                dict_value_keys=("name", "title", "label", "value", "id"),
            )
        )
        if file_types:
            return file_types
    # 4) stare klucze w configu
    try:
        cfg = _load_config()
        lst = _clean_list(cfg.get("typy_narzedzi"))
        return lst
    except Exception:
        return []

def _append_type_to_config(new_type: str) -> bool:
    t = (new_type or "").strip()
    if not t:
        return False
    cfg = _load_config()
    cur = _clean_list(cfg.get("typy_narzedzi")) or []
    if t.lower() in [x.lower() for x in cur]:
        return False
    cur.append(t)
    cfg["typy_narzedzi"] = cur
    _save_config(cfg)
    _dbg("Dopisano typ do config:", t)
    return True


_TOOLS_DEFINITIONS_CACHE: dict[str, dict] = {}


def _definitions_path_for_collection(collection_id: str) -> str:
    """Resolve definitions path for given *collection_id*."""

    candidate: str | None = None
    try:
        cfg_mgr = ConfigManager()
        paths_cfg = cfg_mgr.get("tools.collections_paths", {}) or {}
        if isinstance(paths_cfg, dict):
            for key in (collection_id, collection_id.upper(), collection_id.lower()):
                value = paths_cfg.get(key)
                if value:
                    candidate = str(value)
                    break
        if not candidate:
            candidate = cfg_mgr.get("tools.definitions_path", None)
    except Exception:
        candidate = None

    default_path = _default_tools_tasks_file()
    fallback = getattr(LZ, "TOOL_TASKS_PATH", None)
    chosen = candidate or fallback
    return _resolve_path_candidate(chosen, default_path)


def _invalidate_tools_definitions_cache() -> None:
    """Clear cached tool definitions paths."""

    _TOOLS_DEFINITIONS_CACHE.clear()


def _load_tools_definitions(collection_id: str, *, force: bool = False) -> dict:
    """Load tools definitions for *collection_id* with caching."""

    path = _definitions_path_for_collection(collection_id)
    cache_key = f"{collection_id}|{path}"
    if force or cache_key not in _TOOLS_DEFINITIONS_CACHE:
        _TOOLS_DEFINITIONS_CACHE[cache_key] = load_config(path) or {}
    return _TOOLS_DEFINITIONS_CACHE[cache_key]


def _type_names_for_collection(collection_id: str, *, force: bool = False) -> list[str]:
    """Return distinct type names available for *collection_id*."""

    if not collection_id:
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    items = get_types(cfg_data, collection_id)
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item.get("name") or item.get("id") or "").strip()
        if not name:
            continue
        lower = name.lower()
        if lower in seen:
            continue
        seen.add(lower)
        result.append(name)
    return result


def _status_names_for_type(
    collection_id: str,
    type_name: str,
    *,
    force: bool = False,
) -> list[str]:
    """Return statuses defined for ``type_name`` in *collection_id*."""

    if not collection_id or not type_name:
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    definitions_path = _definitions_path_for_collection(collection_id)
    tool_type = find_type(cfg_data, collection_id, type_name)
    if not tool_type:
        logger.warning(
            "[WM-DBG][TOOL] Typ '%s' nie istnieje w kolekcji %s (plik: %s)",
            type_name,
            collection_id,
            definitions_path,
        )
        return []
    try:
        statuses = tool_type.get("statuses") or []
    except Exception as exc:
        logger.warning(
            "[WM-DBG][NARZ][STATUS] Błąd wczytywania statusów dla typu '%s' (kolekcja %s): %s",
            type_name,
            collection_id,
            exc,
        )
        return []
    cleaned: list[str] = []
    for status in statuses:
        if isinstance(status, dict):
            value = status.get("name") or status.get("id") or str(status)
        else:
            value = str(status)
        value = value.strip()
        if value:
            cleaned.append(value)
    if not cleaned:
        logger.info(
            "[WM-DBG][NARZ][STATUS] Brak statusów dla typu '%s' (plik: %s)",
            type_name,
            definitions_path,
        )
    return cleaned


def _task_names_for_status(
    collection_id: str,
    type_name: str,
    status_name: str,
    *,
    force: bool = False,
) -> list[str]:
    """Return tasks defined for ``status_name`` of ``type_name``."""

    if not (collection_id and type_name and status_name):
        return []
    cfg_data = _load_tools_definitions(collection_id, force=force)
    tasks = get_tasks_for_status(cfg_data, collection_id, type_name, status_name)
    return [
        str(task).strip()
        for task in tasks
        if str(task or "").strip()
    ]


def _is_allowed_file(path: str) -> bool:
    """Verify selected file extension and size."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    try:
        return os.path.getsize(path) <= MAX_FILE_SIZE
    except OSError:
        return False


def _delete_task_files(task: dict) -> None:
    """Remove media and thumbnail files referenced by *task*."""
    for key in ("media", "miniatura"):
        p = task.get(key)
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _remove_task(tasks: list, index: int) -> None:
    """Remove task at *index* and delete associated files."""
    try:
        task = tasks[index]
    except IndexError:
        return
    _delete_task_files(task)
    del tasks[index]

# ===== Zadania – pomocnicze funkcje =====


def _task_to_display(task):
    """Return listbox display text for *task*.

    Accepts both legacy string format ``"[ ] text"`` and dictionary
    representation with keys like ``text`` and ``done``.  The returned
    string always contains a prefix ``[x]`` or ``[ ]``.
    """

    if isinstance(task, str):
        return task
    text = task.get("text") or task.get("tytul") or ""
    prefix = "[x]" if task.get("done") else "[ ]"
    return f"{prefix} {text}".strip()


def _task_title(task: Dict[str, Any]) -> str:
    """Return normalised task title for messaging purposes."""

    title = (
        task.get("tytul")
        or task.get("text")
        or task.get("title")
        or ""
    )
    return str(title).strip() or "bez tytułu"


def _pending_tasks_before(tasks: Sequence[Dict[str, Any]], index: int) -> list[tuple[int, str]]:
    """Return ``(idx, title)`` for unfinished tasks before ``index``.

    The helper normalises entries with :func:`ensure_task_shape` to tolerate
    partially shaped task dictionaries.
    """

    if index <= 0:
        return []
    limit = min(len(tasks), max(index, 0))
    pending: list[tuple[int, str]] = []
    for pos in range(limit):
        task = ensure_task_shape(tasks[pos])
        try:
            tasks[pos] = task  # type: ignore[index]
        except Exception:
            pass
        if not task.get("done"):
            pending.append((pos, _task_title(task)))
    return pending


def _build_skip_note(
    current_title: str,
    skipped: Sequence[Tuple[int, str]],
    comment: str | None = None,
) -> str:
    """Compose a history message describing skipped tasks ordering."""

    safe_title = (current_title or "").strip() or "bez tytułu"
    if skipped:
        skipped_text = ", ".join(f"{idx + 1}. {title}" for idx, title in skipped)
        base = (
            f"Pominięto kolejność przy zadaniu '{safe_title}' "
            f"– wcześniejsze bez ✔: {skipped_text}"
        )
    else:
        base = f"Pominięto kolejność przy zadaniu '{safe_title}'"
    if comment:
        extra = comment.strip()
        if extra:
            base += f". Powód: {extra}"
    return base


def _update_global_tasks(state, comment, ts):
    """Mark all tasks on *state* as done and refresh the listbox.

    ``state`` is expected to provide ``global_tasks`` and ``tasks_listbox``
    attributes. Tasks may be strings or dictionaries.  They are updated
    in-place to dictionary form and the listbox is repopulated using
    :func:`_task_to_display`.
    """

    tasks = []
    for item in getattr(state, "global_tasks", []):
        if isinstance(item, str):
            text = item[3:].strip() if item.startswith("[") else item.strip()
            task = {"text": text}
        elif isinstance(item, dict):
            task = dict(item)
            if "text" not in task:
                task["text"] = task.get("tytul") or task.get("title") or ""
        else:
            continue
        task["done"] = True
        iso_now = _now_iso()
        task["state"] = "done"
        task["status"] = "Zrobione"
        task["done_at"] = ts
        if not task.get("date_added"):
            task["date_added"] = iso_now
        task["date_done"] = _normalize_date_value(task.get("date_done")) or iso_now
        task["comment"] = comment
        tasks.append(task)

    state.global_tasks[:] = tasks

    lb = getattr(state, "tasks_listbox", None)
    if lb is not None:
        try:
            lb.delete(0, "end")
            for t in state.global_tasks:
                lb.insert("end", _task_to_display(t))
        except Exception:
            pass


# ===== Uprawnienia z config =====
def _can_convert_nn_to_sn(rola: str | None) -> bool:
    """Sprawdza uprawnienie narzedzia.uprawnienia.zmiana_klasy: 'brygadzista' | 'brygadzista_serwisant'."""
    cfg = _load_config()
    setg = (((cfg.get("narzedzia") or {}).get("uprawnienia") or {}).get("zmiana_klasy") or "brygadzista").strip().lower()
    if setg == "brygadzista_serwisant":
        allowed = {"brygadzista", "serwisant"}
    else:
        allowed = {"brygadzista"}
    # zawsze przepuść „admin” jeśli używacie takiej roli
    if (rola or "").lower() in profile_utils.ADMIN_ROLE_NAMES:
        return True
    return (rola or "").lower() in allowed

# ===== Zadania per typ (wg specy) =====
def _tasks_for_type(typ: str, phase: str):
    """
    phase: 'produkcja' | 'serwis'
    Czyta z config['narzedzia']['typy'][typ][phase], z fallbackiem na płaskie listy.
    """
    cfg = _load_config()
    try:
        narz = cfg.get("narzedzia", {})
        typy = narz.get("typy", {})
        entry = typy.get(typ)
        if not entry:
            for k in typy.keys():
                if str(k).strip().lower() == str(typ).strip().lower():
                    entry = typy[k]
                    break
        if entry:
            out = _clean_list(entry.get(phase))
            if out:
                return out
    except (AttributeError, KeyError, TypeError) as e:
        _dbg("Błąd odczytu narzedzia.typy:", e)

    if phase == "produkcja":
        return _task_templates_from_config()
    else:
        return _stare_convert_templates_from_config()

# ===== Szablony z pliku zadania_narzedzia.json =====
class _TaskTemplateUI:
    """Helper object building comboboxes for collection/type/status and tasks."""

    def __init__(self, parent):
        self.parent = parent
        self._state = {"collection": "", "type": "", "status": ""}
        self._types: list[dict] = []
        self._statuses: list[dict] = []
        self._ui_updating = False
        self.tasks_state: list[dict] = []

        self.var_collection = tk.StringVar()
        self.var_type = tk.StringVar()
        self.var_status = tk.StringVar()

        Combobox = getattr(ttk, "Combobox", getattr(ttk, "Entry", lambda *a, **k: None))
        self.cb_collection = Combobox(parent, textvariable=self.var_collection, state="readonly", values=[])
        self.cb_type = Combobox(parent, textvariable=self.var_type, state="readonly", values=[])
        self.cb_status = Combobox(parent, textvariable=self.var_status, state="readonly", values=[])
        self.lst = tk.Listbox(parent, height=8)

        self.cb_collection.bind("<<ComboboxSelected>>", self._on_collection_selected)
        self.cb_type.bind("<<ComboboxSelected>>", self._on_type_selected)
        self.cb_status.bind("<<ComboboxSelected>>", self._on_status_selected)

        self.cb_collection.pack()
        self.cb_type.pack()
        self.cb_status.pack()
        self.lst.pack(fill="both", expand=True)

        self._render_collections_initial()

    # ===================== helpers =====================
    @contextmanager
    def _suspend_ui(self):
        prev = self._ui_updating
        self._ui_updating = True
        try:
            yield
        finally:
            self._ui_updating = prev

    def _log(self, *msg):  # pragma: no cover - debug helper
        try:
            print("[WM-DBG][NARZ]", *msg)
        except Exception:
            pass

    @staticmethod
    def _lookup_id_by_name(name: str, items: list[dict]) -> str:
        for it in items:
            if it.get("name") == name:
                return it.get("id", "")
        return ""

    def _get_collections(self):
        return LZ.get_collections()

    def _get_types(self, collection_id):
        return LZ.get_tool_types(collection=collection_id)

    def _get_statuses(self, type_id, collection_id):
        return LZ.get_statuses(type_id, collection=collection_id)

    def _get_tasks(self, type_id, status_id, collection_id):
        return LZ.get_tasks(type_id, status_id, collection=collection_id)

    def _set_info(self, msg: str) -> None:
        try:
            self.parent.statusbar.config(text=msg)  # type: ignore[attr-defined]
        except Exception:
            print(f"[WM-DBG][NARZ] {msg}")

    # ===================== renderers =====================
    def _render_collections_initial(self):
        try:
            collections = self._get_collections()
        except Exception as e:
            self._log("collections", e)
            collections = []
        with self._suspend_ui():
            names = [c.get("name", "") for c in collections]
            self.cb_collection.config(values=names)
            cid = self._state.get("collection") or LZ.get_default_collection()
            sel_name = next((c.get("name") for c in collections if c.get("id") == cid), "")
            if not sel_name and names:
                sel_name = names[0]
                cid = self._lookup_id_by_name(sel_name, collections)
            else:
                if not names:
                    cid = ""
            self.var_collection.set(sel_name)
            self._state["collection"] = cid or ""
        self._render_types()

    def _render_types(self):
        cid = self._state.get("collection")
        try:
            types = self._get_types(cid) if cid else []
        except Exception as e:
            self._log("types", e)
            types = []
        if types:
            self._set_info("")
        else:
            self._set_info("Brak typów narzędzi w ustawieniach.")
            if cid:
                _notify_missing_configuration(
                    "types",
                    (
                        "Brak zdefiniowanych typów narzędzi dla wybranej kolekcji. "
                        "Dodaj typy w module Ustawienia → Narzędzia."
                    ),
                )
        with self._suspend_ui():
            self._types = types
            names = [t.get("name", "") for t in types]
            self.cb_type.config(values=names)
            tid = self._state.get("type")
            sel_name = next((t.get("name") for t in types if t.get("id") == tid), "")
            if not sel_name and names:
                sel_name = names[0]
                tid = self._lookup_id_by_name(sel_name, types)
            else:
                if not names:
                    tid = ""
            self.var_type.set(sel_name)
            self._state["type"] = tid or ""
        self._render_statuses()

    def _render_statuses(self):
        cid = self._state.get("collection")
        tid = self._state.get("type")
        try:
            statuses = self._get_statuses(tid, cid) if tid else []
        except Exception as e:
            self._log("statuses", e)
            statuses = []
        if statuses:
            self._set_info("")
        else:
            if tid:
                self._set_info("Brak statusów w ustawieniach dla wybranego typu.")
                _notify_missing_configuration(
                    "statuses",
                    (
                        "Brak zdefiniowanych statusów dla wybranego typu. "
                        "Dodaj statusy w module Ustawienia → Narzędzia."
                    ),
                )
            else:
                self._set_info("")
        with self._suspend_ui():
            self._statuses = statuses
            names = [s.get("name", "") for s in statuses]
            self.cb_status.config(values=names)
            sid = self._state.get("status")
            sel_name = next((s.get("name") for s in statuses if s.get("id") == sid), "")
            if not sel_name and names:
                sel_name = names[0]
                sid = self._lookup_id_by_name(sel_name, statuses)
            else:
                if not names:
                    sid = ""
            self.var_status.set(sel_name)
            self._state["status"] = sid or ""
        self._render_tasks()

    def _render_tasks(self):
        cid = self._state.get("collection")
        tid = self._state.get("type")
        sid = self._state.get("status")
        try:
            tasks = self._get_tasks(tid, sid, cid) if (cid and tid and sid) else []
        except Exception as e:
            self._log("tasks", e)
            tasks = []
        with self._suspend_ui():
            self.lst.delete(0, tk.END)
            self.tasks_state.clear()
            if tasks:
                for t in tasks:
                    self.tasks_state.append({"text": t, "done": False})
                if LZ.should_autocheck(sid, cid):
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    iso_now = _now_iso()
                    user = getattr(self.parent, "login", None) or getattr(self.parent, "user", None)
                    for task in self.tasks_state:
                        task["done"] = True
                        task["done_at"] = ts
                        task["status"] = _clean_status(task.get("status"), "done")
                        if not task.get("date_added"):
                            task["date_added"] = iso_now
                        task["date_done"] = _normalize_date_value(task.get("date_done")) or iso_now
                        if user:
                            task["user"] = user
                for t in self.tasks_state:
                    prefix = "[x]" if t.get("done") else "[ ]"
                    self.lst.insert(tk.END, f"{prefix} {t['text']}")
                self._set_info("")
            else:
                if cid and tid and sid:
                    self._set_info("Brak zadań w ustawieniach dla wybranego statusu.")
                    _notify_missing_configuration(
                        "tasks",
                        (
                            "Brak zdefiniowanych zadań dla wybranego statusu. "
                            "Dodaj zadania w module Ustawienia → Narzędzia."
                        ),
                    )
                else:
                    self._set_info("")
                self.lst.insert(tk.END, "-- brak zadań --")
                try:
                    self.lst.itemconfig(0, state="disabled")
                except Exception:
                    pass

    # ===================== event handlers =====================
    def _on_collection_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_collection.get()
        self._state["collection"] = self._lookup_id_by_name(name, self._get_collections())
        self._state["type"] = ""
        self._state["status"] = ""
        self._render_types()

    def _on_type_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_type.get()
        self._state["type"] = self._lookup_id_by_name(name, self._types)
        self._state["status"] = ""
        self._render_statuses()

    def _on_status_selected(self, _=None):
        if self._ui_updating:
            return
        name = self.var_status.get()
        self._state["status"] = self._lookup_id_by_name(name, self._statuses)
        self._render_tasks()

    def _reload_from_lz(self) -> None:
        try:
            self._render_collections_initial()
        except Exception as e:  # pragma: no cover
            self._log("_reload_from_lz", e)
            self._set_info("Błąd odświeżania danych")

    def _odswiez_zadania(self) -> None:
        try:
            LZ.invalidate_cache()
            self._render_types()
            print("[WM-DBG][NARZ] Odświeżono zadania (invalidate_cache).")
        except Exception as e:  # pragma: no cover
            self._log("Odświeżanie zadań:", e)
            self._set_info("Błąd odświeżania zadań")


def build_task_template(parent):
    """Build simple comboboxes for collection/type/status and a tasks list."""

    LZ.invalidate_cache()
    ui = _TaskTemplateUI(parent)
    return {
        "cb_collection": ui.cb_collection,
        "cb_type": ui.cb_type,
        "cb_status": ui.cb_status,
        "listbox": ui.lst,
        "on_collection_change": ui._on_collection_selected,
        "on_type_change": ui._on_type_selected,
        "on_status_change": ui._on_status_selected,
        "on_collection_selected": ui._on_collection_selected,
        "on_type_selected": ui._on_type_selected,
        "on_status_selected": ui._on_status_selected,
        "tasks_state": ui.tasks_state,
        "odswiez_zadania": ui._odswiez_zadania,
        "reload_from_lz": ui._reload_from_lz,
        "set_info": ui._set_info,
    }

# ===================== ŚCIEŻKI DANYCH =====================
def _resolve_tools_dir():
    cfg, _, _, _ = _init_tools_data(_TOOLS_CFG_CACHE)
    return tools_dir(cfg)

def _ensure_folder():
    folder = _resolve_tools_dir()
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


def _generate_dxf_preview(dxf_path: str) -> str | None:
    """Spróbuj wygenerować miniaturę PNG dla pliku DXF.

    Zwraca ścieżkę do wygenerowanego pliku lub None w przypadku błędu.
    """
    try:  # pragma: no cover - zależne od opcjonalnych bibliotek
        import ezdxf
        from ezdxf.addons.drawing import matplotlib as ezdxf_matplotlib
        import matplotlib.pyplot as plt

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        fig = ezdxf_matplotlib.draw(msp)
        png_path = os.path.splitext(dxf_path)[0] + "_dxf.png"
        fig.savefig(png_path)
        plt.close(fig)
        try:
            from PIL import Image

            with Image.open(png_path) as img:
                img.thumbnail((600, 800))
                img.save(png_path)
        except OSError:  # pragma: no cover - Pillow best effort
            pass
        return png_path
    except (OSError, ImportError, ValueError, RuntimeError) as e:  # pragma: no cover - best effort
        _dbg("Błąd generowania miniatury DXF:", e)
        return None

# ===================== STATUSY / NORMALIZACJA =====================
def _statusy_for_mode(mode):
    """
    Zwraca listę statusów. Preferuje config['tools']['statuses'] (kolejność
    globalna). Fallback: definicje dla typu/trybu oraz stare klucze/stałe.
    Gwarantuje obecność 'sprawne' bez naruszania kolejności.
    """

    # 1) nowe ustawienia – globalna kolejność
    try:
        cfg_mgr = ConfigManager()
        statuses = cfg_mgr.get("tools.statuses", None)
        if isinstance(statuses, list) and statuses:
            ordered = [str(s).strip() for s in statuses if str(s).strip()]
        else:
            ordered = []
    except Exception:
        ordered = []

    if ordered:
        # dopnij 'sprawne' jeśli brak
        if "sprawne" not in [x.lower() for x in ordered]:
            ordered.append("sprawne")
        return ordered

    # 2) fallback: stare klucze/tryby + plik konfiguracyjny
    cfg = _load_config()
    if mode == "NOWE":
        statuses = _clean_list(cfg.get("statusy_narzedzi_nowe")) or _clean_list(
            cfg.get("statusy_narzedzi")
        )
        if not statuses:
            statuses = _clean_list(
                _load_tools_list_from_file(
                    "tools.statuses_file",
                    ("NOWE", "nowe", "statusy", "statuses", "list"),
                )
            )
        if not statuses:
            return []
    else:
        statuses = _clean_list(cfg.get("statusy_narzedzi_stare")) or _clean_list(
            cfg.get("statusy_narzedzi")
        )
        if not statuses:
            statuses = _clean_list(
                _load_tools_list_from_file(
                    "tools.statuses_file",
                    ("STARE", "stare", "statusy", "statuses", "list"),
                )
            )
        if not statuses:
            return []
    if "sprawne" not in [x.lower() for x in statuses]:
        statuses.append("sprawne")
    return statuses

def _normalize_status(s: str) -> str:
    sl = (s or "").strip().lower()
    if sl in ("na produkcji", "działające", "dzialajace"):
        return "sprawne"
    return (s or "").strip()

# ===================== I/O narzędzi =====================
def _existing_numbers():
    folder = _resolve_tools_dir()
    if not os.path.isdir(folder):
        return set()
    nums = set()
    for f in os.listdir(folder):
        if f.endswith(".json") and f[:-5].isdigit():
            nums.add(f[:-5].zfill(3))
    return nums

def _is_taken(nr3):
    return nr3.zfill(3) in _existing_numbers()

def _next_free_in_range(start, end):
    """Return the first free tool number within the provided bounds."""

    used = _existing_numbers()

    try:
        start_int = int(start)
    except (TypeError, ValueError):
        start_int = 1

    try:
        end_int = int(end)
    except (TypeError, ValueError):
        return None

    start_int = max(1, start_int)
    if end_int < start_int or end_int < 1:
        return None

    for i in range(start_int, end_int + 1):
        cand = f"{i:03d}"
        if cand not in used:
            return cand
    return None

def _legacy_parse_tasks(zadania_txt):
    out = []
    if not zadania_txt:
        return out
    for raw in [s.strip() for s in zadania_txt.replace("\n", ",").split(",") if s.strip()]:
        done = raw.startswith("[x]")
        title = raw[3:].strip() if done else raw
        out.append(
            {
                "tytul": title,
                "done": done,
                "by": "",
                "ts_done": "",
                "assigned_to": "",
            }
        )
    return out

def _read_tool(numer_3):
    folder = _resolve_tools_dir()
    p = os.path.join(folder, f"{numer_3}.json")
    if not os.path.exists(p):
        return None
    try:
        data = _safe_tool_doc(p)
        if not data:
            return None
        data["zadania"] = _norm_tasks(data.get("zadania"))
        data.setdefault("numer", str(numer_3).zfill(3))
        data.setdefault("obraz", "")
        data.setdefault("dxf", "")
        data.setdefault("dxf_png", "")
        return _apply_image_normalization(data)
    except Exception as e:
        _dbg("Błąd odczytu narzędzia", p, e)
        return None

def _save_tool(data):
    _ensure_folder()
    override_folder = _resolve_tools_dir()
    obj = dict(data)
    # FIX(TOOLS): normalizacja ID (nr/numer/id/path) -> brak 000 i duplikatów
    prev_id = str(obj.pop("__prev_id__", "") or "").strip()
    prev_path = obj.pop("__prev_path__", None)
    tid = str(
        obj.get("numer")
        or obj.get("nr")
        or obj.get("id")
        or obj.get("number")
        or ""
    ).strip()
    if not tid:
        for cand in ("__path__", "path", "file_path", "tool_path", "current_tool_path"):
            p = obj.get(cand)
            if p:
                try:
                    tid = Path(str(p)).stem
                except Exception:
                    tid = ""
                break
    if tid.isdigit() and len(tid) <= 3:
        tid = tid.zfill(3)
    if prev_id.isdigit() and len(prev_id) <= 3:
        prev_id = prev_id.zfill(3)
    if not tid:
        _dbg("Brak ID – pomijam zapis (blokada duplikatu).")
        return
    obj["numer"] = tid
    obj["nr"] = tid
    obj["id"] = tid
    obj.setdefault("obraz", "")
    obj.setdefault("dxf", "")
    obj.setdefault("dxf_png", "")
    obj = _apply_image_normalization(obj)
    obj["zadania"] = _norm_tasks(obj.get("zadania"))
    cfg, rows, primary, _ = _init_tools_data(_TOOLS_CFG_CACHE)
    path = save_tool_item(cfg, obj)
    final_path = path
    if path:
        _save_tool_doc(path, obj)
    if path and override_folder:
        override_path = os.path.join(override_folder, os.path.basename(path))
        try:
            same_target = os.path.abspath(override_path) == os.path.abspath(path)
        except OSError:
            same_target = False
        if not same_target:
            _save_tool_doc(override_path, obj)
            final_path = override_path
    if final_path:
        _dbg("Zapisano narzędzie:", final_path)

    if isinstance(rows, list):
        tid = str(obj.get("id") or obj.get("nr") or obj.get("numer") or "").strip()
        updated_rows = []
        replaced = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id") or row.get("numer") or row.get("nr") or "").strip()
            if rid and rid == tid:
                merged = dict(row)
                merged.update(obj)
                merged.setdefault("id", tid)
                updated_rows.append(merged)
                replaced = True
            else:
                updated_rows.append(row)
        # FIX(TOOLS): usuń stary wpis przy zmianie numeru
        if prev_id and prev_id != tid:
            updated_rows = [
                r for r in updated_rows
                if str(r.get("id") or r.get("nr") or r.get("numer") or "").strip() != prev_id
            ]
        if not replaced and tid:
            new_entry = dict(obj)
            new_entry.setdefault("id", tid)
            updated_rows.append(new_entry)
        save_tools_rows(primary, updated_rows)
        # FIX(TOOLS): usuń stary plik po renumeracji
        if prev_id and prev_id != tid:
            candidates = []
            if prev_path:
                candidates.append(str(prev_path))
            if override_folder:
                candidates.append(os.path.join(override_folder, f"{prev_id}.json"))
            for old in candidates:
                try:
                    if old and os.path.exists(old) and os.path.abspath(old) != os.path.abspath(path or ""):
                        os.remove(old)
                except Exception:
                    pass

def _iter_folder_items() -> Iterator[Dict[str, Any]]:
    """Yield normalized tool entries from the configured tools folder."""

    folder = _resolve_tools_dir()
    if not folder or not os.path.isdir(folder):
        _dbg("Folder narzędzi nie istnieje:", folder)
        return iter(())

    try:
        files = sorted(
            (
                os.path.join(folder, name)
                for name in os.listdir(folder)
                if name.lower().endswith(".json") and name.lower() != "narzedzia.json"
            ),
            key=lambda p: p.lower(),
        )
    except Exception:
        logger.exception("[NARZ] Nie można odczytać listy plików z %s", folder)
        return iter(())

    def _gen() -> Iterator[Dict[str, Any]]:
        for path in files:
            try:
                raw = _safe_tool_doc(path)
                if not raw:
                    continue

                doc: Dict[str, Any] = dict(raw)
                basename = os.path.splitext(os.path.basename(path))[0]
                doc.setdefault("id", basename)

                nr_raw = str(
                    doc.get("nr") or doc.get("numer") or doc.get("id") or basename
                ).strip()
                if nr_raw.isdigit() and len(nr_raw) <= 6:
                    doc["nr"] = nr_raw.zfill(3)
                else:
                    doc["nr"] = nr_raw or basename

                if not is_valid_tool_record(doc):
                    continue

                tasks = _norm_tasks(doc.get("zadania"))
                doc["zadania"] = tasks

                total = len(tasks)
                done = sum(1 for t in tasks if isinstance(t, dict) and t.get("done"))
                if total:
                    try:
                        progress = int(done * 100 / total)
                    except Exception:
                        progress = 0
                else:
                    try:
                        progress = int(doc.get("postep", 0))
                    except Exception:
                        progress = 0
                doc["postep"] = max(0, min(100, progress))

                doc.setdefault("nazwa", "")
                doc.setdefault("typ", "")
                doc.setdefault("status", "")
                doc["tryb"] = doc.get("tryb", "")

                interwencje = doc.get("interwencje")
                doc["interwencje"] = interwencje if isinstance(interwencje, list) else []

                historia = doc.get("historia")
                doc["historia"] = historia if isinstance(historia, list) else []

                doc["opis"] = doc.get("opis", "")
                doc["pracownik"] = doc.get("pracownik", "")
                doc = _apply_image_normalization(doc)
                doc["dxf"] = doc.get("dxf", "")
                doc["dxf_png"] = doc.get("dxf_png", "")
                doc["data"] = doc.get("data_dodania", doc.get("data", ""))
                doc["__path__"] = path

                yield doc
            except Exception:
                logger.exception("[NARZ] Błąd wczytywania %s", path)
                continue

    return list(_gen())

def _iter_legacy_json_items():
    cfg = _load_config()
    p_cfg_flat = (cfg.get("paths") or {}).get("narzedzia")
    if p_cfg_flat:
        LOG.debug("[WM-DBG][TOOLS] paths.narzedzia deprecated")
    base = (cfg.get("sciezka_danych") or "").strip()
    p_in_base = os.path.join(base, "narzedzia.json") if base else None
    p_cwd = "narzedzia.json"
    cands = []

    for p in [p_cfg_flat, p_in_base, p_cwd]:
        if p and os.path.isfile(p):
            cands.append(p)

    items = []
    if not cands:
        _dbg("Legacy narzedzia.json – brak kandydata do odczytu")
        return items

    picked = cands[0]
    _dbg("Wczytuję LEGACY z pliku:", picked)

    try:
        with open(picked, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _dbg("Błąd odczytu legacy:", picked, e)
        return items

    if isinstance(data, list):
        src_list = data
    elif isinstance(data, dict) and isinstance(data.get("narzedzia"), list):
        src_list = data["narzedzia"]
    elif isinstance(data, dict):
        src_list = []
        for k, v in data.items():
            if isinstance(v, dict):
                v2 = dict(v)
                v2.setdefault("numer", k)
                src_list.append(v2)
    else:
        _dbg("Legacy plik ma nieobsługiwany format")
        return items

    for d in src_list:
        try:
            tasks = _norm_tasks(d.get("zadania"))
            total = len(tasks)
            done = sum(1 for t in tasks if t.get("done"))
            postep = int(done * 100 / total) if total else 0
            images = _normalized_tool_images(d)
            entry = {
                "nr": str(d.get("numer", "") or d.get("nr", "")).zfill(3)
                if (d.get("numer") or d.get("nr"))
                else "",
                "nazwa": d.get("nazwa", ""),
                "typ": d.get("typ", ""),
                "status": d.get("status", ""),
                "data": d.get("data_dodania", d.get("data", "")),
                "zadania": tasks,
                "postep": postep,
                "tryb": d.get("tryb", ""),
                "interwencje": d.get("interwencje", []),
                "historia": d.get("historia", []),
                "opis": d.get("opis", ""),
                "pracownik": d.get("pracownik", ""),
                "obrazy": images,
                "obraz": images[0] if images else "",
                "dxf": d.get("dxf", ""),
                "dxf_png": d.get("dxf_png", ""),
            }
            if not is_valid_tool_record(entry):
                continue
            items.append(entry)
        except (KeyError, TypeError) as e:
            _dbg("Błąd parsowania pozycji legacy:", e)
    return items


def _normalize_tool_entry(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}

    raw_nr = data.get("nr") or data.get("numer") or data.get("id") or ""
    nr_str = str(raw_nr).strip()
    if nr_str.isdigit() and len(nr_str) <= 3:
        nr = nr_str.zfill(3)
    else:
        nr = nr_str

    candidate = dict(data)
    candidate["nr"] = nr
    if not is_valid_tool_record(candidate):
        return {}

    tasks = _norm_tasks(data.get("zadania"))

    total = len(tasks)
    done = sum(1 for t in tasks if isinstance(t, dict) and t.get("done"))
    if total:
        try:
            postep = int(done * 100 / total)
        except Exception:
            postep = 0
    else:
        try:
            postep = int(data.get("postep", 0))
        except Exception:
            postep = 0
    postep = max(0, min(100, postep))

    images = _normalized_tool_images(data)

    return {
        "nr": nr,
        "nazwa": data.get("nazwa", ""),
        "typ": data.get("typ", ""),
        "status": data.get("status", ""),
        "data": data.get("data_dodania", data.get("data", "")),
        "zadania": tasks,
        "postep": postep,
        "tryb": data.get("tryb", ""),
        "interwencje": data.get("interwencje", []),
        "historia": data.get("historia", []),
        "opis": data.get("opis", ""),
        "pracownik": data.get("pracownik", ""),
        "obrazy": images,
        "obraz": images[0] if images else "",
        "dxf": data.get("dxf", ""),
        "dxf_png": data.get("dxf_png", ""),
    }


def _load_tools_rows(path: str) -> list[dict]:
    """Safely read tools definitions tolerating list or dict payloads."""

    if not path:
        return []

    default_doc = {"items": [], "narzedzia": []}
    raw = _safe_read_json(path, default_doc)
    data = normalize_tools_index(raw)

    rows = data.get("items", [])
    if not isinstance(rows, list):
        rows = []

    return [row for row in rows if isinstance(row, dict)]


def _load_tools_rows_from_json() -> list[dict]:
    _, cached_rows, primary_path, _ = _init_tools_data(_TOOLS_CFG_CACHE)

    path = _TOOLS_PRIMARY_PATH or primary_path
    rows = _load_tools_rows(path) if path else []
    if not rows and isinstance(cached_rows, list):
        rows = [row for row in cached_rows if isinstance(row, dict)]

    items: list[dict] = []
    for row in rows:
        norm = _normalize_tool_entry(row)
        if norm:
            items.append(norm)
    return items


def _load_all_tools(force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    Ładuje wszystkie narzędzia.
    Jeśli force_reload=False i cache jest wypełniony – zwraca dane z cache.
    """
    if not force_reload and STATE.tools_docs_cache:
        return list(STATE.tools_docs_cache.values())

    _dbg("CWD:", os.getcwd())
    _init_tools_data(_TOOLS_CFG_CACHE)
    tools_dir = _resolve_tools_dir()
    _dbg("tools_dir:", tools_dir)

    items = list(_iter_folder_items())
    if items:
        _dbg("Załadowano z folderu:", len(items), "szt.")
        try:
            items.sort(key=lambda x: str(x.get("nr") or x.get("id") or "").zfill(6))
        except Exception:
            pass

        STATE.tools_docs_cache.clear()
        for item in items:
            path = item.get("__path__") or item.get("path")
            if path:
                STATE.tools_docs_cache[_normalize_path(path)] = item
        return items

    legacy = _iter_legacy_json_items()
    if legacy:
        _dbg("Załadowano LEGACY z narzedzia.json:", len(legacy), "szt.")
        legacy.sort(key=lambda x: x["nr"])
        return legacy

    rows = _load_tools_rows_from_json()
    if rows:
        _dbg("Załadowano R-06F z narzedzia/narzedzia.json:", len(rows), "szt.")
        rows.sort(key=lambda x: x.get("nr", ""))
        return rows

    _dbg("Brak narzędzi do wyświetlenia (folder i legacy puste).")
    return []


def migrate_tools_folder_once() -> None:
    """Normalize legacy list-based tool files to dict representation once."""

    folder = _resolve_tools_dir()
    if not folder or not os.path.isdir(folder):
        return

    for name in os.listdir(folder):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            raw = _safe_read_json(path, {})
            if isinstance(raw, list):
                data = _as_tool_dict(raw)
                data["zadania"] = _norm_tasks(data.get("zadania"))
                _safe_write_json(path, data)
                logger.info("[NARZ][MIGRACJA] Znormalizowano %s (list → dict)", path)
        except Exception:
            logger.exception("[NARZ][MIGRACJA] Błąd normalizacji %s", path)
            continue

# ===================== POSTĘP =====================
def _bar_text(percent):
    try:
        p = int(percent)
    except (TypeError, ValueError):
        p = 0
    p = max(0, min(100, p))
    filled = p // 10
    empty = 10 - filled
    return ("■" * filled) + ("□" * empty) + f"  {p}%"

def _band_tag(percent):
    try:
        p = int(percent)
    except (TypeError, ValueError):
        p = 0
    p = max(0, min(100, p))
    if p == 0: return "p0"
    if p <= 25: return "p25"
    if p <= 75: return "p75"
    return "p100"


def _update_main_tools_progress_for_path(path: Path, doc: dict | None = None) -> None:
    """
    Aktualizuje komórkę 'Postęp' w głównej tabeli narzędzi dla konkretnego pliku narzędzia,
    bez pełnego refresh_list().
    """
    tree = getattr(STATE, "tools_main_tree", None)
    row_data = getattr(STATE, "tools_main_row_data", None)
    if tree is None or row_data is None:
        return

    # znajdź iid po ścieżce
    target_iid = None
    try:
        for iid, meta in row_data.items():
            if not isinstance(meta, dict):
                continue
            mp = meta.get("path") or meta.get("__path__")
            try:
                # mp może być Path albo str
                mp_str = str(mp)
            except Exception:
                mp_str = ""
            if mp_str and str(path) == mp_str:
                target_iid = iid
                break
    except Exception:
        target_iid = None

    if not target_iid:
        return

    if not isinstance(doc, dict):
        try:
            doc = _safe_tool_doc(str(path))
        except Exception:
            doc = None
    if not isinstance(doc, dict):
        return

    postep = _compute_postep_from_tasks(doc)
    bar = _bar_text(postep)
    tag = _band_tag(postep)

    try:
        vals = list(tree.item(target_iid, "values"))
        # Twoja tabela ma kolumny: Nr, Nazwa, Typ, Status aktualny, Data, Postęp
        # czyli Postęp jest na index 5【turn4file12†L84-L98】.
        if len(vals) >= 6:
            vals[5] = bar
            tree.item(target_iid, values=tuple(vals), tags=(tag,))
    except Exception:
        pass

    # odśwież cache meta, jeśli jest trzymane
    try:
        meta = row_data.get(target_iid)
        if isinstance(meta, dict):
            meta["doc"] = doc
            meta["__doc__"] = doc
            meta["path"] = path
            meta["__path__"] = path
    except Exception:
        pass


def _compute_postep_from_tasks(tool_doc: dict) -> int:
    """
    Liczy postęp z zadań (done/total), jeżeli zadania istnieją.
    Pole 'postep' traktuje jako fallback tylko gdy brak zadań.

    Powód: w praktyce 'postep' w JSON potrafi się nie aktualizować przy odhaczaniu,
    więc ufanie mu powoduje "zamrożony" pasek postępu w tabeli.
    """
    tasks = tool_doc.get("zadania") or []
    if isinstance(tasks, list) and tasks:
        total = 0
        done = 0
        for t in tasks:
            if not isinstance(t, dict):
                continue
            total += 1
            if bool(t.get("done")):
                done += 1
        if total <= 0:
            return 0
        try:
            return int(round((done / total) * 100.0))
        except Exception:
            return 0

    # fallback: brak zadań -> ewentualnie użyj pola 'postep'
    try:
        p = int(tool_doc.get("postep", 0))
    except Exception:
        p = 0
    return max(0, min(100, p))


def _schedule_delayed_progress_recalc(
    root, tree, row_data, delay_ms: int = 5000, batch_size: int = 10, tick_ms: int = 50
):
    """
    root: widget z .after()
    tree: Treeview z listą narzędzi
    row_data: ta sama lista/dict meta co używasz do budowy wierszy (musi dawać path/doc)
             (w Twoim refresh_list budujesz 'rows' z kluczami 'path' i 'doc')
    """

    try:
        if getattr(STATE, "progress_after_id", None):
            root.after_cancel(STATE.progress_after_id)
    except Exception:
        pass

    STATE.progress_job_active = True

    def _iter_iids():
        try:
            return list(tree.get_children(""))
        except Exception:
            return []

    iids = _iter_iids()
    total = len(iids)
    idx_box = {"i": 0}
    t0 = time.perf_counter()

    def _tick():
        if not getattr(STATE, "progress_job_active", False):
            return

        i = idx_box["i"]
        end = min(i + batch_size, total)

        for k in range(i, end):
            iid = iids[k]
            meta = None
            try:
                meta = row_data.get(iid)
            except Exception:
                meta = None
            if not isinstance(meta, dict):
                continue

            path = meta.get("path")
            doc = meta.get("doc")

            if not isinstance(doc, dict):
                try:
                    if isinstance(path, Path):
                        p = path
                    else:
                        p = Path(str(path))
                    doc = _safe_tool_doc(str(p))
                except Exception:
                    doc = None

            if not isinstance(doc, dict):
                continue

            postep = _compute_postep_from_tasks(doc)
            bar = _bar_text(postep)
            tag = _band_tag(postep)

            try:
                vals = list(tree.item(iid, "values"))
                if len(vals) >= 6:
                    vals[5] = bar
                    tree.item(iid, values=tuple(vals), tags=(tag,))
            except Exception:
                pass

        idx_box["i"] = end

        if end < total:
            STATE.progress_after_id = root.after(tick_ms, _tick)
        else:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            perf(f"[WM-PERF][TOOLS] progress recalc done n={total} dt={dt_ms:.2f}ms")
            STATE.progress_after_id = None
            STATE.progress_job_active = False

    STATE.progress_after_id = root.after(int(delay_ms), _tick)


def _cancel_progress_recalc(root):
    STATE.progress_job_active = False
    try:
        if getattr(STATE, "progress_after_id", None):
            root.after_cancel(STATE.progress_after_id)
    except Exception:
        pass
    STATE.progress_after_id = None

# ===================== POMOCNICZE – faza pracy dla statusu =====================
def _phase_for_status(tool_mode: str, status_text: str) -> str | None:
    stl = (status_text or "").strip().lower()
    if tool_mode == "NOWE" and stl in NN_PROD_STATES:
        return "produkcja"
    if stl == "w serwisie":
        return "serwis"
    return None

# ===================== UI GŁÓWNY =====================
_OPEN_TOOL_EDITOR_BY_ID: Callable[[str], bool] | None = None


def open_tool_editor_by_id(
    master: tk.Misc | None,
    tool_id: str,
    current_user: str = "",
    current_role: str | None = None,
) -> bool:
    """Otwórz narzędzie przez edytor podpięty do głównej listy narzędzi."""
    del current_user, current_role

    print(f"[WM-DBG][DYSPO->NARZ] open_tool_editor_by_id tool_id={tool_id!r}")
    print(f"[WM-DBG][DYSPO->NARZ] opener callable={callable(_OPEN_TOOL_EDITOR_BY_ID)}")
    print(f"[WM-DBG][DYSPO->NARZ] master={master!r}")

    if _OPEN_TOOL_EDITOR_BY_ID is None:
        print("[WM-DBG][DYSPO->NARZ] Brak aktywnego callbacka edytora, tworzę moduł Narzędzia w Toplevel")
        try:
            win = tk.Toplevel(master) if master is not None else tk.Toplevel()
            win.title("Narzędzia")
            win.geometry("1400x850")
            win.resizable(True, True)
            try:
                apply_theme(win)
                ensure_theme_applied(win)
            except Exception:
                pass

            frame = ttk.Frame(win, style="WM.TFrame")
            frame.pack(fill="both", expand=True)

            panel_narzedzia(win, frame, login=None, rola=None)
            print(f"[WM-DBG][DYSPO->NARZ] panel_narzedzia zbudowany, opener callable={callable(_OPEN_TOOL_EDITOR_BY_ID)}")
            print(f"[WM-DBG][DYSPO->NARZ] planuję ponowne otwarcie tool_id={tool_id!r} za 300ms")
            win.after(
                300,
                lambda: open_tool_editor_by_id(win, tool_id),
            )
            return True
        except Exception as exc:
            raise RuntimeError(
                "Nie udało się automatycznie otworzyć modułu Narzędzia dla edycji narzędzia."
            ) from exc

    return _OPEN_TOOL_EDITOR_BY_ID(str(tool_id or "").strip())


def panel_narzedzia(root, frame, login=None, rola=None):
    try:
        from gui_panel import wm_set_module_source
        from utils_paths import tools_dir

        cfg = {}
        try:
            cfg = ConfigManager().load()
        except Exception:
            cfg = {}
        wm_set_module_source(root, "Narzędzia", tools_dir(cfg))
    except Exception:
        pass

    bridge = _TOOLS_BRIDGE
    STATE.current_login = login
    STATE.current_role = rola
    STATE.assign_tree = None
    STATE.assign_row_data.clear()
    STATE.cmb_user_var = None
    STATE.var_filter_mine = None
    STATE.tasks_history_var = None
    STATE.tasks_archived_var = None
    STATE.tasks_tree = None
    STATE.tasks_owner = None
    STATE.tasks_selected_path = None
    STATE.tasks_selected_nr = None
    STATE.tasks_rows_meta.clear()
    STATE.tasks_docs_cache.clear()
    STATE.tasks_tooltips.clear()
    STATE.tasks_tooltip_helper = None
    STATE.progress_after_id = None
    STATE.progress_job_active = False
    _load_config()
    _maybe_seed_config_templates()
    apply_theme(root)
    clear_frame(frame)

    _init_tools_data(_TOOLS_CFG_CACHE)

    header = ttk.Frame(frame, style="WM.TFrame")
    header.pack(fill="x", padx=10, pady=(10, 0))
    ttk.Label(header, text="🔧 Narzędzia", style="WM.H1.TLabel").pack(side="left")

    if open_dyspo_wizard is not None:
        target = root
        if hasattr(root, "winfo_toplevel"):
            try:
                target = root.winfo_toplevel()
            except Exception:
                target = root
        ttk.Button(
            header,
            text="Nowa dyspozycja…",
            command=lambda: _maybe_open_dyspo(
                target, {"module": "Narzędzia"}
            ),
        ).pack(side="right", padx=(0, 8))
        bind_ctrl_d(target, context={"module": "Narzędzia"})

    btn_add = ttk.Button(header, text="Dodaj", style="WM.Side.TButton")
    btn_add.pack(side="right", padx=(0, 8))

    tools_view: ToolsThreeTabsView | None = None

    def tools_provider() -> list[dict[str, Any]]:
        return _load_all_tools()

    def _normalize_tool_mode(value: str | None) -> str | None:
        normalized = (value or "").strip().upper()
        if normalized in {"NOWE", "NN"}:
            return "NOWE"
        if normalized in {"STARE", "SN"}:
            return "STARE"
        return None

    def _collection_for_tool(tool: Mapping[str, Any]) -> str:
        mode = _normalize_tool_mode(tool.get("tryb") or tool.get("mode"))
        if mode is None:
            inferred = infer_mode_from_id(
                tool.get("nr") or tool.get("numer") or tool.get("id") or 0
            )
            mode = "NOWE" if inferred == "NN" else "STARE"
        if mode == "NOWE":
            return "NN"
        fallback = "SN"
        try:
            cfg_mgr = ConfigManager()
            enabled = cfg_mgr.get("tools.collections_enabled", []) or []
            for candidate in ("SN", "ST"):
                if candidate in enabled:
                    fallback = candidate
                    break
        except Exception:
            pass
        result = str(fallback or "SN").strip()
        return result.upper() if result else "SN"

    def _resolve_statuses_for_tool(tool: Mapping[str, Any]) -> list[str]:
        type_name = str(
            tool.get("typ") or tool.get("typ_narzedzia") or tool.get("type") or ""
        ).strip()
        if not type_name:
            return []
        collection_id = _collection_for_tool(tool)
        return _status_names_for_type(collection_id, type_name)

    def _first_status_for_tool(tool: Mapping[str, Any]) -> str:
        statuses = _resolve_statuses_for_tool(tool)
        return statuses[0] if statuses else ""

    def _last_status_for_tool(tool: Mapping[str, Any]) -> str:
        statuses = _resolve_statuses_for_tool(tool)
        return statuses[-1] if statuses else ""

    def _resolve_actor_login() -> str:
        return str(STATE.current_login or "")

    def _refresh_tools_view() -> None:
        if tools_view is None:
            return
        try:
            tools_view._refresh_all()
        except Exception:
            pass

    def refresh_list(*_args: object, force_reload: bool = False) -> None:
        if force_reload or not STATE.tools_docs_cache:
            try:
                _load_all_tools(force_reload=True)
            except TypeError:
                _load_all_tools()
        _refresh_tools_view()

    def _refresh_progress(delay_ms: int = 5000) -> None:
        _refresh_tools_view()

    def _start_auto_progress_refresh(period_ms: int = 5000) -> None:
        _refresh_tools_view()

    def _refresh_one_tool_row_by_path(
        tool_path: Path | str | None, doc: dict | None = None
    ) -> bool:
        if tool_path is None:
            return False
        if isinstance(doc, dict):
            STATE.tools_docs_cache[_normalize_path(tool_path)] = deepcopy(doc)
        _refresh_tools_view()
        return True

    def _open_tool_by_id(tool_id: str) -> bool:
        if not tool_id:
            return False
        normalized = str(tool_id).strip()
        for tool in tools_provider():
            if not isinstance(tool, dict):
                continue
            candidate = str(
                tool.get("id") or tool.get("nr") or tool.get("numer") or ""
            ).strip()
            if not candidate:
                continue
            if candidate == normalized or candidate.zfill(3) == normalized.zfill(3):
                open_tool_dialog(_as_tool_dict(tool))
                return True
        try:
            file_name = f"{normalized.zfill(3)}.json"
            path_str = str(Path(_resolve_tools_dir()) / file_name)
            if not Path(path_str).exists():
                return False
            norm_path = _normalize_path(path_str)
            if norm_path in STATE.tools_docs_cache:
                doc = STATE.tools_docs_cache[norm_path]
            else:
                doc = _safe_tool_doc(path_str)
                if isinstance(doc, dict):
                    STATE.tools_docs_cache[norm_path] = doc
            if isinstance(doc, dict):
                open_tool_dialog(_as_tool_dict(doc))
                return True
        except Exception:
            return False
        return False

    global _OPEN_TOOL_EDITOR_BY_ID
    _OPEN_TOOL_EDITOR_BY_ID = _open_tool_by_id
    print("[WM-DBG][DYSPO->NARZ] zarejestrowano _OPEN_TOOL_EDITOR_BY_ID = _open_tool_by_id")

    class _ToolsViewFallback:
        def _refresh_all(self) -> None:
            return None

        def bind_open_detail(self, *_args: object, **_kwargs: object) -> None:
            return None

    tools_wrap = ttk.Frame(frame, style="WM.Card.TFrame")
    tools_wrap.pack(fill="both", expand=True, padx=10, pady=10)
    try:
        tools_view = ToolsThreeTabsView(
            tools_wrap,
            tools_provider=tools_provider,
            save_tool=_save_tool,
            status_first_resolver=_first_status_for_tool,
            status_last_resolver=_last_status_for_tool,
            actor_login_resolver=_resolve_actor_login,
        )
        tools_view.pack(fill="both", expand=True)
    except Exception:
        tools_view = _ToolsViewFallback()
        try:
            fallback_tree = ttk.Treeview(tools_wrap)
            fallback_tree.pack(fill="both", expand=True)

            def _fallback_open(_event=None) -> None:
                return None

            fallback_tree.bind("<Double-1>", _fallback_open)
            fallback_tree.bind("<Return>", _fallback_open)
            base_dir = Path(_resolve_tools_dir())
            for tool in tools_provider():
                if not isinstance(tool, dict):
                    continue
                hover_paths: list[str] = []
                rel = tool.get("dxf_png")
                if isinstance(rel, str):
                    hover_paths.append(str(base_dir / rel))
                for rel_img in _normalized_tool_images(tool):
                    if not isinstance(rel_img, str):
                        continue
                    path = str(base_dir / rel_img)
                    if path not in hover_paths:
                        hover_paths.append(path)
                if hover_paths:
                    ui_hover.bind_treeview_row_hover(
                        fallback_tree,
                        "fallback",
                        hover_paths,
                    )
        except Exception:
            pass

    _defs_watch_state: dict[str, object] = {"path": None, "mtime": None}

    def _resolve_definitions_path() -> str | None:
        candidate: str | None = None
        try:
            cfg_mgr = ConfigManager()
            candidate = cfg_mgr.get("tools.definitions_path", None)
        except Exception:
            candidate = None
        if not candidate:
            candidate = getattr(LZ, "TOOL_TASKS_PATH", None)
        resolved = _resolve_path_candidate(candidate, _default_tools_tasks_file())
        return resolved or None

    def _definitions_mtime(path: str | None) -> float | None:
        if not path:
            return None
        try:
            return os.path.getmtime(path)
        except (OSError, AttributeError):
            return None

    def _reload_definitions_from_disk(path: str | None) -> None:
        if not path:
            return

        if not any(
            _wm_widget_alive(widget)
            for widget in (root, frame, getattr(frame, "master", None), tools_view)
        ):
            return

        try:
            LZ.invalidate_cache()
        except Exception as exc:
            print("[ERROR][NARZ] błąd przeładowania definicji:", exc)
        _invalidate_tools_definitions_cache()
        print(
            f"[WM-DBG][NARZ] Definicje narzędzi przeładowane po zapisie w ustawieniach ({path})."
        )

        _refresh_tools_view()

    def _maybe_reload_definitions(_event=None, *, force: bool = False) -> bool:
        path = _resolve_definitions_path()
        mtime = _definitions_mtime(path)
        prev_path = _defs_watch_state.get("path")
        prev_mtime = _defs_watch_state.get("mtime")
        _defs_watch_state["path"] = path
        _defs_watch_state["mtime"] = mtime
        if not path:
            return False
        if not force and prev_path == path and prev_mtime == mtime:
            return False
        print(f"[WM-DBG][NARZ] Wykryto zmianę definicji ({path}) → przeładowuję.")
        _reload_definitions_from_disk(path)
        return True

    _defs_watch_state["path"] = _resolve_definitions_path()
    _defs_watch_state["mtime"] = _definitions_mtime(_defs_watch_state["path"])

    def _on_focus_back(_event=None):
        _maybe_reload_definitions()

    widgets_to_bind = {root, frame, getattr(frame, "master", None)}
    try:
        widgets_to_bind.add(frame.winfo_toplevel())
    except Exception:
        pass
    for widget in widgets_to_bind:
        if widget is None:
            continue
        try:
            widget.bind("<FocusIn>", _on_focus_back, add="+")
        except Exception:
            pass

    def _on_cfg_updated(_event=None):
        _maybe_seed_config_templates()
        changed = _maybe_reload_definitions(force=True)
        if not changed:
            refresh_list()

    root.bind("<<ConfigUpdated>>", _on_cfg_updated)

    # ===================== POPUP WYBORU TRYBU =====================
    def choose_mode_and_add():
        dlg = tk.Toplevel(root)
        dlg.title("Dodaj narzędzie – wybierz tryb")
        apply_theme(dlg)
        ensure_theme_applied(dlg)
        frm = ttk.Frame(dlg, padding=10, style="WM.Card.TFrame")
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Jakie narzędzie chcesz dodać?", style="WM.Card.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,6))
        var = tk.StringVar(master=dlg, value="NOWE")
        ttk.Radiobutton(frm, text="Nowe (001–499)", variable=var, value="NOWE").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(frm, text="Stare/produkcyjne (500–1000)", variable=var, value="STARE").grid(row=2, column=0, sticky="w")
        btns = ttk.Frame(frm, style="WM.TFrame")
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8,0))

        def _next(_event=None):
            dlg.destroy()
            open_tool_dialog(None, var.get())

        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0,8))
        ttk.Button(btns, text="Dalej", command=_next, style="WM.Side.TButton").pack(side="right")
        dlg.bind("<Return>", _next)

    # ===================== DIALOG DODAWANIA / EDYCJI =====================
    def open_tool_dialog(tool, mode=None):
        editing = tool is not None

        def _normalize_mode_label(value: str | None) -> str | None:
            val = (value or "").strip().upper()
            if val in {"NOWE", "NN"}:
                return "NOWE"
            if val in {"STARE", "SN"}:
                return "STARE"
            return None

        if editing:
            normalized = _normalize_mode_label(tool.get("tryb") or tool.get("mode"))
            if normalized is None:
                fallback = infer_mode_from_id(
                    tool.get("nr")
                    or tool.get("numer")
                    or tool.get("id")
                    or tool.get("number")
                    or 0
                )
                normalized = "NOWE" if fallback == "NN" else "STARE"
            tool_mode = normalized
        else:
            tool_mode = _normalize_mode_label(mode) or "NOWE"

        if tool_mode == "NOWE":
            range_lo, range_hi = 1, 499
            statusy = _statusy_for_mode("NOWE")
        else:
            range_lo, range_hi = 500, 1000
            statusy = _statusy_for_mode("STARE")

        if not statusy:
            _notify_missing_configuration(
                "statuses",
                (
                    "Brak globalnych statusów narzędzi. "
                    "Dodaj statusy w module Ustawienia → Narzędzia."
                ),
            )

        default_start = {
            "nr": None,
            "nazwa": "",
            "typ": "",
            "status": "",
            "opis": "",
            "pracownik": login or "",
            "zadania": [],
            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tryb": tool_mode,
            "interwencje": [],
            "historia": [],
            "obrazy": [],
            "obraz": "",
            "dxf": "",
            "dxf_png": "",
        }

        start = dict(default_start)
        if tool:
            for key, value in tool.items():
                start[key] = value
        start = _apply_image_normalization(start)

        dlg = tk.Toplevel(root)
        dlg.title(("Edytuj" if editing else "Dodaj") + " – " + tool_mode)
        apply_theme(dlg)
        ensure_theme_applied(dlg)

        dialog_master = dlg

        tool_path = None
        if isinstance(tool, dict):
            for cand in ("__path__", "path", "file_path", "tool_path", "current_tool_path"):
                candidate = tool.get(cand)
                if candidate:
                    tool_path = candidate
                    break

        role = rola
        for owner in (dlg, getattr(dlg, "master", None), getattr(getattr(dlg, "master", None), "app", None)):
            if not owner:
                continue
            for attr in ("current_user", "current_profile"):
                data = getattr(owner, attr, None)
                if isinstance(data, dict):
                    role = data.get("rola") or data.get("role") or role
        role_norm = (role or "").strip().lower()

        # FIX(TOOLS): w EDYCJI nie generuj nowego numeru
        nr_auto = (
            start.get("nr")
            or start.get("numer")
            or start.get("id")
            or start.get("number")
        )
        if nr_auto:
            nr_auto = str(nr_auto).strip()
            if nr_auto.isdigit() and len(nr_auto) <= 3:
                nr_auto = nr_auto.zfill(3)
        elif editing and tool_path:
            try:
                stem = Path(str(tool_path)).stem
                nr_auto = stem.zfill(3) if stem.isdigit() and len(stem) <= 3 else stem
            except Exception:
                nr_auto = ""
        else:
            nr_auto = _next_free_in_range(range_lo, range_hi) or ""

        var_nr = tk.StringVar(master=dialog_master, value=str(nr_auto))
        var_nm = tk.StringVar(master=dialog_master, value=start.get("nazwa", ""))
        var_st = tk.StringVar(master=dialog_master, value=start.get("status", ""))
        var_op = tk.StringVar(master=dialog_master, value=start.get("opis", ""))
        var_pr = tk.StringVar(master=dialog_master, value=start.get("pracownik", login or ""))
        images = list(start.get("obrazy", []))
        var_dxf = tk.StringVar(master=dialog_master, value=start.get("dxf", ""))
        var_dxf_png = tk.StringVar(master=dialog_master, value=start.get("dxf_png", ""))
        wizyty_data = list((tool.get("wizyty") if editing else []) or [])

        main_container = ttk.Frame(dlg, padding=10, style="WM.TFrame")
        main_container.pack(fill="both", expand=True)

        header = ttk.Frame(main_container, style="WM.Card.TFrame", padding=(12, 10))
        header.pack(fill="x", pady=(0, 10))
        header_left = ttk.Frame(header, style="WM.TFrame")
        header_left.pack(side="left", fill="x", expand=True)
        ttk.Label(
            header_left,
            textvariable=var_nr,
            style="WM.Card.TLabel",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header_left,
            textvariable=var_nm,
            style="WM.Card.TLabel",
            font=("Segoe UI", 12),
        ).pack(anchor="w")

        header_right = ttk.Frame(header, style="WM.TFrame")
        header_right.pack(side="right", anchor="e")
        ttk.Label(header_right, text="Status:", style="WM.Muted.TLabel").pack(anchor="e")
        ttk.Label(
            header_right,
            textvariable=var_st,
            style="WM.Card.TLabel",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="e")
        ttk.Label(header_right, text="Typ:", style="WM.Muted.TLabel").pack(anchor="e", pady=(6, 0))
        var_typ = tk.StringVar(master=dialog_master, value=start.get("typ", ""))
        ttk.Label(header_right, textvariable=var_typ, style="WM.Card.TLabel").pack(anchor="e")

        nb = ttk.Notebook(main_container, style="TNotebook")
        nb.pack(fill="both", expand=True)

        tab_tasks = ttk.Frame(nb, padding=10, style="WM.Card.TFrame"); nb.add(tab_tasks, text="Zadania")
        tab_description = ttk.Frame(nb, padding=10, style="WM.Card.TFrame"); nb.add(tab_description, text="Opis narzędzia")
        tab_history = ttk.Frame(nb, padding=10, style="WM.Card.TFrame"); nb.add(tab_history, text="Historia")
        tab_visits = ttk.Frame(nb, padding=10, style="WM.Card.TFrame"); nb.add(tab_visits, text="Wizyty")

        def _on_delete_tool_from_tab():
            import os
            from tkinter import messagebox

            target_path = tool_path
            if not target_path:
                messagebox.showerror(
                    "Usuń narzędzie",
                    "Brak ścieżki pliku narzędzia w edytorze.",
                    parent=dlg,
                )
                return

            # FIX(DELETE): po usunięciu narzędzia musimy wyczyścić cache,
            # bo sama operacja refresh_list() bez force_reload potrafi dalej
            # pokazywać skasowany wpis aż do restartu WM.
            try:
                target_norm = _normalize_path(target_path)
            except Exception:
                target_norm = None

            def _purge_deleted_tool_from_cache() -> None:
                try:
                    if target_norm is not None:
                        STATE.tools_docs_cache.pop(target_norm, None)
                except Exception:
                    pass
                try:
                    if target_norm is not None:
                        STATE.tasks_docs_cache.pop(target_norm, None)
                except Exception:
                    pass
                try:
                    selected_path = getattr(STATE, "tasks_selected_path", None)
                    if selected_path is not None and target_norm is not None:
                        if _normalize_path(selected_path) == target_norm:
                            STATE.tasks_selected_path = None
                            STATE.tasks_selected_nr = None
                except Exception:
                    pass

            if not messagebox.askyesno(
                "Usuń narzędzie",
                "Czy na pewno chcesz trwale usunąć to narzędzie?",
                icon=messagebox.WARNING,
                parent=dlg,
            ):
                return

            try:
                os.remove(target_path)
            except FileNotFoundError:
                _purge_deleted_tool_from_cache()
                messagebox.showinfo(
                    "Usuń narzędzie", "Plik narzędzia był już usunięty.", parent=dlg
                )
                try:
                    dlg.destroy()
                except Exception:
                    pass
                try:
                    refresh_list(force_reload=True)
                except Exception:
                    pass
                return
            except Exception as exc:
                messagebox.showerror(
                    "Błąd usuwania", f"Nie udało się usunąć narzędzia:\n{exc}", parent=dlg
                )
                return

            _purge_deleted_tool_from_cache()
            messagebox.showinfo("Usunięto", "Narzędzie zostało usunięte.", parent=dlg)
            try:
                dlg.destroy()
            except Exception:
                pass
            try:
                refresh_list(force_reload=True)
            except Exception:
                pass

        if role_norm == "brygadzista":
            tab_delete_tool = ttk.Frame(nb)
            nb.add(tab_delete_tool, text="Usuń narzędzie")

            lbl = ttk.Label(
                tab_delete_tool,
                text=(
                    "Uwaga: ta operacja trwale usuwa plik narzędzia.\n"
                    "Nie można tego cofnąć."
                ),
                justify="left",
            )
            lbl.pack(anchor="w", padx=12, pady=(12, 8))

            btn = ttk.Button(
                tab_delete_tool,
                text="Usuń narzędzie",
                style="WM.Danger.TButton",
                command=_on_delete_tool_from_tab,
            )
            btn.pack(anchor="w", padx=12, pady=(0, 12))

        desc_frame = ttk.Frame(tab_description, style="WM.TFrame")
        desc_frame.pack(fill="both", expand=True)
        ttk.Label(desc_frame, text="Opis narzędzia", style="WM.Card.TLabel").pack(anchor="w")
        desc_body = ttk.Frame(desc_frame, style="WM.TFrame")
        desc_body.pack(fill="both", expand=True, pady=(6, 0))
        desc_text = tk.Text(desc_body, wrap="word", height=12)
        desc_scroll = ttk.Scrollbar(desc_body, orient="vertical", command=desc_text.yview)
        desc_text.configure(yscrollcommand=desc_scroll.set)
        desc_text.pack(side="left", fill="both", expand=True)
        desc_scroll.pack(side="right", fill="y")
        try:
            desc_text.insert("1.0", var_op.get())
        except Exception:
            pass

        def _sync_description_var():
            try:
                var_op.set(desc_text.get("1.0", "end").strip())
            except Exception:
                pass

        # ===== HISTORIA (kompakt, toggle) =====
        hist_frame = ttk.Frame(tab_history, style="WM.TFrame")
        hist_frame.pack(fill="x")
        ttk.Label(hist_frame, text="Historia (najnowsze na górze)", style="WM.Card.TLabel").pack(side="left")
        hist_shown = [True]
        btn_toggle = ttk.Button(hist_frame, text="Schowaj", style="WM.Side.TButton")
        btn_toggle.pack(side="right")

        hist_cols = ("ts", "by", "action", "details")
        hist_view = ttk.Treeview(tab_history, columns=hist_cols, show="headings", height=10, style="WM.Treeview")
        for c, txt, w in (
            ("ts", "Kiedy", 160),
            ("by", "Kto", 120),
            ("action", "Akcja", 160),
            ("details", "Szczegóły", 220),
        ):
            hist_view.heading(c, text=txt)
            hist_view.column(c, width=w, anchor="w")
        hist_view.pack(fill="both", expand=True, pady=(6, 0))

        hist_items = list((tool.get("historia") if editing else []) or [])

        def _format_history_row(item: dict[str, Any]) -> tuple[str, str, str, str]:
            ts = item.get("ts", "")
            by = item.get("by", "")
            action = (item.get("action") or item.get("typ") or "").strip()
            if not action and (item.get("z") or item.get("na")):
                action = "status_changed"
            elif not action and item.get("status"):
                action = "status_changed"
            if not action:
                z_text = (item.get("z") or "").strip()
                action = "info" if not z_text else z_text

            action_labels = {
                "task_added": "Dodano zadanie",
                "task_done": "Zadanie wykonane",
                "status_changed": "Zmiana statusu",
                "visit": "Wizyta",
                "task_note": "Notatka do zadania",
            }
            action_display = action_labels.get(action, action)

            details = item.get("details") or ""
            if not details:
                if action == "status_changed":
                    details = f"{item.get('z', '')} → {item.get('na', '')}".strip()
                elif action in {"task_added", "task_done"}:
                    details = item.get("title") or item.get("task") or item.get("task_id") or ""
                elif action == "visit":
                    details = item.get("comment") or item.get("komentarz") or item.get("status") or ""
                else:
                    details = item.get("na") or item.get("status") or item.get("comment") or ""
            return ts, by, action_display, details

        def _add_history_entry(entry: dict[str, Any], *, refresh: bool = True) -> None:
            hist_items.append(entry)
            if refresh:
                repaint_hist()

        def repaint_hist():
            hist_view.delete(*hist_view.get_children())
            for h in reversed(hist_items[-50:]):
                hist_view.insert("", "end", values=_format_history_row(h))
            _refresh_visits()

        def toggle_hist():
            if hist_shown[0]:
                try:
                    hist_view.pack_forget()
                except Exception:
                    pass
                btn_toggle.config(text="Pokaż")
            else:
                hist_view.pack(fill="both", expand=True, pady=(6, 0))
                btn_toggle.config(text="Schowaj")
            hist_shown[0] = not hist_shown[0]
        btn_toggle.configure(command=toggle_hist)

        visits_nb = ttk.Notebook(tab_visits, style="TNotebook")
        visits_nb.pack(fill="both", expand=True)

        tab_visits_summary = ttk.Frame(visits_nb, padding=0, style="WM.Card.TFrame")
        tab_visits_tree = ttk.Frame(visits_nb, padding=0, style="WM.Card.TFrame")
        tab_visits_comments = ttk.Frame(visits_nb, padding=0, style="WM.Card.TFrame")
        visits_nb.add(tab_visits_summary, text="Podsumowanie")
        visits_nb.add(tab_visits_tree, text="Wizyty → Zadania")
        visits_nb.add(tab_visits_comments, text="Komentarze")

        visits_header = ttk.Frame(tab_visits_summary, style="WM.TFrame")
        visits_header.pack(fill="x")
        visits_count_var = tk.StringVar(master=dialog_master, value="Liczba wizyt: 0")
        ttk.Label(visits_header, textvariable=visits_count_var, style="WM.Card.TLabel").pack(side="left")
        visits_base_var = tk.StringVar(master=dialog_master, value="")
        ttk.Label(visits_header, textvariable=visits_base_var, style="WM.Muted.TLabel").pack(side="right")
        visits_total_var = tk.StringVar(master=dialog_master, value="Łączny czas wizyt: 0h")

        visits_cols = ("ts", "by", "from", "duration", "comment")
        visits_tree = ttk.Treeview(
            tab_visits_summary,
            columns=visits_cols,
            show="headings",
            style="WM.Treeview",
            height=8,
        )
        for c, txt, w in (
            ("ts", "Data powrotu", 180),
            ("by", "Zmienione przez", 160),
            ("from", "Z statusu", 180),
            ("duration", "Czas wizyty", 160),
            ("comment", "Komentarz", 220),
        ):
            visits_tree.heading(c, text=txt)
            visits_tree.column(c, width=w, anchor="w")
        visits_tree.pack(fill="both", expand=True, pady=(6, 0))

        visits_summary = ttk.Frame(tab_visits_summary, style="WM.TFrame")
        visits_summary.pack(fill="x", pady=(6, 0))
        ttk.Label(
            visits_summary,
            textvariable=visits_total_var,
            style="WM.Card.TLabel",
        ).pack(side="left")

        visits_tasks_frame = ttk.Frame(tab_visits_tree, style="WM.TFrame")
        visits_tasks_frame.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(
            visits_tasks_frame,
            text="Wizyty → Zadania",
            style="WM.Card.TLabel",
        ).pack(anchor="w")
        visits_tasks_cols = ("start", "end", "who", "comment")
        visits_tree_tasks = ttk.Treeview(
            visits_tasks_frame,
            columns=visits_tasks_cols,
            show="tree headings",
            style="WM.Treeview",
            height=8,
        )
        for c, txt, w in (
            ("start", "Start wizyty", 160),
            ("end", "Koniec wizyty", 160),
            ("who", "Wykonawca", 160),
            ("comment", "Komentarz", 220),
        ):
            visits_tree_tasks.heading(c, text=txt)
            visits_tree_tasks.column(c, width=w, anchor="w")
        visits_tree_tasks.pack(fill="both", expand=True, pady=(6, 0))

        visits_comments_frame = ttk.Frame(tab_visits_comments, style="WM.TFrame")
        visits_comments_frame.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(
            visits_comments_frame,
            text="Komentarze z wizyt",
            style="WM.Card.TLabel",
        ).pack(anchor="w")
        visits_comments_list = tk.Listbox(visits_comments_frame, height=10)
        visits_comments_scroll = ttk.Scrollbar(
            visits_comments_frame, orient="vertical", command=visits_comments_list.yview
        )
        visits_comments_list.configure(yscrollcommand=visits_comments_scroll.set)
        visits_comments_list.pack(side="left", fill="both", expand=True, pady=(6, 0))
        visits_comments_scroll.pack(side="right", fill="y", pady=(6, 0))

        def _parse_ts(ts_value: str | None):
            raw = (ts_value or "").strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    return datetime.strptime(raw, fmt)
                except (TypeError, ValueError):
                    continue
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None

        def _format_ts(ts_value, raw: str) -> str:
            if isinstance(ts_value, datetime):
                return ts_value.strftime("%d-%m-%y %H:%M")
            return raw

        def _refresh_visits_comments() -> None:
            visits_comments_list.delete(0, "end")
            visits = []
            if isinstance(tool, dict):
                v = tool.get("wizyty")
                if isinstance(v, list):
                    visits = v
            if not visits and isinstance(wizyty_data, list):
                visits = wizyty_data

            idx = 0
            for visit in visits:
                if not isinstance(visit, dict):
                    continue
                comment_text = (visit.get("comment") or "").strip()
                if not comment_text:
                    continue
                idx += 1
                visits_comments_list.insert("end", f"{idx}. {comment_text}")

            if idx == 0:
                visits_comments_list.insert("end", "Brak komentarzy z wizyt.")

        def _refresh_visits() -> None:
            visits_tree.delete(*visits_tree.get_children())

            # 1) Preferuj jawne wizyty zapisane w tool["wizyty"] (jeśli są)
            wizyty_list = []
            if isinstance(tool, dict):
                v = tool.get("wizyty")
                if isinstance(v, list):
                    wizyty_list = v

            if isinstance(wizyty_list, list):
                total_duration = 0
                visits_rows = []

                base_status = (tool.get("status") or "").strip() if isinstance(tool, dict) else ""

                for visit in wizyty_list:
                    if not isinstance(visit, dict):
                        continue

                    start_dt = _parse_ts(visit.get("start_ts", ""))
                    end_dt = _parse_ts(visit.get("end_ts", ""))

                    who = (visit.get("end_by") or visit.get("start_by") or "").strip() or "—"
                    comment_text = (visit.get("comment") or "").strip() or "—"

                    # "Z statusu" – najlepiej start_status, fallback na status/base_status
                    prev_status = (visit.get("start_status") or visit.get("status") or base_status or "—")

                    if start_dt and end_dt:
                        duration = int((end_dt - start_dt).total_seconds())
                        if duration < 0:
                            duration = 0
                        total_duration += duration
                        dur_txt = _wm_humanize_duration_seconds(duration)
                    else:
                        dur_txt = "w toku"

                    visits_rows.append(
                        (
                            _format_ts(end_dt, visit.get("end_ts", "")) if end_dt else "w toku",
                            who,
                            prev_status or "—",
                            dur_txt,
                            comment_text,
                        )
                    )

                visits_count_var.set(f"Liczba wizyt: {len(visits_rows)}")
                visits_total_var.set(
                    f"Łączny czas wizyt: {_wm_humanize_duration_seconds(total_duration)}"
                )

                for row in visits_rows:
                    visits_tree.insert("", "end", values=row)

                _refresh_visits_comments()
                return

            # 2) Fallback: stara logika z historii (jeśli tool["wizyty"] brak)
            history = list((hist_items or []))
            base_status = (tool.get("status") or "").strip() if isinstance(tool, dict) else ""

            visits_rows = []
            total_duration = 0

            first_status = _get_first_status(_status_values_list())
            last_exit = None

            for change in history:
                if not isinstance(change, dict):
                    continue
                action = change.get("action")
                if action != "status_changed":
                    continue

                prev_status = str(change.get("z") or "").strip()
                new_status = str(change.get("na") or "").strip()
                ts_val = _parse_ts(change.get("ts", ""))

                if not first_status:
                    continue

                # wejście do pracy: first -> inne
                if prev_status.lower() == first_status.lower() and new_status.lower() != first_status.lower():
                    last_exit = ts_val
                    continue

                # powrót: inne -> first (zamyka wizytę)
                if prev_status.lower() != first_status.lower() and new_status.lower() == first_status.lower():
                    end_dt = ts_val
                    if last_exit and end_dt:
                        duration = int((end_dt - last_exit).total_seconds())
                        if duration < 0:
                            duration = 0
                        total_duration += duration
                        comment_text = str(change.get("comment") or "").strip() or "—"
                        who = str(change.get("by") or "").strip() or "—"
                        visits_rows.append(
                            (
                                _format_ts(end_dt, change.get("ts", "")),
                                who,
                                prev_status or "—",
                                _wm_humanize_duration_seconds(duration),
                                comment_text,
                            )
                        )
                    last_exit = None

            visits_count_var.set(f"Liczba wizyt: {len(visits_rows)}")
            visits_total_var.set(
                f"Łączny czas wizyt: {_wm_humanize_duration_seconds(total_duration)}"
            )

            for row in visits_rows:
                visits_tree.insert("", "end", values=row)

            _refresh_visits_comments()

        def _refresh_visits_tree() -> None:
            if not isinstance(tool, dict):
                # tryb "Dodaj" (tool=None) – nic do odświeżenia
                return
            visits_tree_tasks.delete(*visits_tree_tasks.get_children())
            visits = []
            v = None
            if isinstance(tool, dict):
                v = tool.get("wizyty")
            if isinstance(v, list):
                visits = v
            elif isinstance(wizyty_data, list):
                # fallback – w dialogu dodawania bywa tylko lista runtime
                visits = wizyty_data
            for idx, visit in enumerate(visits, start=1):
                raw_start = visit.get("start_ts")
                ts_start = _parse_ts(raw_start) if isinstance(raw_start, str) else None
                if raw_start and ts_start:
                    start_ts = _format_ts(ts_start, raw_start)
                else:
                    start_ts = "—" if not raw_start else str(raw_start)

                raw_end = visit.get("end_ts")
                ts_end = _parse_ts(raw_end) if isinstance(raw_end, str) else None
                if raw_end and ts_end:
                    end_ts = _format_ts(ts_end, raw_end)
                else:
                    end_ts = "w toku" if not raw_end else str(raw_end)

                who = visit.get("end_by") or visit.get("start_by") or "—"
                comment = visit.get("comment", "")

                parent_id = visits_tree_tasks.insert(
                    "",
                    "end",
                    text=f"Wizyta {idx}",
                    values=(start_ts, end_ts, who, comment),
                    open=False,
                )

                tasks = visit.get("zadania")
                if isinstance(tasks, list) and tasks:
                    for task in tasks:
                        title = (task.get("tytul") or task.get("title") or task.get("nazwa") or "").strip() or "—"
                        done = "✓" if task.get("done") else "—"
                        by = task.get("by") or task.get("done_by") or "—"
                        raw_when = task.get("ts_done") or task.get("date_done")
                        ts_when = (
                            _parse_ts(raw_when) if isinstance(raw_when, str) else None
                        )
                        if raw_when and ts_when:
                            when = _format_ts(ts_when, raw_when)
                        else:
                            when = "—" if not raw_when else str(raw_when)

                        visits_tree_tasks.insert(
                            parent_id,
                            "end",
                            text=title,
                            values=("", when, by, done),
                        )
                else:
                    visits_tree_tasks.insert(
                        parent_id,
                        "end",
                        text="(brak zadań w tej wizycie)",
                        values=("", "", "", ""),
                    )

        repaint_hist()
        _refresh_visits_tree()

      # ===== POLA OGÓLNE =====
        frm = tab_tasks
        r = 0
        # ostatnio obsłużony status (do gardy)
        last_applied_status = [ (start.get("status") or "").strip() ]
        # status aktualny (do historii/przyszłych reguł)
        last_status = [ (start.get("status") or "").strip() ]
        # status poprzedni (do wykrycia przejścia)
        prev_status = [ (start.get("status") or "").strip() ]
        def _active_collection() -> str:
            if tool_mode == "NOWE":
                return "NN"
            fallback = "SN"
            try:
                cfg_mgr = ConfigManager()
                enabled = cfg_mgr.get("tools.collections_enabled", []) or []
                for candidate in ("SN", "ST"):
                    if candidate in enabled:
                        fallback = candidate
                        break
            except Exception:
                pass
            result = str(fallback or "SN").strip()
            return result.upper() if result else "SN"
        def row(lbl, widget):
            nonlocal r
            ttk.Label(frm, text=lbl, style="WM.Card.TLabel").grid(row=r, column=0, sticky="w")
            widget.grid(row=r, column=1, sticky="ew", pady=2)
            r += 1

        # <<<=== ZMIANA – pole numeru z blokadą przy edycji ===>>>
        nr_frame = ttk.Frame(frm, style="WM.TFrame")
        ent_nr = ttk.Entry(nr_frame, textvariable=var_nr, style="WM.Search.TEntry")
        ent_nr.pack(side="left", fill="x", expand=True)

        def _free_numbers_in_range(start_nr: int, end_nr: int) -> list[str]:
            used = _existing_numbers()
            out: list[str] = []
            for i in range(start_nr, end_nr + 1):
                cand = f"{i:03d}"
                if cand not in used:
                    out.append(cand)
            return out

        def _show_free_numbers() -> None:
            free_nums = _free_numbers_in_range(range_lo, range_hi)
            if not free_nums:
                messagebox.showinfo(
                    "Wolne numery",
                    f"Brak wolnych numerów w zakresie {range_lo:03d}–{range_hi:03d}.",
                    parent=dlg,
                )
                return

            # FIX(UI): szybki podgląd wolnych numerów bez ręcznego sprawdzania plików.
            # Pokazujemy pierwsze 80 pozycji, żeby okno nie było przesadnie długie.
            preview = free_nums[:80]
            suffix = ""
            if len(free_nums) > len(preview):
                suffix = f"\n\n... oraz kolejne {len(free_nums) - len(preview)} numerów."

            messagebox.showinfo(
                "Wolne numery",
                (
                    f"Zakres: {range_lo:03d}–{range_hi:03d}\n"
                    f"Liczba wolnych numerów: {len(free_nums)}\n\n"
                    + ", ".join(preview)
                    + suffix
                ),
                parent=dlg,
            )

        btn_free_numbers = ttk.Button(
            nr_frame,
            text="Wolne numery",
            style="WM.Side.TButton",
            command=_show_free_numbers,
        )
        btn_free_numbers.pack(side="left", padx=(6, 0))
        row("Numer (3 cyfry)", nr_frame)

        if editing:
            try:
                ent_nr.state(["readonly"])
            except Exception:
                ent_nr.configure(state="disabled")
        # <<<=== KONIEC ZMIANY ===>>>

        keep_number_var = tk.BooleanVar(master=dialog_master, value=editing)
        keep_chk = ttk.Checkbutton(
            frm,
            text="Zachowaj numer przy zmianie trybu",
            variable=keep_number_var,
        )
        keep_chk.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, 6))
        r += 1
        if not editing:
            keep_number_var.set(False)
            try:
                keep_chk.state(["disabled"])
            except tk.TclError:
                pass

        # Oryginalny numer edytowanego narzędzia (do przywracania po zaznaczeniu "Zachowaj numer")
        _orig_nr = ""
        try:
            raw_orig = (start.get("nr") or start.get("numer") or start.get("id") or start.get("number") or "")
            _orig_nr = str(raw_orig).strip()
            if _orig_nr.isdigit():
                _orig_nr = _orig_nr.zfill(3)
        except Exception:
            _orig_nr = ""

        row("Nazwa", ttk.Entry(frm, textvariable=var_nm, style="WM.Search.TEntry"))

        # === Typ (Combobox z definicji) ===
        typ_frame = ttk.Frame(frm, style="WM.TFrame")
        collection_for_types = _active_collection()
        type_names = _type_names_for_collection(collection_for_types, force=True)
        start_typ = (start.get("typ", "") or "").strip()
        if start_typ and start_typ not in type_names:
            type_names = [start_typ] + [name for name in type_names if name != start_typ]
        print(
            "[WM-DBG][NARZ] Typy z definicji: "
            f"coll={collection_for_types} → {len(type_names)} pozycji"
        )
        cb_ty = ttk.Combobox(
            typ_frame,
            textvariable=var_typ,
            values=type_names,
            state="readonly",
            width=28,
        )
        if not type_names:
            _notify_missing_configuration(
                "types",
                (
                    "Brak zdefiniowanych typów narzędzi. "
                    "Dodaj typy w module Ustawienia → Narzędzia."
                ),
            )
        if start_typ:
            cb_ty.set(start_typ)
        elif type_names:
            try:
                cb_ty.set(type_names[0])
            except tk.TclError:
                var_typ.set(type_names[0])
        cb_ty.pack(side="left", fill="x", expand=True)
        row("Typ", typ_frame)

        status_frame = ttk.Frame(frm, style="WM.TFrame")
        cb_status = ttk.Combobox(
            status_frame,
            textvariable=var_st,
            values=statusy,
            state="readonly",
        )
        cb_status.pack(side="left", fill="x", expand=True)
        btn_status_reload = ttk.Button(
            status_frame,
            text="↻",
            width=3,
            style="WM.Side.TButton",
        )
        btn_status_reload.pack(side="left", padx=(6, 0))
        row("Status", status_frame)

        status_fallback = list(statusy)

        def _combobox_values(widget: ttk.Combobox) -> list[str]:
            try:
                raw_values = widget.cget("values")
            except Exception:
                return []
            if isinstance(raw_values, (list, tuple)):
                return [str(v) for v in raw_values]
            try:
                split = widget.tk.splitlist(raw_values)
            except Exception:
                return [str(raw_values)] if raw_values else []
            return [str(v) for v in split]

        def _status_values_list() -> list[str]:
            return _combobox_values(cb_status)

        def _ensure_type_value(value: str) -> None:
            normalized = (value or "").strip()
            if not normalized:
                return
            values = _combobox_values(cb_ty)
            if normalized.lower() not in {val.lower() for val in values}:
                cb_ty.config(values=[normalized] + values)

        def _reload_statuses_from_definitions(*, via_button: bool = False, force: bool = False) -> None:
            type_name = (var_typ.get() or "").strip()
            if not type_name:
                cb_status.config(values=status_fallback)
                return
            collection_id = _active_collection()
            definitions_path = _definitions_path_for_collection(collection_id)
            cfg_data = _load_tools_definitions(collection_id, force=force)
            tool_type = find_type(cfg_data, collection_id, type_name)
            if not tool_type:
                logger.warning(
                    "[WM-DBG][TOOL] Typ '%s' nie istnieje w kolekcji %s (plik: %s)",
                    type_name,
                    collection_id,
                    definitions_path,
                )
                _ensure_type_value(type_name)
                try:
                    messagebox.showwarning(
                        "Brak typu",
                        (
                            f"Typ „{type_name}” nie istnieje w kolekcji {collection_id}.\n"
                            "Zaktualizuj konfigurację narzędzi lub dodaj typ do pliku"
                            " definicji."
                        ),
                        parent=dlg,
                    )
                except Exception:
                    pass
                names = []
            else:
                names_raw = _status_names_for_type(
                    collection_id, type_name, force=force
                )
                names = []
                for s in names_raw:
                    if isinstance(s, dict):
                        value = s.get("name") or s.get("id") or str(s)
                    else:
                        value = str(s)
                    value = value.strip()
                    if value:
                        names.append(value)
            print("DEBUG names =", names)
            print(
                "[WM-DBG][NARZ] Statusy z definicji: "
                f"coll={collection_id} typ={type_name} → {len(names)} pozycji"
            )
            if not names:
                cb_status.config(values=status_fallback)
                if not status_fallback:
                    logger.info(
                        "[WM-DBG][NARZ][STATUS] Brak statusów dla typu '%s' w kolekcji %s (plik: %s)",
                        type_name,
                        collection_id,
                        definitions_path,
                    )
                    try:
                        messagebox.showinfo(
                            "Statusy", 
                            (
                                f"Brak statusów dla typu „{type_name}” w kolekcji {collection_id}.\n"
                                f"Plik definicji: {definitions_path or 'nieznany'}."
                            ),
                            parent=dlg,
                        )
                    except Exception:
                        pass
                if via_button and type_name:
                    messagebox.showinfo(
                        "Brak statusów",
                        f"Nie znaleziono statusów dla typu '{type_name}' w kolekcji {collection_id}.",
                    )
                _notify_missing_configuration(
                    "statuses",
                    (
                        "Brak zdefiniowanych statusów dla wybranego typu. "
                        "Dodaj statusy w module Ustawienia → Narzędzia."
                    ),
                )
                return
            cb_status.config(values=names)
            current_raw = var_st.get()
            current = (current_raw if isinstance(current_raw, str) else str(current_raw)).strip()
            names_lower = {n.lower() for n in names}
            if current.lower() not in names_lower and current:
                var_st.set(current)

        def _reload_statuses_and_refresh(
            *, via_button: bool = False, force: bool = False, refresh_presets: bool = True
        ) -> None:
            _reload_statuses_from_definitions(via_button=via_button, force=force)
            if refresh_presets:
                try:
                    _refresh_task_presets()
                except Exception:
                    pass
            try:
                _refresh_status_filter_options()
            except Exception:
                pass

        def _handle_status_reload() -> None:
            _reload_statuses_and_refresh(
                via_button=True, force=True, refresh_presets=False
            )
            _on_status_change(force=True)

        def _handle_type_change(*_args: object) -> None:
            _reload_statuses_and_refresh(refresh_presets=False)
            _on_status_change(force=True)

        btn_status_reload.configure(command=_handle_status_reload)

        cb_ty.bind("<<ComboboxSelected>>", _handle_type_change)
        try:
            var_typ.trace_add("write", _handle_type_change)
        except AttributeError:
            pass

        _reload_statuses_and_refresh()

        def _format_images_label() -> str:
            names = [os.path.basename(p) for p in images if isinstance(p, str) and p]
            if not names:
                return "—"
            if len(names) == 1:
                return names[0]
            if len(names) <= 3:
                return ", ".join(names)
            return f"{len(names)} pliki"

        images_var = tk.StringVar(master=dialog_master, value=_format_images_label())

        def _media_dir():
            path = os.path.join(_resolve_tools_dir(), "media")
            os.makedirs(path, exist_ok=True)
            return path

        img_frame = ttk.Frame(frm, style="WM.TFrame")
        btn_img = ttk.Button(img_frame, text="Wybierz...", style="WM.Side.TButton")
        btn_img.pack(side="left")
        preview_btn = ttk.Button(img_frame, text="Podgląd", style="WM.Side.TButton")
        preview_btn.pack(side="left", padx=(6, 0))
        preview_delay_ms = 3000
        try:
            cfg_mgr = ConfigManager()
            delay_raw = cfg_mgr.get("tools.preview_delay_sec", 3)
            delay_value = float(delay_raw)
        except Exception:
            delay_value = 3.0
        delay_value = max(1.0, min(delay_value, 3.0))
        preview_delay_ms = int(delay_value * 1000)

        preview_tooltip = ui_hover.ImageHoverTooltip(
            preview_btn,
            None,
            delay=preview_delay_ms,
            bind_events=False,
        )
        img_lbl = ttk.Label(
            img_frame,
            textvariable=images_var,
            style="WM.Muted.TLabel",
        )
        img_lbl.pack(side="left", padx=6)
        clear_btn = ttk.Button(img_frame, text="Wyczyść", style="WM.Side.TButton")
        clear_btn.pack(side="left", padx=(6, 0))

        dxf_frame = ttk.Frame(frm, style="WM.TFrame")
        btn_dxf = ttk.Button(dxf_frame, text="Wybierz...", style="WM.Side.TButton")
        btn_dxf.pack(side="left")
        dxf_lbl = ttk.Label(
            dxf_frame,
            text=os.path.basename(var_dxf.get()) if var_dxf.get() else "—",
            style="WM.Muted.TLabel",
        )
        dxf_lbl.pack(side="left", padx=6)

        def _refresh_images_label() -> None:
            images_var.set(_format_images_label())

        def clear_images() -> None:
            if not images:
                return
            try:
                proceed = messagebox.askyesno(
                    "Obrazy",
                    "Usunąć wszystkie powiązane obrazy?",
                    parent=dlg,
                )
            except Exception:
                proceed = True
            if proceed:
                images.clear()
                _refresh_images_label()
                preview_tooltip.hide_tooltip()

        def select_img():
            files = filedialog.askopenfilenames(
                filetypes=[("Obrazy", "*.png *.jpg *.jpeg")]
            )
            if not files:
                return
            numer_raw = (var_nr.get() or "").strip()
            if not numer_raw.isdigit():
                messagebox.showwarning(
                    "Obrazy",
                    "Najpierw ustaw numer narzędzia (3 cyfry).",
                    parent=dlg,
                )
                return
            numer = numer_raw.zfill(3)
            dest_dir = _media_dir()
            added = False
            for src in files:
                if not _is_allowed_file(str(src)):
                    messagebox.showwarning(
                        "Obrazy",
                        f"Pominięto plik '{os.path.basename(src)}' (niedozwolony format lub rozmiar).",
                        parent=dlg,
                    )
                    continue
                ext = os.path.splitext(src)[1].lower()
                attempt = len(images) + 1
                while True:
                    dest_name = f"{numer}_img{attempt}{ext}"
                    dest_path = os.path.join(dest_dir, dest_name)
                    rel = os.path.relpath(dest_path, _resolve_tools_dir())
                    if rel not in images and not os.path.exists(dest_path):
                        break
                    attempt += 1
                try:
                    shutil.copy2(src, dest_path)
                except (OSError, shutil.Error) as e:
                    _dbg("Błąd kopiowania obrazu:", e)
                    continue
                images.append(rel)
                added = True
            if added:
                _refresh_images_label()

        def select_dxf():
            p = filedialog.askopenfilename(filetypes=[("DXF", "*.dxf")])
            if not p:
                return
            numer = (var_nr.get() or "").strip().zfill(3)
            dest_dir = _media_dir()
            dest = os.path.join(dest_dir, f"{numer}.dxf")
            try:
                shutil.copy2(p, dest)
                rel = os.path.relpath(dest, _resolve_tools_dir())
                var_dxf.set(rel)
                dxf_lbl.config(text=os.path.basename(dest))
                png = _generate_dxf_preview(dest)
                if png:
                    rel_png = os.path.relpath(png, _resolve_tools_dir())
                    var_dxf_png.set(rel_png)
            except (OSError, shutil.Error) as e:
                _dbg("Błąd kopiowania DXF:", e)

        def _collect_preview_paths() -> List[str]:
            base = _resolve_tools_dir()
            seen: set[str] = set()
            allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
            result: List[str] = []
            candidates: List[str] = []
            candidates.extend(images)
            dxf_png = (var_dxf_png.get() or "").strip()
            if dxf_png:
                candidates.append(dxf_png)
            for rel in candidates:
                rel_clean = (rel or "").strip()
                if not rel_clean or rel_clean in seen:
                    continue
                seen.add(rel_clean)
                ext = os.path.splitext(rel_clean)[1].lower()
                if ext not in allowed_ext:
                    continue
                full = os.path.join(base, rel_clean)
                # jw. – bez exists() na etapie ładowania listy
                result.append(full)
            return result

        def preview_media(_event: object | None = None) -> None:
            paths = _collect_preview_paths()
            if not paths:
                preview_tooltip.hide_tooltip()
                messagebox.showinfo("Podgląd", "Brak pliku do podglądu.")
                return
            preview_tooltip.update_image_paths(paths)
            preview_tooltip.show_tooltip()

        def _hide_preview(_event: object | None = None) -> None:
            preview_tooltip.hide_tooltip()

        btn_img.config(command=select_img)
        btn_dxf.config(command=select_dxf)
        preview_btn.config(command=preview_media)
        preview_btn.bind("<Return>", lambda e: preview_media(e))
        preview_btn.bind("<Leave>", _hide_preview, add="+")
        preview_btn.bind("<FocusOut>", _hide_preview, add="+")
        preview_btn.bind("<Key-Escape>", _hide_preview, add="+")
        clear_btn.config(command=clear_images)

        row("Obraz", img_frame)
        row("Plik DXF", dxf_frame)

        # ===== Konwersja NN→SN (tylko dla NOWE) =====
        convert_var = tk.BooleanVar(master=dialog_master, value=False)
        convert_tasks_var = tk.StringVar(
            master=dialog_master, value="replace"
        )  # 'keep' | 'replace' | 'sum'
        conv_frame = ttk.Frame(frm, style="WM.TFrame")
        chk = ttk.Checkbutton(conv_frame, text="Przenieś do SN przy zapisie", variable=convert_var)
        chk.pack(side="left")
        ttk.Label(conv_frame, text="  Zadania po konwersji:", style="WM.Muted.TLabel").pack(side="left", padx=(8,4))
        cb_conv = ttk.Combobox(conv_frame, values=["pozostaw", "podmień na serwis wg typu", "dodaj serwis do istniejących"], state="readonly", width=28)
        cb_conv.current(1)  # domyślnie "podmień"
        def _sync_conv_mode(*_):
            lab = (cb_conv.get() or "").strip().lower()
            if lab.startswith("pozostaw"):
                convert_tasks_var.set("keep")
            elif lab.startswith("dodaj"):
                convert_tasks_var.set("sum")
            else:
                convert_tasks_var.set("replace")
        cb_conv.bind("<<ComboboxSelected>>", _sync_conv_mode)
        cb_conv.pack(side="left", padx=(0,0))

        def _apply_mode_based_suggestion(*_):
            if not editing:
                return
            if keep_number_var.get():
                return
            if tool_mode != "NOWE":
                return
            if not convert_var.get():
                return
            suggestion = _next_free_in_range(500, 1000)
            if suggestion:
                try:
                    var_nr.set(str(suggestion).zfill(3))
                except Exception:
                    var_nr.set(str(suggestion))

        try:
            convert_var.trace_add("write", _apply_mode_based_suggestion)
        except AttributeError:
            convert_var.trace("w", _apply_mode_based_suggestion)

        def _on_keep_toggle(*_):
            if keep_number_var.get():
                # Jeśli wcześniej zasugerowano numer SN (np. 643), a użytkownik zaznaczył "Zachowaj numer",
                # to wracamy do numeru źródłowego (np. 006) — inaczej zapis tworzy duplikat.
                if _orig_nr:
                    try:
                        var_nr.set(_orig_nr)
                    except Exception:
                        pass
                return
            _apply_mode_based_suggestion()

        try:
            keep_number_var.trace_add("write", _on_keep_toggle)
        except AttributeError:
            keep_number_var.trace("w", _on_keep_toggle)

        # uprawnienia i widoczność
        if tool_mode == "NOWE":
            allowed = _can_convert_nn_to_sn(rola)
            chk.state(["!alternate"])
            if not allowed:
                try:
                    chk.state(["disabled"])
                    cb_conv.state(["disabled"])
                except tk.TclError:
                    pass
                ttk.Label(conv_frame, text=" (wymaga roli brygadzisty)", style="WM.Muted.TLabel").pack(side="left", padx=(6,0))
            row("Konwersja NN→SN", conv_frame)

        # ===== Zadania (lista) =====
        ttk.Label(frm, text="Zadania narzędzia", style="WM.Card.TLabel").grid(row=r, column=0, sticky="w", pady=(8,2)); r += 1
        tasks_frame = ttk.Frame(frm, style="WM.Card.TFrame"); tasks_frame.grid(row=r, column=0, columnspan=2, sticky="nsew")
        frm.rowconfigure(r, weight=1); frm.columnconfigure(1, weight=1)

        def _bind_text_tooltip(widget: tk.Misc, text: str) -> None:
            if not text:
                return
            tip: dict[str, tk.Toplevel | None] = {"win": None}

            def _show(_event: object | None = None) -> None:
                if tip["win"] is not None:
                    return
                try:
                    x = widget.winfo_rootx() + 16
                    y = widget.winfo_rooty() + 20
                except Exception:
                    return
                tw = tk.Toplevel(widget)
                try:
                    tw.wm_overrideredirect(True)
                except Exception:
                    pass
                try:
                    tw.wm_geometry(f"+{x}+{y}")
                except Exception:
                    pass
                lbl = ttk.Label(tw, text=text, style="WM.Tooltip.TLabel", padding=(6, 3))
                lbl.pack()
                tip["win"] = tw

            def _hide(_event: object | None = None) -> None:
                win = tip.get("win")
                if win is None:
                    return
                try:
                    win.destroy()
                except Exception:
                    pass
                tip["win"] = None

            widget.bind("<Enter>", _show, add="+")
            widget.bind("<Leave>", _hide, add="+")

        actions_frame = ttk.Frame(tasks_frame, style="WM.TFrame")
        actions_frame.pack(fill="x", padx=4, pady=(4, 0))
        btn_add_status_tasks = ttk.Button(
            actions_frame,
            text="Dodaj zadania ustawione dla statusu",
            command=lambda: add_tasks_from_status_config(),
            style="WM.Side.TButton",
        )
        btn_add_status_tasks.pack(side="left", padx=(0, 8))
        _bind_text_tooltip(
            btn_add_status_tasks,
            "Skopiuje listę zadań z konfiguracji dla aktualnego statusu",
        )

        filter_frame = ttk.Frame(tasks_frame, style="WM.TFrame")
        filter_frame.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(filter_frame, text="Filtr zadań", style="WM.Muted.TLabel").pack(side="left")
        filter_label_all = "Wszystkie statusy"
        filter_label_current = "Tylko aktualny status narzędzia"
        tasks_status_filter = tk.StringVar(master=dialog_master, value=filter_label_all)
        filter_values = [filter_label_all, filter_label_current] + list(statusy)
        tasks_filter_box = ttk.Combobox(
            filter_frame,
            textvariable=tasks_status_filter,
            values=filter_values,
            state="readonly",
            width=36,
        )
        tasks_filter_box.pack(side="left", padx=(8, 0))

        def _refresh_status_filter_options() -> None:
            options = [filter_label_all, filter_label_current]
            try:
                options.extend([s for s in _status_values_list() if s])
            except Exception:
                options.extend(list(statusy))
            tasks_filter_box.config(values=options)
            if tasks_status_filter.get() not in options:
                tasks_status_filter.set(filter_label_all)

        _refresh_status_filter_options()

        tasks_table = ttk.Frame(tasks_frame, style="WM.TFrame")
        tasks_table.pack(fill="both", expand=True)

        task_cols = ("tytul", "status", "done", "assigned", "by", "ts")
        tv = ttk.Treeview(tasks_table, columns=task_cols, show="headings", height=7, style="WM.Treeview")
        for c, txt, w in (
            ("tytul", "Tytuł", 260),
            ("status", "Status", 150),
            ("done", "Wykonanie", 90),
            ("assigned", "Przypisane do", 150),
            ("by", "Wykonał", 120),
            ("ts", "Kiedy", 160),
        ):
            tv.heading(c, text=txt); tv.column(c, width=w, anchor="w")
        tv.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(tasks_table, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y")

        tasks = [ensure_task_shape(t) for t in _norm_tasks(start.get("zadania"))]

        def _has_title(title: str) -> bool:
            tl = (title or "").strip().lower()
            return any((t.get("tytul","").strip().lower() == tl) for t in tasks)

        def _add_default_tasks_for_status(status_name: str) -> None:
            status_clean = (status_name or "").strip()
            type_clean = (var_typ.get() or "").strip()
            if not status_clean or not type_clean:
                return
            collection_id = _active_collection()
            defaults = _task_names_for_status(collection_id, type_clean, status_clean)
            print(
                "[WM-DBG][NARZ] Zadania z definicji: "
                f"coll={collection_id} typ={type_clean} "
                f"status={status_clean} → {len(defaults)} zadań"
            )
            if not defaults:
                _notify_missing_configuration(
                    "tasks",
                    (
                        "Brak zdefiniowanych zadań dla wybranego statusu. "
                        "Dodaj zadania w module Ustawienia → Narzędzia."
                    ),
                )
            added = False
            for title in defaults:
                if _has_title(title):
                    continue
                created = _prepare_new_task(
                    {
                        "tytul": title,
                        "done": False,
                        "by": "",
                        "ts_done": "",
                        "assigned_to": "",
                        "status": status_clean,
                        "source": "status_default",
                    }
                )
                tasks.append(created)
                _add_history_entry(
                    {
                        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "by": login or "system",
                        "action": "task_added",
                        "task_id": created.get("id") or created.get("task_id") or title,
                        "title": title,
                        "details": f"status: {status_clean}",
                        "source": created.get("source"),
                    },
                    refresh=False,
                )
                added = True
            if added:
                repaint_tasks()
                repaint_hist()

        def add_tasks_from_status_config() -> None:
            status_clean = (var_st.get() or "").strip()
            type_clean = (var_typ.get() or "").strip()
            collection_id = _active_collection()
            cfg_tasks = _task_names_for_status(
                collection_id, type_clean, status_clean
            )
            if not cfg_tasks:
                messagebox.showinfo(
                    "Zadania", "Brak zadań ustawionych dla statusu"
                )
                return
            added = False
            for title in cfg_tasks:
                normalized = (title or "").strip()
                if not normalized:
                    continue
                if _has_title(normalized):
                    continue
                created = _prepare_new_task(
                    {
                        "tytul": normalized,
                        "done": False,
                        "by": "",
                        "ts_done": "",
                        "assigned_to": "",
                        "status": status_clean,
                        "source": "status_default",
                    }
                )
                tasks.append(created)
                _add_history_entry(
                    {
                        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "by": login or "system",
                        "action": "task_added",
                        "task_id": created.get("id")
                        or created.get("task_id")
                        or normalized,
                        "title": normalized,
                        "details": f"status: {status_clean}",
                        "source": created.get("source"),
                    },
                    refresh=False,
                )
                added = True
            if not added:
                messagebox.showinfo(
                    "Zadania", "Brak zadań ustawionych dla statusu"
                )
                return
            repaint_tasks()
            repaint_hist()

        def repaint_tasks():
            tv.delete(*tv.get_children())
            filter_value = (tasks_status_filter.get() or filter_label_all).strip()
            current_status_lower = (var_st.get() or "").strip().lower()
            filter_lower = filter_value.lower()
            for i, t in enumerate(tasks):
                shaped = ensure_task_shape(t)
                tasks[i] = shaped
                status_value = (shaped.get("status") or "").strip()
                if filter_lower == filter_label_current.lower():
                    if status_value.strip().lower() != current_status_lower:
                        continue
                elif filter_lower != filter_label_all.lower() and filter_value:
                    if status_value.strip().lower() != filter_lower:
                        continue
                tv.insert(
                    "",
                    "end",
                    iid=str(i),
                    values=(
                        shaped.get("tytul", ""),
                        status_value,
                        "✔" if shaped.get("done") else "—",
                        shaped.get("assigned_to", ""),
                        shaped.get("by", ""),
                        shaped.get("ts_done", ""),
                    ),
                )
        repaint_tasks()

        try:
            tasks_status_filter.trace_add("write", lambda *_: repaint_tasks())
        except AttributeError:
            tasks_status_filter.trace("w", lambda *_: repaint_tasks())

        # ---- OPERACJE NA LISTACH ZADAŃ (faza) ----
        def _apply_template_for_phase(phase: str):
            typ_val = (cb_ty.get() or "").strip()
            if not typ_val:
                messagebox.showinfo("Zadania", "Najpierw wybierz 'Typ' narzędzia.")
                return
            tpl = _tasks_for_type(typ_val, phase)
            if not tpl:
                messagebox.showinfo("Zadania", f"Brak zdefiniowanych zadań dla typu „{typ_val}” ({phase}).")
                return
            missing = [t for t in tpl if not _has_title(t)]
            if not missing:
                return
            for m in missing:
                created = _prepare_new_task(
                    {
                        "tytul": m,
                        "done": False,
                        "by": "",
                        "ts_done": "",
                        "assigned_to": "",
                        "status": (var_st.get() or "").strip(),
                        "source": "status_default",
                    }
                )
                tasks.append(created)
                _add_history_entry(
                    {
                        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "by": login or "system",
                        "action": "task_added",
                        "task_id": created.get("id") or created.get("task_id") or m,
                        "title": m,
                        "source": created.get("source"),
                    },
                    refresh=False,
                )
            repaint_tasks()
            repaint_hist()
            repaint_hist()

        # ---- REAKCJA NA ZMIANĘ STATUSU ----
        def _on_status_change(_=None, *, force: bool = False):
            try:
                _refresh_task_presets()
            except Exception:
                pass
            new_st = (var_st.get() or "").strip()
            # garda: jeśli to samo co ostatnio obsłużone, nic nie rób
            if not force and new_st == (last_applied_status[0] or ""):
                return
            if new_st != (last_status[0] or ""):
                prev_status[0] = last_status[0]
                last_status[0] = new_st
            _phase_for_status(tool_mode, new_st)
            if tool_mode == "NOWE" and new_st.lower() == "odbiór zakończony".lower():
                if messagebox.askyesno("Przenieść", "Przenieść do SN?"):
                    convert_var.set(True)
                    convert_tasks_var.set("keep")
                    try:
                        cb_conv.current(0)
                    except tk.TclError:
                        pass
                    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    iso_now = _now_iso()
                    for idx, t in enumerate(tasks):
                        shaped_task = ensure_task_shape(t)
                        if not shaped_task.get("done"):
                            shaped_task["done"] = True
                            shaped_task["by"] = login or "system"
                            shaped_task["ts_done"] = now_ts
                        if not shaped_task.get("date_added"):
                            shaped_task["date_added"] = iso_now
                        shaped_task["date_done"] = _normalize_date_value(shaped_task.get("date_done")) or iso_now
                        shaped_task["status"] = _clean_status(shaped_task.get("status"), "done")
                        shaped_task["state"] = "done"
                        tasks[idx] = shaped_task
                    repaint_tasks()
                    _add_history_entry(
                        {
                            "ts": now_ts,
                            "by": login or "system",
                            "action": "task_done",
                            "title": "auto ✔ przy przeniesieniu do SN",
                        }
                    )
            status_values = [s for s in _status_values_list() if s]
            final_status = status_values[-1] if status_values else ""
            if final_status and new_st.lower() == final_status.lower():
                # AUTO-ODHACZANIE WYŁĄCZONE
                # Zadania mogą być oznaczane jako DONE tylko ręcznie
                pass
            last_applied_status[0] = new_st
            # wymuś odświeżenie zakładek po zmianie statusu (bez zamykania okna)
            try:
                repaint_tasks()
                repaint_hist()
                _refresh_visits_tree()
            except Exception:
                pass

        cb_status.bind("<<ComboboxSelected>>", lambda event=None: _on_status_change(event))
        # (bez '<FocusOut>' – żeby nie dublować)

        try:
            _on_status_change(force=True)
        except Exception:
            pass

        # Pasek narzędzi do zadań (manualnie też można)
        tools_bar = ttk.Frame(frm, style="WM.TFrame"); tools_bar.grid(row=r+1, column=0, columnspan=2, sticky="ew", pady=(6,0))
        legacy_task_presets = list(_task_templates_from_config())
        tmpl_var = tk.StringVar(master=dialog_master)
        tmpl_box = ttk.Combobox(
            tools_bar,
            textvariable=tmpl_var,
            values=legacy_task_presets,
            state="readonly",
            width=36,
        )
        tmpl_box.pack(side="left")

        def _wm_widget_exists(widget) -> bool:
            """Zwraca True, jeśli widget nadal istnieje w Tk (nie został destroy)."""
            try:
                return (widget is not None) and (int(widget.winfo_exists()) == 1)
            except Exception:
                return False

        def _refresh_task_presets() -> None:
            type_name = (var_typ.get() or "").strip()
            status_name = (var_st.get() or "").strip()
            collection_id = _active_collection()
            try:
                tasks_from_defs = _task_names_for_status(collection_id, type_name, status_name)
            except Exception:
                tasks_from_defs = []
            if tasks_from_defs:
                if not _wm_widget_exists(tmpl_box):
                    return
                try:
                    tmpl_box.config(values=tasks_from_defs)
                except tk.TclError:
                    return
                current = (tmpl_var.get() or "").strip()
                if current not in tasks_from_defs:
                    try:
                        tmpl_var.set(tasks_from_defs[0])
                    except tk.TclError:
                        return
                print(
                    "[WM-DBG][TOOLS_UI] presets set from defs "
                    f"coll={collection_id} type='{type_name}' status='{status_name}' "
                    f"count={len(tasks_from_defs)}"
                )
                return
            alt_status: str | None = None
            if type_name and status_name and collection_id:
                try:
                    for candidate in _status_names_for_type(collection_id, type_name):
                        cand_clean = (candidate or "").strip()
                        if not cand_clean or cand_clean == status_name:
                            continue
                        cand_tasks = _task_names_for_status(
                            collection_id, type_name, cand_clean
                        )
                        if cand_tasks:
                            alt_status = cand_clean
                            break
                except Exception:
                    alt_status = None
            if alt_status:
                try:
                    ask_switch = messagebox.askyesno(
                        "Brak zadań dla statusu",
                        (
                            f"Dla statusu „{status_name}” nie ma zdefiniowanych zadań.\n"
                            f"Czy przełączyć na najbliższy status z zadaniami: „{alt_status}”?"
                        ),
                    )
                except Exception:
                    ask_switch = False
                if ask_switch:
                    try:
                        cb_status.set(alt_status)
                    except Exception:
                        pass
                    var_st.set(alt_status)
                    status_name = alt_status
                    try:
                        tasks_from_defs = _task_names_for_status(
                            collection_id, type_name, alt_status
                        )
                    except Exception:
                        tasks_from_defs = []
                    if tasks_from_defs:
                        if not _wm_widget_exists(tmpl_box):
                            return
                        try:
                            tmpl_box.config(values=tasks_from_defs)
                        except tk.TclError:
                            return
                        current = (tmpl_var.get() or "").strip()
                        if current not in tasks_from_defs:
                            try:
                                tmpl_var.set(tasks_from_defs[0])
                            except tk.TclError:
                                return
                        print(
                            f"[WM-DBG][TOOLS_UI] status auto-switched to '{alt_status}' "
                            f"(tasks={len(tasks_from_defs)})"
                        )
                        return
            if not _wm_widget_exists(tmpl_box):
                return
            try:
                tmpl_box.config(values=legacy_task_presets)
            except tk.TclError:
                return
            current = (tmpl_var.get() or "").strip()
            if legacy_task_presets and current not in legacy_task_presets:
                try:
                    tmpl_var.set(legacy_task_presets[0])
                except tk.TclError:
                    return
            print(
                "[WM-DBG][TOOLS_UI] no task defs for "
                f"type='{type_name}' status='{status_name}' — user kept status"
            )

        _refresh_task_presets()

        def _add_from_template(sel):
            s = (sel or "").strip()
            if not s: return
            if _has_title(s):
                messagebox.showinfo("Zadania", "Takie zadanie już istnieje."); return
            created = _prepare_new_task(
                {
                    "tytul": s,
                    "done": False,
                    "by": "",
                    "ts_done": "",
                    "assigned_to": "",
                    "status": (var_st.get() or "").strip(),
                    "source": "preset",
                }
            )
            tasks.append(created)
            _add_history_entry(
                {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "by": login or "system",
                    "action": "task_added",
                    "task_id": created.get("id") or created.get("task_id") or s,
                    "title": s,
                    "source": created.get("source"),
                },
                refresh=False,
            )
            repaint_tasks()

        ttk.Button(
            tools_bar,
            text="Dodaj z listy",
            style="WM.Side.TButton",
            command=lambda: (_add_from_template(tmpl_var.get())),
        ).pack(side="left", padx=(6, 0))

        new_var = tk.StringVar(master=dialog_master)
        ttk.Entry(tools_bar, textvariable=new_var, width=28, style="WM.Search.TEntry").pack(side="left", padx=(12,6))
        def _add_task(var):
            t = (var.get() or "").strip()
            if not t: return
            if _has_title(t):
                messagebox.showinfo("Zadania", "Takie zadanie już istnieje."); return
            created = _prepare_new_task(
                {
                    "tytul": t,
                    "done": False,
                    "by": "",
                    "ts_done": "",
                    "assigned_to": "",
                    "status": (var_st.get() or "").strip(),
                    "source": "manual",
                }
            )
            tasks.append(created)
            _add_history_entry(
                {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "by": login or "system",
                    "action": "task_added",
                    "task_id": created.get("id") or created.get("task_id") or t,
                    "title": t,
                    "source": created.get("source"),
                },
                refresh=False,
            )
            var.set(""); repaint_tasks(); repaint_hist()
        ttk.Button(tools_bar, text="Dodaj własne", style="WM.Side.TButton",
                   command=lambda: _add_task(new_var)).pack(side="left")
        def _sel_idx():
            iid = tv.focus() or (tv.selection()[0] if tv.selection() else "")
            if not iid:
                return -1
            try:
                return int(iid)
            except (TypeError, ValueError):
                pass
            vals = tv.item(iid, "values")
            if not vals:
                return -1
            title = vals[0]
            for i, t in enumerate(tasks):
                if t.get("tytul") == title:
                    return i
            return -1
        def _del_sel():
            i = _sel_idx()
            if i < 0:
                return
            _remove_task(tasks, i)
            repaint_tasks()
        def _toggle_done():
            i = _sel_idx()
            if i < 0:
                return
            shaped = ensure_task_shape(tasks[i])
            tasks[i] = shaped
            marking_done = not shaped.get("done")
            skip_note = ""
            if marking_done:
                iso_now = _now_iso()
                skipped_before = _pending_tasks_before(tasks, i)
                if skipped_before:
                    skipped_text = ", ".join(
                        f"{idx + 1}. {title}" for idx, title in skipped_before
                    )
                    warn_msg = (
                        "Nie wszystkie wcześniejsze zadania są oznaczone jako wykonane.\n"
                        f"Brak ✔ przy: {skipped_text}.\n"
                        "Czy mimo to oznaczyć bieżące zadanie jako wykonane?"
                    )
                    try:
                        proceed = messagebox.askyesno(
                            "Kolejność zadań",
                            warn_msg,
                            parent=dlg,
                        )
                    except Exception:
                        proceed = True
                    if not proceed:
                        return
                    try:
                        skip_comment = simpledialog.askstring(
                            "Pominięcie zadań",
                            "Dodaj komentarz dotyczący pominięcia kolejności (opcjonalnie):",
                            parent=dlg,
                        ) or ""
                    except Exception:
                        skip_comment = ""
                    skip_note = _build_skip_note(
                        _task_title(shaped), skipped_before, skip_comment
                    )
                    ts_note = datetime.now().strftime("%Y-%m-%d %H:%M")
                    _add_history_entry(
                        {
                            "ts": ts_note,
                            "by": login or "nieznany",
                            "action": "task_note",
                            "details": skip_note,
                        }
                    )
            if marking_done:
                shaped["done"] = True
                shaped["by"] = login or "nieznany"
                ts_done = datetime.now().strftime("%Y-%m-%d %H:%M")
                shaped["ts_done"] = ts_done
                if not shaped.get("date_added"):
                    shaped["date_added"] = iso_now
                shaped["date_done"] = _normalize_date_value(shaped.get("date_done")) or iso_now
                shaped["status"] = _clean_status(shaped.get("status"), "done")
                shaped["state"] = "done"
                shaped["archived"] = True
                shaped["archived_at"] = _normalize_date_value(shaped.get("archived_at")) or iso_now
                if skip_note:
                    existing_comment = (shaped.get("komentarz") or "").strip()
                    if existing_comment:
                        shaped["komentarz"] = f"{existing_comment} | {skip_note}"
                    else:
                        shaped["komentarz"] = skip_note
                _add_history_entry(
                    {
                        "ts": ts_done,
                        "by": login or "nieznany",
                        "action": "task_done",
                        "task_id": shaped.get("id") or shaped.get("task_id") or _task_title(shaped),
                        "title": _task_title(shaped),
                    },
                    refresh=False,
                )
                # [MAGAZYN] zużycie materiałów powiązanych z zadaniem / BOM
                can_consume = hasattr(LZ, "consume_for_task") if LZ else False
                if not can_consume:
                    logger.warning(
                        "[TOOLS] Pomijam consume_for_task – brak implementacji w logika_zadan."
                    )
                else:
                    try:
                        zuzyte = LZ.consume_for_task(
                            tool_id=str(nr_auto), task=shaped, uzytkownik=login or "system"
                        )
                        if zuzyte:
                            shaped["zużyte_materialy"] = (
                                shaped.get("zużyte_materialy") or []
                            ) + list(zuzyte)
                    except Exception as _e:
                        logger.error("[TOOLS] consume_for_task wyjątek: %s", _e)
            else:
                try:
                    zuzyte = shaped.get("zużyte_materialy")
                    if zuzyte:
                        for poz in zuzyte:
                            LM.zwrot(
                                poz["id"],
                                float(poz["ilosc"]),
                                uzytkownik=login or "system",
                            )
                        shaped["zużyte_materialy"] = []
                except (KeyError, ValueError, RuntimeError) as _e:
                    shaped["done"] = True
                    messagebox.showerror("Magazyn", f"Błąd zwrotu: {_e}")
                    return
                shaped["done"] = False
                shaped["by"] = ""
                shaped["ts_done"] = ""
                shaped["status"] = _clean_status(shaped.get("status"), "active")
                shaped["date_done"] = ""
                shaped["state"] = "active"
                shaped.pop("archived", None)
                shaped.pop("archived_at", None)
            repaint_tasks()
            repaint_hist()

        def _assign_selected(login_value: str) -> None:
            idx = _sel_idx()
            if idx < 0:
                messagebox.showwarning("Przypisanie", "Najpierw zaznacz zadanie z listy.")
                return
            shaped = ensure_task_shape(tasks[idx])
            tasks[idx] = shaped
            login_clean = (login_value or "").strip()
            shaped["assigned_to"] = login_clean
            if login_clean:
                shaped["assigned_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            else:
                shaped.pop("assigned_ts", None)
            repaint_tasks()
            try:
                tv.selection_set(str(idx))
                tv.focus(str(idx))
            except Exception:
                pass

        def _assign_me():
            login_value = (login or "").strip()
            if not login_value:
                login_value = ProfileService.get_active_user() or ""
            if not login_value:
                try:
                    import getpass

                    login_value = getpass.getuser()
                except Exception:
                    login_value = ""
            login_value = (login_value or "").strip()
            if not login_value:
                messagebox.showerror(
                    "Przypisanie",
                    "Nie udało się ustalić aktualnego loginu użytkownika.",
                )
                return
            _assign_selected(login_value)

        def _assign_to_user():
            user = simpledialog.askstring("Przypisz", "Podaj login użytkownika:")
            if user is None:
                return
            user_clean = user.strip()
            if not user_clean:
                messagebox.showwarning("Przypisanie", "Login nie może być pusty.")
                return
            _assign_selected(user_clean)

        def _clear_assignment():
            idx = _sel_idx()
            if idx < 0:
                return
            shaped = ensure_task_shape(tasks[idx])
            shaped["assigned_to"] = ""
            shaped.pop("assigned_ts", None)
            tasks[idx] = shaped
            repaint_tasks()
            try:
                tv.selection_set(str(idx))
                tv.focus(str(idx))
            except Exception:
                pass
        ttk.Button(tools_bar, text="Usuń zaznaczone", style="WM.Side.TButton",
                   command=_del_sel).pack(side="left", padx=(6,0))
        ttk.Button(tools_bar, text="Oznacz/Cofnij ✔", style="WM.Side.TButton",
                   command=_toggle_done).pack(side="left", padx=(6,0))

        task_menu_cls = getattr(tk, "Menu", None)
        if task_menu_cls is not None:
            task_menu = task_menu_cls(tv, tearoff=0)
            task_menu.add_command(label="Przypisz mnie", command=_assign_me)
            task_menu.add_command(label="Przypisz do użytkownika…", command=_assign_to_user)
            task_menu.add_separator()
            task_menu.add_command(label="Wyczyść przypisanie", command=_clear_assignment)

            def _show_task_menu(event):
                row = tv.identify_row(event.y)
                if row:
                    try:
                        tv.selection_set(row)
                        tv.focus(row)
                    except Exception:
                        pass
                try:
                    task_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    task_menu.grab_release()

            tv.bind("<Button-3>", _show_task_menu)

        def _update_global_tasks(comment, ts):
            path = _resolve_path_candidate(
                getattr(LZ, "TOOL_TASKS_PATH", None),
                _default_tools_tasks_file(),
            )
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = []

            if not isinstance(data, list):
                data = []

            changed = False
            for item in data:
                if not isinstance(item, dict):
                    continue
                if item.get("status") != "Zrobione":
                    item["status"] = "Zrobione"
                    item["by"] = login or "nieznany"
                    item["ts_done"] = ts
                    if comment:
                        item["komentarz"] = comment
                    changed = True
            if changed:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                except Exception as exc:
                    logger.error(
                        "[ERROR] Nie udało się zapisać globalnych zadań: %s", exc
                    )

        def _mark_all_done():
            comment = simpledialog.askstring(
                "Komentarz",
                "Komentarz do wykonania wszystkich zadań:",
                parent=dlg,
            )
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            for t in tasks:
                if not t.get("done"):
                    t["done"] = True
                    t["by"] = login or "nieznany"
                    t["ts_done"] = ts
                    if not t.get("status"):
                        t["status"] = (var_st.get() or "").strip()
                    _add_history_entry(
                        {
                            "ts": ts,
                            "by": login or "nieznany",
                            "action": "task_done",
                            "task_id": t.get("id") or t.get("task_id") or t.get("tytul"),
                            "title": t.get("tytul"),
                        },
                        refresh=False,
                    )
                    if comment:
                        t["komentarz"] = comment
            repaint_tasks()
            repaint_hist()
            _update_global_tasks(comment, ts)
            print("[WM-DBG][TASKS] marked all done")

        ttk.Button(
            tools_bar,
            text="Zaznacz wszystkie jako wykonane",
            style="WM.Side.TButton",
            command=_mark_all_done,
        ).pack(side="left", padx=(6,0))

        # --- PRZYCISKI ZAPISU ---
        btns = ttk.Frame(dlg, padding=8, style="WM.TFrame"); btns.pack(fill="x")

        def _suggest_after(n, mode_local):
            if mode_local == "NOWE":
                nxt = _next_free_in_range(max(1, n+1), 499)
            else:
                nxt = _next_free_in_range(max(500, n+1), 1000)
            return nxt or "—"

        def save(_event=None):
            nonlocal tool_path
            try:
                _sync_description_var()
                raw = (var_nr.get() or "").strip()
                numer = (f"{int(raw):03d}") if raw.isdigit() else raw.zfill(3)
                if (not numer.isdigit()) or len(numer) != 3:
                    raise ValueError("Numer musi mieć dokładnie 3 cyfry (np. 001).")
                nint = int(numer)

                raw_current = start.get("nr") or start.get("numer") or start.get("id") or start.get("number") or ""
                current_nr = str(raw_current).strip()
                if current_nr.isdigit():
                    current_nr = current_nr.zfill(3)
                else:
                    current_nr = ""
                if not current_nr and editing and tool_path:
                    try:
                        stem = Path(str(tool_path)).stem
                        current_nr = stem.zfill(3) if stem.isdigit() and len(stem) <= 3 else stem
                    except Exception:
                        current_nr = ""
                renamed = bool(editing and current_nr and numer != current_nr)

                will_convert = bool(tool_mode == "NOWE" and convert_var.get())
                mode_for_validation = "STARE" if will_convert else tool_mode
                number_changed = editing and (not current_nr or numer != current_nr)
                keep_effective = editing and keep_number_var.get() and not number_changed
                # TODO: Tymczasowo wyłączona walidacja zakresu SN (2025-12-30) – do usunięcia po dopięciu config.tools.sn_range
                if mode_for_validation != "NOWE":
                    if not (1 <= nint <= 1000):
                        raise ValueError("Dozwolone numery 001–1000.")
                else:
                    ok, msg = validate_number(
                        nint,
                        "NN" if mode_for_validation == "NOWE" else "SN",
                        is_new=not editing,
                        keep_number=keep_effective,
                    )
                    if not ok:
                        raise ValueError(msg or "Niepoprawny numer narzędzia.")

                if _is_taken(numer) and (not editing or not current_nr or numer != current_nr):
                    exist = _read_tool(numer) or {}
                    raise ValueError(
                        "Narzędzie %s już istnieje.\nNazwa: %s\nTyp: %s\nStatus: %s\n\nWybierz inny numer (np. %s)."
                        % (
                            numer,
                            exist.get("nazwa", "—"),
                            exist.get("typ", "—"),
                            exist.get("status", "—"),
                            _suggest_after(nint, mode_for_validation),
                        )
                    )

                nazwa = (var_nm.get() or "").strip()
                typ = (cb_ty.get() or "").strip()
                if not nazwa or not typ:
                    raise ValueError("Pola 'Nazwa' i 'Typ' są wymagane.")

                raw_status = (var_st.get() or "").strip()
                st_new = _normalize_status(raw_status)
                if not st_new:
                    raise ValueError("Status narzędzia jest wymagany.")

                allowed = _statusy_for_mode(tool_mode)
                status_values = [s for s in _status_values_list() if s]
                allowed_lower = {x.lower() for x in allowed}
                allowed_lower.update(s.lower() for s in status_values)
                if (st_new.lower() not in allowed_lower) and (raw_status.lower() not in allowed_lower):
                    raise ValueError(f"Status '{raw_status}' nie jest dozwolony.")

                # KONWERSJA: tylko jeśli NN, checkbox zaznaczony i rola pozwala
                tool_mode_local = tool_mode
                now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                if will_convert:
                    if not _can_convert_nn_to_sn(rola):
                        raise ValueError("Tę operację może wykonać tylko brygadzista.")
                    tool_mode_local = "STARE"

                    # co zrobić z zadaniami?
                    mode_tasks = convert_tasks_var.get()  # keep | replace | sum
                    if mode_tasks == "replace":
                        typ_val = (cb_ty.get() or "").strip()
                        serwis_tpl = _tasks_for_type(typ_val, "serwis")
                        tasks[:] = [
                            _prepare_new_task(
                                {
                                    "tytul": t,
                                    "done": False,
                                    "by": "",
                                    "ts_done": "",
                                    "assigned_to": "",
                                    "status": st_new,
                                    "source": "status_default",
                                }
                            )
                            for t in _clean_list(serwis_tpl)
                        ]
                    elif mode_tasks == "sum":
                        typ_val = (cb_ty.get() or "").strip()
                        serwis_tpl = _tasks_for_type(typ_val, "serwis")
                        existing_titles = {
                            (t.get("tytul") or "").strip() for t in tasks
                        }
                        for t in _clean_list(serwis_tpl):
                            title = str(t).strip()
                            if title and title not in existing_titles:
                                tasks.append(
                                    _prepare_new_task(
                                        {
                                            "tytul": title,
                                            "done": False,
                                            "by": "",
                                            "ts_done": "",
                                            "assigned_to": "",
                                            "status": st_new,
                                            "source": "status_default",
                                        }
                                    )
                                )
                                existing_titles.add(title)
                    # keep -> nic nie zmieniamy

                # FIX(TOOLS): zawsze bazuj na istniejącym rekordzie przy edycji
                data_existing = {}
                if editing:
                    try:
                        if tool_path and os.path.exists(str(tool_path)):
                            data_existing = _safe_tool_doc(str(tool_path))
                        elif current_nr:
                            data_existing = _read_tool(current_nr) or {}
                    except Exception:
                        data_existing = {}
                if not data_existing:
                    data_existing = _read_tool(numer) or {}
                historia = list(hist_items)
                st_prev = data_existing.get("status", start.get("status", st_new))
                st_prev_runtime = (prev_status[0] or st_prev).strip()

                # FIX(STATUS): usunięcie wymuszenia przejść sekwencyjnych 1 -> 2 -> 3.
                # Użytkownik ma móc zapisać dowolną zmianę statusu (np. 1 -> 3),
                # a historia ma odnotować realne przejście bez blokady statusu pośredniego.
                prev_label = st_prev_runtime or "brak"
                target_label = st_new or "—"

                tasks[:] = [ensure_task_shape(t) for t in tasks]
                existing_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
                for old_task in _norm_tasks(data_existing.get("zadania")):
                    shaped_old = ensure_task_shape(old_task)
                    key = (
                        shaped_old.get("tytul", ""),
                        shaped_old.get("date_added") or "",
                    )
                    existing_map.setdefault(key, []).append(
                        {
                            "done": bool(shaped_old.get("done")),
                            "date_done": shaped_old.get("date_done")
                            or shaped_old.get("ts_done")
                            or "",
                        }
                    )

                history_added: list[tuple[str, str]] = []
                history_done: list[tuple[str, str]] = []
                archived_tasks: list[dict[str, Any]] = list(
                    data_existing.get("zadania_archiwalne") or []
                )
                status_values = [s for s in _status_values_list() if s]
                first_status = status_values[0] if status_values else ""
                final_status = status_values[-1] if status_values else ""

                def _complete_open_tasks(status_label: str) -> None:
                    iso_now = _now_iso()
                    for idx, item in enumerate(list(tasks)):
                        shaped_item = ensure_task_shape(item)
                        if shaped_item.get("done"):
                            continue
                        shaped_item["done"] = True
                        shaped_item["by"] = login or "system"
                        shaped_item["ts_done"] = now_ts
                        if not shaped_item.get("date_added"):
                            shaped_item["date_added"] = iso_now
                        shaped_item["date_done"] = (
                            _normalize_date_value(shaped_item.get("date_done")) or iso_now
                        )
                        shaped_item["status"] = _clean_status(
                            shaped_item.get("status"), "done"
                        )
                        shaped_item["state"] = "done"
                        shaped_item["archived"] = True
                        shaped_item["archived_at"] = (
                            _normalize_date_value(shaped_item.get("archived_at")) or iso_now
                        )
                        tasks[idx] = shaped_item
                        history_done.append(
                            (shaped_item.get("tytul", ""), shaped_item.get("date_done") or iso_now)
                        )
                        archived_tasks.append(dict(shaped_item))
                for shaped_task in tasks:
                    key = (
                        shaped_task.get("tytul", ""),
                        shaped_task.get("date_added") or "",
                    )
                    pool = existing_map.get(key)
                    if pool:
                        prev = pool.pop(0)
                        if not pool:
                            existing_map.pop(key, None)
                        if not prev.get("done") and shaped_task.get("done"):
                            history_done.append(
                                (
                                    shaped_task.get("tytul", ""),
                                    shaped_task.get("date_done")
                                    or shaped_task.get("ts_done")
                                    or _now_iso(),
                                )
                            )
                    else:
                        history_added.append(
                            (
                                shaped_task.get("tytul", ""),
                                shaped_task.get("date_added") or _now_iso(),
                            )
                        )
                        if shaped_task.get("done"):
                            history_done.append(
                                (
                                    shaped_task.get("tytul", ""),
                                    shaped_task.get("date_done")
                                    or shaped_task.get("ts_done")
                                    or _now_iso(),
                                )
                            )

                tool_status = tool.get("status") if isinstance(tool, dict) else None
                prev_runtime = (
                    tool_status or start.get("status") or st_prev_runtime or ""
                ).strip()

                status_changed = prev_runtime.lower() != (st_new or "").strip().lower()

                wizyty = data_existing.get("wizyty")
                if not isinstance(wizyty, list):
                    wizyty = list(start.get("wizyty") or [])
                data_obj_wizyty = wizyty
                # historia: zmiana statusu
                if status_changed:
                    historia.append(
                        {
                            "ts": now_ts,
                            "by": (login or "nieznany"),
                            "action": "status_changed",
                            "typ": "status_changed",
                            "z": prev_runtime,
                            "na": st_new,
                        }
                    )
                    if (
                        first_status
                        and prev_runtime.lower() == first_status.lower()
                        and st_new.lower() != first_status.lower()
                    ):
                        start_entry = {
                            "start_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                            "start_by": login or "nieznany",
                            "from": prev_runtime,
                            "to": st_new,
                        }

                        data_obj_wizyty.append(start_entry)
                        if wizyty_data is not data_obj_wizyty:
                            wizyty_data.append(start_entry)

                        # każda wizyta = nowy zestaw zadań
                        tasks[:] = []
                        if isinstance(tool, dict):
                            tool["zadania"] = []

                    if (
                        first_status
                        and st_new.lower() == first_status.lower()
                        and prev_runtime.lower() != first_status.lower()
                    ):
                        visit_comment = simpledialog.askstring(
                            "Komentarz wizyty",
                            "Komentarz (opcjonalnie):",
                        )
                        cleaned_comment = (visit_comment or "").strip()

                        open_visit = None
                        for v in reversed(data_obj_wizyty):
                            if isinstance(v, dict) and v.get("start_ts") and not v.get("end_ts"):
                                open_visit = v
                                break

                        if open_visit is None:
                            open_visit = {
                                "start_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                "start_by": login or "nieznany",
                                "from": prev_runtime,
                                "to": prev_runtime,
                            }
                            data_obj_wizyty.append(open_visit)
                            if wizyty_data is not data_obj_wizyty:
                                wizyty_data.append(open_visit)

                        open_visit["end_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                        open_visit["end_by"] = login or "nieznany"
                        open_visit["to"] = st_new
                        open_visit["zadania"] = deepcopy(tasks)

                        if cleaned_comment:
                            open_visit["comment"] = cleaned_comment

                        tasks[:] = []
                        if isinstance(tool, dict):
                            tool["zadania"] = []

                        historia.append(
                            {
                                "ts": now_ts,
                                "by": login or "nieznany",
                                "action": "visit",
                                "typ": "cycle_closed",
                                "status": st_new,
                                "comment": cleaned_comment,
                            }
                        )
                # historia: zmiana trybu NN->SN
                if tool_mode != tool_mode_local:
                    historia.append(
                        {
                            "ts": now_ts,
                            "by": (login or "nieznany"),
                            "action": "mode_changed",
                            "z": "[tryb] NOWE",
                            "na": "[tryb] STARE",
                        }
                    )

                data_obj = {
                    "numer": numer,
                    "nazwa": nazwa,
                    "typ": typ,
                    "status": st_new,
                    "opis": (var_op.get() or "").strip(),
                    "pracownik": (var_pr.get() or "").strip(),
                    "zadania": tasks,
                    "data_dodania": data_existing.get("data_dodania") or start.get("data") or now_ts,
                    "tryb": tool_mode_local,
                    "interwencje": data_existing.get("interwencje", []),
                    "historia": historia,
                    "wizyty": data_obj_wizyty,
                    "zadania_archiwalne": archived_tasks,
                    "obrazy": list(images),
                    "obraz": images[0] if images else "",
                    "dxf": (var_dxf.get() or "").strip(),
                    "dxf_png": (var_dxf_png.get() or "").strip(),
                }
                if tool_mode_local == "STARE":
                    data_obj["is_old"] = True
                    data_obj["kategoria"] = "SN"
                if renamed:
                    data_obj["__prev_id__"] = current_nr
                    data_obj["__prev_path__"] = str(tool_path or "")

                _save_tool(data_obj)

                if renamed:
                    # FIX(TOOLS): aktualizacja stanu po zmianie numeru
                    start["nr"] = numer
                    start["numer"] = numer
                    start["id"] = numer
                    if isinstance(tool, dict):
                        tool["nr"] = numer
                        tool["numer"] = numer
                        tool["id"] = numer
                    try:
                        if tool_path:
                            STATE.tools_docs_cache.pop(_normalize_path(tool_path), None)
                    except Exception:
                        pass
                    try:
                        tool_path = str(Path(_resolve_tools_dir()) / f"{numer}.json")
                    except Exception:
                        tool_path = None
                if isinstance(tool, dict):
                    tool["status"] = st_new
                start["status"] = st_new
                try:
                    repaint_hist()
                except Exception:
                    pass
                try:
                    _refresh_visits_tree()
                except Exception:
                    pass
                if (st_prev_runtime or "").strip().lower() != (st_new or "").strip().lower():
                    _log_tool_history(
                        numer,
                        login,
                        "status_changed",
                        previous=st_prev_runtime,
                        current=st_new,
                        ts=_now_iso(),
                    )
                for title, ts_added in history_added:
                    if title:
                        _add_history_entry(
                            {
                                "ts": ts_added,
                                "by": login or "system",
                                "action": "task_added",
                                "task_id": title,
                                "title": title,
                            },
                            refresh=False,
                        )
                        _log_tool_history(numer, login, "task_added", task=title, ts=ts_added)
                for title, ts_done in history_done:
                    if title:
                        _add_history_entry(
                            {
                                "ts": ts_done,
                                "by": login or "system",
                                "action": "task_done",
                                "task_id": title,
                                "title": title,
                            },
                            refresh=False,
                        )
                        _log_tool_history(numer, login, "task_done", task=title, ts=ts_done)
                # NIE zamykamy okna po zapisie
                # dlg.destroy()
                saved_path = None
                if tool_path:
                    try:
                        saved_path = Path(tool_path)
                    except Exception:
                        saved_path = None
                if saved_path is None:
                    numer_val = str(
                        data_obj.get("numer")
                        or data_obj.get("nr")
                        or data_obj.get("id")
                        or ""
                    ).strip()
                    if numer_val:
                        saved_path = (
                            Path(_resolve_tools_dir()) / f"{numer_val.zfill(3)}.json"
                        )
                if saved_path is None or not _refresh_one_tool_row_by_path(
                    saved_path, data_obj
                ):
                    refresh_list()
                try:
                    _refresh_progress(delay_ms=0)
                except Exception:
                    pass
                # FIX(UI): po zapisie w oknie edycji pokaż krótkie potwierdzenie sukcesu.
                # Do tej pory zapis wykonywał się "po cichu", co wyglądało jak brak reakcji.
                try:
                    if editing:
                        messagebox.showinfo(
                            "Zapis zakończony",
                            f"Narzędzie {numer} zostało zapisane.",
                            parent=dlg,
                        )
                except Exception:
                    pass
            except ValueError as exc:
                messagebox.showerror("Błąd danych", str(exc), parent=dlg)
                logger.exception("[Narzędzia] Walidacja formularza narzędzia nie powiodła się")
            except Exception as exc:
                messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać narzędzia:\n{exc}", parent=dlg)
                logger.exception("[Narzędzia] Błąd podczas zapisu narzędzia")

        ttk.Button(btns, text="Zapisz", command=save, style="WM.Side.TButton").pack(side="right")
        ttk.Button(btns, text="Anuluj", command=dlg.destroy, style="WM.Side.TButton").pack(side="right", padx=(0, 8))
        ttk.Button(
            btns,
            text="Zamknij okno",
            command=dlg.destroy,
            style="WM.Side.TButton",
        ).pack(side="right", padx=(0, 8))
        dlg.bind("<Return>", save)

        # --- SKRÓTY KLAWISZOWE (dialog narzędzia) ---
        def _kb_save(event=None):
            try:
                save()
            finally:
                return "break"

        def _kb_close(event=None):
            try:
                dlg.destroy()
            finally:
                return "break"

        def _kb_refresh(event=None):
            try:
                repaint_tasks()
            except Exception:
                pass
            try:
                repaint_hist()
            except Exception:
                pass
            return "break"

        dlg.bind("<Control-s>", _kb_save)
        dlg.bind("<Escape>", _kb_close)
        dlg.bind("<Control-w>", _kb_close)
        dlg.bind("<F5>", _kb_refresh)

    global _ACTIVE_TOOL_EDITOR_OPENER, _ACTIVE_TOOL_EDITOR_ROOT
    _ACTIVE_TOOL_EDITOR_ROOT = root
    _ACTIVE_TOOL_EDITOR_OPENER = lambda tool: open_tool_dialog(tool)

    # ===================== BINDY / START =====================
    _dbg("Init panel_narzedzia – start listy")
    btn_add.configure(command=choose_mode_and_add)
    if tools_view is not None:
        tools_view.bind_open_detail(_open_tool_by_id)
    refresh_list()

__all__ = [
    "panel_narzedzia",
    "open_tool_editor_by_id",
    "open_tool_from_external_context",
    "_profiles_usernames",
    "_current_user",
    "_selected_task",
    "_asgn_assign",
    "_refresh_assignments_view",
]
# Koniec pliku
