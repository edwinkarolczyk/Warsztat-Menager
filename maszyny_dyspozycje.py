# version: 1.17
# Zmiany 1.17:
# - Karta serwisowa maszyny pokazuje Brygadziście przycisk Korekta wpisu.
# Zmiany 1.16:
# - Korekta przeglądu ma rollback spójności Maszyna <-> automatyczna Dyspozycja.
# Zmiany 1.15:
# - Brygadzista ma bezpieczną korektę wpisów przeglądów/serwisów z historią zmian.
# - Korekta nie zmienia statusu, ID ani klucza cyklu/Dyspozycji.
# Zmiany 1.14:
# - Timeout sesji wylogowuje zalogowanego użytkownika do Gościa zamiast zamykać WM.
# - W trybie Gościa timeout nie zamyka programu; zapis czasu w Ustawieniach działa od razu.
# Zmiany 1.13:
# - Narzędzia korzystają z tego samego aktywnego kreatora Dyspozycji co Maszyny.
# - Stary wm.dyspo_wizard pozostaje poza przepływem bieżącego GUI Narzędzi.
# Zmiany 1.12:
# - Profil pokazuje najpierw osobiste Dyspozycje, dane pracy obok avatara oraz akcje avatar/PW.
# Zmiany 1.11:
# - Zaległa Dyspozycja miga między czerwonym a normalnym kolorem swojego statusu.
# Zmiany 1.10:
# - Kreator Dodaj/Edytuj Dyspozycję otwiera się jako normalne, wyśrodkowane okno zamiast zoomed.
# Zmiany 1.9:
# - Zaległe cykliczne przeglądy mogą tworzyć brakujące Dyspozycje zbiorczo lub ręcznie.
# - Automatyczne okno tworzenia Dyspozycji przed terminem pozostaje bez zmian.
# Zmiany 1.8:
# - Zamknięcie Dyspozycji cyklicznego przeglądu maszyny otwiera formularz wykonania serwisu.
# - Zwykłe Dyspozycje maszyn zachowują dotychczasowy sposób zamykania.
# Zmiany 1.7:
# - Brygadzista może przy wykonaniu przeglądu/serwisu ustawić datę dzisiejszą lub wcześniejszą.
# Zmiany 1.6:
# - Pełna historia statusów i przeglądów mieści się w domyślnym oknie Użytkowanie maszyny.
# - Bieżący status pokazuje „Aktualny” zamiast mylącego „w toku”.
# Zmiany 1.5:
# - Zapis historii DOCX używa trybu zgodnego z dyskami sieciowymi/SMB.
# Zmiany 1.4:
# - Historia DOCX korzysta z bezpośredniego zapisu po wykonaniu przeglądu/naprawy.
# - Dodano integrację wydruku planu przeglądów maszyn.
# Zmiany 1.3:
# - Podłączenie dodatkowej karty historii DOCX do modułu Maszyny.
# - Właściwa logika Dyspozycji maszyn pozostaje bez zmian w module core.
"""Adapter modułu Dyspozycji maszyn z integracją historii DOCX."""

from __future__ import annotations

import sys
import types
from importlib import import_module

import machine_history_runtime as _history_runtime
from dysp_creator_window_runtime import install_dysp_creator_window_behavior
from dyspozycje_blink_runtime import install_dyspozycje_status_blink
from machine_history_docx_io import append_history_entry as _append_history_entry
from machine_history_layout_runtime import install_machine_history_layout
from machine_overdue_dysp_runtime import install_machine_overdue_dysp
from machine_review_backdate_runtime import install_machine_review_backdate
from machine_review_card_correction_runtime import install_machine_review_card_correction
from machine_review_correction_runtime import install_machine_review_correction
from machine_review_correction_tx_runtime import install as install_machine_review_correction_tx
from machine_review_dysp_close_runtime import install_machine_review_dysp_close
from profile_simple_runtime import install_profile_simple_runtime
from session_timeout_runtime import install_session_timeout_runtime
from tools_dysp_creator_runtime import install_tools_dysp_creator

# Runtime zapisuje zdarzenia bezpośrednio po wykonaniu przeglądu/naprawy.
# Podmieniamy wyłącznie warstwę fizycznego zapisu DOCX, aby działała także
# na udziałach sieciowych Windows/SMB, bez zmiany logiki Maszyn i Dyspozycji.
_history_runtime.append_history_entry = _append_history_entry
install_gui_integration = _history_runtime.install_gui_integration

_core = import_module("_maszyny_dyspozycje_core")
__all__ = [name for name in vars(_core) if not name.startswith("_")]


def _ensure_gui_integration() -> None:
    install_session_timeout_runtime()
    install_dysp_creator_window_behavior()
    install_profile_simple_runtime()

    tools_module = sys.modules.get("gui_narzedzia")
    if tools_module is not None:
        install_tools_dysp_creator(tools_module)

    gui_module = sys.modules.get("gui_maszyny")
    if gui_module is not None:
        install_gui_integration(gui_module)
        install_machine_history_layout(gui_module)
        install_machine_review_backdate(gui_module)
        install_machine_review_correction_tx(gui_module)
        install_machine_review_correction(gui_module)
        install_machine_review_card_correction(gui_module)
        install_machine_overdue_dysp(gui_module)

    dysp_module = sys.modules.get("gui_zlecenia")
    if dysp_module is not None:
        install_dyspozycje_status_blink(dysp_module)
        install_machine_review_dysp_close(dysp_module)


class _IntegratedModule(types.ModuleType):
    """Deleguje API do core i podłącza GUI dokładnie przy użyciu modułu Maszyn."""

    def __getattribute__(self, name: str):
        if name not in {
            "_ensure_gui_integration",
            "_core",
            "_IntegratedModule",
            "__class__",
            "__dict__",
            "__name__",
            "__spec__",
            "__loader__",
            "__package__",
            "__file__",
            "__cached__",
            "__all__",
        }:
            _ensure_gui_integration()
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return getattr(_core, name)

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("__") and hasattr(_core, name):
            setattr(_core, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if not name.startswith("__") and hasattr(_core, name):
            delattr(_core, name)
            return
        super().__delattr__(name)


def __getattr__(name: str):
    _ensure_gui_integration()
    return getattr(_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_core)))


sys.modules[__name__].__class__ = _IntegratedModule
_ensure_gui_integration()
