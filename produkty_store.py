# version: 1.0
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
