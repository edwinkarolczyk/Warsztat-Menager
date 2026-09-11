"""Headless regression checks for footer lookup lifecycle."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace


class Widget:
    def __init__(self, text='', children=()):
        self.text = text
        self.children = children
        self.alive = True
        self.scans = 0

    def winfo_children(self):
        self.scans += 1
        return self.children

    def winfo_exists(self):
        return self.alive

    def cget(self, key):
        return self.text

    def configure(self, **kwargs):
        self.text = kwargs['text']


def test_footer_cache_and_rebuild(monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'services/wmm_panel.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_update_footer')
    monkeypatch.setitem(sys.modules, '__version__',
                        SimpleNamespace(__version__='test'))
    monkeypatch.setitem(sys.modules, 'services.wmm_api',
                        SimpleNamespace(WMM_COMPAT_VERSION='test'))
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]),
                 str(source), 'exec'), namespace)
    update = namespace['_update_footer']
    first = Widget('Warsztat Menager vtest')
    root = Widget(children=[first])
    update(root)
    expected = first.text
    assert 'Kompatybilne z WMM' in expected
    update(root)
    assert root.scans == 1
    assert first.scans == 1
    first.alive = False
    second = Widget('Warsztat Menager vtest')
    root.children = [second]
    update(root)
    assert root.scans == 2
    assert second.text == expected
    update(root)
    assert root.scans == 2

    second.alive = False
    root.children = []
    update(root)
    third = Widget('Warsztat Menager vtest')
    root.children = [third]
    update(root)
    assert third.text == expected
