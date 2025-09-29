"""RC1 data bootstrap helpers.

This module initialises missing data files and normalises configuration paths
for RC1 builds.  It is designed to be idempotent – running it multiple times
only creates files that are missing and patches configuration values that still
use legacy absolute Windows paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "config.json"
DEFAULTS_PATH = ROOT / "config.defaults.json"

JsonValue = Any
TemplateFactory = Callable[[Mapping[str, Any], Mapping[str, Any]], JsonValue]


def _load_json(path: Path) -> JsonValue:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def _normalise_list(value: Any) -> List[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: List[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(stripped)
        elif isinstance(item, Mapping):
            for key in ("name", "title", "label", "value", "id"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    result.append(candidate.strip())
                    break
        elif isinstance(item, Iterable):
            result.extend(_normalise_list(item))
    return result


def _read_key(data: Mapping[str, Any], key: Any) -> Any:
    if not isinstance(data, Mapping):
        return None
    if isinstance(key, str):
        if key in data:
            return data[key]
        if "." in key:
            parts = key.split(".")
            current: Any = data
            for part in parts:
                if isinstance(current, Mapping):
                    current = current.get(part)
                else:
                    return None
            return current
        return data.get(key)
    parts = list(key)
    current: Any = data
    for part in parts:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _first_list(
    sources: Iterable[Mapping[str, Any]],
    keys: Iterable[Any],
    fallback: Iterable[str] | None = None,
) -> List[str]:
    for source in sources:
        for key in keys:
            value = _read_key(source, key)
            normalised = _normalise_list(value)
            if normalised:
                return normalised
    return list(fallback or [])


def _write_json(path: Path, data: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


@dataclass(frozen=True)
class FileSpec:
    path: Path
    factory: TemplateFactory


def _seq_default(_: Mapping[str, Any], __: Mapping[str, Any]) -> Dict[str, int]:
    return {"ZW": 0, "ZN": 0, "ZM": 0, "ZZ": 0}


def _pz_seq_default(_: Mapping[str, Any], __: Mapping[str, Any]) -> Dict[str, int]:
    return {"year": datetime.now().year, "seq": 0}


def _empty_dict(_: Mapping[str, Any], __: Mapping[str, Any]) -> Dict[str, Any]:
    return {}


def _empty_list(_: Mapping[str, Any], __: Mapping[str, Any]) -> List[Any]:
    return []


def _warehouse_default(_: Mapping[str, Any], __: Mapping[str, Any]) -> Dict[str, Any]:
    return {"items": {}, "meta": {}}


def _bom_default(_: Mapping[str, Any], __: Mapping[str, Any]) -> Dict[str, Any]:
    return {"items": []}


def _tool_types(defaults: Mapping[str, Any], config: Mapping[str, Any]) -> List[str]:
    fallback = [
        "Tłoczące",
        "Wykrawające",
        "Postępowe",
        "Giętarka",
    ]
    keys = [
        ("tools", "types"),
        "tools.types",
        "typy_narzedzi",
    ]
    return _first_list([config, defaults], keys, fallback)


def _tool_statuses(defaults: Mapping[str, Any], config: Mapping[str, Any]) -> List[str]:
    fallback = [
        "awaria zgłoszona",
        "diagnoza",
        "w naprawie",
        "test",
        "sprawdzona",
        "zakończone",
        "anulowane",
    ]
    keys = [
        ("tools", "statuses"),
        "tools.statuses",
    ]
    return _first_list([config, defaults], keys, fallback)


def _tool_templates(defaults: Mapping[str, Any], config: Mapping[str, Any]) -> List[str]:
    fallback = [
        "Przegląd wizualny",
        "Czyszczenie i smarowanie",
        "Pomiar luzów",
        "Wymiana elementu roboczego",
        "Test na prasie",
    ]
    keys = [
        ("tools", "task_templates"),
        "tools.task_templates",
        "szablony_zadan_narzedzia",
    ]
    return _first_list([config, defaults], keys, fallback)


REQUIRED_DIRECTORIES: List[Path] = [
    DATA_DIR,
    DATA_DIR / "produkty",
    DATA_DIR / "polprodukty",
    DATA_DIR / "magazyn",
    DATA_DIR / "narzedzia",
    DATA_DIR / "zlecenia",
    DATA_DIR / "logs",
    DATA_DIR / "backup",
    DATA_DIR / "layout",
    DATA_DIR / "user",
    DATA_DIR / "maszyny",
]

REQUIRED_FILES: List[FileSpec] = [
    FileSpec(DATA_DIR / "magazyn" / "magazyn.json", _warehouse_default),
    FileSpec(DATA_DIR / "magazyn" / "stany.json", _empty_dict),
    FileSpec(DATA_DIR / "magazyn" / "katalog.json", _empty_dict),
    FileSpec(DATA_DIR / "magazyn" / "polprodukty.json", _empty_dict),
    FileSpec(DATA_DIR / "magazyn" / "przyjecia.json", _empty_list),
    FileSpec(DATA_DIR / "magazyn" / "rezerwacje.json", _empty_list),
    FileSpec(DATA_DIR / "magazyn" / "_seq_pz.json", _pz_seq_default),
    FileSpec(DATA_DIR / "produkty" / "bom.json", _bom_default),
    FileSpec(DATA_DIR / "zlecenia" / "_seq.json", _seq_default),
    FileSpec(DATA_DIR / "narzedzia" / "typy_narzedzi.json", _tool_types),
    FileSpec(DATA_DIR / "narzedzia" / "statusy_narzedzi.json", _tool_statuses),
    FileSpec(DATA_DIR / "narzedzia" / "szablony_zadan.json", _tool_templates),
]


def _ensure_directories() -> List[str]:
    created: List[str] = []
    for directory in REQUIRED_DIRECTORIES:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception:
            continue
        if not any(directory.iterdir()):
            created.append(str(directory.relative_to(ROOT)))
    return created


def _ensure_files(defaults: Mapping[str, Any], config: Mapping[str, Any]) -> List[str]:
    created: List[str] = []
    for spec in REQUIRED_FILES:
        path = spec.path
        if path.exists():
            continue
        try:
            data = spec.factory(defaults, config)
            _write_json(path, data)
            created.append(str(path.relative_to(ROOT)))
        except Exception:
            continue
    return created


def _should_replace(current: Any) -> bool:
    if current in (None, ""):
        return True
    if not isinstance(current, str):
        return True
    if current.startswith("\\\\"):
        return True
    if ":" in current[:3]:
        return True
    return False


def _set_dotted(config: MutableMapping[str, Any], dotted: str, value: Any) -> bool:
    changed = False
    if config.get(dotted) != value:
        config[dotted] = value
        changed = True
    parts = dotted.split(".")
    current: MutableMapping[str, Any] = config
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, MutableMapping):
            child = {}
            current[part] = child
        current = child  # type: ignore[assignment]
    last = parts[-1]
    if current.get(last) != value:
        current[last] = value
        changed = True
    return changed


def _patch_config(config: MutableMapping[str, Any]) -> List[str]:
    replacements = {
        "paths.data_root": DATA_DIR.as_posix(),
        "paths.logs_dir": (DATA_DIR / "logs").as_posix(),
        "paths.backup_dir": (DATA_DIR / "backup").as_posix(),
        "paths.layout_dir": (DATA_DIR / "maszyny").as_posix(),
        "paths.warehouse_dir": (DATA_DIR / "magazyn").as_posix(),
        "paths.products_dir": (DATA_DIR / "produkty").as_posix(),
        "paths.tools_dir": (DATA_DIR / "narzedzia").as_posix(),
        "paths.orders_dir": (DATA_DIR / "zlecenia").as_posix(),
        "warehouse.stock_source": (DATA_DIR / "magazyn" / "magazyn.json").as_posix(),
        "warehouse.reservations_file": (DATA_DIR / "magazyn" / "rezerwacje.json").as_posix(),
        "bom.file": (DATA_DIR / "produkty" / "bom.json").as_posix(),
        "tools.types_file": (DATA_DIR / "narzedzia" / "typy_narzedzi.json").as_posix(),
        "tools.statuses_file": (DATA_DIR / "narzedzia" / "statusy_narzedzi.json").as_posix(),
        "tools.task_templates_file": (DATA_DIR / "narzedzia" / "szablony_zadan.json").as_posix(),
        "hall.machines_file": (DATA_DIR / "maszyny" / "maszyny.json").as_posix(),
        "machines.relative_path": Path("maszyny/maszyny.json").as_posix(),
        "system.data_root": DATA_DIR.as_posix(),
    }
    updated: List[str] = []
    for key, value in replacements.items():
        current = _read_key(config, key)
        if not _should_replace(current):
            continue
        if _set_dotted(config, key, value):
            updated.append(key)
    return updated


def ensure_data_bootstrap(verbose: bool = False) -> Dict[str, List[str]]:
    defaults = _load_json(DEFAULTS_PATH)
    config_data = _load_json(CONFIG_PATH) if CONFIG_PATH.exists() else {}

    created_dirs = _ensure_directories()
    created_files = _ensure_files(defaults, config_data)

    updated_keys: List[str] = []
    if isinstance(config_data, MutableMapping):
        updated_keys = _patch_config(config_data)
        if updated_keys:
            _write_json(CONFIG_PATH, config_data)

    if verbose or created_dirs or created_files or updated_keys:
        summary = {
            "dirs": created_dirs,
            "files": created_files,
            "config_keys": updated_keys,
        }
        print(f"[RC1][bootstrap] {summary}")
    return {
        "dirs": created_dirs,
        "files": created_files,
        "config_keys": updated_keys,
    }


__all__ = ["ensure_data_bootstrap"]

