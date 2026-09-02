# WM-VERSION: 0.1
# Plik: planista_audit_runtime.py
# version: 1.0
"""Domknięcie problemów spójności wykrytych w drugim audycie Planisty."""
from __future__ import annotations

import copy
from pathlib import Path


def _canonical_warehouse_snapshot():
    import logika_magazyn as LM

    return copy.deepcopy(LM.load_magazyn(include_external=False))


def _restore_canonical_warehouse(snapshot) -> None:
    import logika_magazyn as LM

    data = copy.deepcopy(snapshot)
    LM.save_magazyn(data)
    try:
        LM.zapisz_stan_magazynu(copy.deepcopy(data))
    except Exception:
        pass


def _file_snapshot(path: Path):
    path = Path(path)
    return (path.exists(), path.read_bytes() if path.exists() else b"")


def _restore_file(path: Path, snapshot) -> None:
    existed, payload = snapshot
    path = Path(path)
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    elif path.exists():
        path.unlink()


def _disposition_snapshot():
    try:
        import dyspozycje_store as DS

        path = Path(DS.get_dyspozycje_path())
        return path, _file_snapshot(path)
    except Exception:
        return None, None


def _restore_disposition_snapshot(path, snapshot) -> None:
    if path is None or snapshot is None:
        return
    try:
        _restore_file(path, snapshot)
    except Exception:
        pass


def _install_active_product_loader() -> None:
    import gui_magazyn_bom as GMB
    import zlecenia_logika as ZL

    Model = GMB.WarehouseModel
    current = Model._load_dir
    if not getattr(current, "_wm_active_products_only", False):
        def load_dir(folder: Path):
            out = {}
            folder = Path(folder)
            for pth in folder.glob("*.json"):
                if folder.name == "produkty" and "__v" in pth.stem:
                    continue
                rec = GMB._load_json(pth, None)
                if isinstance(rec, dict):
                    key = rec.get("kod") or rec.get("symbol") or pth.stem
                    out[str(key)] = rec
            return out
        load_dir._wm_active_products_only = True
        Model._load_dir = staticmethod(load_dir)

    if not getattr(ZL.list_produkty, "_wm_active_products_only", False):
        def list_products():
            ZL._ensure_dirs()
            out = []
            for path in ZL._paths()[1].glob("*.json"):
                if "__v" in path.stem:
                    continue
                try:
                    rec = ZL._read_json(path)
                except Exception:
                    continue
                out.append({
                    "kod": rec.get("kod") or rec.get("symbol") or path.stem,
                    "nazwa": rec.get("nazwa") or path.stem,
                    "version": rec.get("version"),
                    "revision": rec.get("revision", rec.get("rewizja")),
                })
            return out
        list_products._wm_active_products_only = True
        ZL.list_produkty = list_products


def _refresh_model_from_disk(model) -> None:
    import gui_magazyn_bom as GMB

    fresh = GMB.WarehouseModel()
    model.surowce = fresh.surowce
    model.raw_kinds = fresh.raw_kinds
    model.polprodukty = fresh.polprodukty
    model.produkty = fresh.produkty
    model.data_dir = fresh.data_dir
    model.src_file = fresh.src_file
    model.raw_kinds_file = fresh.raw_kinds_file
    model.pol_dir = fresh.pol_dir
    model.prd_dir = fresh.prd_dir


def _install_fresh_dependency_checks() -> None:
    import gui_magazyn_bom as GMB

    Model = GMB.WarehouseModel
    for name in ("delete_surowiec", "delete_polprodukt", "delete_produkt"):
        current = getattr(Model, name)
        if getattr(current, "_wm_fresh_dependencies", False):
            continue

        def make_wrapper(fn):
            def wrapped(self, *args, **kwargs):
                _refresh_model_from_disk(self)
                return fn(self, *args, **kwargs)
            wrapped._wm_fresh_dependencies = True
            wrapped._wm_original = fn
            return wrapped

        setattr(Model, name, make_wrapper(current))


def _install_cached_editor_refresh() -> None:
    import gui_magazyn_bom as GMB
    import gui_planista_panel as GPP

    current = GPP.PlanistaPanel._load_catalog
    if getattr(current, "_wm_fresh_model", False):
        return

    def load_catalog(self, label):
        cache = getattr(self, "_wm_catalog_editors", {}) or {}
        editor = cache.get(label)
        if editor is not None:
            try:
                if editor.winfo_exists():
                    editor.model = GMB.WarehouseModel()
                    editor._kind_dimension_modes = {
                        str(item["nazwa"]): str(item.get("pole") or "wymiar").casefold()
                        for item in editor.model.raw_kinds
                        if isinstance(item, dict) and item.get("nazwa")
                    }
                    if hasattr(editor, "s_kind_combo"):
                        editor.s_kind_combo.configure(values=tuple(editor._kind_dimension_modes))
            except Exception:
                pass
        return current(self, label)

    load_catalog._wm_fresh_model = True
    load_catalog._wm_original = current
    GPP.PlanistaPanel._load_catalog = load_catalog


