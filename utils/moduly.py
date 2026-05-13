# utils/moduly.py
# version: 1.0
# Zmiany:
# - Nowy loader manifestu modułów (PL) + walidacja zależności + tag do logów.
# - Brak wpływu na istniejącą logikę; wyłącznie funkcje pomocnicze.

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, TYPE_CHECKING

from core.path_utils import resolve_path

if TYPE_CHECKING:  # pragma: no cover - tylko na potrzeby typowania
    from config_manager import ConfigManager

MODULES_DEFAULT_ACTIVE: Dict[str, bool] = {
    "narzedzia": True,
    "zlecenia": False,
    "magazyn": False,
    "maszyny": False,
    "profil": False,
    "jarvis": False,
    "ustawienia": False,
    "panel_glowny": False,
    "hala": False,
    "planowanie": True,
}

MODULY: Dict[str, Dict[str, Any]] = {
    "narzedzia": {"active": MODULES_DEFAULT_ACTIVE["narzedzia"], "label": "Narzędzia"},
    "zlecenia": {"active": MODULES_DEFAULT_ACTIVE["zlecenia"], "label": "Zlecenia"},
    "magazyn": {"active": MODULES_DEFAULT_ACTIVE["magazyn"], "label": "Magazyn"},
    "profil": {"active": MODULES_DEFAULT_ACTIVE["profil"], "label": "Profil"},
    "maszyny": {"active": MODULES_DEFAULT_ACTIVE["maszyny"], "label": "Maszyny"},
    "jarvis": {"active": MODULES_DEFAULT_ACTIVE["jarvis"], "label": "Jarvis"},
    "ustawienia": {"active": MODULES_DEFAULT_ACTIVE["ustawienia"], "label": "Ustawienia"},
    "panel_glowny": {
        "active": MODULES_DEFAULT_ACTIVE["panel_glowny"],
        "label": "Panel główny",
    },
    "hala": {"active": MODULES_DEFAULT_ACTIVE["hala"], "label": "Hala"},
    "planowanie": {"active": MODULES_DEFAULT_ACTIVE["planowanie"], "label": "Planowanie"},
}

_MANIFEST_CACHE: Dict[str, Any] | None = None
_MANIFEST_CACHE_PATH: str | None = None


class ManifestBlad(Exception):
    """Błąd związany z manifestem modułów."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _wczytaj_json(sciezka: str) -> Dict[str, Any]:
    if not os.path.exists(sciezka):
        raise ManifestBlad(f"[ERROR] Brak pliku manifestu modułów: {sciezka}")
    with open(sciezka, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestBlad(f"[ERROR] Niepoprawny JSON w {sciezka}: {e}") from e


def _default_module_entry(modul_id: str) -> Dict[str, Any]:
    active = MODULY.get(modul_id, {}).get("active", True)
    return {"id": modul_id, "active": bool(active)}


def manifest_path(cfg: "ConfigManager") -> str:
    return _norm(resolve_path(cfg.path_data(), "moduly_manifest.json"))


def zaladuj_manifest(cfg: "ConfigManager" | None = None) -> Dict[str, Any]:
    """
    Ładuje i cache'uje manifest modułów.
    """
    global _MANIFEST_CACHE, _MANIFEST_CACHE_PATH
    if cfg is None:
        from config_manager import ConfigManager as _ConfigManager

        cfg = _ConfigManager()
    path = manifest_path(cfg)
    if _MANIFEST_CACHE is not None and _MANIFEST_CACHE_PATH == path:
        return _MANIFEST_CACHE
    if not os.path.isfile(path):
        default = {
            "modules": [
                _default_module_entry("panel_glowny"),
                _default_module_entry("ustawienia"),
                _default_module_entry("profil"),
                _default_module_entry("narzedzia"),
                _default_module_entry("magazyn"),
                _default_module_entry("zlecenia"),
                _default_module_entry("jarvis"),
                _default_module_entry("maszyny"),
                _default_module_entry("planowanie"),
            ]
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"[WM-DBG][MANIFEST] Utworzono domyślny manifest modułów: {path}")
    manifest = _wczytaj_json(path)
    _MANIFEST_CACHE = manifest
    _MANIFEST_CACHE_PATH = path
    return manifest


def _iter_modules(manifest: Dict[str, Any]) -> List[Any]:
    if not isinstance(manifest, dict):
        return []
    modules = manifest.get("modules")
    if isinstance(modules, list):
        return modules
    legacy = manifest.get("moduly")
    if isinstance(legacy, list):
        return legacy
    return []


def _module_id(entry: Any) -> str:
    if isinstance(entry, dict):
        value = entry.get("id") or entry.get("name")
        if value is not None:
            return str(value)
    return str(entry)


def pobierz_modul(modul_id: str, manifest: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Zwraca definicję modułu wg ``id``."""

    man = manifest or zaladuj_manifest()
    for entry in _iter_modules(man):
        if _module_id(entry) == modul_id:
            if isinstance(entry, dict):
                payload = dict(entry)
            else:
                payload = {"id": _module_id(entry)}
            payload.setdefault("depends", payload.pop("korzysta_z", []))
            payload["active"] = bool(payload.get("active", True))
            if isinstance(payload["depends"], list):
                payload["depends"] = [str(dep) for dep in payload["depends"]]
            else:
                payload["depends"] = [str(payload["depends"])] if payload["depends"] else []
            return payload
    raise ManifestBlad(f"[ERROR] Nie znaleziono modułu o id='{modul_id}'.")


