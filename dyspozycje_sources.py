# version: 1.2
"""Źródła danych dla Dyspozycji (bez GUI)."""
# Zmiany 1.2:
# - Lista Magazynu w kreatorze korzysta z logika_magazyn.load_magazyn(include_external=True).
# - Klucze techniczne items/meta nie są już traktowane jak pozycje magazynowe.
# Zmiany 1.1:
# - Zlecenie wykonania korzysta z realnego Planowania oraz katalogów Produkt/Półprodukt.
# - Dodano kontekst źródła: poziom wykonania, nr zlecenia, produkt i ilość.

from __future__ import annotations

import json
import os
import sys
from typing import List, Tuple

try:
    print(f"[WM-DBG][DYSP][SRC] module_file={__file__}")
except Exception:
    pass

try:
    from config_manager import ConfigManager, get_config, get_machines_path, resolve_rel
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore
    get_config = None  # type: ignore
    get_machines_path = None  # type: ignore
    resolve_rel = None  # type: ignore

try:
    from core import root_paths as wm_root_paths
except Exception:  # pragma: no cover
    wm_root_paths = None  # type: ignore


def _runtime_cfg_manager():
    try:
        start_mod = sys.modules.get("start")
        if start_mod is not None:
            mgr = getattr(start_mod, "CONFIG_MANAGER", None)
            if mgr is not None:
                try:
                    print(
                        "[WM-DBG][DYSP][SRC] runtime manager=start.CONFIG_MANAGER "
                        f"{type(mgr).__name__}"
                    )
                except Exception:
                    pass
                return mgr
    except Exception:
        pass
    if ConfigManager is not None:
        try:
            mgr = ConfigManager()
            try:
                print(
                    "[WM-DBG][DYSP][SRC] runtime manager=ConfigManager() "
                    f"{type(mgr).__name__}"
                )
            except Exception:
                pass
            return mgr
        except Exception:
            pass
    return None


def _cfg() -> dict:
    mgr = _runtime_cfg_manager()
    if mgr is not None and hasattr(mgr, "load"):
        try:
            cfg = mgr.load() or {}
            try:
                paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
                print(
                    "[WM-DBG][DYSP][SRC] cfg paths:"
                    f" anchor_root={paths.get('anchor_root')}"
                    f" data_root={paths.get('data_root')}"
                    f" logs_dir={paths.get('logs_dir')}"
                )
            except Exception:
                pass
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    if callable(get_config):
        try:
            cfg = get_config() or {}
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    if ConfigManager is not None:
        try:
            cfg = ConfigManager().load() or {}
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    return {}


def _root_path(*parts: str) -> str:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        try:
            path_anchor = getattr(mgr, "path_anchor", None)
            if callable(path_anchor):
                result = os.path.join(str(path_anchor()), *parts)
                try:
                    print(f"[WM-DBG][DYSP][SRC] path_anchor{parts} -> {result}")
                except Exception:
                    pass
                return result
        except Exception:
            pass
    try:
        cfg = _cfg()
        paths = cfg.get("paths") or {}
        anchor = str(paths.get("anchor_root") or "").strip()
        if anchor:
            result = os.path.join(anchor, *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] cfg_anchor{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    return os.path.join(os.getcwd(), *parts)


def _data_path(*parts: str) -> str:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        try:
            path_data = getattr(mgr, "path_data", None)
            if callable(path_data):
                result = path_data(*parts)
                try:
                    print(f"[WM-DBG][DYSP][SRC] path_data{parts} -> {result}")
                except Exception:
                    pass
                return result
        except Exception:
            pass
    try:
        if wm_root_paths is not None:
            result = os.path.join(str(wm_root_paths.get_data_root()), *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] root_paths_data{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    try:
        cfg = _cfg()
        paths = cfg.get("paths") or {}
        data_root = str(paths.get("data_root") or "").strip()
        if data_root:
            result = os.path.join(data_root, *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] cfg_data{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    return os.path.join("data", *parts)


def _tools_dir_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_tools_dir())
        except Exception:
            pass
    return _data_path("narzedzia")


def _machines_file_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_machines())
        except Exception:
            pass
    return _data_path("maszyny", "maszyny.json")


def _warehouse_file_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_warehouse())
        except Exception:
            pass
    return _data_path("magazyn", "magazyn.json")


def _magazyn_dir_path() -> str:
    return _data_path("magazyn")


def _produkty_dir_path() -> str:
    return _data_path("produkty")


def _polprodukty_dir_path() -> str:
    return _data_path("polprodukty")


def _first_existing_path(*candidates: str | None) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        try:
            if os.path.exists(candidate):
                return candidate
        except Exception:
            continue
    return None


