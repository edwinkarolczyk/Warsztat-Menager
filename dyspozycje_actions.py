# version: 1.0
# -*- coding: utf-8 -*-
"""Wspólne akcje biznesowe rozpoczęcia i zakończenia Dyspozycji.

Moduł nie tworzy GUI. Pilnuje skutków ubocznych wymaganych przez Dyspozycje:
- rezerwacji i rozliczenia Magazynu dla wykonania produkcji,
- historii/statusu we wspólnym store,
- synchronizacji automatycznych przeglądów Maszyn.
"""

from __future__ import annotations

from typing import Any

from dyspozycje_store import set_dyspozycja_status, update_dyspozycja
from maszyny_dyspozycje import sync_machine_review_from_dyspozycja
from planowanie_magazyn import (
    WarehouseIntegrationError,
    add_semiproduct_surplus,
    reconcile_and_consume_execution,
    release_execution_reservations,
    reserve_execution_requirements,
    stock_snapshot_for_operation,
)


class DyspozycjaActionError(RuntimeError):
    """Kontrolowany błąd akcji Dyspozycji przeznaczony do pokazania w GUI."""


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "").strip().lower()


def _type(row: dict[str, Any]) -> str:
    return str(row.get("typ_dyspozycji") or row.get("typ") or "").strip().lower()


def _calculate_execution_requirements(
    row: dict[str, Any],
    qty: float,
    *,
    stock_snapshot: Any = None,
) -> dict[str, Any]:
    meta = dict(row.get("meta") or {}) if isinstance(row.get("meta"), dict) else {}
    level = str(meta.get("poziom_wykonania") or "").strip().lower()

    from produkty_store import ProductCatalog
    from polprodukty_store import SemiProductCatalog
    from planowanie_zapotrzebowanie import RequirementCalculator, RequirementError

    products = ProductCatalog()
    calc = RequirementCalculator(products, SemiProductCatalog(products.cfg))
    if level in {"zlecenie", "produkt"}:
        code = str(meta.get("product_code") or "").strip()
        if not code:
            raise RequirementError("Brak produktu w Dyspozycji wykonania.")
        return calc.calculate_with_stock(code, qty, stock_snapshot=stock_snapshot)
    if level == "polprodukt":
        code = str(meta.get("polprodukt_code") or "").strip()
        if not code:
            raise RequirementError("Brak półproduktu w Dyspozycji wykonania.")
        return calc.calculate_semi_with_stock(
            code,
            qty,
            ignore_root_stock=True,
            stock_snapshot=stock_snapshot,
        )
    raise RequirementError("Nieznany poziom wykonania Dyspozycji.")


def start_dyspozycja(row: dict[str, Any], *, who: str) -> dict[str, Any]:
    """Rozpocznij Dyspozycję z pełnymi skutkami biznesowymi."""

    mapped = dict(row or {})
    dysp_id = str(mapped.get("id") or "").strip()
    if not dysp_id:
        raise DyspozycjaActionError("Brak ID Dyspozycji.")
    if _status(mapped) != "nowa":
        raise DyspozycjaActionError("Rozpocząć można tylko nową Dyspozycję.")

    actor = str(who or mapped.get("autor") or "").strip()
    is_execution = _type(mapped) == "zlecenie_wykonania"

    if is_execution:
        meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
        try:
            planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
            requirements = _calculate_execution_requirements(mapped, planned)
            reservations = reserve_execution_requirements(
                dysp_id,
                list(requirements.get("rows") or []),
                user=actor,
                context=f"Rozpoczęcie Dyspozycji {dysp_id}",
            )
        except Exception as exc:
            raise DyspozycjaActionError(
                f"Nie udało się przygotować Dyspozycji wykonania:\n{exc}"
            ) from exc

        meta["zapotrzebowanie_start"] = list(requirements.get("rows") or [])
        meta["magazyn_rezerwacje"] = reservations
        updated = update_dyspozycja(dysp_id, {"meta": meta})
        if not updated:
            try:
                release_execution_reservations(
                    dysp_id,
                    user=actor,
                    context="Błąd zapisu Dyspozycji",
                )
            except Exception:
                pass
            raise DyspozycjaActionError(
                "Nie udało się zapisać rezerwacji w Dyspozycji."
            )
        mapped = updated

    changed = set_dyspozycja_status(
        dysp_id,
        "w_toku",
        changed_by=actor,
    )
    if not changed:
        if is_execution:
            try:
                release_execution_reservations(
                    dysp_id,
                    user=actor,
                    context="Nieudane rozpoczęcie Dyspozycji",
                )
            except Exception:
                pass
        raise DyspozycjaActionError("Ta zmiana statusu nie jest dozwolona.")

    try:
        sync_machine_review_from_dyspozycja(changed, actor=actor)
    except Exception as exc:
        # Status jest już zapisany. Synchronizacja maszyny nie może cofnąć
        # poprawnej zmiany Dyspozycji, ale błąd ma być widoczny dla wywołującego.
        raise DyspozycjaActionError(
            f"Dyspozycja została rozpoczęta, ale nie udało się zsynchronizować Maszyny:\n{exc}"
        ) from exc

    return changed


