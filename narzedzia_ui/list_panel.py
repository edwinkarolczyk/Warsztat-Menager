# version: 1.0
"""Widok listy narzędzi wydzielony z głównego modułu GUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable, Mapping, Sequence

import tkinter as tk
from tkinter import messagebox, ttk

# FIX(PREVIEW): obsługa JPG/JPEG/PNG przez Pillow
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from ui_theme import ensure_theme_applied
from narzedzia_ui.detail_view import open_tool_detail
from narzedzia_ui.state import STATE
from tools_templates import load_default_templates


def _tool_id(tool: Mapping[str, Any]) -> str:
    return str(tool.get("id") or tool.get("nr") or tool.get("numer") or "")


def _tool_name(tool: Mapping[str, Any]) -> str:
    return str(tool.get("nazwa") or tool.get("name") or "")


def _tool_type_label(tool: Mapping[str, Any]) -> str:
    return str(tool.get("typ") or tool.get("typ_narzedzia") or tool.get("type") or "")


def _tool_status_label(tool: Mapping[str, Any]) -> str:
    value = tool.get("status") or tool.get("status_aktualny") or tool.get(
        "aktualny_status"
    ) or ""
    if isinstance(value, dict):
        return str(value.get("nazwa") or value.get("name") or "")
    return str(value or "")


def _tool_status_first(tool: Mapping[str, Any], statuses: Any | None = None) -> str:
    if statuses is None:
        statuses = tool.get("statusy") or tool.get("statuses") or []
    if isinstance(statuses, Mapping):
        return str(statuses.get("nazwa") or statuses.get("name") or "")
    if isinstance(statuses, Sequence) and not isinstance(statuses, (str, bytes)):
        if statuses:
            first = statuses[0]
            if isinstance(first, Mapping):
                return str(first.get("nazwa") or first.get("name") or "")
            return str(first or "")
        return ""
    return str(statuses or "")


def _tool_mode_label(tool: Mapping[str, Any]) -> str:
    candidate_keys = ("nn_sn", "nn/sn", "rodzaj", "oznaczenie", "tag_nn_sn")
    raw = None
    for key in candidate_keys:
        if key in tool:
            raw = tool.get(key)
            break
    if raw is None:
        return ""
    val = str(raw).strip().upper()
    if val in {"NN", "SN", "NOWE", "STARE"}:
        return val
    return ""


def _is_nn_sn(tool: Mapping[str, Any]) -> bool:
    return bool(_tool_mode_label(tool))


def _tool_status_last(tool: Mapping[str, Any], statuses: Any | None = None) -> str:
    if statuses is None:
        statuses = tool.get("statusy") or tool.get("statuses") or []
    if isinstance(statuses, Mapping):
        return str(statuses.get("nazwa") or statuses.get("name") or "")
    if isinstance(statuses, Sequence) and not isinstance(statuses, (str, bytes)):
        if statuses:
            last = statuses[-1]
            if isinstance(last, Mapping):
                return str(last.get("nazwa") or last.get("name") or "")
            return str(last or "")
        return ""
    return str(statuses or "")


def _tool_visits(tool: Mapping[str, Any]) -> list:
    visits = tool.get("wizyty") or tool.get("visits") or []
    return visits if isinstance(visits, list) else []


def _visit_start_iso(visit: Mapping[str, Any]) -> str:
    return str(visit.get("start") or visit.get("ts") or visit.get("start_ts") or "")


def _tool_current_visit_start(tool: Mapping[str, Any]) -> str:
    visits = _tool_visits(tool)
    if not visits:
        return ""
    last = visits[-1]
    return _visit_start_iso(last) if isinstance(last, Mapping) else ""


def _pretty_dt(value: str) -> str:
    if not value:
        return "—"
    value = str(value)
    value = value.replace("T", " ")
    if len(value) >= 16:
        return value[:16]
    return value


def _pretty_dt_pl(value: str) -> str:
    """Format daty do tabel: dd-mm-rr hh:mm."""

    if not value:
        return "—"
    raw = str(value or "").strip()
    if not raw:
        return "—"
    if "T" not in raw and " " in raw:
        raw = raw.replace(" ", "T", 1)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        fallback = raw.replace("T", " ")
        return fallback[:16] if len(fallback) >= 16 else fallback
    return parsed.strftime("%d-%m-%y %H:%M")


def _parse_visit_dt(value: str):
    """Bezpiecznie parsuje timestamp wizyty z JSON."""

    raw = str(value or "").strip()
    if not raw:
        return None
    if "T" not in raw and " " in raw:
        raw = raw.replace(" ", "T", 1)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _visit_end_iso(visit: Mapping[str, Any]) -> str:
    return str(
        visit.get("end")
        or visit.get("koniec")
        or visit.get("stop")
        or visit.get("end_ts")
        or visit.get("closed_at")
        or ""
    )


def _human_duration_from_seconds(seconds: float) -> str:
    """Czytelny czas: <24h w godzinach, potem dni, potem miesiące."""

    if seconds <= 0:
        return "0h"

    hours = int(seconds // 3600)
    if hours < 24:
        return f"{max(1, hours)}h"

    days = hours // 24
    rem_hours = hours % 24

    if days < 30:
        if rem_hours and days < 7:
            return f"{days}d {rem_hours}h"
        return f"{days}d"

    months = days // 30
    rem_days = days % 30
    if months < 12:
        return f"{months} mies. {rem_days}d" if rem_days else f"{months} mies."

    years = months // 12
    rem_months = months % 12
    return f"{years}r {rem_months} mies." if rem_months else f"{years}r"


def _visit_duration_label(tool: Mapping[str, Any]) -> str:
    """Zwraca czas trwania aktualnej/ostatniej wizyty w ludzkim formacie."""

    visits = _tool_visits(tool)
    if not visits:
        return "—"
    last = visits[-1]
    if not isinstance(last, Mapping):
        return "—"

    start = _parse_visit_dt(_visit_start_iso(last))
    if start is None:
        return "—"

    end = _parse_visit_dt(_visit_end_iso(last))
    if end is None:
        end = datetime.now(tz=start.tzinfo) if start.tzinfo else datetime.now()

    return _human_duration_from_seconds((end - start).total_seconds())


def _visit_closed_at_iso(visit: Mapping[str, Any]) -> str:
    return str(
        visit.get("end")
        or visit.get("koniec")
        or visit.get("stop")
        or visit.get("end_ts")
        or visit.get("closed_at")
        or visit.get("data_powrotu")
        or visit.get("returned_at")
        or ""
    )


def _visit_closed_by(visit: Mapping[str, Any]) -> str:
    return str(
        visit.get("closed_by")
        or visit.get("end_by")
        or visit.get("returned_by")
        or visit.get("zmienione_przez")
        or visit.get("changed_by")
        or visit.get("by")
        or visit.get("login")
        or ""
    ).strip()


def _last_closed_visit(tool: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Zwraca ostatnią wizytę z datą zakończenia."""

    closed: list[Mapping[str, Any]] = []
    for visit in _tool_visits(tool):
        if not isinstance(visit, Mapping):
            continue
        if _visit_closed_at_iso(visit):
            closed.append(visit)
    if not closed:
        return None

    def _sort_key(visit: Mapping[str, Any]):
        parsed = _parse_visit_dt(_visit_closed_at_iso(visit))
        return parsed or datetime.min

    return sorted(closed, key=_sort_key)[-1]


