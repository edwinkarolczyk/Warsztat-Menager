from enum import Enum


class Role(str, Enum):
    """Predefined application roles."""

    ADMIN = "admin"
    MAGAZYNIER = "magazynier"
    KIEROWNIK = "kierownik"
    BRYGADZISTA = "brygadzista"
    BRYGADZISTA_SERWISANT = "brygadzista_serwisant"
    LIDER = "lider"


def _normalize(role: str | None) -> str:
    return str(role or "").strip().lower()


def has_role(role: str | None, *roles: Role) -> bool:
    """Return True if *role* matches any of *roles*."""
    normalized = _normalize(role)
    return any(normalized == r.value for r in roles)


def can_manage_stock(role: str | None) -> bool:
    """True if role is allowed to modify warehouse data."""
    return has_role(role, Role.ADMIN, Role.MAGAZYNIER)