def close_dyspozycja(
    row: dict[str, Any],
    *,
    who: str,
    note: str = "",
    actual_qty: float | None = None,
) -> dict[str, Any]:
    """Zakończ Dyspozycję z rozliczeniem produkcji i synchronizacją Maszyn."""

    mapped = dict(row or {})
    dysp_id = str(mapped.get("id") or "").strip()
    if not dysp_id:
        raise DyspozycjaActionError("Brak ID Dyspozycji.")
    if _status(mapped) not in {"w_toku", "wstrzymana"}:
        raise DyspozycjaActionError(
            "Zakończyć można Dyspozycję W toku albo Wstrzymaną."
        )

    actor = str(who or mapped.get("autor") or "").strip()
    typ = _type(mapped)

    if typ == "zlecenie_wykonania":
        if actual_qty is None:
            raise DyspozycjaActionError(
                "Przy zakończeniu wykonania trzeba podać faktycznie wykonaną ilość."
            )
        try:
            actual = float(actual_qty)
        except (TypeError, ValueError) as exc:
            raise DyspozycjaActionError("Nieprawidłowa wykonana ilość.") from exc
        if actual < 0:
            raise DyspozycjaActionError("Wykonana ilość nie może być ujemna.")

        meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
        try:
            planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
        except (TypeError, ValueError):
            planned = 0.0
        meta["ilosc_wykonana"] = actual
        meta["brak_wykonania"] = max(0.0, planned - actual)
        level = str(meta.get("poziom_wykonania") or "").strip().lower()

        try:
            if actual <= 0:
                release_execution_reservations(
                    dysp_id,
                    user=actor,
                    context=f"Zamknięcie bez wykonania {dysp_id}",
                )
                requirements_actual: dict[str, Any] = {"rows": [], "warnings": []}
                consumption: list[Any] = []
            else:
                own_snapshot = stock_snapshot_for_operation(dysp_id)
                requirements_actual = _calculate_execution_requirements(
                    mapped,
                    actual,
                    stock_snapshot=own_snapshot,
                )
                raw_shortages: list[str] = []
                for req_row in requirements_actual.get("rows") or []:
                    if str(req_row.get("typ") or "").strip().lower() != "surowiec":
                        continue
                    try:
                        missing = float(req_row.get("brak") or 0)
                    except (TypeError, ValueError):
                        missing = 0.0
                    if missing > 1e-9:
                        raw_shortages.append(
                            f"{req_row.get('kod', '')}: {missing:g} {req_row.get('jednostka', '')}"
                        )
                critical_warnings = [
                    str(item)
                    for item in (requirements_actual.get("warnings") or [])
                    if str(item).startswith("Brak definicji półproduktu")
                    or "nie ma surowca ani własnego składu" in str(item)
                ]
                if raw_shortages or critical_warnings:
                    details: list[str] = []
                    if raw_shortages:
                        details.append("Braki surowców:\n" + "\n".join(raw_shortages[:15]))
                    if critical_warnings:
                        details.append(
                            "Braki definicji:\n" + "\n".join(critical_warnings[:10])
                        )
                    raise DyspozycjaActionError(
                        "Nie można zakończyć wykonania, bo Magazyn/Skład nie pozwala "
                        "rozliczyć podanej ilości.\n\n" + "\n\n".join(details)
                    )
                consumption = reconcile_and_consume_execution(
                    dysp_id,
                    list(requirements_actual.get("rows") or []),
                    user=actor,
                    context=f"Dyspozycja {dysp_id}",
                )
        except DyspozycjaActionError:
            raise
        except WarehouseIntegrationError as exc:
            raise DyspozycjaActionError(
                f"Nie udało się rozliczyć Magazynu:\n{exc}\n\nDyspozycja nie została zakończona."
            ) from exc
        except Exception as exc:
            raise DyspozycjaActionError(
                f"Nie udało się przeliczyć wykonanej ilości:\n{exc}\n\nDyspozycja nie została zakończona."
            ) from exc

        meta["zapotrzebowanie_wykonane"] = list(requirements_actual.get("rows") or [])
        meta["magazyn_zuzycie"] = consumption
        if level == "polprodukt":
            surplus = max(0.0, actual - planned)
            meta["naddatek"] = surplus
            if surplus > 0:
                code = str(meta.get("polprodukt_code") or "").strip()
                name = str(meta.get("polprodukt_name") or code)
                try:
                    result = add_semiproduct_surplus(
                        code,
                        surplus,
                        name=name,
                        user=actor,
                        context=f"Dyspozycja {dysp_id}",
                        operation_id=dysp_id,
                    )
                except WarehouseIntegrationError as exc:
                    raise DyspozycjaActionError(
                        "Zużycie zostało rozliczone, ale nie udało się zaksięgować "
                        f"naddatku:\n{exc}\n\nDyspozycja nie została zakończona. "
                        "Ponowna próba nie zużyje materiału drugi raz."
                    ) from exc
                meta["naddatek_zaksiegowany"] = bool(
                    result.get("dodano") or result.get("already_settled")
                )
        updated = update_dyspozycja(dysp_id, {"meta": meta})
        if updated:
            mapped = updated

    changed = set_dyspozycja_status(
        dysp_id,
        "zamknieta",
        changed_by=actor,
        uwagi=str(note or "").strip(),
    )
    if not changed:
        raise DyspozycjaActionError("Nie udało się zakończyć Dyspozycji.")

    try:
        sync_machine_review_from_dyspozycja(
            changed,
            actor=actor,
            result_note=str(note or "").strip(),
        )
    except Exception as exc:
        raise DyspozycjaActionError(
            f"Dyspozycja została zakończona, ale nie udało się zsynchronizować Maszyny:\n{exc}"
        ) from exc

    return changed


__all__ = [
    "DyspozycjaActionError",
    "close_dyspozycja",
    "start_dyspozycja",
]
