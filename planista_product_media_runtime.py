# WM-VERSION: 0.1
"""Zdjęcia i rysunki techniczne w kartotece produktów Planisty."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from tkinter import filedialog, ttk
from uuid import uuid4

from PIL import Image, ImageTk

_MEDIA_FIELDS = {
    "zdjecie": "Zdjęcie produktu",
    "rysunek_techniczny": "Rysunek techniczny",
}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
_PDF_SUFFIXES = {".pdf"}


def _safe_symbol(symbol: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", str(symbol or "").strip()).strip("._")
    if not value or value in {".", ".."}:
        raise ValueError("Nieprawidłowe oznaczenie produktu.")
    return value[:100]


def store_product_media(data_dir: str | Path, symbol: str, kind: str, source: str | Path) -> dict:
    """Kopiuje oryginał do danych WM i tworzy miniaturę dla obrazów."""
    if kind not in _MEDIA_FIELDS:
        raise ValueError("Nieznany rodzaj pliku produktu.")
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku: {source_path}")
    suffix = source_path.suffix.lower()
    if suffix not in _IMAGE_SUFFIXES | _PDF_SUFFIXES:
        raise ValueError("Dozwolone są obrazy (PNG/JPG/TIFF/WEBP) lub dokument PDF.")
    if suffix == ".pdf" and kind == "zdjecie":
        raise ValueError("Zdjęcie produktu musi być plikiem graficznym.")
    if suffix in _IMAGE_SUFFIXES:
        with Image.open(source_path) as image:
            image.verify()

    folder = Path(data_dir) / "produkty_media" / _safe_symbol(symbol)
    folder.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex[:12]
    original = folder / f"{kind}_{token}{suffix}"
    shutil.copy2(source_path, original)
    relative_original = original.relative_to(Path(data_dir)).as_posix()
    result = {"path": relative_original, "thumbnail": ""}
    if suffix in _IMAGE_SUFFIXES:
        thumb = folder / f"{kind}_{token}_miniatura.jpg"
        with Image.open(original) as image:
            image.thumbnail((480, 360))
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(thumb, "JPEG", quality=84, optimize=True)
        result["thumbnail"] = thumb.relative_to(Path(data_dir)).as_posix()
    return result


def resolve_product_media(data_dir: str | Path, relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    root = Path(data_dir).resolve()
    candidate = (root / str(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def install_planista_product_media_runtime() -> None:
    import gui_magazyn_bom as GMB

    UI = GMB.MagazynBOM
    if getattr(UI, "_wm_product_media", False):
        return

    old_build = UI._build_produkty
    old_new = UI._new_produkt
    old_select = UI._on_pr_select
    old_save = UI._save_produkt

    def _show_preview(self, kind: str) -> None:
        thumb_key = f"{kind}_miniatura"
        path = resolve_product_media(self.model.data_dir, self._wm_media_vars[thumb_key].get())
        if path is None:
            self._wm_media_images[kind] = None
            self._wm_media_preview[kind].configure(image="", text="Brak podglądu")
            return
        try:
            with Image.open(path) as image:
                image.thumbnail((150, 110))
                preview = ImageTk.PhotoImage(image.copy())
            self._wm_media_images[kind] = preview
            self._wm_media_preview[kind].configure(image=preview, text="")
        except Exception:
            self._wm_media_images[kind] = None
            self._wm_media_preview[kind].configure(image="", text="Nie można wyświetlić podglądu")

    def _set_media_record(self, record: dict) -> None:
        for key in ("zdjecie", "zdjecie_miniatura", "rysunek_techniczny", "rysunek_techniczny_miniatura"):
            self._wm_media_vars[key].set(str(record.get(key) or ""))
        _show_preview(self, "zdjecie")
        _show_preview(self, "rysunek_techniczny")
        for kind, label in _MEDIA_FIELDS.items():
            path = resolve_product_media(self.model.data_dir, self._wm_media_vars[kind].get())
            self._wm_media_labels[kind].configure(text=Path(path).name if path else "Nie wybrano pliku")

    def _choose_media(self, kind: str) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        if not symbol:
            GMB._msg_error(self, "Produkty", "Najpierw podaj oznaczenie produktu.")
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title=_MEDIA_FIELDS[kind],
            filetypes=[
                ("Pliki graficzne i PDF", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.pdf"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if not selected:
            return
        try:
            stored = store_product_media(self.model.data_dir, symbol, kind, selected)
        except Exception as exc:
            GMB._msg_error(self, "Plik produktu", str(exc))
            return
        self._wm_media_vars[kind].set(stored["path"])
        self._wm_media_vars[f"{kind}_miniatura"].set(stored["thumbnail"])
        self._wm_media_labels[kind].configure(text=Path(selected).name)
        _show_preview(self, kind)

    def build_products(self, parent):
        old_build(self, parent)
        form = next((child for child in parent.winfo_children()
                     if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "Karta produktu"), None)
        if form is None:
            return
        self._wm_media_vars = {
            key: GMB.tk.StringVar(master=self, value="")
            for key in ("zdjecie", "zdjecie_miniatura", "rysunek_techniczny", "rysunek_techniczny_miniatura")
        }
        self._wm_media_images = {"zdjecie": None, "rysunek_techniczny": None}
        self._wm_media_labels = {}
        self._wm_media_preview = {}
        for row, (kind, title) in enumerate(_MEDIA_FIELDS.items(), start=4):
            frame = ttk.LabelFrame(form, text=title, padding=5)
            frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=3)
            preview = ttk.Label(frame, text="Brak podglądu", width=22, anchor="center")
            preview.pack(side="left", padx=(0, 8))
            self._wm_media_preview[kind] = preview
            info = ttk.Frame(frame)
            info.pack(side="left", fill="x", expand=True)
            label = ttk.Label(info, text="Nie wybrano pliku")
            label.pack(anchor="w")
            self._wm_media_labels[kind] = label
            ttk.Button(
                info,
                text="Wybierz plik…",
                command=lambda selected_kind=kind: _choose_media(self, selected_kind),
            ).pack(anchor="w", pady=(4, 0))
        bom_box = next((child for child in form.winfo_children()
                        if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "Półprodukty w produkcie"), None)
        if bom_box is not None:
            bom_box.grid_configure(row=6)
        _set_media_record(self, {})

    def new_product(self):
        old_new(self)
        if hasattr(self, "_wm_media_vars"):
            _set_media_record(self, {})

    def select_product(self, event=None):
        old_select(self, event)
        if not hasattr(self, "_wm_media_vars"):
            return
        selection = self.tree_pr.selection()
        if not selection:
            return
        symbol = str(self.tree_pr.item(selection[0], "values")[0])
        _set_media_record(self, self.model.produkty.get(symbol, {}))

    def save_product(self):
        if not hasattr(self, "_wm_media_vars"):
            return old_save(self)
        pending = {key: var.get().strip() for key, var in self._wm_media_vars.items()}
        model_save = self.model.add_or_update_produkt

        def save_with_media(record):
            payload = dict(record)
            payload.update(pending)
            return model_save(payload)

        self.model.add_or_update_produkt = save_with_media
        try:
            result = old_save(self)
            if not self.pr_vars["symbol"].get().strip():
                _set_media_record(self, {})
            return result
        finally:
            self.model.add_or_update_produkt = model_save

    UI._build_produkty = build_products
    UI._new_produkt = new_product
    UI._on_pr_select = select_product
    UI._save_produkt = save_product
    UI._wm_product_media = True


__all__ = ["install_planista_product_media_runtime", "store_product_media", "resolve_product_media"]
