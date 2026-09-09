# version: 1.1
# Zmiany 1.1:
# - Okno szczegółów narzędzia ma większy rozmiar startowy i minimum, żeby nie ucinać treści.
"""Widok szczegółów narzędzia oparty o szablony zadań."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import tkinter as tk
from tkinter import ttk

from ui_theme import ensure_theme_applied


def _pick_template(templates: Sequence[Mapping[str, Any]], tool: Mapping[str, Any]) -> Mapping[str, Any] | None:
    candidate_ids = [
        tool.get("template_id"),
        tool.get("szablon"),
        tool.get("tryb"),
        tool.get("typ"),
    ]
    normalized = [str(cid).lower() for cid in candidate_ids if cid]
    for candidate in normalized:
        for template in templates:
            tpl_id = str(template.get("id", "")).lower()
            if tpl_id and tpl_id == candidate:
                return template
    return templates[0] if templates else None


def _template_payload(template: Mapping[str, Any]) -> Any:
    for key in ("template", "tasks", "zadania", "items", "sections"):
        if key in template:
            return template[key]
    return {k: v for k, v in template.items() if k != "id"}


class ToolDetailWindow:
    """Okno prezentujące podstawowe informacje o narzędziu."""

    def __init__(
        self,
        owner: tk.Misc | None,
        tool: Mapping[str, Any],
        templates: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self.window = tk.Toplevel(owner)
        self.window.title(f"Narzędzie {tool.get('id', '')}")
        self.window.geometry("900x650")
        self.window.minsize(800, 560)
        self.window.resizable(True, True)
        ensure_theme_applied(self.window)

        top = ttk.Frame(self.window)
        top.pack(fill="x", padx=12, pady=12)

        ttk.Label(
            top, text=str(tool.get("nazwa", "Narzędzie")), font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")
        meta = f"ID: {tool.get('id', '-')}, typ: {tool.get('typ', '-')} | status: {tool.get('status', '-')}"
        ttk.Label(top, text=meta, style="WM.Muted.TLabel").pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        info_tab = ttk.Frame(notebook)
        notebook.add(info_tab, text="Informacje")

        ttk.Label(info_tab, text="Opis", style="WM.Card.TLabel").pack(anchor="w", pady=(8, 4))
        description = tk.Text(info_tab, height=4, wrap="word")
        description.insert("1.0", str(tool.get("opis", "")))
        description.configure(state="disabled")
        description.pack(fill="x")

        ttk.Label(info_tab, text="Powiązane narzędzia", style="WM.Card.TLabel").pack(
            anchor="w", pady=(10, 4)
        )
        related = tool.get("narzedzia_powiazane") or []
        related_str = ", ".join(str(item) for item in related) if related else "brak"
        ttk.Label(info_tab, text=related_str).pack(anchor="w")

        tasks_tab = ttk.Frame(notebook)
        notebook.add(tasks_tab, text="Szablon zadań")

        template = _pick_template(list(templates or []), tool)
        payload = _template_payload(template) if template else {}

        if isinstance(payload, Mapping):
            tree = ttk.Treeview(tasks_tab, columns=("name",), show="tree")
            tree.pack(fill="both", expand=True, pady=8)
            for section, tasks in payload.items():
                section_id = tree.insert("", "end", text=str(section))
                if isinstance(tasks, (list, tuple)):
                    for task in tasks:
                        tree.insert(section_id, "end", text=str(task))
                else:
                    tree.insert(section_id, "end", text=str(tasks))
        else:
            text = tk.Text(tasks_tab, height=12, wrap="word")
            text.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))
            text.configure(state="disabled")
            text.pack(fill="both", expand=True, pady=8)

        footer = ttk.Frame(self.window)
        footer.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(footer, text="Zamknij", command=self.window.destroy).pack(side="right")


def open_tool_detail(
    owner: tk.Misc | None, tool: Mapping[str, Any], templates: Sequence[Mapping[str, Any]] | None = None
) -> tk.Toplevel:
    """Helper for opening :class:`ToolDetailWindow` in one call."""

    window = ToolDetailWindow(owner, tool, templates=templates)
    return window.window


__all__ = ["ToolDetailWindow", "open_tool_detail"]
