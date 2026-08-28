# version: 1.0
# Moduł: settings_help_runtime
# UI-only: krótkie, zamykane podpowiedzi „?” przy trudniejszych ustawieniach.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


_HELP: dict[str, tuple[str, str]] = {
    "wymagaj logowania": (
        "Wymagaj logowania",
        "Gdy opcja jest włączona, użytkownik musi przejść przez autoryzację przed uzyskaniem dostępu do chronionych funkcji WM. Wyłączenie tej opcji ma sens głównie w środowisku testowym albo na stanowisku bez danych wymagających ochrony.",
    ),
    "pomiń ekran logowania": (
        "Pomiń ekran logowania",
        "Po włączeniu WM może automatycznie zalogować wskazany profil przy uruchomieniu programu. Używaj tego tylko na stanowisku, do którego dostęp ma jedna zaufana osoba, ponieważ pomija ręczne podanie PIN-u.",
    ),
    "profil automatycznego logowania": (
        "Profil automatycznego logowania",
        "To konto zostanie użyte przy starcie, jeśli włączone jest pomijanie ekranu logowania. Wybierz profil świadomie, ponieważ jego rola i uprawnienia będą aktywne od razu po uruchomieniu WM.",
    ),
    "timeout sesji (min)": (
        "Automatyczne wylogowanie",
        "Określa, po jakim czasie bezczynności WM wyloguje aktualnego użytkownika. Krótszy czas zwiększa bezpieczeństwo, a dłuższy jest wygodniejszy na stanowisku używanym stale przez tę samą osobę.",
    ),
    "dodaj automatyczną dyspozycję [dni przed terminem]": (
        "Automatyczna Dyspozycja z przeglądu",
        "Określa, ile dni przed planowanym przeglądem maszyny WM ma utworzyć powiązaną Dyspozycję. Wartość 0 oznacza utworzenie jej dopiero w dniu przeglądu; większa wartość daje więcej czasu na zaplanowanie pracy.",
    ),
    "miganie nowych [ms]": (
        "Miganie nowych Dyspozycji",
        "To odstęp między zmianami koloru dla nowych Dyspozycji, podany w milisekundach. Mniejsza wartość oznacza szybsze miganie; przykładowo 2000 ms to 2 sekundy.",
    ),
    "miganie po terminie [ms]": (
        "Miganie zaległych Dyspozycji",
        "To odstęp między zmianami koloru dla Dyspozycji po terminie, podany w milisekundach. Mniejsza wartość daje szybsze miganie i mocniej zwraca uwagę na zaległe zadania.",
    ),
    "próg alertu stanu (%)": (
        "Próg niskiego stanu",
        "Po zejściu zapasu do tego poziomu Magazyn może traktować pozycję jako wymagającą uwagi. Ustawienie wpływa na sygnalizację niskiego stanu, dlatego zbyt wysoka wartość może generować zbyt wiele ostrzeżeń.",
    ),
    "rezerwuj materiał przy zleceniu": (
        "Rezerwowanie materiału",
        "Po włączeniu materiał potrzebny do zlecenia jest odkładany logicznie dla tego zlecenia i nie powinien być liczony jako swobodnie dostępny dla innych prac. Pomaga to uniknąć sytuacji, w której ten sam zapas zostanie zaplanowany dwa razy.",
    ),
    "stan docelowy (%)": (
        "Stan docelowy magazynu",
        "To poziom, do którego WM może odnosić uzupełnianie zapasu po wykryciu braków lub niskiego stanu. Wartość powyżej 100% oznacza utrzymywanie dodatkowego zapasu względem poziomu bazowego.",
    ),
    "rozmiar kratki (px)": (
        "Rozmiar kratki hali",
        "Określa wizualny rozmiar pojedynczej kratki na planie hali. Zmienia dokładność i czytelność rozmieszczania obiektów, ale nie zmienia rzeczywistych wymiarów maszyn.",
    ),
    "przyciągaj do siatki": (
        "Przyciąganie do siatki",
        "Po włączeniu przesuwane obiekty ustawiają się na najbliższych punktach siatki zamiast w dowolnym miejscu. Ułatwia to równe rozmieszczanie maszyn i utrzymanie porządku na planie hali.",
    ),
    "dopasowanie tła": (
        "Dopasowanie tła hali",
        "Określa, jak obraz planu hali jest dopasowywany do dostępnego obszaru. „Dopasuj” zachowuje cały obraz, „Wypełnij” może przyciąć brzegi, a „Rozciągnij” może zmienić jego proporcje.",
    ),
    "przezroczystość tła (%)": (
        "Przezroczystość tła",
        "Zmniejszenie wartości sprawia, że plan hali jest mniej dominujący wizualnie i łatwiej odczytać oznaczenia maszyn. Wysoka wartość pokazuje tło wyraźniej, ale może obniżyć kontrast znaczników.",
    ),
    "statusy oznaczające wykonane zadania": (
        "Statusy kończące zadania",
        "Tutaj określasz, przy których statusach narzędzia WM może automatycznie uznać zadania za wykonane. Lista powinna zawierać tylko statusy rzeczywiście oznaczające zakończenie pracy, aby nie odhaczać zadań zbyt wcześnie.",
    ),
    "odhaczaj zadania przy ostatnim statusie": (
        "Automatyczne odhaczanie zadań",
        "Po włączeniu przejście narzędzia na ostatni status z jego listy może automatycznie oznaczyć wszystkie zadania jako wykonane. Wyłącz tę opcję, jeśli zadania mają być zawsze potwierdzane ręcznie.",
    ),
    "włącz miganie dyspozycji": (
        "Miganie Dyspozycji",
        "Włącza animowane zmiany kolorów dla wybranych stanów Dyspozycji, np. nowych lub zaległych. Wyłączenie pozostawia statyczne kolory i może być wygodniejsze, jeśli miganie rozprasza użytkownika.",
    ),
}


