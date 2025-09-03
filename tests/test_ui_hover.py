import types

import ui_hover


class DummyPhotoImage:
    def __init__(self, **_):
        pass

    def put(self, *_args, **_kwargs):
        pass


class DummyLabel:
    def __init__(self, master):
        self.master = master
        self.image = None

    def configure(self, image=None):
        self.image = image

    def pack(self):
        pass


class DummyToplevel:
    def __init__(self, widget):
        self.widget = widget
        self.visible = True

    def wm_overrideredirect(self, _flag):
        pass

    def geometry(self, _geo):
        pass

    def destroy(self):
        self.visible = False

    def deiconify(self):
        self.visible = True


class DummyWidget:
    def __init__(self):
        self.bindings = {}
        self.after_calls = {}
        self.cancelled = set()
        self._after_counter = 0

    def bind(self, seq, func):
        self.bindings[seq] = func

    def after(self, _delay, func):
        self._after_counter += 1
        self.after_calls[self._after_counter] = func
        return self._after_counter

    def after_cancel(self, ident):
        self.cancelled.add(ident)

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0

    def winfo_width(self):
        return 10

    def winfo_height(self):
        return 10


class DummyCanvas(DummyWidget):
    def tag_bind(self, item, seq, func):
        self.bindings[(item, seq)] = func

    def trigger(self, item, seq):
        self.bindings[(item, seq)](None)


class DummyTree(DummyWidget):
    def tag_bind(self, item, seq, func):
        self.bindings[(item, seq)] = func

    def trigger(self, item, seq):
        self.bindings[(item, seq)](None)


def setup_dummy(monkeypatch):
    dummy_tk = types.SimpleNamespace(
        PhotoImage=DummyPhotoImage,
        Label=DummyLabel,
        Toplevel=DummyToplevel,
    )
    monkeypatch.setattr(ui_hover, "tk", dummy_tk)
    monkeypatch.setattr(
        ui_hover.ImageHoverTooltip,
        "_load_image",
        lambda self, _p: DummyPhotoImage(),
    )
    return dummy_tk


def test_hover_shows_and_hides(monkeypatch):
    setup_dummy(monkeypatch)
    widget = DummyWidget()
    tooltip = ui_hover.ImageHoverTooltip(widget, ["a", "b"], delay=1)

    widget.bindings["<Enter>"](None)
    assert tooltip._tooltip is not None
    after_id = tooltip._after_id
    assert after_id in widget.after_calls

    widget.bindings["<Leave>"](None)
    assert tooltip._tooltip is None
    assert after_id in widget.cancelled


def test_bind_helpers(monkeypatch):
    setup_dummy(monkeypatch)
    canvas = DummyCanvas()
    tip_canvas = ui_hover.bind_canvas_item_hover(canvas, 1, [])
    canvas.trigger(1, "<Enter>")
    assert tip_canvas._tooltip is not None
    canvas.trigger(1, "<Leave>")
    assert tip_canvas._tooltip is None

    tree = DummyTree()
    tip_tree = ui_hover.bind_treeview_row_hover(tree, "row", [])
    tree.trigger("row", "<Enter>")
    assert tip_tree._tooltip is not None
    tree.trigger("row", "<Leave>")
    assert tip_tree._tooltip is None


def test_load_image_respects_max_size(monkeypatch):
    opened = []

    class DummyPILImage:
        def __init__(self, size):
            self.size = size
            self.thumb_called_with = None

        def thumbnail(self, size):
            self.thumb_called_with = size
            self.size = (
                min(self.size[0], size[0]),
                min(self.size[1], size[1]),
            )

    def fake_open(_path):
        img = DummyPILImage((1000, 2000))
        opened.append(img)
        return img

    class DummyPhoto:
        def __init__(self, image):
            self.width, self.height = image.size

    monkeypatch.setattr(ui_hover, "_PIL_AVAILABLE", True)
    monkeypatch.setattr(
        ui_hover,
        "Image",
        types.SimpleNamespace(open=fake_open),
    )
    monkeypatch.setattr(
        ui_hover,
        "ImageTk",
        types.SimpleNamespace(PhotoImage=DummyPhoto),
    )
    widget = types.SimpleNamespace(bind=lambda *_a, **_k: None)
    tooltip = ui_hover.ImageHoverTooltip(widget, None, max_size=(600, 800))
    result = tooltip._load_image("dummy")
    pil_img = opened[0]
    assert pil_img.thumb_called_with == (600, 800)
    assert result.width <= 600
    assert result.height <= 800
