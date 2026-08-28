# version: 1.1
"""Układ aktywnego Profilu: osobiste Dyspozycje, dane pracy, avatar i PW."""

from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

logger = logging.getLogger(__name__)


def install_profile_simple_runtime() -> bool:
    """Podłącz ulepszony układ do istniejącego ``gui_profile.ProfileView``."""

    try:
        import gui_profile as gp
    except Exception:
        logger.exception("[PROFILE][RUNTIME] Nie udało się zaimportować gui_profile.")
        return False

    cls = getattr(gp, "ProfileView", None)
    if cls is None:
        return False
    if getattr(cls, "_wm_simple_profile_runtime", False):
        return True

    original_render_simple = cls._render_simple_profile

    def _compact_avatar(self, parent: tk.Widget) -> tk.Widget:
        if gp.Image is None or gp.ImageTk is None:
            return self._avatar_placeholder(parent)

        login = str(self.login or "").strip()
        candidates = [
            Path("avatars") / f"{login}.png",
            Path("avatars") / "default.jpg",
        ]
        image = None
        for path in candidates:
            try:
                image = gp.Image.open(path)
                break
            except Exception:
                image = None
        if image is None:
            return self._avatar_placeholder(parent)

        try:
            image.thumbnail((112, 112))
            photo = gp.ImageTk.PhotoImage(image)
            label = tk.Label(parent, image=photo, bg=gp.WM_BG, bd=0)
            label.image = photo
            return label
        except Exception:
            return self._avatar_placeholder(parent)

    def _render_avatar_area(self, parent: tk.Widget) -> None:
        for child in list(parent.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        avatar = self._make_avatar(parent)
        avatar.pack(pady=(0, 6))
        ttk.Button(
            parent,
            text="Dodaj / zmień avatar",
            command=self._wm_choose_avatar,
            style="WM.Outline.TButton",
        ).pack(fill="x")

    def _choose_avatar(self) -> None:
        login = str(self.login or "").strip()
        if not login:
            messagebox.showwarning("Profil", "Brak zalogowanego użytkownika.", parent=self)
            return
        if gp.Image is None:
            messagebox.showwarning(
                "Profil",
                "Zmiana avatara wymaga biblioteki Pillow.",
                parent=self,
            )
            return

        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Wybierz avatar",
            filetypes=[
                ("Obrazy", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if not path:
            return

        try:
            image = gp.Image.open(path)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            image.thumbnail((320, 320))
            target_dir = Path("avatars")
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{login}.png"
            image.save(target, format="PNG")
        except Exception as exc:
            logger.exception("[PROFILE][AVATAR] Nie udało się zapisać avatara: %s", exc)
            messagebox.showerror(
                "Profil",
                f"Nie udało się zapisać avatara:\n{exc}",
                parent=self,
            )
            return

        avatar_wrap = getattr(self, "_wm_avatar_wrap", None)
        if avatar_wrap is not None:
            try:
                _render_avatar_area(self, avatar_wrap)
            except Exception:
                pass

    def _unread_pw_count(self) -> int:
        login = str(self.login or "").strip()
        if not login:
            return 0
        try:
            inbox = gp.list_inbox(login) or []
        except Exception:
            inbox = []
        return sum(
            1
            for msg in inbox
            if isinstance(msg, dict) and not bool(msg.get("read"))
        )

    def _refresh_pw_button(self) -> None:
        btn = getattr(self, "btn_open_pw", None)
        if btn is None:
            return
        try:
            if not btn.winfo_exists():
                return
        except Exception:
            return
        unread = _unread_pw_count(self)
        try:
            btn.configure(text=f"Wiadomości ({unread})" if unread else "Wiadomości")
        except Exception:
            pass

    def _open_pw_window(self) -> None:
        login = str(self.login or "").strip()
        if not login:
            messagebox.showwarning("Profil", "Brak zalogowanego użytkownika.", parent=self)
            return

        existing = getattr(self, "_wm_pw_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass

        try:
            self._reload_profile_data()
        except Exception:
            pass

        win = tk.Toplevel(self)
        self._wm_pw_window = win
        win.title(f"Wiadomości (PW) – {login}")
        win.geometry("960x640")
        win.minsize(760, 480)
        try:
            win.transient(self.winfo_toplevel())
        except Exception:
            pass
        try:
            gp.apply_theme(win)
        except Exception:
            pass

        host = ttk.Frame(win, style="WM.Card.TFrame")
        host.pack(fill="both", expand=True)

        try:
            self._build_pw_tab(host)
        except Exception as exc:
            logger.exception("[PROFILE][PW] Nie udało się zbudować skrzynki PW: %s", exc)
            for child in host.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
            ttk.Label(
                host,
                text=f"Nie udało się otworzyć skrzynki PW:\n{exc}",
                style="WM.CardLabel.TLabel",
                justify="left",
            ).pack(anchor="w", padx=16, pady=16)

        def _close_pw(_event=None) -> None:
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
            self._wm_pw_window = None
            try:
                self._reload_profile_data()
            except Exception:
                pass
            _refresh_pw_button(self)

        win.protocol("WM_DELETE_WINDOW", _close_pw)
        win.bind("<Escape>", _close_pw, add="+")
        try:
            win.focus_set()
        except Exception:
            pass

    def _build_header(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="WM.Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)
        wrap.columnconfigure(1, weight=1)

        user = gp.get_user(self.login) or {}
        display = (
            user.get("display_name")
            or self.display_name
            or " ".join(
                part
                for part in (
                    str(user.get("imie") or "").strip(),
                    str(user.get("nazwisko") or "").strip(),
                )
                if part
            )
            or self.login
            or "—"
        )
        role = user.get("rola") or self.rola or "—"

        identity = ttk.Frame(wrap, style="WM.Card.TFrame")
        identity.grid(row=0, column=0, sticky="nw", padx=(0, 24))
        ttk.Label(
            identity,
            text=str(display),
            style="WM.H1.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            identity,
            text=f"@{self.login}" if self.login else "@—",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            identity,
            text=f"Rola: {role}",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        pw_actions = ttk.Frame(identity, style="WM.Card.TFrame")
        pw_actions.pack(anchor="w", pady=(4, 0))

        self.btn_open_pw = ttk.Button(
            pw_actions,
            text="Wiadomości",
            command=self._wm_open_pw_window,
            style="WM.Button.TButton",
        )
        self.btn_open_pw.pack(side="left")

        self.btn_send_pw = ttk.Button(
            pw_actions,
            text="Wyślij wiadomość",
            command=self._on_send_pw,
            style="WM.Outline.TButton",
        )
        self.btn_send_pw.pack(side="left", padx=(8, 0))
        _refresh_pw_button(self)

        work = ttk.LabelFrame(
            wrap,
            text="Praca",
            style="WM.Section.TLabelframe",
            padding=(12, 8),
        )
        work.grid(row=0, column=1, sticky="nsew")

        employed = str(user.get("zatrudniony_od") or self.zatrudniony_od or "—")
        if self._staz_days:
            tenure = f"{self.staz_lata} lat ({self._staz_days} dni)"
        else:
            tenure = f"{self.staz_lata} lat"

        def _row(label: str, value: str) -> None:
            row = ttk.Frame(work, style="WM.Card.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(
                row,
                text=f"{label}:",
                style="WM.CardMuted.TLabel",
                width=18,
            ).pack(side="left")
            ttk.Label(
                row,
                text=value or "—",
                style="WM.CardLabel.TLabel",
            ).pack(side="left")

        _row("Dzisiejsza zmiana", self._profile_shift_text())
        _row("Zatrudniony od", employed)
        _row("Staż", tenure)

    def _build_cover_header(self) -> None:
        cover = ttk.Frame(self, style="WM.Cover.TFrame")
        cover.pack(fill="x", padx=16, pady=(16, 8))
        cover.configure(height=205)
        cover.grid_propagate(False)

        inner = ttk.Frame(cover, style="WM.Header.TFrame")
        inner.place(relx=0, rely=1.0, x=0, y=-16, relwidth=1.0, anchor="sw")
        inner.grid_columnconfigure(1, weight=1)

        avatar_holder = ttk.Frame(inner, style="WM.Header.TFrame")
        avatar_holder.grid(
            row=0,
            column=0,
            padx=(16, 12),
            pady=(10, 8),
            sticky="nw",
        )
        self._wm_avatar_wrap = avatar_holder
        _render_avatar_area(self, avatar_holder)

        info = ttk.Frame(inner, style="WM.Header.TFrame")
        info.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=(10, 8))
        self._header_container = info
        self._build_header(info)

        separator = tk.Frame(self, height=1, bg=gp.WM_DIVIDER)
        separator.pack(fill="x", padx=16, pady=(8, 0))

    def _find_tree(widget) -> ttk.Treeview | None:
        try:
            children = list(widget.winfo_children())
        except Exception:
            return None
        for child in children:
            if isinstance(child, ttk.Treeview):
                return child
            found = _find_tree(child)
            if found is not None:
                return found
        return None

    def _row_is_personal(self, displayed_title: str) -> bool:
        title = str(displayed_title or "").replace(" • dla wszystkich", "").strip()
        login = str(self.login or "").strip().lower()
        for row in self._dysp_cache or []:
            if not isinstance(row, dict):
                continue
            row_title = str(
                row.get("tytul")
                or row.get("opis")
                or row.get("id")
                or "Dyspozycja"
            ).strip()
            if row_title != title:
                continue
            assigned = str(row.get("przypisane_do") or "").strip().lower()
            performer = str(row.get("wykonuje") or "").strip().lower()
            if login and (assigned == login or performer == login):
                return True
        return "• dla wszystkich" not in str(displayed_title or "")

    def _render_simple_profile(self, parent: ttk.Frame) -> None:
        # Zachowujemy istniejące akcje Rozpocznij/Zakończ i dwuklik edycji.
        original_render_simple(self, parent)

        dysp_box = None
        for child in list(parent.winfo_children()):
            try:
                text = str(child.cget("text") or "")
            except Exception:
                text = ""
            if text == "Praca":
                try:
                    child.destroy()
                except Exception:
                    pass
            elif text == "Moje Dyspozycje":
                dysp_box = child

        if dysp_box is None:
            return

        try:
            dysp_box.pack_forget()
            dysp_box.pack(fill="both", expand=True)
        except Exception:
            pass

        tree = _find_tree(dysp_box)
        if tree is None:
            return

        try:
            current = list(tree.get_children(""))
            ranked: list[tuple[int, int, str]] = []
            for pos, iid in enumerate(current):
                values = tree.item(iid, "values") or ()
                title = str(values[1] if len(values) > 1 else "")
                rank = 0 if _row_is_personal(self, title) else 1
                ranked.append((rank, pos, iid))
            ranked.sort(key=lambda item: (item[0], item[1]))
            for new_pos, (_rank, _old_pos, iid) in enumerate(ranked):
                tree.move(iid, "", new_pos)
        except Exception:
            logger.exception("[PROFILE][DYSP] Nie udało się ustawić kolejności Dyspozycji.")

    cls._make_avatar = _compact_avatar
    cls._wm_choose_avatar = _choose_avatar
    cls._wm_unread_pw_count = _unread_pw_count
    cls._wm_refresh_pw_button = _refresh_pw_button
    cls._wm_open_pw_window = _open_pw_window
    cls._build_header = _build_header
    cls._build_cover_header = _build_cover_header
    cls._render_simple_profile = _render_simple_profile
    cls._wm_simple_profile_runtime = True
    return True


__all__ = ["install_profile_simple_runtime"]
