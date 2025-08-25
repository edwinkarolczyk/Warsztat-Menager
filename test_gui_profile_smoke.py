import importlib

def test_public_api():
    mod = importlib.import_module('gui_profile')
    assert hasattr(mod, 'uruchom_panel')
    assert callable(mod.uruchom_panel)
    assert hasattr(mod, 'panel_profil')
    assert mod.panel_profil is mod.uruchom_panel
