"""Helpers for building warehouse item names and codes."""
from __future__ import annotations

from typing import Dict, Any, Optional
import re


def build_code(category: str, material_type: str, **kwargs: Any) -> Dict[str, str]:
    """Return dictionary with generated ``nazwa`` and ``id`` for a warehouse item.

    Parameters
    ----------
    category:
        Item category (``profil``, ``rura``, ``półprodukt``).
    material_type:
        Material type used for the item.
    kwargs:
        Additional fields depending on the category.
    """
    category = category.lower()
    material_type = material_type.strip()
    if category == "profil":
        profile = str(kwargs.get("rodzaj_profilu", "")).strip()
        wymiar = str(kwargs.get("wymiar", "")).strip()
        name = f"{profile} {wymiar} {material_type}".strip()
        code_parts = ["PRF", profile, wymiar, material_type]
    elif category == "rura":
        fi = kwargs.get("fi")
        grubosc = kwargs.get("grubosc_scianki")
        name = f"Rura fi{fi}" + (f"x{grubosc}" if grubosc else "") + f" {material_type}"
        code_parts = ["RUR", f"FI{fi}"]
        if grubosc:
            code_parts.append(str(grubosc))
        code_parts.append(material_type)
    elif category == "półprodukt":
        nazwa = str(kwargs.get("nazwa", "")).strip()
        name = nazwa or material_type
        code_parts = ["PP", nazwa or material_type]
    else:
        name = material_type
        code_parts = [category, material_type]
    code = "-".join(str(p).replace(" ", "").upper() for p in code_parts if p)
    return {"nazwa": name, "id": code}
