# version: 1.0
# Moduł: planowanie_zapotrzebowanie
# U2A-3: wyliczanie zapotrzebowania bez ruchów magazynowych i bez Dyspozycji.

from __future__ import annotations

from typing import Any

from polprodukty_store import SemiProductCatalog
from produkty_store import ProductCatalog


class RequirementError(RuntimeError):
    pass


def unique_order_number(proposed: str, orders: list[dict[str, Any]], *, exclude_id: str | None = None) -> str:
    base = str(proposed or "").strip()
    if not base:
        raise RequirementError("Nr zlecenia jest wymagany.")
    used = {
        str(row.get("number") or "").strip().casefold()
        for row in orders
        if str(row.get("id") or "") != str(exclude_id or "")
    }
    if base.casefold() not in used:
        return base
    index = 2
    while f"{base}_{index}".casefold() in used:
        index += 1
    return f"{base}_{index}"


def _number(value: Any, default: float | None = None) -> float:
    if value is None or value == "":
        if default is not None:
            return default
        raise ValueError
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    return float(value)


def _entry_code(entry: dict[str, Any]) -> str:
    return str(entry.get("kod") or entry.get("id") or entry.get("symbol") or "").strip()


def _entry_qty(entry: dict[str, Any]) -> float:
    return _number(entry.get("ilosc_na_szt", entry.get("ilosc_na_sztuke", entry.get("ilosc", 1))), 1.0)


def _nested_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("polprodukty", "sklad"):
        value = raw.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, dict)]
    value = raw.get("BOM")
    if isinstance(value, list):
        out = []
        for row in value:
            if not isinstance(row, dict):
                continue
            typ = str(row.get("typ") or "polprodukt").strip().casefold()
            if typ not in {"polprodukt", "półprodukt", "semi", "semiproduct"}:
                continue
            out.append({
                "kod": _entry_code(row),
                "ilosc_na_szt": row.get("ilosc_na_szt", row.get("ilosc_na_sztuke", row.get("ilosc", 1))),
            })
        return out
    value = raw.get("bom")
    if isinstance(value, dict):
        return [{"kod": str(code), "ilosc_na_szt": qty} for code, qty in value.items()]
    return []


