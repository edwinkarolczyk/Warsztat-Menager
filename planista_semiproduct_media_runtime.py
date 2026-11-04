# WM-VERSION: 0.1
"""Zdjęcie półproduktu w kartotece Planisty."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from tkinter import filedialog, ttk
from uuid import uuid4

from PIL import Image, ImageTk

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


def _safe_code(code: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", str(code or "").strip()).strip("._")
    if not value or value in {".", ".."}:
        raise ValueError("Nieprawidłowe ID półproduktu.")
    return value[:100]


def store_semiproduct_photo(data_dir: str | Path, code: str, source: str | Path) -> dict:
    """Zapisuje oryginał zdjęcia i miniaturę w katalogu danych WM."""
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku: {source_path}")
    suffix = source_path.suffix.lower()
    if suffix not in _IMAGE_SUFFIXES:
        raise ValueError("Zdjęcie półproduktu musi być plikiem graficznym.")
    with Image.open(source_path) as image:
        image.verify()

    data_root = Path(data_dir)
    folder = data_root / "polprodukty_media" / _safe_code(code)
    folder.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex[:12]
    original = folder / f"zdjecie_{token}{suffix}"
    shutil.copy2(source_path, original)
    thumbnail = folder / f"zdjecie_{token}_miniatura.jpg"
    with Image.open(original) as image:
        image.thumbnail((480, 360))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(thumbnail, "JPEG", quality=84, optimize=True)
    return {
        "zdjecie": original.relative_to(data_root).as_posix(),
        "zdjecie_miniatura": thumbnail.relative_to(data_root).as_posix(),
    }


def resolve_semiproduct_photo(data_dir: str | Path, relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    root = Path(data_dir).resolve()
    candidate = (root / str(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def install_planista_semiproduct_media_runtime() -> None:
    import gui_magazyn_bom as GMB

    UI = GMB.MagazynBOM
    if getattr(UI, "_wm_semiproduct_media", False):
        return

    old_build = UI._build_polprodukty
    old_new = UI._new_polprodukt
    old_select = UI._on_pp_select
    old_save = UI._save_polprodukt

    def _show_preview(self) -> None:
        path = resolve_semiproduct_photo(
            self.model.data_dir, self._wm_pp_media_vars["zdjecie_miniatura"].get()
        )
        if path is None:
            self._wm_pp_media_image = None
            self._wm_pp_media_preview.configure(image="", text="Brak podglądu")
            return
        try:
            with Image.open(path) as image:
                image.thumbnail((72, 54))
                preview = ImageTk.PhotoImage(image.copy())
            self._wm_pp_media_image = preview
            self._wm_pp_media_preview.configure(image=preview, text="")
        except Exception:
            self._wm_pp_media_image = None
            self._wm_pp_media_preview.configure(image="", text="Nie można wyświetlić podglądu")

    def _set_record(self, record: dict) -> None:
        for key in ("zdjecie", "zdjecie_miniatura"):
            self._wm_pp_media_vars[key].set(str(record.get(key) or ""))
        _show_preview(self)
        path = resolve_semiproduct_photo(
            self.model.data_dir, self._wm_pp_media_vars["zdjecie"].get()
        )
        self._wm_pp_media_label.configure(
            text=Path(path).name if path else "Nie wybrano zdjęcia"
        )

    def _choose_photo(self) -> None:
        code = self.pp_vars["kod"].get().strip()
        if not code:
            GMB._msg_error(self, "Półprodukty", "Najpierw zapisz lub nadaj ID półproduktu.")
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="Zdjęcie półproduktu",
            filetypes=[
                ("Pliki graficzne", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if not selected:
            return
        try:
            stored = store_semiproduct_photo(self.model.data_dir, code, selected)
        except Exception as exc:
            GMB._msg_error(self, "Plik półproduktu", str(exc))
            return
        for key, value in stored.items():
            self._wm_pp_media_vars[key].set(value)
        self._wm_pp_media_label.configure(text=Path(selected).name)
        _show_preview(self)

    def build_semiproducts(self, parent):
        old_build(self, parent)
        form = next((child for child in parent.winfo_children()
                     if isinstance(child, ttk.LabelFrame)
                     and str(child.cget("text")) == "Karta półproduktu"), None)
        if form is None:
            return
        import tkinter as tk

        self._wm_pp_media_vars = {
            key: tk.StringVar(master=self, value="")
            for key in ("zdjecie", "zdjecie_miniatura")
        }
        self._wm_pp_media_image = None
        frame = ttk.Frame(form)
        frame.grid(row=7, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
        self._wm_pp_media_preview = ttk.Label(frame, text="", width=10, anchor="center")
        self._wm_pp_media_preview.pack(side="left", padx=(0, 5))
        ttk.Button(frame, text="Zdjęcie…", width=11, command=lambda: _choose_photo(self)).pack(
            side="left", padx=(0, 6)
        )
        self._wm_pp_media_label = ttk.Label(frame, text="Nie wybrano zdjęcia")
        self._wm_pp_media_label.pack(side="left", fill="x", expand=True)
        _set_record(self, {})

    def new_semiproduct(self):
        old_new(self)
        if hasattr(self, "_wm_pp_media_vars"):
            _set_record(self, {})

    def select_semiproduct(self, event=None):
        old_select(self, event)
        if not hasattr(self, "_wm_pp_media_vars"):
            return
        selection = self.tree_pp.selection()
        if not selection:
            return
        code = str(self.tree_pp.item(selection[0], "values")[-1])
        _set_record(self, self.model.polprodukty.get(code, {}))

    def save_semiproduct(self):
        if not hasattr(self, "_wm_pp_media_vars"):
            return old_save(self)
        pending = {key: var.get().strip() for key, var in self._wm_pp_media_vars.items()}
        model_save = self.model.add_or_update_polprodukt

        def save_with_media(record):
            payload = dict(record)
            payload.update(pending)
            return model_save(payload)

        self.model.add_or_update_polprodukt = save_with_media
        try:
            return old_save(self)
        finally:
            self.model.add_or_update_polprodukt = model_save

    UI._build_polprodukty = build_semiproducts
    UI._new_polprodukt = new_semiproduct
    UI._on_pp_select = select_semiproduct
    UI._save_polprodukt = save_semiproduct
    UI._wm_semiproduct_media = True


__all__ = [
    "install_planista_semiproduct_media_runtime",
    "store_semiproduct_photo",
    "resolve_semiproduct_photo",
]
