# version: 1.5
import tkinter as tk
from tkinter import ttk

import gui_profile_calendar as calendar_ui
import profile_calendar_team_runtime as team_runtime
import profile_foreman_workspace_runtime as workspace
import profile_login_calendar_fix_runtime as final_fix
import profile_workday_policy_runtime as policy


def _walk(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_walk(child))
    return out


def test_attendance_tree_gets_polish_weekday_column():
    root = tk.Tk()
    try:
        tree = ttk.Treeview(root, columns=("date", "slot"), show="headings")
        tree.heading("date", text="Data")
        tree.heading("slot", text="Zmiana")
        first = tree.insert("", "end", values=("2026-09-07", "RANO"))

        policy._install_weekday_column(tree)

        assert tuple(tree.cget("columns")) == ("date", "weekday", "slot")
        assert tuple(tree.item(first, "values")) == ("2026-09-07", "Pon", "RANO")

        second = tree.insert("", "end", values=("2026-09-12", "POPO"))
        assert tuple(tree.item(second, "values")) == ("2026-09-12", "Sob", "POPO")
    finally:
        root.destroy()


def test_team_tile_lines_use_two_columns_and_six_people_limit():
    rows = [
        {
            "login": f"login{idx}",
            "short_name": f"Login{idx}",
            "summary": "06–14",
            "status_code": "PLAN",
        }
        for idx in range(1, 8)
    ]

    lines = final_fix._team_tile_lines(7, rows)

    assert lines[0] == "7"
    assert len(lines) == 4
    assert "Login1 06–14" in lines[1] and "Login2 06–14" in lines[1]
    assert "Login3 06–14" in lines[2] and "Login4 06–14" in lines[2]
    assert "Login5 06–14" in lines[3] and "Login6 06–14" in lines[3]
    assert "+1" in lines[3]
    assert "Login7" not in "\n".join(lines)


def test_foreman_calendar_is_single_advanced_view_with_inline_day(monkeypatch):
    monkeypatch.setattr(team_runtime, "_is_foreman", lambda: True)
    monkeypatch.setattr(calendar_ui.ProfileCalendarPanel, "refresh", lambda self: None)
    team_runtime.install()
    workspace.install()
    policy._install_calendar_layout()
    final_fix.install()

    sample_rows = [
        {
            "login": "marek",
            "name": "Marek",
            "short_name": "Marek",
            "slot": "POPO",
            "shift": "14–22",
            "status_code": "PLAN",
            "status": "Zaplanowana zmiana",
            "summary": "14–22",
            "pay_percent": None,
            "pay_label": "—",
        },
        {
            "login": "dawid",
            "name": "Dawid Karolczyk",
            "short_name": "Dawid",
            "slot": "RANO",
            "shift": "06–14",
            "status_code": "ŚW",
            "status": "Siła wyższa",
            "summary": "ŚW",
            "pay_percent": 50.0,
            "pay_label": "50%",
        },
        {
            "login": "sebastian",
            "name": "Sebastian",
            "short_name": "Sebastian",
            "slot": "RANO",
            "shift": "06–14",
            "status_code": "PLAN",
            "status": "Zaplanowana zmiana",
            "summary": "06–14",
            "pay_percent": None,
            "pay_label": "—",
        },
        {
            "login": "edwin",
            "name": "Edwin",
            "short_name": "Edwin",
            "slot": "",
            "shift": "—",
            "status_code": "UR",
            "status": "Urlop",
            "summary": "UR",
            "pay_percent": 100.0,
            "pay_label": "100%",
        },
    ]
    monkeypatch.setattr(team_runtime, "_team_day_rows", lambda _day: sample_rows)
    monkeypatch.setattr(
        team_runtime,
        "_team_month_rows",
        lambda _year, _month: {day: sample_rows for day in range(1, 31)},
    )

    root = tk.Tk()
    try:
        panel = calendar_ui.ProfileCalendarPanel(root, login="edwin")
        panel.pack(fill="both", expand=True)
        panel.year = 2026
        panel.month = 9
        panel._snapshot = {"leaves": [], "requests": []}
        panel._render_calendar()
        root.update_idletasks()

        radios = [
            str(widget.cget("text"))
            for widget in _walk(panel)
            if isinstance(widget, ttk.Radiobutton)
        ]
        assert "Mój" not in radios
        assert "Zespół" not in radios

        day_buttons = [
            widget
            for widget in panel.calendar_box.winfo_children()
            if isinstance(widget, tk.Button)
        ]
        assert day_buttons
        assert all(str(button.cget("text")).strip().isdigit() for button in day_buttons)

        # Każdy dzień zespołu ma osobną nakładkę. Wpisy nie są już sklejane
        # spacjami w tekście przycisku, tylko zajmują dwie równe kolumny.
        frames = getattr(panel, "_wm_team_tile_frames", {})
        assert frames
        sample_frame = frames[min(frames)]
        cells = [
            widget
            for widget in sample_frame.winfo_children()
            if isinstance(widget, tk.Label) and str(widget.cget("relief")) == "solid"
        ]
        assert len(cells) == 4  # 4 osoby = dwa rzędy po dwie komórki
        texts = [str(cell.cget("text")) for cell in cells]
        assert texts == ["Marek 14–22", "Dawid ŚW", "Sebastian 06–14", "Edwin UR"]
        grids = [cell.grid_info() for cell in cells]
        assert [int(info["column"]) for info in grids] == [0, 1, 0, 1]
        assert [int(info["row"]) for info in grids] == [1, 1, 2, 2]

        detail_tree = panel._wm_team_detail_tree
        assert len(detail_tree.get_children()) == 4
        assert int(detail_tree.cget("height")) == 4
        assert panel._wm_team_max_visible_rows == 6

        body = panel.calendar_box.master
        side = detail_tree.master
        calendar_grid = panel.calendar_box.grid_info()
        side_grid = side.grid_info()
        assert int(calendar_grid.get("row", -1)) == 0
        assert int(calendar_grid.get("column", -1)) == 0
        assert int(calendar_grid.get("columnspan", 1)) == 2
        assert int(side_grid.get("row", -1)) == 1
        assert int(side_grid.get("column", -1)) == 0
        assert int(side_grid.get("columnspan", 1)) == 2
        assert side.master is body

        button_texts = {
            str(widget.cget("text"))
            for widget in _walk(side)
            if isinstance(widget, ttk.Button)
        }
        assert "Obecność" not in button_texts
        assert "Urlopy" not in button_texts

        before_windows = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
        day_buttons[0].invoke()
        root.update_idletasks()
        after_windows = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
        assert after_windows == before_windows
    finally:
        root.destroy()
