from __version__ import __version__
from profile_foreman_edit_runtime import _parse_carryover


def test_profile_release_is_096():
    assert __version__ == "0.9.6"


def test_carryover_keeps_source_years():
    assert _parse_carryover("2024=2; 2025=4", 2026) == {2024: 2.0, 2025: 4.0}


def test_carryover_rejects_current_year():
    try:
        _parse_carryover("2026=1", 2026)
    except ValueError:
        return
    raise AssertionError("Bieżący rok nie może być zapisany jako urlop zaległy")