class RequirementCalculator:
    def __init__(self, product_catalog: ProductCatalog, semi_catalog: SemiProductCatalog | None = None) -> None:
        self.product_catalog = product_catalog
        self.semi_catalog = semi_catalog or SemiProductCatalog(product_catalog.cfg)

    def calculate(self, product_code: str, product_qty: int | float) -> dict[str, Any]:
        code = str(product_code or "").strip()
        if not code:
            raise RequirementError("Zlecenie nie ma wybranego produktu.")
        try:
            qty = _number(product_qty)
        except (TypeError, ValueError):
            raise RequirementError("Ilość produktu musi być liczbą.") from None
        if qty <= 0:
            raise RequirementError("Ilość produktu musi być większa od zera.")

        products = {
            str(item.get("kod") or "").strip().casefold(): item
            for item in self.product_catalog.list_products()
            if str(item.get("kod") or "").strip()
        }
        product = products.get(code.casefold())
        if product is None:
            raise RequirementError(f"Nie znaleziono produktu '{code}' w katalogu produktów.")

        semi_map = {
            str(item.get("kod") or "").strip().casefold(): item
            for item in self.semi_catalog.list_items()
            if str(item.get("kod") or "").strip()
        }
        semi_totals: dict[str, dict[str, Any]] = {}
        raw_totals: dict[tuple[str, str], dict[str, Any]] = {}
        warnings: list[str] = []

        root = product.get("polprodukty") or []
        if not isinstance(root, list):
            root = []
        if not root:
            warnings.append(f"Produkt '{code}' nie ma zdefiniowanego składu produktu.")

        for entry in root:
            if not isinstance(entry, dict):
                continue
            child = _entry_code(entry)
            if not child:
                warnings.append("Pominięto pozycję składu bez kodu półproduktu.")
                continue
            try:
                child_qty = _entry_qty(entry)
            except (TypeError, ValueError):
                warnings.append(f"Półprodukt '{child}' ma nieprawidłową ilość.")
                continue
            if child_qty <= 0:
                warnings.append(f"Półprodukt '{child}' ma ilość <= 0.")
                continue
            self._walk(child, qty * child_qty, semi_map, semi_totals, raw_totals, warnings, (), f"Produkt {code}")

        rows = []
        for item in sorted(semi_totals.values(), key=lambda x: str(x["kod"]).casefold()):
            rows.append({
                "typ": "Półprodukt", "kod": item["kod"], "nazwa": item.get("nazwa", ""),
                "ilosc": item["ilosc"], "jednostka": "szt.",
                "zrodlo": ", ".join(sorted(item.get("zrodla") or [])),
            })
        for item in sorted(raw_totals.values(), key=lambda x: (str(x["kod"]).casefold(), str(x["jednostka"]).casefold())):
            rows.append({
                "typ": "Surowiec", "kod": item["kod"], "nazwa": item.get("nazwa", ""),
                "ilosc": item["ilosc"], "jednostka": item.get("jednostka", ""),
                "zrodlo": ", ".join(sorted(item.get("zrodla") or [])),
            })
        return {
            "product_code": code,
            "product_name": str(product.get("nazwa") or ""),
            "product_qty": qty,
            "composition_revision": product.get("bom_revision", 1),
            "rows": rows,
            "warnings": warnings,
        }

    def _walk(self, code, qty, semi_map, semi_totals, raw_totals, warnings, path, source) -> None:
        key = str(code).strip().casefold()
        if key in path:
            warnings.append("Wykryto pętlę w składzie półproduktów: " + " → ".join((*path, key)))
            return
        semi = semi_map.get(key)
        bucket = semi_totals.setdefault(key, {
            "kod": str(code).strip(), "nazwa": str((semi or {}).get("nazwa") or ""),
            "ilosc": 0.0, "zrodla": set(),
        })
        bucket["ilosc"] += qty
        bucket["zrodla"].add(source)
        if semi is None:
            warnings.append(f"Brak definicji półproduktu '{code}'.")
            return

        raw = semi.get("_raw") if isinstance(semi.get("_raw"), dict) else {}
        nested = _nested_entries(raw)
        for child in nested:
            child_code = _entry_code(child)
            if not child_code:
                warnings.append(f"Półprodukt '{code}' zawiera pozycję bez kodu.")
                continue
            try:
                child_qty = _entry_qty(child)
            except (TypeError, ValueError):
                warnings.append(f"Półprodukt '{code}' ma nieprawidłową ilość składnika '{child_code}'.")
                continue
            if child_qty > 0:
                self._walk(child_code, qty * child_qty, semi_map, semi_totals, raw_totals, warnings, (*path, key), f"Półprodukt {code}")

        material = semi.get("surowiec") if isinstance(semi.get("surowiec"), dict) else {}
        material_code = str(material.get("kod") or material.get("symbol") or material.get("typ") or "").strip()
        if material_code:
            try:
                per_piece = _number(material.get("ilosc_na_szt", material.get("ilosc", material.get("dlugosc"))))
            except (TypeError, ValueError):
                warnings.append(f"Półprodukt '{code}' ma nieprawidłową ilość surowca '{material_code}'.")
            else:
                if per_piece > 0:
                    try:
                        loss = max(0.0, _number(semi.get("norma_strat_proc"), 0.0))
                    except (TypeError, ValueError):
                        loss = 0.0
                    unit = str(material.get("jednostka") or "").strip()
                    raw_key = (material_code.casefold(), unit.casefold())
                    raw_bucket = raw_totals.setdefault(raw_key, {
                        "kod": material_code, "nazwa": str(material.get("nazwa") or ""),
                        "ilosc": 0.0, "jednostka": unit, "zrodla": set(),
                    })
                    raw_bucket["ilosc"] += qty * per_piece * (1.0 + loss / 100.0)
                    raw_bucket["zrodla"].add(str(code))
        elif not nested:
            warnings.append(f"Półprodukt '{code}' nie ma surowca ani własnego składu.")
