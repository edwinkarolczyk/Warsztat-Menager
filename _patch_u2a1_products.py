from __future__ import annotations

from pathlib import Path

PLAN = Path("gui_planowanie.py")
STORE = Path("produkty_store.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


store_content = r'''# version: 1.0
# Moduł: produkty_store
# U2A-1:
# - Jedno wejście do katalogu produktów z aktywnego WM_DATA_ROOT.
# - Odczyt zgodny z obecnym formatem `kod` oraz starszym `symbol`.
# - Nowe/edytowane produkty zapisują wspólny format bez automatycznej migracji reszty danych.

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from config_manager import ConfigManager


class ProductCatalogError(RuntimeError):
    pass


class ProductCatalog:
    """Katalog produktów oparty o DATA_ROOT/produkty/*.json.

    Sam odczyt nigdy nie modyfikuje plików. Starsze rekordy z polem ``symbol``
    są normalizowane wyłącznie w pamięci. Zapis produktu zachowuje nieznane
    pola i istniejący BOM, a ujednolica metadane produktu.
    """

    _FORBIDDEN_FILENAME_CHARS = set('<>:"/\\|?*')

    def __init__(self, cfg: ConfigManager | None = None) -> None:
        self.cfg = cfg or ConfigManager()
        self.products_dir = Path(self.cfg.path_data("produkty"))
        self.backup_dir = Path(self.cfg.path_backup("produkty"))
        self.products_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _normalise_bom_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
        value = raw.get("polprodukty")
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]

        value = raw.get("BOM")
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]

        value = raw.get("bom")
        if isinstance(value, dict):
            result: list[dict[str, Any]] = []
            for code, qty in value.items():
                result.append({"kod": str(code), "ilosc_na_szt": qty})
            return result
        return []

    @classmethod
    def _normalise(cls, raw: dict[str, Any], path: Path) -> dict[str, Any]:
        code = str(raw.get("kod") or raw.get("symbol") or path.stem).strip()
        name = str(raw.get("nazwa") or raw.get("name") or code).strip()
        bom = cls._normalise_bom_entries(raw)
        try:
            revision = int(raw.get("bom_revision") or 1)
        except (TypeError, ValueError):
            revision = 1
        return {
            "kod": code,
            "nazwa": name,
            "version": str(raw.get("version") or "1.0"),
            "bom_revision": max(1, revision),
            "is_default": bool(raw.get("is_default", True)),
            "polprodukty": bom,
            "_path": str(path),
            "_legacy_symbol": "kod" not in raw and "symbol" in raw,
            "_raw": raw,
        }

    def list_products(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.products_dir.glob("*.json"), key=lambda p: p.name.lower()):
            if path.name.lower() == "bom.json":
                # Stary centralny BOM nie jest rekordem produktu.
                continue
            raw = self._read_json(path)
            if raw is None:
                continue
            item = self._normalise(raw, path)
            if item.get("kod"):
                items.append(item)
        return items

    @classmethod
    def _filename_for_code(cls, code: str) -> str:
        value = str(code or "").strip()
        if not value:
            raise ProductCatalogError("Oznaczenie produktu jest wymagane.")
        if value in {".", ".."}:
            raise ProductCatalogError("Nieprawidłowe oznaczenie produktu.")
        if value.endswith((" ", ".")):
            raise ProductCatalogError("Oznaczenie nie może kończyć się spacją ani kropką.")
        if any(ord(ch) < 32 or ch in cls._FORBIDDEN_FILENAME_CHARS for ch in value):
            raise ProductCatalogError(
                "Oznaczenie zawiera znak niedozwolony w nazwie pliku Windows."
            )
        return f"{value}.json"

    def _backup(self, path: Path) -> None:
        if not path.exists():
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dst = self.backup_dir / f"{path.stem}_{stamp}{path.suffix}"
        shutil.copy2(path, dst)

    def save_product(
        self,
        fields: dict[str, Any],
        *,
        original_path: str | Path | None = None,
    ) -> dict[str, Any]:
        code = str(fields.get("kod") or "").strip()
        name = str(fields.get("nazwa") or "").strip()
        if not name:
            raise ProductCatalogError("Nazwa produktu jest wymagana.")

        filename = self._filename_for_code(code)
        target = self.products_dir / filename
        source = Path(original_path) if original_path else None
        if source is not None:
            try:
                source = source.resolve()
            except Exception:
                pass
        try:
            target_resolved = target.resolve()
        except Exception:
            target_resolved = target

        if target.exists() and (source is None or target_resolved != source):
            raise ProductCatalogError(f"Produkt o oznaczeniu '{code}' już istnieje.")

        raw: dict[str, Any] = {}
        if source is not None and source.exists():
            raw = self._read_json(source) or {}

        try:
            revision = int(fields.get("bom_revision") or 1)
        except (TypeError, ValueError):
            raise ProductCatalogError("Rewizja BOM musi być liczbą całkowitą.") from None
        if revision < 1:
            raise ProductCatalogError("Rewizja BOM musi być większa od zera.")

        # Zachowujemy wszystkie nieznane pola oraz obecny BOM.
        payload = dict(raw)
        payload["kod"] = code
        if "symbol" in payload:
            # Kompatybilność ze starszym czytnikiem — nie usuwamy pola.
            payload["symbol"] = code
        payload["nazwa"] = name
        payload["version"] = str(fields.get("version") or "1.0").strip() or "1.0"
        payload["bom_revision"] = revision
        payload["is_default"] = bool(fields.get("is_default", True))
        if "polprodukty" not in payload and "BOM" not in payload and "bom" not in payload:
            payload["polprodukty"] = []

        if source is not None and source.exists():
            self._backup(source)
        if target.exists() and (source is None or target_resolved != source):
            self._backup(target)

        tmp = target.with_suffix(target.suffix + ".tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

        if source is not None and source.exists():
            try:
                same_file = source.resolve() == target.resolve()
            except Exception:
                same_file = source == target
            if not same_file:
                source.unlink()

        return self._normalise(payload, target)

    def delete_product(self, product: dict[str, Any]) -> None:
        raw_path = product.get("_path")
        if not raw_path:
            raise ProductCatalogError("Nie można ustalić pliku produktu.")
        path = Path(str(raw_path))
        if not path.exists():
            raise ProductCatalogError("Plik produktu już nie istnieje.")
        self._backup(path)
        path.unlink()
'''

if STORE.exists():
    raise RuntimeError("produkty_store.py already exists; aborting to avoid overwrite")
STORE.write_text(store_content, encoding="utf-8")

s = PLAN.read_text(encoding="utf-8")

s = replace_once(
    s,
    "# =========================================================\n# WM - PLANOWANIE PRODUKCJI (ROZBUDOWA MVP)\n# =========================================================\n",
    "# =========================================================\n# WM - PLANOWANIE PRODUKCJI (ROZBUDOWA MVP)\n# version: 1.1\n# =========================================================\n"
    "# Zmiany 1.1:\n"
    "# - U2A-1: dodano zakładkę Produkty opartą o aktywny WM_DATA_ROOT.\n"
    "# - Produkty obsługują obecny format `kod` i starszy `symbol` bez automatycznej migracji.\n"
    "# - Oznaczenia produktów nie są ograniczone do jednego firmowego schematu.\n",
    "plan version header",
)

s = replace_once(
    s,
    "from config_manager import ConfigManager\n",
    "from config_manager import ConfigManager\n"
    "from produkty_store import ProductCatalog, ProductCatalogError\n",
    "product store import",
)

s = replace_once(
    s,
    '''        self.store = PlanStore()
        self.calendar_year = date.today().year
        self.calendar_month = date.today().month
        self.search_var = tk.StringVar(value="")
        self.filter_status = tk.StringVar(value="")
        self._build_ui()
''',
    '''        self.store = PlanStore()
        self.product_catalog = ProductCatalog()
        self.can_manage_products = (
            not self.role
            or self.role in {"admin", "administrator", "kierownik", "brygadzista"}
        )
        self.calendar_year = date.today().year
        self.calendar_month = date.today().month
        self.search_var = tk.StringVar(value="")
        self.filter_status = tk.StringVar(value="")
        self.product_search_var = tk.StringVar(value="")
        self._product_rows: dict[str, dict] = {}
        self._build_ui()
''',
    "plan init products",
)

s = replace_once(
    s,
    '''        tab_cal = ttk.Frame(notebook)
        tab_ord = ttk.Frame(notebook)
        notebook.add(tab_cal, text="KALENDARZ")
        notebook.add(tab_ord, text="ZLECENIA")
        self._build_calendar_tab(tab_cal)
        self._build_orders_tab(tab_ord)
''',
    '''        tab_cal = ttk.Frame(notebook)
        tab_ord = ttk.Frame(notebook)
        tab_prod = ttk.Frame(notebook)
        notebook.add(tab_cal, text="KALENDARZ")
        notebook.add(tab_ord, text="ZLECENIA")
        notebook.add(tab_prod, text="PRODUKTY")
        self._build_calendar_tab(tab_cal)
        self._build_orders_tab(tab_ord)
        self._build_products_tab(tab_prod)
''',
    "plan products tab",
)

products_methods = r'''    def _build_products_tab(self, tab):
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Szukaj:").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.product_search_var)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ent.bind("<KeyRelease>", lambda _e: self._refresh_products_list())

        ttk.Button(top, text="Odśwież", command=self._refresh_products_list).pack(
            side="right", padx=(3, 0)
        )
        if self.can_manage_products:
            ttk.Button(top, text="Usuń", command=self._delete_selected_product).pack(
                side="right", padx=3
            )
            ttk.Button(top, text="Edytuj", command=self._edit_selected_product).pack(
                side="right", padx=3
            )
            ttk.Button(top, text="Dodaj", command=self._add_product).pack(
                side="right", padx=3
            )

        cols = ("kod", "nazwa", "version", "bom_revision", "bom_count")
        self.products_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for key, label, width in (
            ("kod", "Oznaczenie", 180),
            ("nazwa", "Nazwa", 320),
            ("version", "Wersja", 90),
            ("bom_revision", "Rewizja BOM", 100),
            ("bom_count", "Pozycji BOM", 100),
        ):
            self.products_tree.heading(key, text=label)
            self.products_tree.column(key, width=width, anchor="w")
        self.products_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.products_tree.bind("<Double-1>", lambda _e: self._edit_selected_product())

        info = ttk.LabelFrame(tab, text="Informacja")
        info.pack(fill="x", padx=8, pady=(0, 8))
        text = (
            "Ta zakładka zarządza metadanymi produktów. Istniejący BOM produktu "
            "nie jest tu przepisywany ani usuwany; osobny edytor BOM zostanie "
            "podpięty w kolejnym etapie."
        )
        ttk.Label(info, text=text, wraplength=1000).pack(anchor="w", padx=8, pady=8)

        self._refresh_products_list()

    def _refresh_products_list(self):
        if not hasattr(self, "products_tree"):
            return
        self.products_tree.delete(*self.products_tree.get_children())
        self._product_rows = {}
        query = self.product_search_var.get().strip().lower()
        try:
            products = self.product_catalog.list_products()
        except Exception as exc:
            messagebox.showerror("Produkty", f"Nie udało się wczytać produktów:\n{exc}")
            return

        visible = []
        for product in products:
            blob = f"{product.get('kod', '')} {product.get('nazwa', '')}".lower()
            if query and query not in blob:
                continue
            visible.append(product)

        visible.sort(key=lambda p: (str(p.get("kod") or "").lower(), str(p.get("nazwa") or "").lower()))
        for idx, product in enumerate(visible):
            iid = f"prd-{idx}"
            self._product_rows[iid] = product
            self.products_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    product.get("kod", ""),
                    product.get("nazwa", ""),
                    product.get("version", ""),
                    product.get("bom_revision", 1),
                    len(product.get("polprodukty") or []),
                ),
            )

    def _selected_product(self):
        if not hasattr(self, "products_tree"):
            return None
        selected = self.products_tree.selection()
        if not selected:
            return None
        return self._product_rows.get(selected[0])

    def _add_product(self):
        if not self.can_manage_products:
            return
        self._open_product_form()

    def _edit_selected_product(self):
        if not self.can_manage_products:
            return
        product = self._selected_product()
        if not product:
            return
        self._open_product_form(product)

    def _open_product_form(self, product=None):
        if not self.can_manage_products:
            return

        values = product or {}
        win = tk.Toplevel(self.root)
        win.title("Produkt" if product else "Nowy produkt")
        win.transient(self.root)
        win.grab_set()

        form = ttk.Frame(win, padding=12)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        kod_var = tk.StringVar(value=str(values.get("kod") or ""))
        nazwa_var = tk.StringVar(value=str(values.get("nazwa") or ""))
        version_var = tk.StringVar(value=str(values.get("version") or "1.0"))
        revision_var = tk.StringVar(value=str(values.get("bom_revision") or 1))
        default_var = tk.BooleanVar(value=bool(values.get("is_default", True)))

        for row, (label, var) in enumerate((
            ("Oznaczenie:", kod_var),
            ("Nazwa:", nazwa_var),
            ("Wersja:", version_var),
            ("Rewizja BOM:", revision_var),
        )):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(form, textvariable=var, width=48).grid(row=row, column=1, sticky="ew", pady=4)

        ttk.Checkbutton(form, text="Domyślna wersja produktu", variable=default_var).grid(
            row=4, column=1, sticky="w", pady=4
        )
        ttk.Label(
            form,
            text="Oznaczenie jest tekstem; ograniczenia dotyczą tylko znaków niedozwolonych w nazwach plików Windows.",
            wraplength=520,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 10))

        def save():
            payload = {
                "kod": kod_var.get(),
                "nazwa": nazwa_var.get(),
                "version": version_var.get(),
                "bom_revision": revision_var.get(),
                "is_default": default_var.get(),
            }
            try:
                self.product_catalog.save_product(
                    payload,
                    original_path=(values.get("_path") if product else None),
                )
            except ProductCatalogError as exc:
                messagebox.showerror("Produkt", str(exc), parent=win)
                return
            except Exception as exc:
                messagebox.showerror("Produkt", f"Nie udało się zapisać produktu:\n{exc}", parent=win)
                return
            win.destroy()
            self._refresh_products_list()

        buttons = ttk.Frame(form)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Anuluj", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Zapisz", command=save).pack(side="right")

    def _delete_selected_product(self):
        if not self.can_manage_products:
            return
        product = self._selected_product()
        if not product:
            return
        code = str(product.get("kod") or "")
        if not messagebox.askyesno(
            "Usuń produkt",
            f"Usunąć produkt '{code}'?\n\nPrzed usunięciem zostanie wykonana kopia pliku.",
            parent=self.root,
        ):
            return
        try:
            self.product_catalog.delete_product(product)
        except ProductCatalogError as exc:
            messagebox.showerror("Produkty", str(exc), parent=self.root)
            return
        except Exception as exc:
            messagebox.showerror("Produkty", f"Nie udało się usunąć produktu:\n{exc}", parent=self.root)
            return
        self._refresh_products_list()

'''

s = replace_once(
    s,
    "    def _build_calendar_tab(self, tab):\n",
    products_methods + "    def _build_calendar_tab(self, tab):\n",
    "product tab methods",
)

PLAN.write_text(s, encoding="utf-8")
print("U2A-1 patch prepared")
