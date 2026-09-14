# version: 1.0
"""Mała warstwa naprawcza UI Maszyn.

Naprawa pozostaje poza ``gui_maszyny_legacy.py``: przywraca stały dostęp do
wydruku planu przeglądów, dodaje zbiorczy wydruk QR i porządkuje okno edycji
bez zmiany modelu danych Maszyn.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from tkinter import filedialog, messagebox

from machine_history_runtime import _print_plan
from machine_qr_runtime import (
    PRINT_DPI,
    build_machine_qr_print_page,
    machine_qr_payload,
    open_machine_qr,
)
from ui_context_help import add_help_button


def _machine_id(row: Mapping[str, Any]) -> str:
    return str(
        row.get("id")
        or row.get("nr_ewid")
        or row.get("nr")
        or row.get("numer")
        or ""
    ).strip()


def _machine_name(row: Mapping[str, Any]) -> str:
    return str(
        row.get("nazwa")
        or row.get("name")
        or row.get("machine_name")
        or ""
    ).strip()


def collect_machine_qr_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Zwróć unikalne maszyny nadające się do zbiorczego wydruku QR."""

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        machine_id = _machine_id(row)
        if not machine_id or machine_id in seen:
            continue
        seen.add(machine_id)
        result.append({"id": machine_id, "name": _machine_name(row)})
    return result


def create_all_machine_qr_pdf(
    output_path: str | Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    page_format: str = "A6",
) -> tuple[Path, int]:
    """Utwórz jeden wielostronicowy PDF, po jednej maszynie na stronę."""

    machines = collect_machine_qr_rows(rows)
    if not machines:
        raise ValueError("Brak maszyn z identyfikatorem do wydruku QR.")

    pages = [
        build_machine_qr_print_page(
            machine_qr_payload(machine["id"]),
            machine["id"],
            label=machine["name"],
            page_format=page_format,
        )
        for machine in machines
    ]

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(
        path,
        "PDF",
        resolution=float(PRINT_DPI),
        save_all=True,
        append_images=pages[1:],
    )
    return path, len(machines)


def _find_action_bar(tree: Any):
    try:
        parent = tree.master
        children = parent.winfo_children()
    except Exception:
        return None

    for child in children:
        try:
            nested = child.winfo_children()
        except Exception:
            continue
        for widget in nested:
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                continue
            if text == "Drukuj pustą kartę maszyny":
                return child
    return None


def _find_button(parent: Any, text: str):
    try:
        children = parent.winfo_children()
    except Exception:
        return None
    for child in children:
        try:
            if str(child.cget("text") or "") == text:
                return child
        except Exception:
            continue
    return None


def _load_rows(module: Any) -> list[dict[str, Any]]:
    loader = getattr(module, "load_machines_rows", None)
    if not callable(loader):
        return []
    try:
        rows = loader()
    except Exception:
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _open_generated_pdf(module: Any, path: Path, *, parent=None) -> None:
    opener = getattr(module, "_open_external", None)
    try:
        opened = bool(callable(opener) and opener(str(path)))
    except Exception:
        opened = False
    if not opened:
        messagebox.showinfo(
            "Maszyny",
            f"PDF zapisany:\n{path}",
            parent=parent,
        )