def _root_json_path(folder: str, filename: str) -> str:
    # Legacy helper zostawiony dla kompatybilności.
    # Nowe źródła kreatora Dyspozycji mają używać <ROOT>/data przez _data_path().
    return _root_path(folder, filename)


# =========================================================
# NARZĘDZIA
# =========================================================
def load_tool_choices() -> List[Tuple[str, str]]:
    tools_dir = _tools_dir_path()
    try:
        print(f"[WM-DBG][DYSP][SRC] tools_dir_selected={tools_dir}")
    except Exception:
        pass
    out = []

    try:
        for filename in sorted(os.listdir(tools_dir)):
            if not filename.endswith(".json"):
                continue

            file_stem = os.path.splitext(filename)[0].strip()
            if not file_stem.isdigit():
                continue

            path = os.path.join(tools_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            except Exception:
                continue

            if isinstance(doc, dict) and isinstance(doc.get("narzedzie"), dict):
                doc = doc.get("narzedzie") or {}
            elif isinstance(doc, dict) and isinstance(doc.get("tool"), dict):
                doc = doc.get("tool") or {}

            tool_id = str(
                doc.get("id")
                or doc.get("nr")
                or doc.get("numer")
                or file_stem
            ).strip()
            name = str(
                doc.get("nazwa")
                or doc.get("name")
                or doc.get("opis")
                or ""
            ).strip()

            if not tool_id:
                continue

            label = f"{tool_id} - {name}" if name else tool_id
            out.append((tool_id, label))

    except Exception:
        return []

    return out


# =========================================================
# MASZYNY
# =========================================================
def load_machine_choices() -> List[Tuple[str, str]]:
    cfg = _cfg()
    machine_path = None
    root_data_machine_path = _machines_file_path()

    if callable(get_machines_path):
        try:
            machine_path = get_machines_path(cfg)
        except Exception:
            machine_path = None

    path = _first_existing_path(
        root_data_machine_path,
        machine_path,
        _data_path("maszyny", "maszyny.json"),
    )
    try:
        print(
            "[WM-DBG][DYSP][SRC] machine_candidates="
            f"root_data:{root_data_machine_path} | "
            f"get_machines_path:{machine_path} | "
            f"data:{_data_path('maszyny', 'maszyny.json')}"
        )
        print(f"[WM-DBG][DYSP][SRC] machine_path_selected={path}")
    except Exception:
        pass
    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    rows = []
    if isinstance(data, dict):
        if isinstance(data.get("maszyny"), list):
            rows = data.get("maszyny") or []
        elif isinstance(data.get("items"), list):
            rows = data.get("items") or []
        elif isinstance(data.get("machines"), list):
            rows = data.get("machines") or []
        elif isinstance(data.get("lista"), list):
            rows = data.get("lista") or []
    elif isinstance(data, list):
        rows = data

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        if isinstance(row.get("maszyna"), dict):
            row = row.get("maszyna") or row

        mid = str(
            row.get("id")
            or row.get("nr_ewid")
            or row.get("nr")
            or row.get("numer")
            or row.get("kod")
            or ""
        ).strip()
        name = str(
            row.get("nazwa")
            or row.get("name")
            or row.get("opis")
            or row.get("typ")
            or ""
        ).strip()

        if not mid:
            continue

        label = f"{mid} - {name}" if name else mid
        out.append((mid, label))

    return out


# =========================================================
# MAGAZYN
# =========================================================
def load_magazyn_choices() -> List[Tuple[str, str]]:
    """Zwróć realne pozycje z tego samego loadera, którego używa moduł Magazyn."""
    try:
        from logika_magazyn import load_magazyn

        data = load_magazyn(include_external=True) or {}
    except Exception as exc:
        try:
            print(f"[WM-DBG][DYSP][SRC] canonical magazyn load failed: {exc}")
        except Exception:
            pass
        return []

    rows = data.get("pozycje") or data.get("items") or {}
    if isinstance(rows, dict):
        iterable = list(rows.items())
    elif isinstance(rows, list):
        iterable = [("", row) for row in rows]
    else:
        return []

    type_labels = {
        "surowiec": "Surowiec",
        "półprodukt": "Półprodukt",
        "polprodukt": "Półprodukt",
        "produkt": "Produkt",
    }
    type_order = {"surowiec": 0, "półprodukt": 1, "polprodukt": 1, "produkt": 2}
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    for key, raw in iterable:
        if not isinstance(raw, dict):
            continue
        code = str(
            raw.get("id")
            or raw.get("kod")
            or raw.get("nr")
            or raw.get("symbol")
            or key
            or ""
        ).strip()
        if not code:
            continue
        folded = code.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        name = str(raw.get("nazwa") or raw.get("name") or raw.get("opis") or "").strip()
        raw_type = str(raw.get("typ") or "").strip().lower()
        section = type_labels.get(raw_type, raw_type.capitalize() if raw_type else "Magazyn")
        main = f"{code} - {name}" if name and name != code else code
        out.append((code, f"{section} | {main}"))

    def _sort_key(item: Tuple[str, str]):
        code, label = item
        raw = rows.get(code) if isinstance(rows, dict) else None
        typ = str((raw or {}).get("typ") or "").strip().lower() if isinstance(raw, dict) else ""
        return (type_order.get(typ, 9), label.casefold())

    out.sort(key=_sort_key)
    return out


# =========================================================
# ZLECENIE WYKONANIA
# =========================================================
def _read_json_dict(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _planowanie_file_path() -> str:
    return _data_path('planowanie', 'plan.json')


def _product_record(code: str) -> dict:
    path = os.path.join(_produkty_dir_path(), f'{code}.json')
    data = _read_json_dict(path)
    if not data:
        return {}
    return {
        'kod': str(data.get('kod') or data.get('symbol') or code).strip(),
        'nazwa': str(data.get('nazwa') or data.get('name') or '').strip(),
    }


def _semi_record(code: str) -> dict:
    path = os.path.join(_polprodukty_dir_path(), f'{code}.json')
    data = _read_json_dict(path)
    if not data:
        return {}
    return {
        'kod': str(data.get('kod') or data.get('id') or code).strip(),
        'nazwa': str(data.get('nazwa') or data.get('name') or '').strip(),
    }


def _plan_orders() -> list[dict]:
    data = _read_json_dict(_planowanie_file_path())
    rows = data.get('orders') or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def load_zlecenie_wykonania_choices() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    for row in _plan_orders():
        number = str(row.get('number') or '').strip()
        if not number:
            continue
        object_id = f'zlecenie:{number}'
        key = object_id.casefold()
        if key in seen:
            continue
        seen.add(key)
        product = str(row.get('product_code') or row.get('symbol') or '').strip()
        qty = row.get('qty', '')
        label = f'ZLECENIE {number}'
        if product:
            label += f' — {product}'
        if qty not in ('', None):
            label += f' × {qty}'
        out.append((object_id, label))

    for prefix, folder, label_prefix in (
        ('produkt', _produkty_dir_path(), 'PRODUKT'),
        ('polprodukt', _polprodukty_dir_path(), 'PÓŁPRODUKT'),
    ):
        try:
            names = sorted(os.listdir(folder))
        except Exception:
            names = []
        for filename in names:
            if not filename.lower().endswith('.json'):
                continue
            code = os.path.splitext(filename)[0].strip()
            if not code or code.lower() == 'bom':
                continue
            object_id = f'{prefix}:{code}'
            if object_id.casefold() in seen:
                continue
            seen.add(object_id.casefold())
            rec = _product_record(code) if prefix == 'produkt' else _semi_record(code)
            name = str(rec.get('nazwa') or '').strip()
            label = f'{label_prefix} — {code}' + (f' — {name}' if name else '')
            out.append((object_id, label))

    return out


def load_zlecenie_wykonania_context(object_id: str) -> dict:
    raw = str(object_id or '').strip()
    if ':' not in raw:
        return {}
    prefix, code = raw.split(':', 1)
    prefix = prefix.strip().lower()
    code = code.strip()
    if not code:
        return {}

    if prefix == 'zlecenie':
        for row in _plan_orders():
            number = str(row.get('number') or '').strip()
            if number.casefold() != code.casefold():
                continue
            product_code = str(row.get('product_code') or row.get('symbol') or '').strip()
            return {
                'poziom_wykonania': 'zlecenie',
                'nr_zlecenia': number,
                'order_id': str(row.get('id') or ''),
                'product_code': product_code,
                'ilosc_domyslna': row.get('qty', 1),
                'client': str(row.get('client') or ''),
            }
        return {'poziom_wykonania': 'zlecenie', 'nr_zlecenia': code, 'ilosc_domyslna': 1}

    if prefix == 'produkt':
        rec = _product_record(code)
        return {
            'poziom_wykonania': 'produkt',
            'product_code': str(rec.get('kod') or code),
            'product_name': str(rec.get('nazwa') or ''),
            'ilosc_domyslna': 1,
        }

    if prefix == 'polprodukt':
        rec = _semi_record(code)
        return {
            'poziom_wykonania': 'polprodukt',
            'polprodukt_code': str(rec.get('kod') or code),
            'polprodukt_name': str(rec.get('nazwa') or ''),
            'ilosc_domyslna': 1,
        }

    return {}
