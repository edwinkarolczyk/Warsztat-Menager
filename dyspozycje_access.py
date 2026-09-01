# version: 1.0
"""Uprawnienia akcji Dyspozycji niezależne od dostępu do samego modułu."""
from __future__ import annotations

from typing import Any

from config_manager import ConfigManager
from wm_access import is_module_allowed_for_role, normalize_role_name

ACTION_ADD = "dyspozycje_add"
ACTION_EDIT = "dyspozycje_edit"
ACTIONS = (ACTION_ADD, ACTION_EDIT)

DEFAULT_ROLE_ACTIONS: dict[str, dict[str, bool]] = {
    "administrator": {ACTION_ADD: True, ACTION_EDIT: True},
    "kierownik": {ACTION_ADD: True, ACTION_EDIT: True},
    "brygadzista": {ACTION_ADD: True, ACTION_EDIT: True},
    "operator": {ACTION_ADD: False, ACTION_EDIT: False},
    "student": {ACTION_ADD: False, ACTION_EDIT: False},
    "sezonowiec": {ACTION_ADD: False, ACTION_EDIT: False},
    "guest": {ACTION_ADD: False, ACTION_EDIT: False},
}


def _load_all() -> dict[str, dict[str, bool]]:
    cfg = ConfigManager()
    raw = cfg.get("access.role_actions", {})
    result = {role: dict(actions) for role, actions in DEFAULT_ROLE_ACTIONS.items()}
    if not isinstance(raw, dict):
        return result
    for raw_role, raw_actions in raw.items():
        role = normalize_role_name(raw_role)
        if not role or not isinstance(raw_actions, dict):
            continue
        target = result.setdefault(role, {action: False for action in ACTIONS})
        for action in ACTIONS:
            if action in raw_actions:
                target[action] = bool(raw_actions[action])
    return result


def get_role_actions(role: str) -> dict[str, bool]:
    role_key = normalize_role_name(role)
    default = DEFAULT_ROLE_ACTIONS.get(role_key, {action: False for action in ACTIONS})
    current = _load_all().get(role_key, default)
    return {action: bool(current.get(action, False)) for action in ACTIONS}


def set_role_actions(role: str, actions: dict[str, Any]) -> None:
    role_key = normalize_role_name(role)
    if not role_key:
        return
    cfg = ConfigManager()
    raw = cfg.get("access.role_actions", {})
    payload: dict[str, dict[str, bool]] = dict(raw) if isinstance(raw, dict) else {}
    existing = payload.get(role_key)
    role_payload = dict(existing) if isinstance(existing, dict) else {}
    for action in ACTIONS:
        if action in actions:
            role_payload[action] = bool(actions[action])
    payload[role_key] = role_payload
    cfg.set("access.role_actions", payload)
    if hasattr(cfg, "save_all"):
        cfg.save_all()
    else:
        cfg.save()


def is_role_action_allowed(role: str, action: str) -> bool:
    action_key = str(action or "").strip()
    if action_key not in ACTIONS:
        return False
    role_key = normalize_role_name(role)
    if not is_module_allowed_for_role(role_key, "zlecenia"):
        return False
    return bool(get_role_actions(role_key).get(action_key, False))


def resolve_role_for_login(login: str) -> str:
    login_key = str(login or "").strip().casefold()
    try:
        from services.profile_service import ProfileService

        active = ProfileService.get_active_profile()
        if isinstance(active, dict):
            active_login = str(active.get("login") or "").strip().casefold()
            if not login_key or not active_login or active_login == login_key:
                role = str(active.get("rola") or active.get("role") or "").strip()
                if role:
                    return normalize_role_name(role)
        if login_key:
            for profile in ProfileService.list_profiles() or []:
                if not isinstance(profile, dict):
                    continue
                if str(profile.get("login") or "").strip().casefold() != login_key:
                    continue
                return normalize_role_name(profile.get("rola") or profile.get("role") or "")
    except Exception:
        pass
    return ""


__all__ = [
    "ACTION_ADD",
    "ACTION_EDIT",
    "ACTIONS",
    "DEFAULT_ROLE_ACTIONS",
    "get_role_actions",
    "set_role_actions",
    "is_role_action_allowed",
    "resolve_role_for_login",
]