def lista_modulow(manifest: Dict[str, Any] | None = None) -> List[str]:
    """Zwraca listę identyfikatorów modułów."""

    man = manifest or zaladuj_manifest()
    return [_module_id(entry) for entry in _iter_modules(man)]


def zaleznosci(modul_id: str, manifest: Dict[str, Any] | None = None) -> List[str]:
    """Zwraca listę zależności modułu."""

    mod = pobierz_modul(modul_id, manifest)
    deps = mod.get("depends", []) if isinstance(mod, dict) else []
    if isinstance(deps, list):
        return [str(dep) for dep in deps]
    if deps:
        return [str(deps)]
    return []


def sprawdz_reguly(manifest: Dict[str, Any] | None = None) -> List[str]:
    """
    Sprawdza sekcję 'reguly' i zwraca listę ostrzeżeń/błędów (stringi).
    Na dziś: tylko raport tekstowy (bez podnoszenia wyjątków).
    """
    man = manifest or zaladuj_manifest()
    komunikaty: List[str] = []
    reguly = man.get("reguly", []) if isinstance(man, dict) else []
    znane = set(lista_modulow(man))
    for r in reguly:
        a = r.get("modul")
        b = r.get("musi_startowac_przed")
        if a not in znane:
            komunikaty.append(f"[WARN] Reguła odwołuje się do nieznanego modułu: {a}")
        if b not in znane:
            komunikaty.append(f"[WARN] Reguła odwołuje się do nieznanego modułu: {b}")
    return komunikaty


def assert_zaleznosci_gotowe(modul_id: str, zainicjowane: List[str], manifest: Dict[str, Any] | None = None) -> None:
    """
    Dla danego modułu sprawdza, czy wszystkie 'korzysta_z' znajdują się na liście zainicjowanych.
    Jeśli nie – rzuca ManifestBlad z czytelnym komunikatem PL.
    """
    deps = zaleznosci(modul_id, manifest)
    brak = [d for d in deps if d not in zainicjowane]
    if brak:
        raise ManifestBlad(
            "[ERROR] Moduł '{0}' wymaga wcześniejszej inicjalizacji: {1}".format(
                modul_id, ", ".join(brak)
            )
        )


def module_active(
    modul_id: str,
    manifest: Dict[str, Any] | None = None,
    cfg: "ConfigManager | Mapping[str, Any] | None" = None,
) -> bool:
    """Zwróć informację o aktywności modułu.

    Flagi wygaszania zostały usunięte, dlatego wszystkie moduły pozostają
    aktywne niezależnie od konfiguracji.
    """
    return True


def tag_logu(modul_id: str) -> str:
    """
    Zwraca ujednolicony tag do logów, np. '[WM-DBG][mod:magazyn]'
    """
    return f"[WM-DBG][mod:{modul_id}]"


# ⏹ KONIEC KODU