def _install_main_actions(module: Any, tree: Any, root: Any) -> None:
    actions = _find_action_bar(tree)
    if actions is None:
        return

    ttk = getattr(module, "ttk", None)
    if ttk is None:
        return

    plan_button = _find_button(actions, "Drukuj plan przeglądów")
    if plan_button is None:
        plan_button = ttk.Button(
            actions,
            text="Drukuj plan przeglądów",
            command=lambda: _print_plan(module, parent=root),
        )
        plan_button.pack(side="left", padx=(6, 0))
    else:
        try:
            plan_button.configure(command=lambda: _print_plan(module, parent=root))
        except Exception:
            pass
    actions._wm_service_plan_button = plan_button

    if not getattr(plan_button, "_wm_help_added", False):
        help_button = add_help_button(
            actions,
            "Drukuje aktualny plan aktywnych i zaplanowanych przeglądów maszyn. "
            "Dane są pobierane z bieżących kart maszyn.",
        )
        help_button.pack(side="left", padx=(2, 0))
        plan_button._wm_help_added = True

    if _find_button(actions, "Drukuj QR wszystkich maszyn") is not None:
        return

    def _print_all_qr() -> None:
        rows = _load_rows(module)
        machines = collect_machine_qr_rows(rows)
        if not machines:
            messagebox.showinfo(
                "QR wszystkich maszyn",
                "Brak maszyn z identyfikatorem do wydruku.",
                parent=root,
            )
            return

        target = filedialog.asksaveasfilename(
            parent=root,
            title="Zapisz QR wszystkich maszyn",
            initialfile="QR_wszystkie_maszyny_A6.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not target:
            return

        try:
            path, count = create_all_machine_qr_pdf(target, rows, page_format="A6")
        except ModuleNotFoundError as exc:
            if exc.name == "qrcode":
                messagebox.showwarning(
                    "QR wszystkich maszyn",
                    "Brakuje obsługi QR w tej wersji WM.",
                    parent=root,
                )
                return
            raise
        except Exception as exc:
            messagebox.showerror(
                "QR wszystkich maszyn",
                f"Nie udało się przygotować PDF:\n{exc}",
                parent=root,
            )
            return

        _open_generated_pdf(module, path, parent=root)
        try:
            logger = getattr(module, "logger", None)
            if logger is not None:
                logger.info(
                    "[Maszyny][QR] Zbiorczy wydruk: %s maszyn -> %s",
                    count,
                    path,
                )
        except Exception:
            pass

    all_qr_button = ttk.Button(
        actions,
        text="Drukuj QR wszystkich maszyn",
        command=_print_all_qr,
    )
    all_qr_button.pack(side="left", padx=(6, 0))
    help_button = add_help_button(
        actions,
        "Tworzy jeden PDF A6 z kodem QR każdej maszyny. "
        "Każda maszyna trafia na osobną stronę gotową do wydruku.",
    )
    help_button.pack(side="left", padx=(2, 0))


def _walk_widgets(widget: Any):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield from _walk_widgets(child)


def _find_editor_footer(window: Any):
    try:
        children = window.winfo_children()
    except Exception:
        return None
    for child in children:
        texts: set[str] = set()
        try:
            nested = child.winfo_children()
        except Exception:
            continue
        for widget in nested:
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                continue
            if text:
                texts.add(text)
        if "Zapisz" in texts and ("Anuluj" in texts or "Zamknij" in texts):
            return child
    return None


def _find_review_box(window: Any):
    for widget in _walk_widgets(window):
        try:
            if str(widget.cget("text") or "") == "Przeglądy cykliczne":
                return widget
        except Exception:
            continue
    return None


def _fit_editor(window: Any) -> None:
    try:
        window.update_idletasks()
        screen_w = max(1024, int(window.winfo_screenwidth()))
        screen_h = max(700, int(window.winfo_screenheight()))
        req_w = max(1100, int(window.winfo_reqwidth()))
        req_h = max(720, int(window.winfo_reqheight()))
        width = min(req_w, max(980, screen_w - 80))
        height = min(req_h, max(680, screen_h - 100))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(min(980, width), min(620, height))
        window.resizable(True, True)
    except Exception:
        pass


def _decorate_machine_editor(window: Any, module: Any) -> None:
    if getattr(window, "_wm_machine_ui_repaired", False):
        return
    if window.__class__.__name__ != "MachineEditDialog":
        return
    row = getattr(window, "_row", None)
    if not isinstance(row, dict):
        return

    window._wm_machine_ui_repaired = True
    ttk = getattr(module, "ttk", None)
    if ttk is None:
        return

    footer = _find_editor_footer(window)
    if footer is not None and _find_button(footer, "Kod QR WMM") is None:
        def _show_editor_qr() -> None:
            machine_id = ""
            machine_name = ""
            try:
                machine_id = str(window.e_id.get() or "").strip()
            except Exception:
                machine_id = _machine_id(row)
            try:
                machine_name = str(window.e_nazwa.get() or "").strip()
            except Exception:
                machine_name = _machine_name(row)
            if not machine_id:
                messagebox.showinfo(
                    "Kod QR WMM",
                    "Najpierw nadaj maszynie ID / nr ewidencyjny.",
                    parent=window,
                )
                return
            open_machine_qr(window, machine_id, label=machine_name)

        qr_button = ttk.Button(footer, text="Kod QR WMM", command=_show_editor_qr)
        qr_button.pack(side="left")
        help_button = add_help_button(
            footer,
            "Pokazuje kod QR bieżącej maszyny używany przez WMM. "
            "W oknie QR możesz zapisać etykietę A5 albo A6 do druku.",
        )
        help_button.pack(side="left", padx=(2, 0))

    review_box = _find_review_box(window)
    if review_box is not None and not getattr(window, "_wm_review_toggle", None):
        try:
            form = review_box.master
            review_box.grid_remove()
            toggle_bar = ttk.Frame(form)
            toggle_bar.grid(
                row=9,
                column=0,
                columnspan=3,
                sticky="ew",
                padx=6,
                pady=(8, 4),
            )
            expanded = {"value": False}

            def _toggle_reviews() -> None:
                expanded["value"] = not expanded["value"]
                if expanded["value"]:
                    review_box.grid(
                        row=10,
                        column=0,
                        columnspan=2,
                        sticky="ew",
                        pady=(2, 4),
                    )
                    toggle.configure(text="Serwis i przeglądy ▾")
                else:
                    review_box.grid_remove()
                    toggle.configure(text="Serwis i przeglądy ▸")
                window.after_idle(lambda: _fit_editor(window))

            toggle = ttk.Button(
                toggle_bar,
                text="Serwis i przeglądy ▸",
                command=_toggle_reviews,
            )
            toggle.pack(side="left")
            help_button = add_help_button(
                toggle_bar,
                "Rozwija ustawienia cyklicznych przeglądów i sugerowanych wykonawców. "
                "Sekcja jest domyślnie zwinięta, żeby uprościć edycję maszyny.",
            )
            help_button.pack(side="left", padx=(2, 0))
            window._wm_review_toggle = toggle
        except Exception:
            pass

    window.after_idle(lambda: _fit_editor(window))
    try:
        window.after(80, lambda: _fit_editor(window))
    except Exception:
        pass


def _install_toplevel_hook(module: Any) -> None:
    tk_module = getattr(module, "tk", None)
    if tk_module is None or getattr(tk_module, "_wm_machine_ui_repair_proxy", False):
        return
    real_toplevel = getattr(tk_module, "Toplevel", None)
    if real_toplevel is None:
        return

    class _RepairAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.after_idle(lambda: _decorate_machine_editor(self, module))
            except Exception:
                pass

    class _TkProxy:
        _wm_machine_ui_repair_proxy = True
        _wm_base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
        Toplevel = _RepairAwareToplevel

        def __getattr__(self, name: str):
            return getattr(tk_module, name)

    module.tk = _TkProxy()


def install_machine_ui_repair(module: Any) -> None:
    """Podłącz wyłącznie zaakceptowane naprawy UI i wydruków Maszyn."""

    if getattr(module, "_WM_MACHINE_UI_REPAIR", False):
        return

    _install_toplevel_hook(module)
    original_open_panel = module._open_machines_panel

    def _open_machines_panel_repaired(*args, **kwargs):
        tree = original_open_panel(*args, **kwargs)
        root = args[0] if args else kwargs.get("root")
        try:
            _install_main_actions(module, tree, root)
        except Exception:
            logger = getattr(module, "logger", None)
            if logger is not None:
                logger.exception("[Maszyny] nie udało się podłączyć napraw UI/wydruków")
        return tree

    module._open_machines_panel = _open_machines_panel_repaired
    module.create_all_machine_qr_pdf = create_all_machine_qr_pdf
    module.collect_machine_qr_rows = collect_machine_qr_rows
    module._WM_MACHINE_UI_REPAIR = True
