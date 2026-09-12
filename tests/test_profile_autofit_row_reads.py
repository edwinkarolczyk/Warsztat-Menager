"""Autofit keeps widths while reading each row only once."""
from types import SimpleNamespace

import pytest

import profile_tree_autofit_runtime as runtime


@pytest.mark.parametrize('rows', [
    [tuple(f'Wiersz {i}, kolumna {j}' for j in range(8)) for i in range(100)],
    [],
    [('Marek',), (), ('Dawid', None, 'Długi opis z polskimi znakami')],
    [OSError('row unavailable'), ('Dawid', '12')],
])
def test_autofit_widths_and_single_read(monkeypatch, rows):
    columns = tuple(f'c{i}' for i in range(8))
    headings = ['Pracownik', 'Dni', 'Opis', '', 'A', 'B', 'C', 'D']
    reads = []
    widths = {}

    def item(iid, option):
        reads.append(iid)
        value = rows[iid]
        if isinstance(value, Exception):
            raise value
        return value

    tree = SimpleNamespace(
        cget=lambda key: columns,
        get_children=lambda parent: range(len(rows)),
        heading=lambda column, option: headings[columns.index(column)],
        item=item,
        column=lambda column, **kwargs: widths.update({column: kwargs['width']}),
    )
    monkeypatch.setattr(runtime.ttk, 'Style', lambda _: SimpleNamespace(
        lookup=lambda *args: 'test-font'))
    monkeypatch.setattr(runtime, '_font_width',
                        lambda tree, font, value: len(str(value or '')) * 8)
    # Expected original behavior: heading padding 24, cell padding 20,
    # missing/unreadable cells empty, and minimum column width 42.
    expected = {}
    for index, column in enumerate(columns):
        candidates = [42, len(headings[index]) * 8 + 24]
        for row in rows:
            value = (row[index] if not isinstance(row, Exception)
                     and index < len(row) else '')
            candidates.append(len(str(value or '')) * 8 + 20)
        expected[column] = max(candidates)
    runtime._autofit_tree(tree)
    assert widths == expected
    assert reads == list(range(len(rows)))
