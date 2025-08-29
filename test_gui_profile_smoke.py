import importlib
import os
import pytest

def test_public_api():
    mod = importlib.import_module('gui_profile')
    assert hasattr(mod, 'uruchom_panel')
    assert callable(mod.uruchom_panel)
    assert hasattr(mod, 'panel_profil')
    assert mod.panel_profil is mod.uruchom_panel


def test_default_avatar_used(monkeypatch):
    mod = importlib.import_module('gui_profile')
    if mod.Image is None or mod.ImageTk is None:
        pytest.skip("Pillow not installed")

    opened = []

    def fake_open(path):
        opened.append(path)
        if path.endswith(os.path.join('avatars', 'ghost.png')):
            raise FileNotFoundError
        class Img:
            pass
        return Img()

    class DummyPhoto:
        def __init__(self, img):
            self.img = img

    class DummyLabel:
        def __init__(self, parent, image=None):
            self.image = image
        def pack(self, *a, **k):
            pass

    monkeypatch.setattr(mod.Image, 'open', fake_open)
    monkeypatch.setattr(mod.ImageTk, 'PhotoImage', DummyPhoto)
    monkeypatch.setattr(mod.tk, 'Label', DummyLabel)

    lbl = mod._load_avatar(None, 'ghost')

    assert opened == [
        os.path.join('avatars', 'ghost.png'),
        os.path.join('avatars', 'default.jpg'),
    ]
    assert isinstance(lbl.image, DummyPhoto)


def test_avatar_fallback_without_pillow(monkeypatch):
    mod = importlib.import_module('gui_profile')

    monkeypatch.setattr(mod, 'Image', None)
    monkeypatch.setattr(mod, 'ImageTk', None)

    class DummyLabel:
        def __init__(self, parent, text=None, style=None):
            self.text = text

    monkeypatch.setattr(mod.ttk, 'Label', DummyLabel)

    lbl = mod._load_avatar(None, 'ghost')
    assert isinstance(lbl, DummyLabel)
    assert 'ghost' in lbl.text
