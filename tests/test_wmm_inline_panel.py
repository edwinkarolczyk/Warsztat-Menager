"""Stały panel nie otwiera QR automatycznie i sprząta timer."""
import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock

from services import wmm_panel


def test_inline_panel_lifecycle(monkeypatch):
    interp = tk.Tcl()
    widgets = []

    class Widget(tk.Misc):
        def __init__(self, parent=None, **kwargs):
            self.tk = interp.tk
            self._tclCommands = None
            self.options = kwargs
            self.handlers = {}
            self.alive = True
            widgets.append(self)

        def pack(self, **kwargs):
            pass

        def configure(self, **kwargs):
            self.options.update(kwargs)

        def bind(self, event, callback, add=None):
            self.handlers[event] = callback

        def winfo_exists(self):
            return self.alive

        def destroy(self):
            callback = self.handlers.get('<Destroy>')
            if callback:
                callback(SimpleNamespace(widget=self))
            self.alive = False
            super().destroy()

    for name in ('Frame', 'Label', 'Button'):
        monkeypatch.setattr(ttk, name, Widget)
    monkeypatch.setitem(sys.modules, 'ui_context_help', SimpleNamespace(
        add_help_button=lambda *a, **kw: Widget()))
    running = Mock(return_value=False)
    monkeypatch.setitem(sys.modules, 'services.wmm_api', SimpleNamespace(
        api_running=running,
        pairing_info=lambda: {'host': '192.168.0.65', 'port': 8765},
        mobile_status=lambda: {'users': [{'name': 'Marek'}]},
    ))
    popup = Mock()
    monkeypatch.setattr(wmm_panel, 'show_wmm_popup', popup)
    monkeypatch.setattr(wmm_panel, '_update_footer', Mock())
    host = Widget()
    root = SimpleNamespace(_wmm_panel_host=host)
    wmm_panel.mount_wmm_panel(root)
    panel = host._wmm_status_panel
    popup.assert_not_called()
    assert any(w.options.get('text') == '● API nie działa' for w in widgets)
    wmm_panel.mount_wmm_panel(root)
    assert len(interp.call('after', 'info')) == 1
    running.return_value = True
    timer, = interp.call('after', 'info')
    script, _ = interp.call('after', 'info', timer)
    interp.call('after', 'cancel', timer)
    interp.eval(script)
    assert any(w.options.get('text') == '● API działa' for w in widgets)
    assert any(w.options.get('text') == 'Połączeni: Marek' for w in widgets)
    next(w for w in widgets if w.options.get('text') == 'Pokaż QR').options['command']()
    popup.assert_called_once_with(root)
    panel.destroy()
    assert not interp.call('after', 'info')
    wmm_panel.mount_wmm_panel(root)
    assert host._wmm_status_panel is not panel
    host._wmm_status_panel.destroy()
    assert not interp.call('after', 'info')
