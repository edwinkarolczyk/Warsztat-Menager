# version: 1.1
# Moduł: narzedzia_ui.editor_followup_runtime
# Drobne poprawki nowego edytora NN/SN po pomiarach z konsoli:
# - powiązania etapowe zapisują się bezpośrednio w WM_ROOT,
# - stary błędnie położony plik relacji jest bezpiecznie migrowany do WM_ROOT,
# - lista narzędzi dla powiązań nie otwiera zagnieżdżonej pętli Tk,
# - obrazy karuzeli są dekodowane raz na rozmiar i trzymane w cache okna,
# - dopasowanie okna nie wymusza synchronicznego update_idletasks(),
# - numer narzędzia jest zachowany dla powiązań etapowych po przebudowie nagłówka.

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox

from core import root_paths as _root_paths
from . import editor_variant_runtime as _variant
from . import multistage_runtime as _multistage


_REL_LOG_SIGNATURE: tuple[str, int, int] | None = None


def _root_relations_path() -> Path:
    return Path(_root_paths.get_root_anchor()) / _multistage._REL_FILE


def _legacy_relations_path() -> Path:
    return Path(_multistage._tools_dir()) / _multistage._REL_FILE


def _migrate_legacy_relations_if_needed() -> None:
    target = _root_relations_path()
    legacy = _legacy_relations_path()
    if target.is_file() or not legacy.is_file():
        return

    try:
        raw = json.loads(legacy.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("plik relacji nie zawiera obiektu JSON")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, target)
        print(
            "[WM-DBG][TOOLS_EDITOR][MULTISTAGE] MIGRATE "
            f"{legacy} -> {target}"
        )
    except Exception as exc:
        print(
            "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] MIGRATE "
            f"source={legacy} target={target} "
            f"{type(exc).__name__}: {exc}"
        )


def _remember_editor_number(window: tk.Toplevel, value: object) -> str:
    nr = _multistage._norm_nr(value)
    if not (nr.isdigit() and len(nr) == 3):
        return ""
    try:
        window._wm_tool_number = nr  # type: ignore[attr-defined]
    except Exception:
        pass
    return nr


def _install_multistage_number_source() -> None:
    """Zachowaj numer edytowanego narzędzia zanim nowy nagłówek ukryje stary UI."""

    current_build_header = getattr(_variant, "_build_header", None)
    if callable(current_build_header) and not getattr(
        current_build_header, "_wm_multistage_number_capture", False
    ):
        original_build_header = current_build_header

        def _build_header_with_number(window, header, colors):
            try:
                _remember_editor_number(
                    window,
                    _variant._entry_value_from_field(window, "Numer (3 cyfry)"),
                )
            except Exception:
                pass
            return original_build_header(window, header, colors)

        _build_header_with_number._wm_multistage_number_capture = True  # type: ignore[attr-defined]
        _build_header_with_number._wm_multistage_number_original = original_build_header  # type: ignore[attr-defined]
        _variant._build_header = _build_header_with_number

    current_nr = getattr(_multistage, "_current_nr", None)
    if not callable(current_nr) or getattr(current_nr, "_wm_canonical_number", False):
        return
    original_current_nr = current_nr

    def _current_nr_canonical(window: tk.Toplevel) -> str:
        # Najpierw odczyt bieżącego formularza. Dla nowego narzędzia numer może
        # jeszcze zostać wybrany przed pierwszym zapisem.
        try:
            live = _remember_editor_number(window, original_current_nr(window))
        except Exception:
            live = ""
        if live:
            return live

        remembered = _multistage._norm_nr(
            getattr(window, "_wm_tool_number", "")
        )
        if remembered.isdigit() and len(remembered) == 3:
            return remembered

        # Ostatni bezpieczny fallback: po zbudowaniu nowego widoku tytuł ma
        # postać „Narzędzie 512 — ... [SN]”. Nie zgadujemy innych liczb.
        try:
            title = str(window.title() or "")
        except Exception:
            title = ""
        match = re.search(r"\bNarzędzie\s+(\d{3})\b", title, re.IGNORECASE)
        if match:
            return _remember_editor_number(window, match.group(1))
        return ""

    _current_nr_canonical._wm_canonical_number = True  # type: ignore[attr-defined]
    _current_nr_canonical._wm_canonical_number_original = original_current_nr  # type: ignore[attr-defined]
    _multistage._current_nr = _current_nr_canonical


