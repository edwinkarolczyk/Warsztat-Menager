"""Timery okna WMM są anulowane także przy bezpośrednim destroy()."""
import sys
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services import wmm_panel


@pytest.mark.parametrize("after_refresh", [False, True])
@pytest.mark.parametrize("direct_destroy", [False, True])
def test_popup_cancels_tcl_timers_and_reopens(
    monkeypatch, after_refresh, direct_destroy,
):
    interp = tk.Tcl()
    interp.eval('set errors {}; proc bgerror {msg} {lappend ::errors $msg}')
    popups = []

    class Popup(tk.Misc):
        def __init__(self, root):
            self.tk = interp.tk
            self._tclCommands = None
            self.handlers = {}
            self.protocols = {}
            self.alive = True
            popups.append(self)

        def bind(self, sequence, callback, add=None):
            self.handlers[sequence] = callback

        def protocol(self, name, callback):
            self.protocols[name] = callback

        def winfo_exists(self):
            return self.alive

        def destroy(self):
            self.handlers['<Destroy>'](SimpleNamespace(widget=self))
            self.alive = False
            super().destroy()

        def noop(self, *args, **kwargs):
            pass

        title = resizable = transient = configure = lift = attributes = noop

    monkeypatch.setattr(tk, 'Toplevel', Popup)
    for name in ('Label', 'Canvas', 'Frame', 'Button', 'StringVar'):
        monkeypatch.setattr(tk, name, Mock())
    monkeypatch.setattr(wmm_panel, '_center_window', Mock())
    monkeypatch.setattr(wmm_panel, '_draw_qr', Mock())
    monkeypatch.setattr(wmm_panel, '_update_footer', Mock())
    status = Mock(return_value={'users': []})
    monkeypatch.setitem(sys.modules, 'services.wmm_api', SimpleNamespace(
        pairing_info=lambda: {}, mobile_status=status,
    ))
    root = SimpleNamespace()
    wmm_panel.show_wmm_popup(root)
    popup = root._wmm_popup
    assert len(interp.call('after', 'info')) == 2
    # Zdarzenie potomka nie może wyłączyć odświeżania całego okna.
    popup.handlers['<Destroy>'](SimpleNamespace(widget=object()))
    assert len(interp.call('after', 'info')) == 2
    if after_refresh:
        # Wykonaj oczekujące komendy Tcl bez czekania 500 ms.
        for timer_id in interp.call('after', 'info'):
            script, _kind = interp.call('after', 'info', timer_id)
            interp.call('after', 'cancel', timer_id)
            interp.eval(script)
        status.assert_called_once()
        assert len(interp.call('after', 'info')) == 1
    if direct_destroy:
        popup.destroy()
    else:
        popup.protocols['WM_DELETE_WINDOW']()
    assert not interp.call('after', 'info')
    assert root._wmm_popup is None
    interp.eval('update')
    assert not interp.eval('set errors')
    wmm_panel.show_wmm_popup(root)
    assert root._wmm_popup is not popup
    assert len(interp.call('after', 'info')) == 2
    root._wmm_popup.protocols['WM_DELETE_WINDOW']()
    assert not interp.call('after', 'info')
    interp.eval('update')
    assert not interp.eval('set errors')
