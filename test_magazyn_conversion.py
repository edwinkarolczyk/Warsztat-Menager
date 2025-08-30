import logika_magazyn as lm
import logika_zadan as lz


def _setup_mag(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    lm.upsert_item({
        'id': 'MAT',
        'nazwa': 'Test',
        'typ': 'materiał',
        'jednostka': 'opak',
        'wsp_konwersji': 10,
        'stan': 100,
        'min_poziom': 0,
    })


def test_zuzyj_converts_units(tmp_path, monkeypatch):
    _setup_mag(tmp_path, monkeypatch)
    lm.zuzyj('MAT', 3, uzytkownik='t', kontekst='k')
    item = lm.get_item('MAT')
    assert item['stan'] == 70
    assert item['historia'][-1]['ilosc'] == 30.0


def test_consume_for_task_uses_conversion(tmp_path, monkeypatch):
    _setup_mag(tmp_path, monkeypatch)
    task = {'materials': [{'id': 'MAT', 'ilosc': 2}]}
    consumed = lz.consume_for_task('narz', task, uzytkownik='t')
    assert consumed == [{'id': 'MAT', 'ilosc': 20.0}]
    item = lm.get_item('MAT')
    assert item['stan'] == 80
