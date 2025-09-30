# -*- coding: utf-8 -*-
"""Runtime hook that prefers the optional rc1_audit_plus module for audit.run."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any, Callable, Optional


_AUDIT_PATCH_FLAG = "_rc1_audit_run_wrapped"


def _load_audit_plus() -> Optional[ModuleType]:
    """Safely import the optional :mod:`rc1_audit_plus` module."""
    try:
        return importlib.import_module("rc1_audit_plus")
    except Exception:  # pragma: no cover - defensive fallback
        return None


def _wrap_audit_run(audit_module: ModuleType) -> None:
    """Patch :mod:`audit` so that ``audit.run`` prefers Audit+ implementation."""
    if getattr(audit_module, _AUDIT_PATCH_FLAG, False):
        return

    original_run: Optional[Callable[..., Any]] = getattr(audit_module, "run", None)
    audit_plus = _load_audit_plus()
    audit_plus_run: Optional[Callable[..., Any]] = None
    if audit_plus is not None:
        audit_plus_run = getattr(audit_plus, "run", None)

    def run_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if callable(audit_plus_run):
            try:
                result = audit_plus_run(*args, **kwargs)
            except Exception:  # pragma: no cover - keep compatibility on failure
                result = None
            else:
                if (
                    isinstance(result, dict)
                    and "ok" in result
                    and "msg" in result
                ):
                    return result
        if callable(original_run):
            return original_run(*args, **kwargs)
        return {"ok": False, "msg": "audit.run missing", "path": None}

    try:
        setattr(audit_module, "run", run_wrapper)
        setattr(audit_module, _AUDIT_PATCH_FLAG, True)
    except Exception:  # pragma: no cover - we can live without the patch
        pass


def _patch_if_loaded_now() -> bool:
    """Patch an already-imported :mod:`audit` module."""
    audit_module = sys.modules.get("audit")
    if audit_module is None:
        return False
    _wrap_audit_run(audit_module)
    return True


class _AuditPostImportHook(importlib.abc.MetaPathFinder):
    """Finder that patches :mod:`audit` immediately after it is imported."""

    def __init__(self) -> None:
        self._reentrant = False

    def find_spec(
        self,
        fullname: str,
        path: Optional[list[str]] = None,
        target: Optional[ModuleType] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        if fullname != "audit" or self._reentrant:
            return None

        self._reentrant = True
        try:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        finally:
            self._reentrant = False

        if spec is None or spec.loader is None:
            return spec

        spec.loader = _LoaderWrapper(spec.loader)
        return spec


class _LoaderWrapper(importlib.abc.Loader):
    """Loader proxy that patches the module after executing it."""

    def __init__(self, wrapped_loader: importlib.abc.Loader) -> None:
        self._wrapped_loader = wrapped_loader

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped_loader, item)

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> Optional[ModuleType]:
        if hasattr(self._wrapped_loader, "create_module"):
            return self._wrapped_loader.create_module(spec)  # type: ignore[misc]
        return None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped_loader.exec_module(module)
        _wrap_audit_run(module)


def _install() -> None:
    if _patch_if_loaded_now():
        return

    hook = _AuditPostImportHook()
    if not any(isinstance(existing, _AuditPostImportHook) for existing in sys.meta_path):
        sys.meta_path.insert(0, hook)


try:
    _install()
except Exception:  # pragma: no cover - hook installation should not break startup
    pass
