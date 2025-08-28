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