def _tool_last_closed_visit_date(tool: Mapping[str, Any]) -> str:
    visit = _last_closed_visit(tool)
    if visit is None:
        return "—"
    return _pretty_dt_pl(_visit_closed_at_iso(visit))


def _tool_last_closed_visit_by(tool: Mapping[str, Any]) -> str:
    visit = _last_closed_visit(tool)
    if visit is None:
        return "—"
    return _visit_closed_by(visit) or "—"


def _tool_total_visits_duration_label(tool: Mapping[str, Any]) -> str:
    """Łączny czas wizyt narzędzia w ludzkim formacie."""

    total_seconds = 0.0
    now_cache: datetime | None = None

    for visit in _tool_visits(tool):
        if not isinstance(visit, Mapping):
            continue
        start = _parse_visit_dt(_visit_start_iso(visit))
        if start is None:
            continue
        end = _parse_visit_dt(_visit_closed_at_iso(visit))
        if end is None:
            if now_cache is None:
                now_cache = datetime.now(tz=start.tzinfo) if start.tzinfo else datetime.now()
            end = now_cache
        total_seconds += max(0.0, (end - start).total_seconds())

    return _human_duration_from_seconds(total_seconds) if total_seconds > 0 else "—"


def _tool_visits_count(tool: Mapping[str, Any]) -> int:
    return len(_tool_visits(tool))


def _tool_tasks(tool: Mapping[str, Any]) -> list:
    tasks = tool.get("zadania") or tool.get("tasks") or []
    return tasks if isinstance(tasks, list) else []


def _task_done(task: Mapping[str, Any]) -> bool:
    return bool(task.get("done") is True)


def _task_title(task: Mapping[str, Any]) -> str:
    return str(task.get("tytul") or task.get("title") or task.get("nazwa") or "")


def _task_assigned(task: Mapping[str, Any]) -> str:
    return str(
        task.get("assigned_to") or task.get("przypisane") or task.get("do_kogo") or ""
    )


def _task_done_date(task: Mapping[str, Any]) -> str:
    return str(
        task.get("date_done")
        or task.get("ts_done")
        or task.get("done_ts")
        or task.get("done_at")
        or task.get("data_wykonania")
        or ""
    )


def _task_done_by(task: Mapping[str, Any]) -> str:
    return str(task.get("done_by") or task.get("wykonal") or "")


def _tool_tasks_counts(tool: Mapping[str, Any]) -> tuple[int, int]:
    tasks = _tool_tasks(tool)
    total = len(tasks)
    active = sum(1 for item in tasks if isinstance(item, Mapping) and not _task_done(item))
    return active, total


def _tool_progress_pct(tool: Mapping[str, Any]) -> str:
    tasks = _tool_tasks(tool)
    if not tasks:
        try:
            progress = int(tool.get("postep", 0))
        except (TypeError, ValueError):
            progress = 0
        return f"{max(0, min(100, progress))}%"
    total = len(tasks)
    done = sum(1 for item in tasks if isinstance(item, Mapping) and _task_done(item))
    pct = int(round((done / total) * 100)) if total else 0
    return f"{pct}%"


def _progress_value(progress_text: str) -> int:
    """Zwraca liczbę 0-100 z tekstu typu '75%'."""

    raw = str(progress_text or "").strip().replace("%", "")
    try:
        value = int(float(raw.replace(",", ".")))
    except (TypeError, ValueError):
        value = 0
    return max(0, min(100, value))


def _progress_tag(progress_text: str) -> str:
    """Dobiera tag koloru do postępu narzędzia."""

    progress = _progress_value(progress_text)
    if progress <= 0:
        return "progress_0"
    if progress < 50:
        return "progress_low"
    if progress < 90:
        return "progress_mid"
    if progress < 100:
        return "progress_high"
    return "progress_done"


REFRESH_INTERVAL_SECONDS = 30