def _install_live_reservation_state() -> None:
    import logika_magazyn as LM
    import planista_safety_runtime as PSR

    def reservation_state(order: dict):
        raw_need = order.get("zapotrzebowanie_surowce") or {}
        raw_reserved = order.get("rezerwacje_surowce") or {}
        plan = order.get("plan_polprodukty") or {}
        semi_reserved = order.get("rezerwacje_polprodukty") or {}
        pairs = []

        def effective(code, own):
            try:
                rec = LM.get_item(code) or {}
                total_now = max(0.0, float(rec.get("rezerwacje", 0) or 0))
            except Exception:
                total_now = 0.0
            return min(max(0.0, float(own or 0)), total_now)

        for code, rec in raw_need.items():
            if not isinstance(rec, dict):
                continue
            need = max(0.0, float(rec.get("ilosc", 0) or 0))
            if need > 1e-9:
                pairs.append((need, effective(code, raw_reserved.get(code, 0))))
        for code, rec in plan.items():
            if not isinstance(rec, dict):
                continue
            need = max(0.0, float(rec.get("z_magazynu", 0) or 0))
            if need > 1e-9:
                pairs.append((need, effective(code, semi_reserved.get(code, 0))))

        if not pairs:
            return True, "nie dotyczy"
        if all(have + 1e-9 >= need for need, have in pairs):
            return True, "pełne"
        if any(have > 1e-9 for _, have in pairs):
            return False, "częściowe"
        return False, "brak"

    PSR._reservation_state = reservation_state


def _install_full_transactions() -> None:
    import planista_safety_runtime as PSR
    import planista_transaction_runtime as PTR
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP

    # Snapshot rollbacku obejmuje wyłącznie kanoniczny magazyn.json, bez widoku
    # dołączonych kartotek Surowców/Półproduktów.
    PTR._warehouse_snapshot = _canonical_warehouse_snapshot
    PTR._restore_warehouse = _restore_canonical_warehouse

    # Zostaje jeden rollback: cała operacja zlecenia. Prywatny replan nie wykonuje
    # już drugiego, konkurencyjnego odtwarzania rezerwacji.
    PSR._restore_reservations = lambda *_args, **_kwargs: None
    current_replan = ZP._replan_remaining
    if getattr(current_replan, "_wm_warehouse_transaction", False):
        ZP._replan_remaining = current_replan._wm_original

    current_report = ZP.report_wykonano
    if getattr(current_report, "_wm_warehouse_transaction", False):
        current_report = current_report._wm_original

    current_update = ZP.update_zlecenie

    def transactional_existing(fn):
        if getattr(fn, "_wm_full_transaction", False):
            return fn

        def wrapped(zlec_id, *args, **kwargs):
            warehouse = _canonical_warehouse_snapshot()
            order_path = Path(ZL._order_path(zlec_id))
            order_snapshot = _file_snapshot(order_path)
            disp_path, disp_snapshot = _disposition_snapshot()
            try:
                return fn(zlec_id, *args, **kwargs)
            except Exception:
                _restore_canonical_warehouse(warehouse)
                _restore_file(order_path, order_snapshot)
                _restore_disposition_snapshot(disp_path, disp_snapshot)
                raise

        wrapped._wm_full_transaction = True
        wrapped._wm_original = fn
        return wrapped

    ZP.update_zlecenie = transactional_existing(current_update)
    ZP.report_wykonano = transactional_existing(current_report)
    ZL.update_zlecenie = ZP.update_zlecenie
    ZL.report_wykonano = ZP.report_wykonano

    current_create = ZL.create_zlecenie
    if not getattr(current_create, "_wm_full_transaction", False):
        def create_transaction(*args, **kwargs):
            warehouse = _canonical_warehouse_snapshot()
            disp_path, disp_snapshot = _disposition_snapshot()
            before = {p.name for p in ZL._orders_dir().glob("*.json")}
            try:
                return current_create(*args, **kwargs)
            except Exception:
                _restore_canonical_warehouse(warehouse)
                _restore_disposition_snapshot(disp_path, disp_snapshot)
                for path in ZL._orders_dir().glob("*.json"):
                    if path.name not in before:
                        try:
                            path.unlink()
                        except Exception:
                            pass
                raise
        create_transaction._wm_full_transaction = True
        create_transaction._wm_original = current_create
        ZL.create_zlecenie = create_transaction


def install_planista_audit_runtime() -> None:
    _install_active_product_loader()
    _install_fresh_dependency_checks()
    _install_cached_editor_refresh()
    _install_live_reservation_state()
    _install_full_transactions()


__all__ = [
    "install_planista_audit_runtime",
    "_canonical_warehouse_snapshot",
    "_restore_canonical_warehouse",
    "_file_snapshot",
    "_restore_file",
]
