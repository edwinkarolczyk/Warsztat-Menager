import pytest

import gui_magazyn_pz as gmpz


def _make_dialog(cfg, item):
    dlg = gmpz.PZDialog.__new__(gmpz.PZDialog)
    dlg.cfg = cfg
    dlg.item = item
    return dlg


def test_parse_qty_enforces_int_for_szt_by_default():
    dlg = _make_dialog({}, {"jednostka": "szt"})
    with pytest.raises(ValueError):
        dlg._parse_qty("1.5")
    assert dlg._parse_qty("2") == 2


def test_parse_qty_allows_fraction_when_disabled():
    cfg = {"magazyn": {"rounding": {"enforce_integer_for_szt": False}}}
    dlg = _make_dialog(cfg, {"jednostka": "szt"})
    assert dlg._parse_qty("1.5") == 1.5


def test_parse_qty_mb_precision_from_config():
    cfg = {"magazyn": {"rounding": {"mb_precision": 4}}}
    dlg = _make_dialog(cfg, {"jednostka": "mb"})
    assert dlg._parse_qty("1.23456") == pytest.approx(1.2346)


def test_require_reauth_fallbacks():
    assert gmpz._require_reauth({"magazyn_require_reauth": False}) is False
    assert gmpz._require_reauth({}) is True