def _install_multistage_root_and_diagnostics() -> None:
    global _REL_LOG_SIGNATURE

    # Wszystkie istniejące funkcje multistage wywołują _relations_path()
    # dynamicznie, więc wystarczy podmienić jedno źródło ścieżki.
    _multistage._relations_path = _root_relations_path

    original_read = _multistage._read_relations
    if not getattr(original_read, "_wm_followup_wrapped", False):
        def _read_relations_rooted():
            global _REL_LOG_SIGNATURE
            _migrate_legacy_relations_if_needed()
            started = time.perf_counter()
            try:
                groups = original_read()
            except Exception as exc:
                print(
                    "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] LOAD "
                    f"path={_root_relations_path()} "
                    f"{type(exc).__name__}: {exc}"
                )
                raise

            path = _root_relations_path()
            try:
                stat = path.stat()
                signature = (str(path), int(stat.st_mtime_ns), len(groups))
            except OSError:
                signature = (str(path), 0, len(groups))

            if signature != _REL_LOG_SIGNATURE:
                _REL_LOG_SIGNATURE = signature
                elapsed = (time.perf_counter() - started) * 1000.0
                print(
                    "[WM-DBG][TOOLS_EDITOR][MULTISTAGE] LOAD "
                    f"path={path} groups={len(groups)} time={elapsed:.1f}ms"
                )
            return groups

        _read_relations_rooted._wm_followup_wrapped = True
        _multistage._read_relations = _read_relations_rooted

    original_write = _multistage._write_relations
    if not getattr(original_write, "_wm_followup_wrapped", False):
        def _write_relations_rooted(groups):
            started = time.perf_counter()
            try:
                result = original_write(groups)
            except Exception as exc:
                print(
                    "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] SAVE "
                    f"path={_root_relations_path()} "
                    f"{type(exc).__name__}: {exc}"
                )
                raise
            elapsed = (time.perf_counter() - started) * 1000.0
            print(
                "[WM-DBG][TOOLS_EDITOR][MULTISTAGE] SAVE "
                f"path={_root_relations_path()} groups={len(groups)} "
                f"time={elapsed:.1f}ms"
            )
            return result

        _write_relations_rooted._wm_followup_wrapped = True
        _multistage._write_relations = _write_relations_rooted

    original_relation_editor = _multistage._relation_editor
    if not getattr(original_relation_editor, "_wm_followup_wrapped", False):
        def _relation_editor_logged(window: tk.Toplevel, on_saved) -> None:
            nr = _multistage._current_nr(window)
            # Lista wyboru ma być świeża przy każdym jawnym otwarciu edycji etapów.
            _multistage._META_CACHE = None
            print(
                "[WM-DBG][TOOLS_EDITOR][MULTISTAGE] OPEN "
                f"nr={nr or '-'} path={_root_relations_path()}"
            )
            try:
                return original_relation_editor(window, on_saved)
            except Exception as exc:
                print(
                    "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] OPEN "
                    f"nr={nr or '-'} {type(exc).__name__}: {exc}"
                )
                try:
                    messagebox.showerror(
                        "Powiązane narzędzia",
                        "Nie udało się otworzyć powiązań etapowych.\n"
                        "Szczegóły błędu zapisano w konsoli WM.",
                        parent=window,
                    )
                except Exception:
                    pass
                return None

        _relation_editor_logged._wm_followup_wrapped = True
        _multistage._relation_editor = _relation_editor_logged

    original_decorate = _multistage._decorate_multistage
    if not getattr(original_decorate, "_wm_followup_wrapped", False):
        def _decorate_multistage_logged(window: tk.Toplevel) -> None:
            try:
                return original_decorate(window)
            except Exception as exc:
                print(
                    "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] DECORATE "
                    f"{type(exc).__name__}: {exc}"
                )
                raise

        _decorate_multistage_logged._wm_followup_wrapped = True
        _multistage._decorate_multistage = _decorate_multistage_logged