def _normalize(value: str) -> str:
    return str(value or "").strip().rstrip(":").strip().lower()


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _center_window(win: tk.Toplevel, owner: tk.Misc) -> None:
    try:
        win.update_idletasks()
        width = max(420, min(540, win.winfo_reqwidth()))
        height = max(190, min(300, win.winfo_reqheight()))
        top = owner.winfo_toplevel()
        top.update_idletasks()
        x = top.winfo_rootx() + max(0, (top.winfo_width() - width) // 2)
        y = top.winfo_rooty() + max(0, (top.winfo_height() - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _show_help(owner: tk.Misc, title: str, body: str) -> None:
    win = tk.Toplevel(owner.winfo_toplevel())
    win.title(f"Pomoc — {title}")
    win.resizable(False, False)
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass

    outer = ttk.Frame(win, padding=14)
    outer.pack(fill="both", expand=True)

    head = ttk.Frame(outer)
    head.pack(fill="x", pady=(0, 10))
    ttk.Label(head, text="?", font=("", 18, "bold")).pack(side="left", padx=(0, 10))
    ttk.Label(head, text=title, font=("", 11, "bold")).pack(side="left", anchor="w")

    ttk.Label(
        outer,
        text=body,
        wraplength=470,
        justify="left",
    ).pack(fill="x", anchor="w", pady=(0, 14))

    ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 10))
    ttk.Button(outer, text="Zamknij", command=win.destroy).pack(side="right")

    win.bind("<Escape>", lambda _e: win.destroy())
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    _center_window(win, owner)
    try:
        win.grab_set()
        win.focus_set()
    except Exception:
        pass


def _attach_grid_help(widget: tk.Misc, title: str, body: str) -> bool:
    parent = widget.master
    try:
        info = widget.grid_info()
    except Exception:
        return False
    if not info:
        return False

    try:
        row = int(info.get("row", 0))
    except Exception:
        row = 0

    max_col = 0
    for sibling in parent.winfo_children():
        try:
            sibling_info = sibling.grid_info()
            if not sibling_info or int(sibling_info.get("row", -1)) != row:
                continue
            col = int(sibling_info.get("column", 0))
            span = int(sibling_info.get("columnspan", 1))
            max_col = max(max_col, col + max(1, span) - 1)
        except Exception:
            continue

    button = ttk.Button(
        parent,
        text="?",
        width=3,
        command=lambda o=widget, t=title, b=body: _show_help(o, t, b),
    )
    button.grid(row=row, column=max_col + 1, sticky="w", padx=(4, 6), pady=info.get("pady", 4))
    return True


def _decorate(panel: Any) -> None:
    root = getattr(panel, "_content_area", None)
    if root is None:
        return

    for widget in list(_all_descendants(root)):
        if getattr(widget, "_wm_settings_help_done", False):
            continue
        if not isinstance(widget, (ttk.Label, ttk.Checkbutton)):
            continue
        try:
            text = str(widget.cget("text") or "").strip()
        except Exception:
            continue
        help_data = _HELP.get(_normalize(text))
        if help_data is None:
            continue
        if _attach_grid_help(widget, help_data[0], help_data[1]):
            setattr(widget, "_wm_settings_help_done", True)


def install_settings_help_runtime(settings_panel_cls: type) -> None:
    """Dodaj przyciski ? po zbudowaniu i uporządkowaniu całego panelu."""
    if getattr(settings_panel_cls, "_wm_settings_help_runtime", False):
        return

    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original_build_ui):
        return

    def _build_ui_with_help(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        try:
            _decorate(self)
        except Exception:
            pass
        return result

    settings_panel_cls._build_ui = _build_ui_with_help
    settings_panel_cls._wm_settings_help_runtime = True