class ToolsThreeTabsView(ttk.Frame):
    """Zakładki: Narzędzia (w toku), Lista narzędzi, Zadania."""

    def __init__(
        self,
        master,
        tools_provider: Callable[[], list[Mapping[str, Any]]],
        save_tool: Callable[[Mapping[str, Any]], None] | None = None,
        status_first_resolver: Callable[[Mapping[str, Any]], Any] | None = None,
        status_last_resolver: Callable[[Mapping[str, Any]], Any] | None = None,
        actor_login_resolver: Callable[[], str] | None = None,
        **kw,
    ) -> None:
        super().__init__(master, **kw)
        self.tools_provider = tools_provider
        self.save_tool = save_tool
        self.status_first_resolver = status_first_resolver
        self.status_last_resolver = status_last_resolver
        self.actor_login_resolver = actor_login_resolver
        self._refresh_job: str | None = None
        self._refresh_countdown_job: str | None = None
        self._seconds_until_refresh = REFRESH_INTERVAL_SECONDS
        self._open_detail_callback: Callable[[str], None] | None = None
        self._tools_context_menu: tk.Menu | None = None
        self._sort_state: dict[ttk.Treeview, tuple[str, bool]] = {}

        self.refresh_info = ttk.Label(
            self,
            text=f"Odświeżanie za: {self._seconds_until_refresh} s",
            anchor="w",
        )
        self.refresh_info.pack(fill="x", padx=8, pady=(8, 0))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_in_progress = ttk.Frame(self.nb)
        self.nb.add(self.tab_in_progress, text="Narzędzia")

        self.tab_all = ttk.Frame(self.nb)
        self.nb.add(self.tab_all, text="Lista narzędzi")

        self.tab_tasks = ttk.Frame(self.nb)
        self.nb.add(self.tab_tasks, text="Zadania")

        self._build_tab_in_progress()
        self._build_tab_all()
        self._build_tab_tasks()
        self._build_tools_context_menu()
        self._schedule_refresh()

    def bind_open_detail(self, callback: Callable[[str], None]) -> None:
        self._open_detail_callback = callback
        self._bind_double_click(self.tv_inprog)
        self._bind_double_click(self.tv_all)
        self._bind_context_menu(self.tv_inprog)
        self._bind_context_menu(self.tv_all)

    def _bind_double_click(self, tree: ttk.Treeview) -> None:
        def _on_double_click(_event) -> None:
            if not self._open_detail_callback:
                return
            try:
                row_id = tree.selection()[0]
            except IndexError:
                row_id = ""
            if not row_id:
                return
            values = tree.item(row_id, "values") or []
            if not values:
                return
            tool_id = str(values[0])
            if tool_id:
                self._open_detail_callback(tool_id)

        tree.bind("<Double-1>", _on_double_click)

    def _build_tools_context_menu(self) -> None:
        """Buduje wspólne menu PPM dla list narzędzi."""
        try:
            menu = tk.Menu(self, tearoff=0)
        except Exception:
            self._tools_context_menu = None
            return
        menu.add_command(label="Otwórz", command=self._open_context_selected_tool)
        menu.add_command(
            label="Podgląd plików", command=self._preview_context_selected_tool_files
        )
        self._tools_context_menu = menu
        self._context_tree: ttk.Treeview | None = None
        self._context_row_id: str = ""

    def _bind_context_menu(self, tree: ttk.Treeview) -> None:
        """Podpina menu PPM do wskazanego Treeview."""

        def _on_right_click(event) -> str | None:
            row_id = tree.identify_row(event.y)
            if not row_id:
                return None
            try:
                tree.selection_set(row_id)
                tree.focus(row_id)
                tree.see(row_id)
            except Exception:
                pass
            self._context_tree = tree
            self._context_row_id = row_id
            if self._tools_context_menu is not None:
                try:
                    self._tools_context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    try:
                        self._tools_context_menu.grab_release()
                    except Exception:
                        pass
            return "break"

        tree.bind("<Button-3>", _on_right_click)

    def _context_selected_tool_id(self) -> str:
        """Zwraca ID narzędzia z rekordu wybranego przez PPM."""
        tree = getattr(self, "_context_tree", None)
        row_id = getattr(self, "_context_row_id", "") or ""
        if tree is None or not row_id:
            return ""
        try:
            values = tree.item(row_id, "values") or []
        except Exception:
            values = []
        if not values:
            return ""
        return str(values[0] or "").strip()

    def _open_context_selected_tool(self) -> None:
        """Otwiera narzędzie wybrane menu PPM."""
        if not self._open_detail_callback:
            return
        tool_id = self._context_selected_tool_id()
        if tool_id:
            self._open_detail_callback(tool_id)

    def _preview_context_selected_tool_files(self) -> None:
        """Otwiera okno podglądu plików dla narzędzia wybranego przez PPM."""
        tool_id = self._context_selected_tool_id()
        if not tool_id:
            return
        tools = self._get_tools()
        tool = self._find_tool_by_id(tools, tool_id)
        if not tool:
            messagebox.showinfo(
                "Podgląd plików",
                "Nie znaleziono danych narzędzia.",
                parent=self,
            )
            return
        self._open_files_preview_dialog(tool)

    def _tool_media_candidates(self, tool: Mapping[str, Any]) -> dict[str, list[str]]:
        """
        Zwraca listy istniejących plików powiązanych z narzędziem.
        Wspiera:
        - obrazy z pól obraz / obrazy
        - dxf
        - dxf_png
        - pliki pdf znalezione obok JSON-a narzędzia
        """
        tool_id = _tool_id(tool).strip()
        base_dir = None
        try:
            from gui_narzedzia import _resolve_tools_dir

            base_dir = Path(_resolve_tools_dir())
        except Exception:
            base_dir = None

        def _resolve_existing(rel_or_abs: str) -> str | None:
            raw = str(rel_or_abs or "").strip()
            if not raw:
                return None
            candidate = Path(raw)
            if not candidate.is_absolute() and base_dir is not None:
                candidate = base_dir / raw
            try:
                if candidate.exists() and candidate.is_file():
                    return str(candidate)
            except Exception:
                return None
            return None

        images: list[str] = []
        seen: set[str] = set()
        for key in ("obrazy", "obraz"):
            value = tool.get(key)
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                continue
            for item in value:
                path = _resolve_existing(str(item))
                if not path:
                    continue
                lower = path.lower()
                if lower in seen:
                    continue
                if os.path.splitext(lower)[1] not in {".jpg", ".jpeg", ".png"}:
                    continue
                seen.add(lower)
                images.append(path)

        dxf_files: list[str] = []
        dxf_path = _resolve_existing(str(tool.get("dxf") or ""))
        if dxf_path:
            dxf_files.append(dxf_path)

        dxf_previews: list[str] = []
        dxf_png_path = _resolve_existing(str(tool.get("dxf_png") or ""))
        if dxf_png_path:
            dxf_previews.append(dxf_png_path)

        pdf_files: list[str] = []
        if base_dir is not None and tool_id:
            try:
                for path in sorted(base_dir.glob(f"{tool_id}*.pdf")):
                    if path.is_file():
                        pdf_files.append(str(path))
            except Exception:
                pass

        return {
            "images": images,
            "pdfs": pdf_files,
            "dxfs": dxf_files,
            "dxf_previews": dxf_previews,
        }

    def _open_path_system(self, path: str) -> None:
        """Otwiera plik systemowo w Windows."""
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return
        except Exception:
            pass
        try:
            subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
        except Exception as exc:
            messagebox.showerror(
                "Podgląd plików",
                f"Nie udało się otworzyć pliku:\n{path}\n\n{exc}",
                parent=self,
            )

    def _open_files_preview_dialog(self, tool: Mapping[str, Any]) -> None:
        """Pokazuje okno podglądu plików powiązanych z narzędziem."""
        media = self._tool_media_candidates(tool)
        images = list(media.get("images") or [])
        pdfs = list(media.get("pdfs") or [])
        dxfs = list(media.get("dxfs") or [])
        dxf_previews = list(media.get("dxf_previews") or [])

        if not images and not pdfs and not dxfs and not dxf_previews:
            messagebox.showinfo(
                "Podgląd plików",
                "To narzędzie nie ma powiązanych plików do podglądu.",
                parent=self,
            )
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Podgląd plików — {_tool_id(tool)}")
        try:
            ensure_theme_applied(dlg)
        except Exception:
            pass
        try:
            dlg.transient(self.winfo_toplevel())
        except Exception:
            pass

        outer = ttk.Frame(dlg, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=f"Narzędzie {_tool_id(tool)} — {_tool_name(tool)}",
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=f"Typ: {_tool_type_label(tool)}   Status: {_tool_status_label(tool)}",
        ).pack(anchor="w", pady=(0, 8))

        preview_frame = ttk.LabelFrame(outer, text="Podgląd")
        preview_frame.pack(fill="both", expand=True)

        preview_label = ttk.Label(preview_frame, text="Brak obrazu do wyświetlenia")
        preview_label.pack(fill="both", expand=True, padx=8, pady=8)

        preview_paths = images[:] or dxf_previews[:]
        preview_index = {"value": 0}
        preview_photo = {"value": None}

        def _render_preview() -> None:
            if not preview_paths:
                preview_label.configure(text="Brak obrazu do wyświetlenia", image="")
                preview_photo["value"] = None
                return
            idx = max(0, min(preview_index["value"], len(preview_paths) - 1))
            preview_index["value"] = idx
            path = preview_paths[idx]
            try:
                # FIX: PhotoImage nie ogarnia dobrze JPG → używamy Pillow
                if Image is not None and ImageTk is not None:
                    pil_img = Image.open(path)
                    max_w = 900
                    max_h = 520
                    try:
                        pil_img.thumbnail((max_w, max_h))
                    except Exception:
                        pass
                    img = ImageTk.PhotoImage(pil_img)
                else:
                    # fallback (np. tylko PNG)
                    img = tk.PhotoImage(file=path)
                preview_photo["value"] = img
                preview_label.configure(image=img, text="")
            except Exception:
                preview_photo["value"] = None
                preview_label.configure(
                    image="",
                    text=(
                        f"Nie udało się wyświetlić podglądu:\n{os.path.basename(path)}\n\n"
                        "Sprawdź plik lub czy Pillow jest zainstalowane."
                    ),
                )

        nav = ttk.Frame(outer)
        nav.pack(fill="x", pady=(8, 0))

        def _prev_preview() -> None:
            if not preview_paths:
                return
            preview_index["value"] = (preview_index["value"] - 1) % len(preview_paths)
            _render_preview()

        def _next_preview() -> None:
            if not preview_paths:
                return
            preview_index["value"] = (preview_index["value"] + 1) % len(preview_paths)
            _render_preview()

        ttk.Button(nav, text="Poprzednie", command=_prev_preview).pack(side="left")
        ttk.Button(nav, text="Następne", command=_next_preview).pack(
            side="left", padx=(6, 0)
        )

        files_box = ttk.LabelFrame(outer, text="Pliki")
        files_box.pack(fill="x", pady=(10, 0))

        pdf_path = pdfs[0] if pdfs else ""
        dxf_path = dxfs[0] if dxfs else ""

        ttk.Label(
            files_box,
            text=f"PDF: {os.path.basename(pdf_path) if pdf_path else 'brak'}",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(
            files_box,
            text="Otwórz PDF",
            command=lambda: self._open_path_system(pdf_path) if pdf_path else None,
        ).grid(row=0, column=1, sticky="e", padx=8, pady=4)

        ttk.Label(
            files_box,
            text=f"DXF: {os.path.basename(dxf_path) if dxf_path else 'brak'}",
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(
            files_box,
            text="Otwórz DXF",
            command=lambda: self._open_path_system(dxf_path) if dxf_path else None,
        ).grid(row=1, column=1, sticky="e", padx=8, pady=4)

        ttk.Label(
            files_box,
            text=f"Zdjęcia: {len(images)}",
        ).grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(
            files_box,
            text=f"Miniatura DXF: {'tak' if dxf_previews else 'nie'}",
        ).grid(row=2, column=1, sticky="e", padx=8, pady=4)

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Zamknij", command=dlg.destroy).pack(side="right")

        _render_preview()

    def _build_tab_in_progress(self) -> None:
        top = ttk.Frame(self.tab_in_progress)
        top.pack(fill="x", padx=8, pady=6)

        self.lbl_inprog = ttk.Label(top, text="W toku: 0")
        self.lbl_inprog.pack(side="left")

        cols = ("nr", "nazwa", "typ", "status", "visit_start", "progress", "tasks", "visits")
        self.tv_inprog = ttk.Treeview(
            self.tab_in_progress, columns=cols, show="headings", height=18
        )
        self.tv_inprog.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        headings = {
            "nr": "Nr",
            "nazwa": "Nazwa",
            "typ": "Typ",
            "status": "Status",
            "visit_start": "Czas wizyty",
            "progress": "Postęp",
            "tasks": "Zadania (A/W)",
            "visits": "Wizyty",
        }
        widths = {
            "nr": 90,
            "nazwa": 220,
            "typ": 160,
            "status": 180,
            "visit_start": 140,
            "progress": 80,
            "tasks": 110,
            "visits": 70,
        }
        for column in cols:
            self.tv_inprog.heading(
                column,
                text=headings.get(column, column),
                command=lambda col=column: self._sort_by_column(self.tv_inprog, col),
            )
            self.tv_inprog.column(column, width=widths.get(column, 120), anchor="w")

        # Kolory postępu w zakładce "Narzędzia".
        # Tkinter Treeview koloruje tagiem cały wiersz, nie pojedynczą komórkę,
        # więc celowo kolorujemy cały rekord według kolumny "Postęp".
        self.tv_inprog.tag_configure("progress_0", foreground="#9ca3af")
        self.tv_inprog.tag_configure("progress_low", foreground="#f87171")
        self.tv_inprog.tag_configure("progress_mid", foreground="#facc15")
        self.tv_inprog.tag_configure("progress_high", foreground="#86efac")
        self.tv_inprog.tag_configure("progress_done", foreground="#22c55e")

    def _build_tab_all(self) -> None:
        top = ttk.Frame(self.tab_all)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Szukaj:").pack(side="left")
        self.var_search = tk.StringVar(value="")
        self.entry_search = ttk.Entry(top, textvariable=self.var_search, width=40)
        self.entry_search.pack(side="left", padx=(6, 6))
        self.entry_search.bind("<KeyRelease>", lambda _event: self._refresh_all_tools())
        # FIX(UI): Enter w wyszukiwarce ma zaznaczyć i przewinąć do pierwszego wyniku.
        # Drugi Enter na już zaznaczonym rekordzie ma otworzyć szczegóły/edycję.
        self.entry_search.bind("<Return>", self._on_search_enter)

        ttk.Button(
            top,
            text="Wyczyść",
            command=lambda: (
                self.var_search.set(""),
                self._refresh_all_tools(),
                self._focus_first_all_tool_row(),
            ),
        ).pack(side="left")

        cols = (
            "nr",
            "nazwa",
            "typ",
            "status",
            "last_visit_end",
            "last_visit_by",
            "total_visit_time",
            "visits",
        )
        self.tv_all = ttk.Treeview(
            self.tab_all, columns=cols, show="headings", height=18
        )
        self.tv_all.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        headings = {
            "nr": "Nr",
            "nazwa": "Nazwa",
            "typ": "Typ",
            "status": "Status",
            "last_visit_end": "Ostatnia wizyta zakończona",
            "last_visit_by": "Zakończył",
            "total_visit_time": "Łączny czas wizyt",
            "visits": "Ilość wizyt",
        }
        widths = {
            "nr": 90,
            "nazwa": 260,
            "typ": 180,
            "status": 200,
            "last_visit_end": 190,
            "last_visit_by": 120,
            "total_visit_time": 150,
            "visits": 90,
        }
        for column in cols:
            self.tv_all.heading(
                column,
                text=headings.get(column, column),
                command=lambda col=column: self._sort_by_column(self.tv_all, col),
            )
            self.tv_all.column(column, width=widths.get(column, 140), anchor="w")
        self.tv_all.bind("<Return>", self._on_all_tree_enter)

    def _build_tab_tasks(self) -> None:
        top = ttk.Frame(self.tab_tasks)
        top.pack(fill="x", padx=8, pady=6)

        self.var_only_open = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top,
            text="Tylko niewykonane",
            variable=self.var_only_open,
            command=self._refresh_tasks_tree,
        ).pack(side="left")

        self.lbl_tasks = ttk.Label(top, text="")
        self.lbl_tasks.pack(side="right")

        cols = ("check", "title", "assigned", "done_date", "done_by")
        self.tv_tasks = ttk.Treeview(
            self.tab_tasks, columns=cols, show="tree headings", height=18
        )
        self.tv_tasks.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tv_tasks.heading("#0", text="Narzędzie / Zadanie")
        self.tv_tasks.column("#0", width=280, anchor="w")

        self.tv_tasks.heading("check", text="✓")
        self.tv_tasks.column("check", width=40, anchor="center")

        self.tv_tasks.heading("title", text="Tytuł")
        self.tv_tasks.column("title", width=320, anchor="w")

        self.tv_tasks.heading("assigned", text="Przypisane")
        self.tv_tasks.column("assigned", width=160, anchor="w")

        self.tv_tasks.heading("done_date", text="Data wykonania")
        self.tv_tasks.column("done_date", width=160, anchor="w")

        self.tv_tasks.heading("done_by", text="Kto")
        self.tv_tasks.column("done_by", width=120, anchor="w")

        self.tv_tasks.bind("<Button-1>", self._on_tasks_click)

        self._task_item_map: dict[str, tuple[str, int]] = {}

    def _schedule_refresh(self) -> None:
        self._refresh_all()
        self._seconds_until_refresh = REFRESH_INTERVAL_SECONDS
        self._update_refresh_label()
        self._schedule_countdown_tick()

    def _schedule_countdown_tick(self) -> None:
        if self._refresh_countdown_job:
            self.after_cancel(self._refresh_countdown_job)
            self._refresh_countdown_job = None
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        self._refresh_countdown_job = self.after(1000, self._countdown_tick)

    def _countdown_tick(self) -> None:
        self._seconds_until_refresh = max(0, self._seconds_until_refresh - 1)
        self._update_refresh_label()
        if self._seconds_until_refresh <= 0:
            self._refresh_job = self.after(0, self._schedule_refresh)
            self._refresh_countdown_job = None
            return
        self._refresh_countdown_job = self.after(1000, self._countdown_tick)

    def _update_refresh_label(self) -> None:
        self.refresh_info.config(
            text=f"Odświeżanie list za: {self._seconds_until_refresh} s"
        )

    def destroy(self) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        if self._refresh_countdown_job:
            self.after_cancel(self._refresh_countdown_job)
            self._refresh_countdown_job = None
        super().destroy()

    def _refresh_all(self) -> None:
        self._refresh_in_progress_tools()
        self._refresh_all_tools()
        self._refresh_tasks_tree()

    def _get_tools(self) -> list[Mapping[str, Any]]:
        try:
            tools = self.tools_provider() or []
        except Exception:
            tools = []
        return tools if isinstance(tools, list) else []

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item_id in tree.get_children(""):
            tree.delete(item_id)

    def _sort_by_column(self, tree: ttk.Treeview, col: str) -> None:
        rows: list[tuple[tuple[Any, ...], str]] = []
        for item_id in tree.get_children(""):
            values = tree.item(item_id, "values") or ()
            row_values = tuple(values) if isinstance(values, (list, tuple)) else (values,)
            rows.append((row_values, item_id))

        last_state = self._sort_state.get(tree)
        reverse = bool(last_state and last_state[0] == col and not last_state[1])

        try:
            col_index = tree["columns"].index(col)
        except ValueError:
            return

        def _key(row: tuple[tuple[Any, ...], str]) -> Any:
            values, _ = row
            raw = values[col_index] if col_index < len(values) else ""
            text = str(raw).strip()
            normalized = text.replace("%", "").replace(",", ".")
            if "/" in normalized:
                left, _, right = normalized.partition("/")
                if left.strip().isdigit() and right.strip().isdigit():
                    return int(left.strip()), int(right.strip())
            try:
                return float(normalized)
            except (TypeError, ValueError):
                return text.lower()

        rows.sort(key=_key, reverse=reverse)
        for idx, (_, item_id) in enumerate(rows):
            tree.move(item_id, "", idx)

        self._sort_state[tree] = (col, reverse)

    def _refresh_in_progress_tools(self) -> None:
        tools = [tool for tool in self._get_tools() if isinstance(tool, Mapping)]
        tools = [tool for tool in tools if self._is_in_progress(tool)]
        self.lbl_inprog.config(text=f"W toku: {len(tools)}")

        self._clear_tree(self.tv_inprog)
        for tool in tools:
            active, total = _tool_tasks_counts(tool)
            progress_text = _tool_progress_pct(tool)
            self.tv_inprog.insert(
                "",
                "end",
                tags=(_progress_tag(progress_text),),
                values=(
                    _tool_id(tool),
                    _tool_name(tool),
                    _tool_type_label(tool),
                    _tool_status_label(tool),
                    _visit_duration_label(tool),
                    progress_text,
                    f"{active}/{total}",
                    str(_tool_visits_count(tool)),
                ),
            )

    def _refresh_all_tools(self) -> None:
        tools = [tool for tool in self._get_tools() if isinstance(tool, Mapping)]
        query = (self.var_search.get() or "").strip().lower()
        if query:
            tools = [
                tool
                for tool in tools
                if query
                in " ".join(
                    [
                        _tool_id(tool),
                        _tool_name(tool),
                        _tool_type_label(tool),
                        _tool_status_label(tool),
                    ]
                ).lower()
            ]

        self._clear_tree(self.tv_all)
        for tool in tools:
            self.tv_all.insert(
                "",
                "end",
                values=(
                    _tool_id(tool),
                    _tool_name(tool),
                    _tool_type_label(tool),
                    _tool_status_label(tool),
                    _tool_last_closed_visit_date(tool),
                    _tool_last_closed_visit_by(tool),
                    _tool_total_visits_duration_label(tool),
                    str(_tool_visits_count(tool)),
                ),
            )
        self._focus_first_all_tool_row()

    def _focus_first_all_tool_row(self) -> None:
        """Zaznacz i pokaż pierwszy wiersz w zakładce listy narzędzi."""
        try:
            children = self.tv_all.get_children("")
        except Exception:
            return
        if not children:
            return
        first = children[0]
        try:
            self.tv_all.selection_set(first)
            self.tv_all.focus(first)
            self.tv_all.see(first)
        except Exception:
            return

    def _open_selected_all_tool(self) -> None:
        """Otwórz szczegóły dla aktualnie zaznaczonego rekordu z listy narzędzi."""
        if not self._open_detail_callback:
            return
        try:
            row_id = self.tv_all.selection()[0]
        except Exception:
            try:
                row_id = self.tv_all.focus()
            except Exception:
                row_id = ""
        if not row_id:
            return
        try:
            values = self.tv_all.item(row_id, "values") or []
        except Exception:
            values = []
        if not values:
            return
        tool_id = str(values[0] or "").strip()
        if tool_id:
            self._open_detail_callback(tool_id)

    def _on_search_enter(self, _event=None) -> str:
        """
        Enter w polu wyszukiwania:
        - jeśli nic nie jest zaznaczone -> zaznacza pierwszy wynik
        - jeśli pierwszy wynik już jest zaznaczony -> otwiera rekord
        """
        try:
            children = self.tv_all.get_children("")
        except Exception:
            children = ()
        if not children:
            return "break"

        first = children[0]
        try:
            current = self.tv_all.selection()
        except Exception:
            current = ()

        if not current or current[0] != first:
            self._focus_first_all_tool_row()
        else:
            self._open_selected_all_tool()
        return "break"

    def _on_all_tree_enter(self, _event=None) -> str:
        """Enter na liście narzędzi otwiera zaznaczony rekord."""
        self._open_selected_all_tool()
        return "break"

    def _refresh_tasks_tree(self) -> None:
        tools = [tool for tool in self._get_tools() if isinstance(tool, Mapping)]
        only_open = bool(self.var_only_open.get())

        self._clear_tree(self.tv_tasks)
        self._task_item_map.clear()

        total_tasks = 0
        total_open = 0

        for tool in tools:
            tool_id = _tool_id(tool)
            tool_name = _tool_name(tool)
            parent_text = f"{tool_id}  {tool_name}".strip()

            tasks = _tool_tasks(tool)
            if not tasks:
                continue

            open_cnt = sum(
                1 for task in tasks if isinstance(task, Mapping) and not _task_done(task)
            )
            total_cnt = len([task for task in tasks if isinstance(task, Mapping)])
            if only_open and open_cnt == 0:
                continue

            parent_iid = self.tv_tasks.insert(
                "",
                "end",
                text=f"{parent_text}  ({total_cnt - open_cnt}/{total_cnt})",
                values=("", "", "", "", ""),
            )
            self.tv_tasks.item(parent_iid, open=True)

            for idx, task in enumerate(tasks):
                if not isinstance(task, Mapping):
                    continue
                done = _task_done(task)
                if only_open and done:
                    continue

                total_tasks += 1
                if not done:
                    total_open += 1

                chk = "☑" if done else "☐"
                child_iid = self.tv_tasks.insert(
                    parent_iid,
                    "end",
                    text="",
                    values=(
                        chk,
                        _task_title(task),
                        _task_assigned(task),
                        _task_done_date(task),
                        _task_done_by(task),
                    ),
                )
                self._task_item_map[child_iid] = (tool_id, idx)

        self.lbl_tasks.config(
            text=f"Zadania: {total_open} otwarte / {total_tasks} widoczne"
        )

    def _resolve_first_status(self, tool: Mapping[str, Any]) -> str:
        if callable(getattr(self, "status_first_resolver", None)):
            try:
                return str(self.status_first_resolver(tool) or "")
            except Exception:
                return ""
        statuses = tool.get("statusy") or tool.get("statuses") or []
        if isinstance(statuses, list) and statuses:
            first = statuses[0]
            if isinstance(first, Mapping):
                return str(first.get("nazwa") or first.get("name") or "")
            return str(first)
        return ""

    def _resolve_last_status(self, tool: Mapping[str, Any]) -> str:
        if callable(getattr(self, "status_last_resolver", None)):
            try:
                return str(self.status_last_resolver(tool) or "")
            except Exception:
                return ""
        statuses = tool.get("statusy") or tool.get("statuses") or []
        if isinstance(statuses, list) and statuses:
            last = statuses[-1]
            if isinstance(last, Mapping):
                return str(last.get("nazwa") or last.get("name") or "")
            return str(last)
        return ""

    def _is_in_progress(self, tool: Mapping[str, Any]) -> bool:
        current = (_tool_status_label(tool) or "").strip()
        if not current:
            return False
        if _is_nn_sn(tool):
            return False
        first = (self._resolve_first_status(tool) or "").strip()
        if first and current == first:
            return False
        return True

    def _current_actor_login(self) -> str:
        if callable(getattr(self, "actor_login_resolver", None)):
            try:
                return str(self.actor_login_resolver() or "")
            except Exception:
                return ""
        return ""

    def _find_tool_by_id(self, tools: list[Mapping[str, Any]], tool_id: str) -> dict | None:
        for tool in tools:
            if isinstance(tool, Mapping) and _tool_id(tool) == tool_id:
                return dict(tool)
        return None

    def _on_tasks_click(self, event) -> None:
        region = self.tv_tasks.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tv_tasks.identify_column(event.x)
        row = self.tv_tasks.identify_row(event.y)
        if not row or column != "#1":
            return

        if row not in self._task_item_map:
            return

        tool_id, idx = self._task_item_map[row]
        tools = self._get_tools()
        tool = self._find_tool_by_id(tools, tool_id)
        if not tool:
            return

        tasks = _tool_tasks(tool)
        if idx < 0 or idx >= len(tasks) or not isinstance(tasks[idx], Mapping):
            return

        task = dict(tasks[idx])
        new_done = not _task_done(task)
        task["done"] = new_done

        if new_done and not _task_done_date(task):
            import datetime

            ts_done = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task["ts_done"] = ts_done
            task["done_ts"] = ts_done
        if not new_done:
            task["ts_done"] = ""
            task["date_done"] = ""
            task["done_at"] = ""
            task["done_ts"] = ""
            task["done_by"] = ""

        actor = self._current_actor_login()
        if new_done:
            if actor:
                task["done_by"] = actor
            else:
                task["done_by"] = task.get("done_by", "")

        tasks[idx] = task
        tool["zadania"] = tasks

        if callable(self.save_tool):
            self.save_tool(tool)

        self._refresh_tasks_tree()


@dataclass
class ToolRow:
    """Reprezentuje pojedynczy wiersz listy narzędzi."""

    identifier: str
    name: str
    status: str


class ToolsBatchLoader:
    """Wstawia wiersze drzewka partiami, aby nie blokować wątku GUI."""

    def __init__(
        self,
        tree: ttk.Treeview,
        rows: list[Mapping[str, Any]],
        *,
        batch_size: int = 10,
        delay: int = 100,
        prepare_tags=None,
    ) -> None:
        self.tree = tree
        self.rows = list(rows)
        self.batch_size = batch_size
        self.delay = delay
        self.prepare_tags = prepare_tags
        self._job: str | None = None

    def start(self) -> None:
        self._load_batch()

    def _load_batch(self) -> None:
        for _ in range(min(self.batch_size, len(self.rows))):
            row = self.rows.pop(0)
            identifier = str(row.get("id", ""))
            tags: list[str] = []
            if callable(self.prepare_tags):
                extra_tags = self.prepare_tags(row, identifier) or []
                tags.extend(extra_tags)
            values = (
                identifier,
                str(row.get("nazwa", "")),
                str(row.get("status") or "brak"),
            )
            self.tree.insert("", "end", iid=identifier, values=values, tags=tuple(tags))
        if self.rows:
            self._job = self.tree.after(self.delay, self._load_batch)

    def cancel(self) -> None:
        if self._job:
            self.tree.after_cancel(self._job)
            self._job = None


class ToolsListWindow:
    """Okno prezentujące listę narzędzi wraz z paskiem przewijania."""

    _DEFAULT_WIDTH = 900
    _DEFAULT_HEIGHT = 540

    def __init__(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        had_rows: bool,
        path: str,
        templates: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self.window = tk.Toplevel()
        self.window.title("Narzędzia")
        self.window.geometry(f"{self._DEFAULT_WIDTH}x{self._DEFAULT_HEIGHT}")
        ensure_theme_applied(self.window)
        self._center_on_primary_monitor()
        self.window.attributes("-topmost", True)

        self.rows = list(rows)
        self.templates = list(templates or [])

        info = tk.StringVar()
        if had_rows:
            info.set(f"Załadowano {len(self.rows)} pozycji.")
        else:
            info.set(
                "Brak narzędzi w konfiguracji – dodano przykładowe wpisy do "
                f"{path}."
            )

        header = ttk.Label(self.window, textvariable=info)
        header.pack(fill="x", padx=8, pady=8)

        container = ttk.Frame(self.window)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        def _tools_provider() -> list[Mapping[str, Any]]:
            from gui_narzedzia import _load_all_tools

            try:
                tools = _load_all_tools()
            except Exception:
                tools = self.rows
            return tools if isinstance(tools, list) else []

        def _save_tool(tool: Mapping[str, Any]) -> None:
            from gui_narzedzia import _save_tool

            try:
                _save_tool(tool)
            except Exception:
                return

        self._tools_provider = _tools_provider
        self.tools_view = ToolsThreeTabsView(
            container, tools_provider=_tools_provider, save_tool=_save_tool
        )
        self.tools_view.pack(fill="both", expand=True)
        self.tools_view.bind_open_detail(self._open_tool_detail_for_id)

        footer = ttk.Frame(self.window)
        footer.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(footer, text="Zamknij", command=self.window.destroy).pack(side="right")

    def _center_on_primary_monitor(self) -> None:
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x_position = max((screen_width - self._DEFAULT_WIDTH) // 2, 0)
        y_position = max((screen_height - self._DEFAULT_HEIGHT) // 2, 0)
        self.window.geometry(
            f"{self._DEFAULT_WIDTH}x{self._DEFAULT_HEIGHT}+{x_position}+{y_position}"
        )

    def focus_first(self) -> None:
        return

    def _find_tool_by_id(self, tool_id: str) -> dict | None:
        for row in self._tools_provider():
            if str(row.get("id") or row.get("nr") or row.get("numer") or "") == str(
                tool_id
            ):
                return dict(row)
        return None

    def _open_tool_detail_for_id(self, tool_id: str) -> None:
        tool = self._find_tool_by_id(tool_id) or {"id": tool_id}
        if not tool:
            return
        from gui_narzedzia import _normalize_path, _resolve_tools_dir, _safe_read_json

        tool_key = tool.get("id") or tool.get("nr") or tool.get("numer") or tool_id
        path = Path(_resolve_tools_dir()) / f"{tool_key}.json"
        norm_path = _normalize_path(path)
        if STATE.tools_docs_cache.get(norm_path) is None:
            STATE.tools_docs_cache[norm_path] = _safe_read_json(str(path), default={})
        full_tool = STATE.tools_docs_cache[norm_path]
        if isinstance(full_tool, dict):
            tool.update(full_tool or {})
        open_tool_detail(self.window, tool, templates=self.templates)


def open_tools_window(
    rows: Iterable[Mapping[str, Any]],
    *,
    had_rows: bool,
    path: str,
    cfg: Any | None = None,
) -> tk.Toplevel:
    """Utwórz okno listy narzędzi i zwróć je do dalszej konfiguracji."""

    try:
        templates = load_default_templates(cfg)
    except Exception:
        templates = []
    window = ToolsListWindow(rows, had_rows=had_rows, path=path, templates=templates)
    window.focus_first()
    return window.window


__all__ = [
    "open_tools_window",
    "ToolsListWindow",
    "ToolRow",
    "ToolsBatchLoader",
    "ToolsThreeTabsView",
]
