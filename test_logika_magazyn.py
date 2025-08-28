import logika_magazyn as lm


def test_rezerwuj_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    lm.upsert_item({
        'id': 'MAT-X',
        'nazwa': 'Test',
        'typ': 'materiał',
        'jednostka': 'szt',
        'stan': 8,
        'min_poziom': 0,
        'rezerwacje': 3,
    })

    reserved = lm.rezerwuj('MAT-X', 10, uzytkownik='test', kontekst='pytest')

    assert reserved == 5.0
    item = lm.get_item('MAT-X')
    assert item['rezerwacje'] == 8.0
    assert item['historia'][-1]['operacja'] == 'rezerwacja'
    assert item['historia'][-1]['ilosc'] == 5.0


def test_alert_after_zuzycie_below_min(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    logs = []
    monkeypatch.setattr(lm, '_log_mag', lambda a, d: logs.append((a, d)))

    lm.load_magazyn()
    lm.upsert_item({
        'id': 'MAT-AL',
        'nazwa': 'Aluminium',
        'typ': 'materiał',
        'jednostka': 'szt',
        'stan': 5,
        'min_poziom': 2,
    })

    lm.zuzyj('MAT-AL', 4, uzytkownik='test', kontekst='pytest')

    alerts = [d for a, d in logs if a == 'prog_alert']
    assert alerts, 'powinien zostać zalogowany alert progowy'
    assert alerts[0]['item_id'] == 'MAT-AL'
    assert alerts[0]['stan'] == 1.0
    assert alerts[0]['min_poziom'] == 2.0