def _install_fast_multistage_meta_loader() -> None:
    current = _multistage._load_tool_meta_cache
    if getattr(current, "_wm_followup_loader", False):
        return

    def _load_tool_meta_cache_fast(
        owner: tk.Misc | None = None,
        *,
        force: bool = False,
    ) -> dict[str, dict[str, Any]]:
        # owner zostaje w sygnaturze dla zgodności, ale nie tworzymy już
        # dodatkowego Toplevel ani nie wywołujemy wait.update().
        del owner

        if _multistage._META_CACHE is not None and not force:
            return _multistage._META_CACHE

        started = time.perf_counter()
        cache: dict[str, dict[str, Any]] = {}
        base = Path(_multistage._tools_dir())

        try:
            candidates = sorted(base.glob("*.json"))
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][MULTISTAGE] TOOLS_LOAD "
                f"base={base} {type(exc).__name__}: {exc}"
            )
            candidates = []

        errors = 0
        for path in candidates:
            stem = path.stem.strip()
            if not stem.isdigit() or len(stem) > 3:
                continue
            nr = stem.zfill(3)
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                errors += 1
                continue
            if not isinstance(raw, dict):
                continue

            cache[nr] = {
                "nr": nr,
                "nazwa": str(raw.get("nazwa") or "").strip(),
                "typ": str(raw.get("typ") or "").strip(),
                "status": str(raw.get("status") or "").strip(),
                "tryb": str(raw.get("tryb") or raw.get("mode") or "").strip(),
                "obrazy": (
                    raw.get("obrazy")
                    if isinstance(raw.get("obrazy"), list)
                    else []
                ),
                "obraz": str(raw.get("obraz") or "").strip(),
                "dxf_png": str(raw.get("dxf_png") or "").strip(),
            }

        _multistage._META_CACHE = cache
        elapsed = (time.perf_counter() - started) * 1000.0
        print(
            "[WM-PERF][TOOLS_EDITOR][MULTISTAGE] TOOLS_LOAD "
            f"count={len(cache)} errors={errors} time={elapsed:.1f}ms"
        )
        return cache

    _load_tool_meta_cache_fast._wm_followup_loader = True
    _multistage._load_tool_meta_cache = _load_tool_meta_cache_fast


def _install_nonblocking_fit_window() -> None:
    current = getattr(_variant, "_fit_window", None)
    if not callable(current) or getattr(current, "_wm_followup_fit", False):
        return

    def _fit_window_fast(window: tk.Toplevel) -> None:
        started = time.perf_counter()
        try:
            # Wymiary wynikają wyłącznie z ekranu, więc nie trzeba przed nimi
            # wymuszać pełnego przeliczenia layoutu przez update_idletasks().
            sw = max(800, int(window.winfo_screenwidth()))
            sh = max(600, int(window.winfo_screenheight()))
            width = min(1420, max(760, sw - 60))
            height = min(900, max(560, sh - 100))
            x = max(0, (sw - width) // 2)
            y = max(0, (sh - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
            window.minsize(min(1120, width), min(680, height))
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][FIT] "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            print(
                "[WM-PERF][TOOLS_EDITOR][FIT] "
                f"bez update_idletasks={elapsed:.1f}ms"
            )

    _fit_window_fast._wm_followup_fit = True
    _fit_window_fast._wm_followup_original = current
    _variant._fit_window = _fit_window_fast


def _install_photo_cache() -> None:
    current = getattr(_variant, "_load_photo", None)
    if not callable(current) or getattr(current, "_wm_followup_photo_cache", False):
        return
    original = current

    def _load_photo_cached(
        path: Path,
        master: tk.Misc,
        max_size: tuple[int, int],
    ):
        file_path = Path(path)
        try:
            stat = file_path.stat()
            file_token = (
                os.path.normcase(os.path.abspath(str(file_path))),
                int(stat.st_mtime_ns),
                int(stat.st_size),
            )
        except OSError:
            file_token = (
                os.path.normcase(os.path.abspath(str(file_path))),
                0,
                0,
            )

        try:
            owner = master.winfo_toplevel()
        except Exception:
            owner = master

        cache = getattr(owner, "_wm_editor_photo_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            try:
                owner._wm_editor_photo_cache = cache
            except Exception:
                pass

        key = (*file_token, int(max_size[0]), int(max_size[1]))
        cached = cache.get(key)
        if cached is not None:
            return cached

        photo = original(file_path, master, max_size)
        if photo is not None:
            cache[key] = photo
        return photo

    _load_photo_cached._wm_followup_photo_cache = True
    _load_photo_cached._wm_followup_original = original
    _variant._load_photo = _load_photo_cached


def install_editor_followup_runtime() -> None:
    if getattr(_variant, "_wm_editor_followup_installed", False):
        return

    _install_multistage_number_source()
    _install_multistage_root_and_diagnostics()
    _install_fast_multistage_meta_loader()
    _install_nonblocking_fit_window()
    _install_photo_cache()

    _variant._wm_editor_followup_installed = True
    print(
        "[WM-DBG][TOOLS_EDITOR] followup runtime aktywny "
        f"relations={_root_relations_path()}"
    )


__all__ = ["install_editor_followup_runtime"]
