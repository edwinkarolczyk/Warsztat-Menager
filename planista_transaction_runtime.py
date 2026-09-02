# WM-VERSION: 0.1
# Plik: planista_transaction_runtime.py
# version: 1.0
"""Rollback magazynu dla wieloetapowych operacji Planisty."""
from __future__ import annotations

import copy


def _warehouse_snapshot():
    import logika_magazyn as LM
    return copy.deepcopy(LM.load_magazyn(include_external=True))


def _restore_warehouse(snapshot) -> None:
    import logika_magazyn as LM
    LM.save_magazyn(copy.deepcopy(snapshot))
    try:
        LM.zapisz_stan_magazynu(copy.deepcopy(snapshot))
    except Exception:
        pass


def install_planista_transaction_runtime() -> None:
    import zlecenia_logika as ZL
    import zlecenia_progress as ZP

    current_replan = ZP._replan_remaining
    if not getattr(current_replan, "_wm_warehouse_transaction", False):
        def transactional_replan(order, kto="system"):
            snapshot = _warehouse_snapshot()
            order_snapshot = copy.deepcopy(order)
            try:
                return current_replan(order, kto)
            except Exception:
                try:
                    _restore_warehouse(snapshot)
                finally:
                    order.clear()
                    order.update(order_snapshot)
                raise
        transactional_replan._wm_warehouse_transaction = True
        transactional_replan._wm_original = current_replan
        ZP._replan_remaining = transactional_replan

    current_report = ZP.report_wykonano
    if not getattr(current_report, "_wm_warehouse_transaction", False):
        def transactional_report(zlec_id, wykonano, kto="system"):
            snapshot = _warehouse_snapshot()
            try:
                return current_report(zlec_id, wykonano, kto=kto)
            except Exception:
                _restore_warehouse(snapshot)
                raise
        transactional_report._wm_warehouse_transaction = True
        transactional_report._wm_original = current_report
        ZP.report_wykonano = transactional_report

    # Wszystkie starsze wejścia korzystają z tej samej implementacji.
    ZL.update_zlecenie = ZP.update_zlecenie
    ZL.report_wykonano = ZP.report_wykonano


__all__ = ["install_planista_transaction_runtime"]
